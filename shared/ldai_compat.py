"""
Framework-native glue for the current LaunchDarkly AI SDK (``launchdarkly-ai-server``).

Why this module exists
----------------------
The current SDK emits AI metrics from *inside* its own execution paths:
``config().invoke()``, ``execute_and_track()``, ``graph().invoke()``. Every arm in this
experiment deliberately bypasses those paths — the whole point of the bake-off is that the
WALK is the treatment, so each framework's own orchestrator (or this project's dispatcher)
must own execution. Nothing would emit anything for them.

So this module supplies the two pieces the framework-native path needs and the SDK does not
expose: a per-node metrics tracker and a graph-level tracker. Both fire the *same*
``$ld:ai:*`` event keys the SDK fires, copied from the SDK source, so the metrics already
built in AgentControl keep receiving data unchanged.

It also carries the per-framework helpers that used to live in the retired companion
packages ``launchdarkly-server-sdk-ai-langchain`` and ``launchdarkly-server-sdk-ai-openai``.
Those packages have no equivalent in the current generation; the functions below are ported
from their last published releases (0.8.0 and 0.7.0 respectively), with the token-usage
readers rebuilt on the current SDK's ``parse_usage`` so all arms normalize usage the same
way. Every inference is called out in the docstring of the function it affects.

Nothing here is a LaunchDarkly-supported API. It is application code, and it is the price of
driving four frameworks natively rather than through the SDK's own runners.
"""

import logging
import time
import uuid
from dataclasses import dataclass
from typing import Any, Callable, Dict, Iterable, List, Optional, Tuple

from launchdarkly_ai_server import (
    create_handler,
    get_client,
    model_stamps_from_meta,
    parse_template,
    parse_usage,
    run_judges,
)

log = logging.getLogger(__name__)

# Copied verbatim from the SDK so the existing metrics keep receiving data. The SDK fires
# these from execute_and_track() / graph().invoke(); the framework-native arms fire them
# from the trackers below. Changing a string here silently detaches a live metric.
GENERATION_SUCCESS = "$ld:ai:generation:success"
GENERATION_ERROR = "$ld:ai:generation:error"
DURATION_TOTAL = "$ld:ai:duration:total"
TOKENS_TOTAL = "$ld:ai:tokens:total"
TOKENS_INPUT = "$ld:ai:tokens:input"
TOKENS_OUTPUT = "$ld:ai:tokens:output"
TOKENS_TTF = "$ld:ai:tokens:ttf"
TOOL_CALL = "$ld:ai:tool_call"
GRAPH_INVOCATION_SUCCESS = "$ld:ai:graph:invocation_success"
GRAPH_INVOCATION_FAILURE = "$ld:ai:graph:invocation_failure"
GRAPH_DURATION_TOTAL = "$ld:ai:graph:duration:total"
GRAPH_TOTAL_TOKENS = "$ld:ai:graph:total_tokens"
GRAPH_NODE = "$ld:ai:graph:node"
GRAPH_HANDOFF_SUCCESS = "$ld:ai:graph:handoff_success"
GRAPH_HANDOFF_FAILURE = "$ld:ai:graph:handoff_failure"


# ──────────────────────────────────────────────────────────────────────────────────────────
# Value types
# ──────────────────────────────────────────────────────────────────────────────────────────


@dataclass
class TokenUsage:
    """Token counts for one call.

    The SDK's own usage type is ``UsageDict`` — a TypedDict, so a plain dict at runtime.
    The runners read ``usage.input`` and add usages together, so this keeps the attribute
    shape the retired ``ldai.tracker.TokenUsage`` had. ``as_usage()`` converts to the key
    spelling the SDK's ``parse_usage`` understands, for anything handed back to the SDK.
    """

    input: int = 0
    output: int = 0
    total: int = 0

    def as_usage(self) -> Dict[str, int]:
        return {"input_tokens": self.input, "output_tokens": self.output}

    @classmethod
    def from_raw(cls, usage: Optional[Dict[str, Any]]) -> Optional["TokenUsage"]:
        """Read any usage bag the SDK's ``parse_usage`` recognizes, or ``None`` if empty.

        ``parse_usage`` accepts ``input_tokens``/``output_tokens`` (LangChain, OpenAI Agents),
        ``inputTokens``/``outputTokens`` (Bedrock, Strands) and ``input``/``output``, and
        always derives the total rather than trusting a provider-reported one. An
        unrecognized bag reads as all zeros, which this reports as ``None`` so a provider
        that said nothing about usage does not register as a run that used no tokens.
        """
        if not usage:
            return None
        parsed = parse_usage(usage)
        if not (parsed["input"] or parsed["output"] or parsed["total"]):
            return None
        return cls(input=parsed["input"], output=parsed["output"], total=parsed["total"])


