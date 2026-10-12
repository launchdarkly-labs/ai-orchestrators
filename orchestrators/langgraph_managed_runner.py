"""
LangGraph MANAGED runner — Experiment C arm: the SDK's own orchestrator.

Hands the whole traversal to ``launchdarkly_ai_langchain_agents.to_lang_graph()`` — zero
orchestration code; the SDK compiles the drawn graph into a LangGraph ``StateGraph``, walks
it, and emits both the node and the graph metrics. This arm's value is exactly that it is
the zero-code baseline, so it stays as thin as the SDK allows.

Two things the managed path does not do, which this wrapper supplies:

  * It does not fire judges attached to the node configs, so the terminal node's judges are
    fired here with the source papers as input — the same grounding contract as every other
    arm.
  * It does not return the path it walked (it emits one ``$ld:ai:graph:node`` per node
    entered, but the caller gets only the response and the usage totals), so ``path``
    comes back empty. Reported honestly rather than reconstructed.

Returns execute_graph's dict.
"""

import time

from launchdarkly_ai_langchain_agents import to_lang_graph
from launchdarkly_ai_server import resolve_graph

from shared.ldai_compat import (
    ConfigTracker,
    context_has_attr,
    create_langchain_model,
    model_name,
    provider_name,
)
from shared.tools import TOOL_REGISTRY


async def run_graph(graph_key, context, user_input, require_context_attr=None):
    """Run the LD agent graph with the SDK's managed LangGraph adapter as the orchestrator.

    Same return shape as ``dispatcher.execute_graph`` / the native arm:
    ``{"output", "path", "judge_scores", "tokens", "model", "duration_ms"}``.
    Fields the managed runner does not report stay None/empty — reported honestly, not faked.
    """
    if require_context_attr and not context_has_attr(context, require_context_attr):
        raise RuntimeError(
            f"run_graph: context is missing the '{require_context_attr}' attribute — set it to "
            f"the resolved arm before calling (see run_experiment.run_one)."
        )

    # Resolved here rather than inside the adapter so the terminal node's config is available
    # afterwards for the judge and the cost metadata; `to_lang_graph` awaits whatever it is
    # given and returns only the response, so a definition it resolved itself is unreachable.
    definition = await resolve_graph(graph_key, context=context)
    if not definition.enabled:
        raise RuntimeError(
            f"Agent graph '{graph_key}' is not enabled "
            "(check the graph is on and every node config serves a real variation)"
        )

    async def _resolved():
        return definition

    # `model_factory` is what pins the walk to the node configs' served model. Without it the
    # adapter builds a ChatOpenAI from the model name alone, which would silently run these
    # Anthropic nodes on an OpenAI default and invalidate the comparison.
    runner = to_lang_graph(
        _resolved(),
        {
            "context": context,
            "tool_handlers": TOOL_REGISTRY,
            "model_factory": lambda node: create_langchain_model(node.config),
        },
    )

    start = time.monotonic()
    result = await runner.invoke(user_input)  # graph + node tracking fire inside the SDK
    duration_ms = int((time.monotonic() - start) * 1000)

    output = result.get("response") or ""
    usage = result.get("usage") or {}

    terminals = definition.terminal_nodes() or ([definition.root] if definition.root else [])

    # The managed path skips attached judges, so fire the terminal node's here with the
    # SOURCE PAPERS as input — the same grounding contract as the other arms.
    judge_scores = {}
    for node in terminals:
        tracker = ConfigTracker(node.key, node.config, node.meta, context, graph_key)
        judge_scores.update(await tracker.track_judges(node.config, context, user_input, output))

    # Model metadata for cost pricing (pinned: same across nodes in one run).
    any_config = terminals[0].config if terminals else {}
    model_used = {"provider": provider_name(any_config), "name": model_name(any_config)}

    return {
        "output": output,
        # The adapter tracks the path it walked but does not return it.
        "path": [],
        "judge_scores": judge_scores,
        "tokens": {"input": usage.get("input", 0), "output": usage.get("output", 0)},
        "model": model_used,
        "duration_ms": duration_ms,
    }
