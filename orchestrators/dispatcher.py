"""
Generic agent-graph dispatcher (parallel DAG executor).

Executes the LaunchDarkly agent graph as a directed acyclic graph: each node runs once
all of its predecessors have completed, and independent nodes at the same level run
**concurrently**. The same code serves every framework — the only per-framework pieces are
`build_agent` + `invoke`, passed in by each runner.

Routing is **structural**: the topology is whatever the LD graph edges define (read at
runtime), and the dispatcher follows `source → target` directly. Agents do not emit
routes — the graph you draw in the UI IS the execution plan.

Data flow — the papers are the SHARED GROUND TRUTH:
  * The SOURCE PAPERS (with ArXiv IDs) are injected into EVERY node's input, alongside any
    upstream analyses. So every agent — and the judge — works against the real papers, not a
    summary handed down a chain, and each agent keeps the IDs it needs for `fetch_paper`.
  * Every node is a real agent — there are NO structural special cases. The `intake` entry
    node runs like any other, which is what keeps the graph runnable under any UI reshape:
    add or remove a node/edge and the next request runs the new shape, no code change.

Online evaluations: after a node runs, the dispatcher fires any judges attached to that
node's config via `config.evaluator.evaluate(papers, output)` — note the judge is given the
SOURCE PAPERS as its input so faithfulness/citation checks have the ground truth. This
records the judge metric (e.g. `$ld:ai:judge:gap-quality`), driven by the LD attachment.

Metrics are automatic: the graph tracker records handoffs / path / invocation / tokens, and
each node's `config.create_tracker()` records duration + tokens + tool calls via the runner's
`track_metrics_of_async`. Cost / latency / token totals derive from these in AgentControl.

A note on the SDK's managed graph: `LDAIClient.create_agent_graph().run()` hands the whole
traversal to a built-in runner — orchestration, state handling, and metrics come for free,
which is the fastest path when you're building on one of its supported frameworks (LangGraph,
OpenAI Agents). This project's needs are narrower and stricter: a bake-off requires the walk
itself to be a held-constant variable — byte-identical traversal semantics across four
frameworks — plus control over the judge's evaluation input (the source papers). Owning the
~100-line walk gives us both, so the dispatcher is the experiment's control surface and the
frameworks supply only `build_agent` + `invoke`.
"""

import asyncio
import time

from ldai.tracker import TokenUsage


def _context_has_attr(context, attr):
    """True if ``attr`` is set on ``context`` (checked across every kind of a multi-context)."""
    if context.multiple:
        return any(
            (ind := context.get_individual_context(i)) is not None and ind.get(attr) is not None
            for i in range(context.individual_context_count)
        )
    return context.get(attr) is not None


def compose_input(user_input, predecessor_outputs):
    """Build a node's input: the SOURCE PAPERS (ground truth) + any upstream analyses.

    ``predecessor_outputs`` is a list of ``(node_key, output_text)``. Empty outputs are
    dropped so they don't add noise.
    """
    parts = [f"=== SOURCE PAPERS ===\n{user_input}"]
    for key, out in predecessor_outputs:
        if out and out.strip():
            parts.append(f"=== {key} ===\n{out}")
    return "\n\n".join(parts)