@dataclass
class LDAIMetrics:
    """What one invocation reported, for ``ConfigTracker.track_metrics_of_async``.

    Ported from the retired ``ldai.providers.types.LDAIMetrics``, field for field, so the
    runners' extractor lambdas are unchanged.
    """

    success: bool
    tokens: Optional[TokenUsage] = None
    tool_calls: Optional[List[str]] = None
    duration_ms: Optional[int] = None


# ──────────────────────────────────────────────────────────────────────────────────────────
# Config reading (AI configs are plain dicts now)
# ──────────────────────────────────────────────────────────────────────────────────────────


def model_name(config: Dict[str, Any]) -> str:
    return ((config or {}).get("model") or {}).get("name") or ""


def provider_name(config: Dict[str, Any]) -> str:
    return ((config or {}).get("provider") or {}).get("name") or ""


def model_parameters(config: Dict[str, Any]) -> Dict[str, Any]:
    """The served model's generation parameters, without the tool definitions.

    Tools arrive under ``model.parameters.tools`` on the wire, so every caller that forwards
    parameters to a framework's model constructor has to drop them first or the constructor
    rejects the unknown kwarg.
    """
    params = dict(((config or {}).get("model") or {}).get("parameters") or {})
    params.pop("tools", None)
    return params


def instructions(config: Dict[str, Any], variables: Optional[Dict[str, Any]] = None) -> str:
    """The node's instructions, with any mustache variables rendered.

    Rendering is not automatic in the current SDK: ``invoke()`` forwards ``variables``
    untouched and only the first-party handlers call ``parse_template``. Anything that reads
    instructions and hands them to a framework has to render them itself, or the model is
    shown raw ``{{placeholders}}``.
    """
    text = (config or {}).get("instructions") or ""
    if not text or not variables:
        return text
    return parse_template(text, variables)


def tool_names(config: Dict[str, Any]) -> List[str]:
    """Names of the tools attached to this config, in definition order.

    Two shapes are accepted because both are live: the wire format puts an array of tool
    definitions under ``model.parameters.tools``, while the SDK's own validation treats a
    top-level ``tools`` key as an object keyed by tool name.
    """
    names: List[str] = []
    top_level = (config or {}).get("tools")
    if isinstance(top_level, dict):
        names.extend(str(name) for name in top_level)
    definitions = (((config or {}).get("model") or {}).get("parameters") or {}).get("tools")
    if isinstance(definitions, list):
        for definition in definitions:
            name = definition.get("name") if isinstance(definition, dict) else None
            if name and name not in names:
                names.append(str(name))
    return names


# ──────────────────────────────────────────────────────────────────────────────────────────
# Contexts
# ──────────────────────────────────────────────────────────────────────────────────────────


def multi_context(key: str, **attributes: Any) -> Dict[str, Any]:
    """A user + request multi-context as a plain dict.

    Contexts are dicts in the current SDK — there is no builder, and ``resolve_graph`` runs
    its argument through ``Context.from_dict``, so an ``ldclient.Context`` instance is not
    accepted. ``to_ld_context`` converts this for the direct ``ldclient`` calls that still
    need a real Context (flag evaluation, custom metric tracking).

    "user" keeps the user-unit autogenerated metrics populating; "request" is the per-run
    unit for the AI and graph latency/token metrics and the experiment's randomization unit.
    Each run is one user and one request, so both share the key.
    """
    kinds = {"user": {"key": key}, "request": {"key": key}}
    for kind in kinds.values():
        kind.update({k: v for k, v in attributes.items() if v is not None})
    return {"kind": "multi", **kinds}


