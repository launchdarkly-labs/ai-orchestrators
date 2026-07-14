"""
Google ADK NATIVE runner — Experiment C arm: ADK workflow agents own the walk.

ADK has no arbitrary-DAG primitive, so the drawn topology is reshaped into nested
``SequentialAgent`` / ``ParallelAgent`` levels running in one session. Treatment:
deterministic order (unlike handoffs) but accumulating context — every sub-agent sees the
full session conversation (like LangGraph's shared state, unlike the dispatcher's fresh input).

Per-node usage is attributed from the event stream by author (non-partial events), matching
the dispatcher's ADK accounting; the judge fires per node with the source papers as input;
per-node duration isn't reported and is left untracked. Returns execute_graph's dict.
"""

import time

from google.adk.agents import Agent, ParallelAgent, SequentialAgent
from google.adk.runners import InMemoryRunner
from google.genai import types
from ldai.tracker import TokenUsage

from orchestrators.dispatcher import _context_has_attr
from orchestrators.google_adk_runner import _bind_tools, _model, _safe_name

_APP = "gap-analysis"


def _topological_levels(nodes, preds):
    """Group node keys into dependency levels (Kahn): level N runs after all of N-1."""
    placed, levels = set(), []
    while len(placed) < len(nodes):
        level = [k for k in nodes if k not in placed and all(p in placed for p in preds[k])]
        if not level:
            raise RuntimeError(
                f"Agent graph has a cycle or disconnected dependency (unplaced: "
                f"{sorted(set(nodes) - placed)})"
            )
        levels.append(sorted(level))
        placed.update(level)
    return levels


async def run_graph(ai_client, graph_key, context, user_input, require_context_attr=None):
    """Run the LD agent graph with ADK's native workflow agents as the orchestrator.

    Same return shape as ``dispatcher.execute_graph``:
    ``{"output", "path", "judge_scores", "tokens", "model", "duration_ms"}``.
    """
    if require_context_attr and not _context_has_attr(context, require_context_attr):
        raise RuntimeError(
            f"run_graph: context is missing the '{require_context_attr}' attribute — set it to "
            f"the resolved arm before calling (see run_experiment.run_one)."
        )
    graph = ai_client.agent_graph(graph_key, context)
    if not graph.is_enabled():
        raise RuntimeError(
            f"Agent graph '{graph_key}' is not enabled "
            "(check the graph is on and every node config serves a real variation)"
        )

    graph_tracker = graph.create_tracker()

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

    configs = {k: n.get_config() for k, n in nodes.items()}
    any_config = next(iter(configs.values()), None)
    model_used = {
        "provider": any_config.provider.name if any_config and any_config.provider else "",
        "name": any_config.model.name if any_config and any_config.model else "",
    }

    # Reshape the DAG into ADK's native constructs: levels → SequentialAgent steps,
    # multi-node levels → ParallelAgent fan-outs. Node agents are built exactly like the
    # dispatcher arm (model/tools/instructions from the LD config).
    key_by_safe_name = {}
    def _node_agent(key):
        config = configs[key]
        safe = _safe_name(key)
        key_by_safe_name[safe] = key
        return Agent(
            name=safe,
            model=_model(config),
            instruction=config.instructions or "Process the input and respond.",
            tools=_bind_tools(config),
        )

    steps = []
    for i, level in enumerate(_topological_levels(nodes, preds)):
        agents = [_node_agent(k) for k in level]
        steps.append(agents[0] if len(agents) == 1
                     else ParallelAgent(name=f"level_{i}_parallel", sub_agents=agents))
    workflow = steps[0] if len(steps) == 1 else SequentialAgent(name="graph_walk", sub_agents=steps)

    outputs = {}
    path = []
    usage_by_key = {}

    start = time.monotonic()
    try:
        runner = InMemoryRunner(agent=workflow, app_name=_APP)
        session = await runner.session_service.create_session(app_name=_APP, user_id="harness")
        content = types.Content(role="user", parts=[types.Part(text=user_input)])
        async for event in runner.run_async(
            user_id="harness", session_id=session.id, new_message=content
        ):
            key = key_by_safe_name.get(getattr(event, "author", None))
            # Same accounting as the dispatcher's ADK arm: usage on non-partial events only.
            um = getattr(event, "usage_metadata", None)
            if key and um and not getattr(event, "partial", False):
                tok = usage_by_key.setdefault(key, [0, 0])
                tok[0] += getattr(um, "prompt_token_count", 0) or 0
                tok[1] += getattr(um, "candidates_token_count", 0) or 0
            if key and event.is_final_response() and event.content and event.content.parts:
                text = event.content.parts[0].text or ""
                if text:
                    outputs[key] = text
                    if key not in path:
                        path.append(key)
        duration_ms = int((time.monotonic() - start) * 1000)
    except Exception:
        graph_tracker.track_invocation_failure()
        raise

    # Post-hoc per-node tracking + judge (ADK ran the nodes; attribute from the stream).
    judge_scores = {}
    totals = {"in": 0, "out": 0}
    for key in nodes:
        in_tok, out_tok = usage_by_key.get(key, (0, 0))
        out = outputs.get(key, "")
        if not (in_tok or out_tok or out):
            continue  # node never ran (e.g. reshape dropped it) — nothing to record
        tracker = configs[key].create_tracker()
        if in_tok or out_tok:
            tracker.track_tokens(TokenUsage(input=in_tok, output=out_tok, total=in_tok + out_tok))
            totals["in"] += in_tok
            totals["out"] += out_tok
        tracker.track_success() if out.strip() else tracker.track_error()

        evaluator = getattr(configs[key], "evaluator", None)
        if evaluator is not None and out:
            for r in await evaluator.evaluate(user_input, out):
                if r.sampled and r.success:
                    tracker.track_judge_result(r)
                    judge_scores[r.metric_key] = r.score

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
