"""
Strands NATIVE runner — Experiment C arm: Strands' own Graph owns the walk.

Compiles the same LaunchDarkly graph into a native Strands ``Graph`` (``GraphBuilder``).
Treatment: Strands composes each node's input as the original task + a digest of its
dependencies' outputs — close to the dispatcher's fresh per-node input, unlike LangGraph's
accumulating state. Note Strands fires a node when ANY predecessor completes (re-executing
multi-predecessor nodes), where the dispatcher joins on ALL.

Strands runs the nodes internally, so per-node tracking is driven post-hoc from the returned
``GraphResult`` (config trackers) + graph tracker; the judge fires per node with the source
papers as input. Returns execute_graph's dict.
"""

import time

from strands.multiagent import GraphBuilder
from strands import Agent

from orchestrators.strands_runner import _bind_tools, _create_strands_model, _message_text
from shared.ldai_compat import (
    ConfigTracker,
    TokenUsage,
    adjacency,
    context_has_attr,
    instructions,
    model_name,
    provider_name,
    read_nodes,
    resolve_graph_run,
)

_COMPLETED = "completed"


def _usage_tokens(usage):
    """Read a Strands Usage (dict-like or attrs) into (input, output, total)."""
    if usage is None:
        return 0, 0, 0
    get = usage.get if hasattr(usage, "get") else lambda k, d=0: getattr(usage, k, d)
    in_tok = get("inputTokens", 0) or 0
    out_tok = get("outputTokens", 0) or 0
    total = get("totalTokens", 0) or (in_tok + out_tok)
    return in_tok, out_tok, total


async def run_graph(graph_key, context, user_input, require_context_attr=None):
    """Run the LD agent graph with Strands' native Graph as the orchestrator.

    Same return shape as ``dispatcher.execute_graph``:
    ``{"output", "path", "judge_scores", "tokens", "model", "duration_ms"}``.
    """
    if require_context_attr and not context_has_attr(context, require_context_attr):
        raise RuntimeError(
            f"run_graph: context is missing the '{require_context_attr}' attribute — set it to "
            f"the resolved arm before calling (see run_experiment.run_one)."
        )
    graph, graph_tracker, run_id = await resolve_graph_run(graph_key, context)

    # Enumerate nodes + adjacency from the LD edges — identical read to the dispatcher's.
    nodes = await read_nodes(graph)
    succ, preds = adjacency(nodes)

    configs = {k: n.config for k, n in nodes.items()}
    any_config = next(iter(configs.values()), None) or {}
    model_used = {"provider": provider_name(any_config), "name": model_name(any_config)}

    # Compile the drawn topology into a native Strands Graph: same per-node agents as the
    # dispatcher arm (model/tools/instructions from the LD config); Strands owns scheduling,
    # fan-out/fan-in, and each node's input composition.
    builder = GraphBuilder()
    for key, config in configs.items():
        builder.add_node(
            Agent(
                name=key,
                model=_create_strands_model(config),
                system_prompt=instructions(config) or "Process the input and respond.",
                tools=_bind_tools(config),
                callback_handler=None,
            ),
            key,
        )
    for key in nodes:
        for target in succ[key]:
            builder.add_edge(key, target)
        if not preds[key]:
            builder.set_entry_point(key)
    strands_graph = builder.build()

    start = time.monotonic()
    try:
        result = await strands_graph.invoke_async(user_input)
        status = str(getattr(result, "status", "")).lower()
        if _COMPLETED not in status:
            raise RuntimeError(
                f"Strands graph run did not complete (status={status!r}, "
                f"completed={result.completed_nodes}/{result.total_nodes})"
            )
        duration_ms = int((time.monotonic() - start) * 1000)
    except Exception:
        graph_tracker.track_invocation_failure()
        raise

    # Post-hoc per-node tracking + judge from the GraphResult (Strands ran the nodes).
    outputs = {}
    judge_scores = {}
    path = [n.node_id for n in getattr(result, "execution_order", []) if n.node_id in nodes]
    totals = {"in": 0, "out": 0}
    for key, node_result in (result.results or {}).items():
        if key not in configs:
            continue
        tracker = ConfigTracker(key, configs[key], nodes[key].meta, context, graph_key, run_id)
        in_tok, out_tok, total = _usage_tokens(node_result.accumulated_usage)
        if total:
            tracker.track_tokens(TokenUsage(input=in_tok, output=out_tok, total=total))
            totals["in"] += in_tok
            totals["out"] += out_tok
        if node_result.execution_time:
            tracker.track_duration(node_result.execution_time)
        agent_results = node_result.get_agent_results()
        for ar in agent_results:
            for tool_name, tm in (getattr(ar.metrics, "tool_metrics", None) or {}).items():
                for _ in range(tm.call_count):
                    tracker.track_tool_call(tool_name)
        out = _message_text(agent_results[-1]) if agent_results else ""
        outputs[key] = out
        node_ok = _COMPLETED in str(getattr(node_result, "status", "")).lower()
        tracker.track_success() if node_ok else tracker.track_error()

        # Judge parity: the judge gets the SOURCE PAPERS as input (ground truth).
        if out:
            judge_scores.update(
                await tracker.track_judges(configs[key], context, user_input, out)
            )

    for key in path:
        for p in preds[key]:
            graph_tracker.track_handoff_success(p, key)
    graph_tracker.track_duration(duration_ms)
    if totals["in"] or totals["out"]:
        graph_tracker.track_total_tokens(
            TokenUsage(input=totals["in"], output=totals["out"], total=totals["in"] + totals["out"])
        )
    graph_tracker.track_path(path)
    graph_tracker.track_invocation_success()

    terminals = {k for k in nodes if not succ[k]}
    final_output = next((outputs.get(k, "") for k in reversed(path) if k in terminals), "")
    return {"output": final_output, "path": path, "judge_scores": judge_scores,
            "tokens": {"input": totals["in"], "output": totals["out"]}, "model": dict(model_used),
            "duration_ms": duration_ms}