def to_ld_context(context: Dict[str, Any]) -> Any:
    """Convert a plain-dict context to the ``ldclient.Context`` the base SDK expects."""
    from ldclient import Context

    return Context.from_dict(context)


def context_has_attr(context: Dict[str, Any], attr: str) -> bool:
    """True if ``attr`` is set on ``context`` (checked across every kind of a multi)."""
    if not isinstance(context, dict):
        return False
    if context.get("kind") == "multi":
        return any(
            isinstance(individual, dict) and individual.get(attr) is not None
            for kind, individual in context.items()
            if kind != "kind"
        )
    return context.get(attr) is not None


# ──────────────────────────────────────────────────────────────────────────────────────────
# Trackers
# ──────────────────────────────────────────────────────────────────────────────────────────


def _node_track_data(
    config_key: str,
    config: Dict[str, Any],
    meta: Dict[str, Any],
    graph_key: Optional[str],
    run_id: str,
) -> Dict[str, Any]:
    """The tracking payload the SDK attaches to a node's events.

    Field for field the same as the SDK's ``make_track_data``, which is what makes these
    events land on the same variation rows in AgentControl as SDK-emitted ones.
    """
    meta = meta if isinstance(meta, dict) else {}
    data = {
        "runId": run_id,
        "configKey": config_key,
        "variationKey": meta.get("variationKey", ""),
        "version": meta.get("version", 1),
        "modelName": model_name(config),
        "providerName": provider_name(config),
        # Pinned model-config identity. Gonfalon's cost attribution reads these off every
        # $ld:ai:* payload, so they have to be on the hand-rolled events too.
        **model_stamps_from_meta(meta),
    }
    if graph_key:
        data["graphKey"] = graph_key
    return data


class _Tracker:
    """Shared plumbing: a context, a payload, and a track() that can never raise."""

    def __init__(self, context: Dict[str, Any], data: Dict[str, Any]):
        self._context = to_ld_context(context)
        self._data = data

    def _track(self, event: str, value: Any = 1, extra: Optional[Dict[str, Any]] = None):
        try:
            data = {**self._data, **extra} if extra else self._data
            get_client().track(event, self._context, data, value)
        except Exception as exc:  # metrics must never break a run
            log.warning("track(%s) failed: %s", event, exc)