async def execute_graph(ai_client, graph_key, context, user_input, build_agent, invoke, max_rounds=10,
                        require_context_attr=None):
    """Execute the LD agent graph as a parallel DAG.

    Args:
        ai_client: an ``LDAIClient``.
        graph_key: the agent graph key (e.g. ``"research-gap-graph"``).
        context: the LaunchDarkly ``Context`` for this run.
        user_input: the SOURCE PAPERS prompt (injected into every node).
        build_agent: ``(node_key, config, instructions) -> agent`` (framework-specific).
        invoke: ``async (agent, input_text, node_tracker) -> (output_text, TokenUsage|None)``.
        max_rounds: safety bound on scheduler rounds (DAG depth); guards against cycles.
        require_context_attr: if set (e.g. ``"orchestrator"``), fail loudly when the context lacks
            that attribute. The node configs route on it, so a missing attribute silently collapses
            every node to the pinned base model — the experiment driver passes this so a caller that
            forgets to set the resolved framework on the context can't quietly break the bake-off.

    Returns:
        ``{"output": <terminal node text>, "path": [<node keys, completion order>],
           "judge_scores": {<metric_key>: <score>}}``.
    """
    if require_context_attr and not _context_has_attr(context, require_context_attr):
        raise RuntimeError(
            f"execute_graph: context is missing the '{require_context_attr}' attribute. The graph's "
            f"node configs route on it (targeting rule: orchestrator == <framework>), so without it "
            f"every node falls through to the pinned base model and the orchestrator bake-off "
            f"silently collapses to one model. Evaluate the orchestrator flag, then set "
            f"'{require_context_attr}'=<resolved framework> on the context (all kinds) before "
            f"calling execute_graph — see run_experiment.run_one."
        )
    graph = ai_client.agent_graph(graph_key, context)
    if not graph.is_enabled():
        raise RuntimeError(
            f"Agent graph '{graph_key}' is not enabled "
            "(check the graph is on and every node config serves a real variation)"
        )

    graph_tracker = graph.create_tracker()
    start = time.monotonic()

    # Enumerate nodes and build adjacency from the graph edges (the execution DAG).
    nodes = {}
    graph.reverse_traverse(lambda node, _acc: nodes.update({node.get_key(): node}), {})
    succ = {k: [] for k in nodes}
    preds = {k: [] for k in nodes}
    for key, node in nodes.items():
        for edge in node.get_edges():
            target = edge.target_config
            if target in nodes:
                succ[key].append(target)
                preds[target].append(key)

    outputs = {}        # node_key -> output text
    judge_scores = {}
    path = []           # completion order
    totals = {"in": 0, "out": 0}

    async def run_node(key):
        config = nodes[key].get_config()
        pred_outputs = [(p, outputs.get(p, "")) for p in preds[key]]
        node_input = compose_input(user_input, pred_outputs)
        agent = build_agent(key, config, config.instructions)
        node_tracker = config.create_tracker()
        out, usage = await invoke(agent, node_input, node_tracker)
        out = out or ""

        # Fire any judges attached to this node (online evaluation). The judge is given the
        # SOURCE PAPERS as input so it can verify the output's grounding/citations against the
        # ground truth — not against a derived upstream analysis. Unattached nodes carry a
        # no-op evaluator, so this is safe on every node.
        evaluator = getattr(config, "evaluator", None)
        if evaluator is not None:
            for r in await evaluator.evaluate(user_input, out):
                if r.sampled and r.success:
                    node_tracker.track_judge_result(r)
                    judge_scores[r.metric_key] = r.score
        return key, out, usage

    try:
        done, pending, rounds = set(), set(nodes), 0
        while pending and rounds < max_rounds:
            rounds += 1
            ready = [k for k in pending if all(p in done for p in preds[k])]
            if not ready:
                break  # no runnable node but work remains → cycle / disconnected; handled below

            # Run every node whose predecessors are done, concurrently. Each node is a real
            # agent — no structural special cases — so any shape drawn or reshaped in the LD
            # UI is runnable as-is.
            results = await asyncio.gather(*(run_node(k) for k in ready))
            for key, out, usage in results:
                outputs[key] = out
                if usage:
                    totals["in"] += usage.input or 0
                    totals["out"] += usage.output or 0
                done.add(key)
                pending.discard(key)
                path.append(key)
                for p in preds[key]:
                    graph_tracker.track_handoff_success(p, key)

        if pending:
            # The graph did not fully execute: a cycle, a disconnected node, or a shape deeper
            # than max_rounds. Don't log a partial run as success — fail loudly (the except below
            # records invocation_failure) so a malformed UI reshape surfaces instead of feeding
            # the experiment a truncated report.
            raise RuntimeError(
                f"Agent graph '{graph_key}' did not fully execute (unreached nodes: "
                f"{sorted(pending)}; check for a cycle or a graph deeper than max_rounds={max_rounds})"
            )

        # End-to-end graph latency ($ld:ai:graph:duration:total) — the experiment's primary
        # metric, recorded once per run on the request-kind context.
        graph_tracker.track_duration(int((time.monotonic() - start) * 1000))
        if totals["in"] or totals["out"]:
            graph_tracker.track_total_tokens(
                TokenUsage(input=totals["in"], output=totals["out"], total=totals["in"] + totals["out"])
            )
        graph_tracker.track_path(path)
        graph_tracker.track_invocation_success()
    except Exception:
        graph_tracker.track_invocation_failure()
        raise

    # Final output = the terminal node's output (the fan-in sink). Take the last terminal
    # to complete, in case the graph has more than one.
    terminals = {k for k in nodes if not succ[k]}
    final_output = next((outputs.get(k, "") for k in reversed(path) if k in terminals), "")
    return {"output": final_output, "path": path, "judge_scores": judge_scores}
