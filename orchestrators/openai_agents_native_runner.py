"""
OpenAI Agents NATIVE runner — Experiment C arm: SDK handoffs own the walk.

Handoffs are model-decided and sequential (one agent transfers to one agent), so they can't
traverse the parallel diamond — this arm runs the linear ``research-gap-graph-linear`` chain
(routed by the ``graph-key`` flag). Prompts live entirely in LaunchDarkly: the OpenAI node
variations carry the handoff-aware instructions; the runner synthesizes no prompt text, it
only builds each agent from config and wires the drawn edges as message-carrying handoffs.

``path`` is the route the model actually took. The SDK reports aggregate usage only (no
per-agent breakdown), so tokens are recorded at the graph level and node trackers record
success + tool calls. The judge fires on the terminal node's output with the source papers as
input (so that variation must have the judge attached). Returns the same dict as
``dispatcher.execute_graph``.
"""

import re
import time

from pydantic import BaseModel
from agents import Agent, Runner, handoff
from agents.items import HandoffOutputItem

from orchestrators.openai_agents_runner import _bind_tools, _create_model, _model_settings
from shared.ldai_compat import (
    ConfigTracker,
    TokenUsage,
    adjacency,
    context_has_attr,
    instructions,
    model_name,
    openai_agents_usage,
    provider_name,
    read_nodes,
    resolve_graph_run,
    tool_names_from_run_items,
)

_MAX_TURNS = 40  # one run spans every agent in the walk, so give it more room than a node


class _HandoffFindings(BaseModel):
    """Transfer-tool payload: the sending agent's complete findings.

    Carrying the analysis in the handoff fuses do-the-work and hand-off into one atomic call,
    so the model can't finish and forget to transfer. The findings ride in the tool-call args
    the receiving agent inherits.
    """

    findings: str


async def _on_handoff(ctx, payload):  # noqa: ARG001 - SDK requires a callback with input_type
    return None


async def run_graph(graph_key, context, user_input, require_context_attr=None):
    """Run the LD agent graph with the Agents SDK's native handoffs as the orchestrator.

    Same return shape as ``dispatcher.execute_graph``:
    ``{"output", "path", "judge_scores", "tokens", "model", "duration_ms"}``.
    """
    if require_context_attr and not context_has_attr(context, require_context_attr):
        raise RuntimeError(
            f"run_graph: context is missing the '{require_context_attr}' attribute — set it to "
            f"the resolved arm before calling (see run_experiment.run_one)."
        )
    graph, graph_tracker, run_id = await resolve_graph_run(graph_key, context)

    nodes = await read_nodes(graph)
    succ, preds = adjacency(nodes)

    configs = {k: n.config for k, n in nodes.items()}
    any_config = next(iter(configs.values()), None) or {}
    model_used = {"provider": provider_name(any_config), "name": model_name(any_config)}

    # Build each agent from its LD config as-is (prompts are authored in LD, not here).
    agents_by_key = {
        key: Agent(
            name=key,
            instructions=instructions(config),
            model=_create_model(config),
            model_settings=_model_settings(config),
            tools=_bind_tools(config),
        )
        for key, config in configs.items()
    }
    # Message-carrying handoffs (see _HandoffFindings). Tool name matches the LD prompt.
    for key, agent in agents_by_key.items():
        agent.handoffs = [
            handoff(
                agents_by_key[t],
                input_type=_HandoffFindings,
                on_handoff=_on_handoff,
                tool_name_override="transfer_to_" + re.sub(r"[^a-zA-Z0-9_]", "_", t),
                tool_description_override=(
                    f"Hand control to {t}. Pass your complete findings in the `findings` field."
                ),
            )
            for t in succ[key]
        ]

    roots = [k for k in nodes if not preds[k]]
    if len(roots) != 1:
        raise RuntimeError(
            f"Handoff orchestration needs exactly one entry node to start from; the drawn "
            f"graph has {len(roots)}: {sorted(roots)}"
        )

    start = time.monotonic()
    try:
        result = await Runner.run(agents_by_key[roots[0]], user_input, max_turns=_MAX_TURNS)
        duration_ms = int((time.monotonic() - start) * 1000)
    except Exception:
        graph_tracker.track_invocation_failure()
        raise

    # The path the model ACTUALLY took: root, then each handoff's target in order.
    path = [roots[0]]
    for item in result.new_items:
        if isinstance(item, HandoffOutputItem):
            src = getattr(item.source_agent, "name", None)
            tgt = getattr(item.target_agent, "name", None)
            if tgt in nodes:
                path.append(tgt)
                if src in nodes:
                    graph_tracker.track_handoff_success(src, tgt)

    # Per-node tracking for visited agents: success + tool calls (the SDK result doesn't
    # attribute tokens per agent, so those stay graph-level — honest, not faked).
    items_by_agent = {}
    for item in result.new_items:
        name = getattr(getattr(item, "agent", None), "name", None)
        if name in nodes:
            items_by_agent.setdefault(name, []).append(item)
    for key in dict.fromkeys(path):  # de-dup, preserve order
        tracker = ConfigTracker(key, configs[key], nodes[key].meta, context, graph_key, run_id)
        tracker.track_success()
        tracker.track_tool_calls(tool_names_from_run_items(items_by_agent.get(key, [])))

    output = str(result.final_output or "")
    usage = openai_agents_usage(result)
    in_tok = (usage.input or 0) if usage else 0
    out_tok = (usage.output or 0) if usage else 0

    # Judge on the drawn TERMINAL node's attached judges with the source papers — the quality
    # contract is the same even if the model's route never reached that node.
    judge_scores = {}
    terminals = [k for k in nodes if not succ[k]] or list(nodes)
    for term_key in terminals:
        if not output:
            continue
        term_tracker = ConfigTracker(
            term_key, configs[term_key], nodes[term_key].meta, context, graph_key, run_id
        )
        judge_scores.update(
            await term_tracker.track_judges(configs[term_key], context, user_input, output)
        )

    graph_tracker.track_duration(duration_ms)
    if in_tok or out_tok:
        graph_tracker.track_total_tokens(
            TokenUsage(input=in_tok, output=out_tok, total=in_tok + out_tok)
        )
    graph_tracker.track_path(path)
    graph_tracker.track_invocation_success()

    return {"output": output, "path": path, "judge_scores": judge_scores,
            "tokens": {"input": in_tok, "output": out_tok}, "model": dict(model_used),
            "duration_ms": duration_ms}