class ConfigTracker(_Tracker):
    """One node's AI metrics.

    Replaces the retired ``config.create_tracker()``. The at-most-once guards on
    success/error, duration, tokens and time-to-first-token are kept from the old tracker:
    a node that recorded twice would double-count its own latency and tokens.
    """

    def __init__(
        self,
        config_key: str,
        config: Dict[str, Any],
        meta: Dict[str, Any],
        context: Dict[str, Any],
        graph_key: Optional[str] = None,
        run_id: Optional[str] = None,
    ):
        super().__init__(
            context,
            _node_track_data(config_key, config, meta, graph_key, run_id or str(uuid.uuid4())),
        )
        self.config_key = config_key
        self._result_recorded = False
        self._duration_recorded = False
        self._tokens_recorded = False
        self._ttf_recorded = False

    def track_success(self) -> None:
        if self._result_recorded:
            return
        self._result_recorded = True
        self._track(GENERATION_SUCCESS)

    def track_error(self) -> None:
        if self._result_recorded:
            return
        self._result_recorded = True
        self._track(GENERATION_ERROR)

    def track_duration(self, duration_ms: int) -> None:
        if self._duration_recorded:
            return
        self._duration_recorded = True
        self._track(DURATION_TOTAL, int(duration_ms))

    def track_time_to_first_token(self, ms: int) -> None:
        if self._ttf_recorded:
            return
        self._ttf_recorded = True
        self._track(TOKENS_TTF, int(ms))

    def track_tokens(self, tokens) -> None:
        """Record token usage. Accepts a :class:`TokenUsage` or a plain mapping.

        Both shapes are handled because the runners hold ``TokenUsage`` while the
        ``shared.launchdarkly`` helpers pass dicts; a missed call site should fail loudly
        rather than silently record nothing.
        """
        if tokens is None or self._tokens_recorded:
            return
        if isinstance(tokens, dict):
            inp = tokens.get("input", 0)
            out = tokens.get("output", 0)
            total = tokens.get("total") or inp + out
        else:
            inp, out, total = tokens.input, tokens.output, tokens.total
        self._tokens_recorded = True
        if total > 0:
            self._track(TOKENS_TOTAL, total)
        if inp > 0:
            self._track(TOKENS_INPUT, inp)
        if out > 0:
            self._track(TOKENS_OUTPUT, out)

    def track_bedrock_converse_metrics(self, response):
        """Record a Bedrock Converse response the caller already has in hand.

        The retired SDK wrapped the call itself; there is no equivalent now, so this reads
        the response. Bedrock reports ``inputTokens``/``outputTokens`` and its own latency.
        """
        usage = (response or {}).get("usage") or {}
        metrics = (response or {}).get("metrics") or {}
        if metrics.get("latencyMs") is not None:
            self.track_duration(int(metrics["latencyMs"]))
        self.track_tokens(
            {"input": usage.get("inputTokens", 0), "output": usage.get("outputTokens", 0)}
        )
        self.track_success()
        return response

    def track_tool_call(self, tool_key: str) -> None:
        """One tool invocation. Repeatable — a node can call several tools, or one twice."""
        self._track(TOOL_CALL, 1, {"toolKey": tool_key})

    def track_tool_calls(self, tool_calls: Iterable[str]) -> None:
        for tool_key in tool_calls:
            self.track_tool_call(tool_key)

    async def track_metrics_of_async(
        self,
        metrics_extractor: Callable[[Any], Optional[LDAIMetrics]],
        func: Callable[[], Any],
    ) -> Any:
        """Await ``func()``, then record what ``metrics_extractor`` reads off its result.

        Ported from the retired ``LDAIConfigTracker.track_metrics_of_async``, including its
        two behaviours the runners rely on: a raising call still records duration and an
        error before re-raising, and an extractor that returns ``None`` records duration
        only (rather than guessing at success).
        """
        start = time.perf_counter()
        try:
            result = await func()
        except Exception:
            self.track_duration(int((time.perf_counter() - start) * 1000))
            self.track_error()
            raise

        elapsed_ms = int((time.perf_counter() - start) * 1000)
        metrics: Optional[LDAIMetrics] = None
        try:
            metrics = metrics_extractor(result)
        except Exception as exc:
            log.warning("Failed to extract metrics: %s", exc)

        if metrics is None:
            self.track_duration(elapsed_ms)
            return result

        self.track_duration(metrics.duration_ms if metrics.duration_ms is not None else elapsed_ms)
        self.track_success() if metrics.success else self.track_error()
        self.track_tokens(metrics.tokens)
        if metrics.tool_calls:
            self.track_tool_calls(metrics.tool_calls)
        return result

    async def track_judges(
        self,
        config: Dict[str, Any],
        context: Dict[str, Any],
        judge_input: str,
        node_output: str,
    ) -> Dict[str, float]:
        """Run the judges attached to this node's config and return ``{judge_key: score}``.

        Replaces the retired ``config.evaluator.evaluate()`` + ``track_judge_result()`` pair.
        The SDK's ``run_judges`` does both in one call: it runs each sampled judge as its own
        tracked AI call and tracks the judge's ``evaluationMetricKey`` against
        ``base_track_data`` — so passing this node's payload is what attaches the score to
        the variation whose output was judged, exactly as ``track_judge_result`` did.

        Two shape changes the callers have to know about:

        * ``judge_input`` is separate from ``node_output`` on purpose. Every arm passes the
          SOURCE PAPERS as the judge's input so grounding and citation checks run against
          ground truth rather than a derived upstream analysis.
        * The returned map is keyed by the judge's CONFIG key (``gap-quality-judge``), not by
          the metric key it emits (``$ld:ai:judge:gap-quality``). The metric key is unchanged
          and still what AgentControl reports on; only this in-process map is re-keyed,
          because that is what ``run_judges`` returns.
        """
        judges = ((config or {}).get("judgeConfiguration") or {}).get("judges") or []
        if not judges:
            return {}
        results = await run_judges(
            config=config,
            user_context=context,
            handler=judge_handler(),
            handlers=[judge_handler()],
            user_input=judge_input,
            llm_response=node_output,
            base_track_data=self._data,
            graph_key=self._data.get("graphKey"),
        )
        return {
            key: result.score
            for key, result in results.items()
            if result.score is not None
        }


