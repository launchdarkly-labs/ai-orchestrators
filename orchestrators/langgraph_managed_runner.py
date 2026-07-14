"""
LangGraph MANAGED runner — Experiment C arm: the SDK's own orchestrator.

Hands the whole traversal to ``LDAIClient.create_agent_graph().run()`` (the ``ldai_langchain``
built-in runner, experimental) — zero orchestration code; the SDK does the walk and the
tracking. The managed path doesn't fire attached judges, so this wrapper fires the terminal
node's evaluator with the source papers as input. Returns execute_graph's dict.
"""

import time

from orchestrators.dispatcher import _context_has_attr
from shared.tools import TOOL_REGISTRY


async def run_graph(ai_client, graph_key, context, user_input, require_context_attr=None):
    """Run the LD agent graph with the SDK's managed LangGraph runner as the orchestrator.

    Same return shape as ``dispatcher.execute_graph`` / the native arm:
    ``{"output", "path", "judge_scores", "tokens", "model", "duration_ms"}``.
    Fields the managed runner does not report stay None/empty — reported honestly, not faked.
    """
    if require_context_attr and not _context_has_attr(context, require_context_attr):
        raise RuntimeError(
            f"run_graph: context is missing the '{require_context_attr}' attribute — set it to "
            f"the resolved arm before calling (see run_experiment.run_one)."
        )

    # `default_ai_provider='langchain'` pins the SDK's provider fallback to the LangGraph
    # runner (the node configs' provider is 'anthropic', which isn't itself a runner package).
    managed = ai_client.create_agent_graph(
        graph_key, context, tools=TOOL_REGISTRY, default_ai_provider="langchain"
    )
    if managed is None:
        raise RuntimeError(
            f"create_agent_graph('{graph_key}') returned None "
            "(graph disabled, or the langchain graph runner package is unavailable)"
        )

    # Read the graph definition once for judge + model metadata (the managed runner owns
    # all execution and tracking; we only need the terminal node's config).
    graph = ai_client.agent_graph(graph_key, context)
    nodes = {}
    graph.reverse_traverse(lambda node, _acc: nodes.update({node.get_key(): node}), {})
    non_terminal = {k for k, n in nodes.items() if n.get_edges()}
    terminals = [k for k in nodes if k not in non_terminal] or list(nodes)

    start = time.monotonic()
    result = await managed.run(user_input)  # graph + node tracking fire inside the SDK
    duration_ms = int((time.monotonic() - start) * 1000)

    summary = result.metrics
    tokens = summary.tokens
    output = result.content or ""

    # The managed path skips attached judges, so fire the terminal node's evaluator here
    # with the SOURCE PAPERS as input — the same grounding contract as the other arms.
    judge_scores = {}
    for term_key in terminals:
        config = nodes[term_key].get_config()
        evaluator = getattr(config, "evaluator", None)
        if evaluator is None:
            continue
        for r in await evaluator.evaluate(user_input, output):
            if r.sampled and r.success:
                config.create_tracker().track_judge_result(r)
                judge_scores[r.metric_key] = r.score

    # Model metadata for cost pricing (pinned: same across nodes in one run).
    any_config = nodes[terminals[0]].get_config() if terminals else None
    model_used = {
        "provider": any_config.provider.name if any_config and any_config.provider else "",
        "name": any_config.model.name if any_config and any_config.model else "",
    }

    return {
        "output": output,
        "path": list(summary.path or []),  # whatever route the model-decided handoffs took
        "judge_scores": judge_scores,
        "tokens": {"input": tokens.input if tokens else 0, "output": tokens.output if tokens else 0},
        "model": model_used,
        "duration_ms": summary.duration_ms or duration_ms,
    }