class GraphTracker(_Tracker):
    """One graph run's metrics.

    Replaces the retired ``graph.create_tracker()``. The current SDK fires these events from
    inside ``graph().invoke()``, which none of these arms use — the walk is the treatment.
    Event keys and payload fields are copied from the SDK's ``graph.py`` so the graph-level
    metrics are comparable between an arm that walks itself and one that does not.

    ``run_id`` is shared with every ``ConfigTracker`` built for the same run, which is how
    the node events and the graph events are correlated.
    """

    def __init__(self, graph_key: str, context: Dict[str, Any], meta: Dict[str, Any], run_id: str):
        meta = meta if isinstance(meta, dict) else {}
        super().__init__(
            context,
            {
                "runId": run_id,
                "configKey": graph_key,
                "variationKey": meta.get("variationKey", ""),
                "version": meta.get("version", 1),
                "modelName": "",
                "providerName": "",
                **model_stamps_from_meta(meta),
                "graphKey": graph_key,
            },
        )
        self.graph_key = graph_key
        self.run_id = run_id
        self._result_recorded = False
        self._duration_recorded = False
        self._tokens_recorded = False

    def track_invocation_success(self) -> None:
        if self._result_recorded:
            return
        self._result_recorded = True
        self._track(GRAPH_INVOCATION_SUCCESS)

    def track_invocation_failure(self) -> None:
        if self._result_recorded:
            return
        self._result_recorded = True
        self._track(GRAPH_INVOCATION_FAILURE)

    def track_duration(self, duration_ms: int) -> None:
        if self._duration_recorded:
            return
        self._duration_recorded = True
        self._track(GRAPH_DURATION_TOTAL, int(duration_ms))

    def track_total_tokens(self, tokens: Optional[TokenUsage]) -> None:
        if tokens is None or tokens.total <= 0 or self._tokens_recorded:
            return
        self._tokens_recorded = True
        self._track(GRAPH_TOTAL_TOKENS, tokens.total)

    def track_path(self, path: List[str]) -> None:
        # 0.2.4 retired the single $ld:ai:graph:path event in favour of one
        # $ld:ai:graph:node per node entered; the ordered series of those events is the
        # path. The SDK emits each one as it enters the node so a later failure still
        # leaves the steps that ran. These runners own their own walk and hand the path
        # over once it is complete, so the events go out together at the end — same
        # stream, same order, same payload, only later.
        for index, node_key in enumerate(path):
            self._track(GRAPH_NODE, 1, {"nodeKey": node_key, "index": index})

    def track_handoff_success(self, source_key: str, target_key: str) -> None:
        self._track(
            GRAPH_HANDOFF_SUCCESS, 1, {"sourceKey": source_key, "targetKey": target_key}
        )

    def track_handoff_failure(self, source_key: str, target_key: str) -> None:
        self._track(
            GRAPH_HANDOFF_FAILURE, 1, {"sourceKey": source_key, "targetKey": target_key}
        )


async def resolve_graph_run(graph_key: str, context: Dict[str, Any]):
    """Read the graph topology and open a tracker for one run of it.

    Returns ``(definition, tracker, run_id)``. Raises when the graph is not enabled, which
    is what every arm wants: a disabled graph means the flag is off or a node config is not
    serving a real variation, and a run against a half-resolved graph is not a data point.

    The graph's own variation metadata is read directly from the base client because
    ``resolve_graph`` does not return it, and the graph-level events need its variation key
    and version to attribute correctly.
    """
    from launchdarkly_ai_server import resolve_graph

    definition = await resolve_graph(graph_key, context=context)
    if not definition.enabled:
        raise RuntimeError(
            f"Agent graph '{graph_key}' is not enabled "
            "(check the graph is on and every node config serves a real variation)"
        )
    raw = get_client().variation(graph_key, to_ld_context(context), {})
    meta = raw.get("_ldMeta") or {} if isinstance(raw, dict) else {}
    run_id = str(uuid.uuid4())
    return definition, GraphTracker(graph_key, context, meta, run_id), run_id


async def read_nodes(definition) -> Dict[str, Any]:
    """Every node of a resolved graph, keyed by node key.

    ``reverse_traverse`` is a coroutine in the current SDK and its visitor is called with
    ``(node, ctx)``; forgetting the await leaves the map empty and the walk silently runs
    nothing.
    """
    nodes: Dict[str, Any] = {}
    await definition.reverse_traverse(lambda node, _acc: nodes.update({node.key: node}), {})
    return nodes


def adjacency(nodes: Dict[str, Any]) -> Tuple[Dict[str, List[str]], Dict[str, List[str]]]:
    """Successor and predecessor maps built from the graph's own edges.

    Edges expose ``target_key`` now (was ``target_config``), and a node's edges are an
    attribute rather than a ``get_edges()`` call.
    """
    succ = {key: [] for key in nodes}
    preds = {key: [] for key in nodes}
    for key, node in nodes.items():
        for edge in node.edges:
            if edge.target_key in nodes:
                succ[key].append(edge.target_key)
                preds[edge.target_key].append(key)
    return succ, preds


# ──────────────────────────────────────────────────────────────────────────────────────────
# Judge handler
# ──────────────────────────────────────────────────────────────────────────────────────────

_JUDGE_HANDLER = None

_JUDGE_RESPONSE_FORMAT = {
    "type": "json_schema",
    "json_schema": {
        "name": "judge_result",
        "schema": {
            "type": "object",
            "properties": {"score": {"type": "number"}, "reasoning": {"type": "string"}},
            "required": ["score", "reasoning"],
            "additionalProperties": False,
        },
    },
}


def judge_handler():
    """A LiteLLM-backed wildcard messages handler, used only to run the judge.

    ``run_judges`` runs the judge as a real AI call and so needs a provider handler. There is
    no first-party messages handler for Anthropic (the judge's provider) in the current
    generation — the published packages are openai-messages, openai-agents, claude-agents and
    langchain-agents, and claude-agents drives the Claude Agent SDK, which is a much heavier
    dependency than one scoring call warrants. LiteLLM is already a dependency here (it backs
    the pinned model on the OpenAI Agents and ADK arms), and registering as ``("*",
    "messages")`` means ``select_handler`` picks this by exact mode match whatever provider
    the judge config is later re-pointed at.
    """
    global _JUDGE_HANDLER
    if _JUDGE_HANDLER is None:
        _JUDGE_HANDLER = create_handler(("*", "messages"), _judge_call)
    return _JUDGE_HANDLER


async def _judge_call(config, user_input, _tool_handlers, variables, history):
    import litellm

    variables = variables or {}
    provider = provider_name(config).lower()
    model = model_name(config)
    # OpenAI models are addressed bare; everything else takes a provider prefix.
    litellm_model = model if provider in ("", "openai") else f"{provider}/{model}"

    messages: List[Dict[str, Any]] = []
    system = instructions(config, variables)
    if system:
        messages.append({"role": "system", "content": system})
    for message in (config or {}).get("messages") or []:
        messages.append(
            {
                "role": message.get("role", "user"),
                "content": parse_template(message.get("content") or "", variables),
            }
        )
    messages.extend(history or [])
    if user_input:
        messages.append({"role": "user", "content": user_input})

    params = model_parameters(config)
    # Without a schema the judge writes its reasoning freehand inside the JSON string, and
    # about a third of the time it runs past max_tokens and truncates mid-string, which the
    # SDK rejects as invalid JSON and the run loses its quality score.
    response = await litellm.acompletion(
        model=litellm_model, messages=messages, response_format=_JUDGE_RESPONSE_FORMAT, **params
    )
    usage = getattr(response, "usage", None)
    return {
        "output": response.choices[0].message.content or "",
        # LiteLLM normalizes to OpenAI's spelling, which parse_usage does not recognize —
        # it would read as all zeros — so translate to the keys it does.
        "usage": {
            "input_tokens": getattr(usage, "prompt_tokens", 0) or 0,
            "output_tokens": getattr(usage, "completion_tokens", 0) or 0,
        },
    }


# ──────────────────────────────────────────────────────────────────────────────────────────
# LangChain helpers (ported from launchdarkly-server-sdk-ai-langchain 0.8.0)
# ──────────────────────────────────────────────────────────────────────────────────────────


def map_provider(ld_provider_name: str) -> str:
    """Map a LaunchDarkly provider name to its LangChain equivalent.

    Ported unchanged. Bedrock is the only provider that arrives as
    ``provider:model_family`` (e.g. ``Bedrock:Anthropic``).
    """
    lowercased = (ld_provider_name or "").lower()
    if lowercased.startswith("bedrock:"):
        return "bedrock_converse"
    return {"gemini": "google-genai", "bedrock": "bedrock_converse"}.get(lowercased, lowercased)


def create_langchain_model(config: Dict[str, Any]):
    """Build a LangChain chat model from a served AI config.

    Ported from the companion package's ``create_langchain_model``, reading the config as a
    dict instead of calling ``to_dict()`` on an object. Bedrock still needs the foundation
    provider passed in parameters separately from ``model_provider``, which LangChain uses
    for routing.
    """
    from langchain.chat_models import init_chat_model

    provider = provider_name(config)
    parameters = model_parameters(config)
    mapped = map_provider(provider)
    if mapped == "bedrock_converse" and "provider" not in parameters:
        parameters["provider"] = provider.removeprefix("bedrock:")
    return init_chat_model(model_name(config), model_provider=mapped, **parameters)


def build_tools(config: Dict[str, Any], tool_registry: Dict[str, Callable]) -> List[Any]:
    """The registry callables for the tools this config attaches.

    Ported from the companion package's ``build_tools``, with the tool names read through
    ``tool_names`` so both the wire shape and the validated shape resolve. Tools missing from
    the registry are skipped with a warning, as before — a config can name a tool the
    deployment does not implement.
    """
    tools = []
    for name in tool_names(config):
        fn = tool_registry.get(name)
        if fn is None:
            log.warning(
                "Tool '%s' is defined in the AI config but was not found in the tool "
                "registry; skipping.",
                name,
            )
            continue
        tools.append(fn)
    return tools


def get_tool_calls_from_response(response: Any) -> List[str]:
    """Tool names requested by one LangChain message, in order. Ported unchanged."""
    names: List[str] = []
    tool_calls = getattr(response, "tool_calls", None)
    if isinstance(tool_calls, list):
        for call in tool_calls:
            name = call.get("name") if isinstance(call, dict) else getattr(call, "name", None)
            if name:
                names.append(str(name))
    return names


def langchain_usage(response: Any) -> Optional[TokenUsage]:
    """Token usage from one LangChain message.

    Ported from the companion package's ``get_ai_usage_from_response``, keeping both of its
    sources: ``usage_metadata`` (what current LangChain populates) and the older
    ``response_metadata['token_usage']`` fallback. Normalization now goes through the SDK's
    ``parse_usage`` so the total is derived the same way as on every other arm.
    """
    usage_metadata = getattr(response, "usage_metadata", None)
    if usage_metadata:
        usage = TokenUsage.from_raw(dict(usage_metadata))
        if usage:
            return usage
    response_metadata = getattr(response, "response_metadata", None) or {}
    token_usage = response_metadata.get("tokenUsage") or response_metadata.get("token_usage")
    if token_usage:
        # This shape spells the counts the OpenAI way, which parse_usage does not read.
        return TokenUsage.from_raw(
            {
                "input_tokens": token_usage.get("promptTokens")
                or token_usage.get("prompt_tokens")
                or 0,
                "output_tokens": token_usage.get("completionTokens")
                or token_usage.get("completion_tokens")
                or 0,
            }
        )
    return None


def sum_langchain_usage(messages: List[Any]) -> Optional[TokenUsage]:
    """Total usage across LangChain messages, or ``None`` if none of them reported any.

    Ported from ``sum_token_usage_from_messages``. The all-zero case reports ``None`` rather
    than a zero usage, so a node whose provider omitted usage does not look like a node that
    used no tokens.
    """
    totals = TokenUsage()
    for message in messages:
        usage = langchain_usage(message)
        if usage is None:
            continue
        totals.input += usage.input
        totals.output += usage.output
        totals.total += usage.total
    if not (totals.input or totals.output or totals.total):
        return None
    return totals


# ──────────────────────────────────────────────────────────────────────────────────────────
# OpenAI Agents helpers (ported from launchdarkly-server-sdk-ai-openai 0.7.0)
# ──────────────────────────────────────────────────────────────────────────────────────────

# Hosted tools the Agents SDK reports as a `<name>_call` raw item type.
_OPENAI_HOSTED_TOOL_NAMES = frozenset(
    {"web_search", "file_search", "code_interpreter", "image_generation", "computer"}
)


def openai_agents_usage(result: Any) -> Optional[TokenUsage]:
    """Token usage from an openai-agents ``RunResult`` or a chat completions response.

    Ported from ``get_ai_usage_from_response``, keeping both sources: a ``RunResult`` carries
    the run's aggregate usage on ``context_wrapper.usage`` (``input_tokens``/
    ``output_tokens``), while a raw completions response carries ``usage``
    (``prompt_tokens``/``completion_tokens``). Only the first spelling is one
    ``parse_usage`` reads, so the second is translated.
    """
    usage = getattr(getattr(result, "context_wrapper", None), "usage", None)
    if usage is not None:
        parsed = TokenUsage.from_raw(
            {
                "input_tokens": getattr(usage, "input_tokens", 0) or 0,
                "output_tokens": getattr(usage, "output_tokens", 0) or 0,
            }
        )
        if parsed:
            return parsed
    usage = getattr(result, "usage", None)
    if usage is not None:
        return TokenUsage.from_raw(
            {
                "input_tokens": getattr(usage, "prompt_tokens", 0) or 0,
                "output_tokens": getattr(usage, "completion_tokens", 0) or 0,
            }
        )
    return None


def get_tool_calls_from_run_items(new_items: List[Any]) -> List[Tuple[str, str]]:
    """``(agent_name, tool_name)`` pairs from ``RunResult.new_items``. Ported unchanged.

    Covers custom FunctionTools (tracked by their config key) and the SDK's native hosted
    tools, which appear as a raw item type rather than a named function call.
    """
    try:
        from agents.items import ToolCallItem
        from openai.types.responses import ResponseFunctionToolCall
    except ImportError:
        return []

    calls: List[Tuple[str, str]] = []
    for item in new_items:
        if not isinstance(item, ToolCallItem):
            continue
        agent_name = getattr(item.agent, "name", None)
        if not agent_name:
            continue
        raw = item.raw_item
        if isinstance(raw, ResponseFunctionToolCall):
            tool_name = raw.name
        else:
            raw_type = getattr(raw, "type", None) or (
                raw.get("type") if isinstance(raw, dict) else None
            )
            if not isinstance(raw_type, str):
                continue
            if raw_type.endswith("_call"):
                base = raw_type.removesuffix("_call")
                tool_name = base if base in _OPENAI_HOSTED_TOOL_NAMES else raw_type
            else:
                tool_name = raw_type
        if tool_name:
            calls.append((agent_name, tool_name))
    return calls


def tool_names_from_run_items(new_items: List[Any], agent_name: Optional[str] = None) -> List[str]:
    """Just the tool names from ``RunResult.new_items``, optionally for one agent."""
    return [
        tool
        for agent, tool in get_tool_calls_from_run_items(new_items)
        if agent_name is None or agent == agent_name
    ]
