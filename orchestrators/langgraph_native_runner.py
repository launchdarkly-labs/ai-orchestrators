"""
LangGraph NATIVE runner — Experiment C arm: LangGraph's StateGraph owns the walk.

Compiles the same LaunchDarkly graph into a native ``StateGraph`` and hands LangGraph the
whole traversal — structural edges, superstep parallelism, and LangGraph-idiomatic SHARED
MESSAGE STATE. That accumulating state is the treatment: every node inherits the papers plus
every upstream agent's full run (vs the dispatcher's fresh per-node input) — compare
``in_tokens`` against the dispatcher arm to read the context-management cost.

Metrics parity with the dispatcher (graph tracker + per-node config trackers), and any
attached judge fires per node with the source papers as input. Returns execute_graph's dict.
"""

import time
from typing import Annotated, TypedDict

from langgraph.graph import END, START, StateGraph
from langgraph.graph.message import add_messages
from langgraph.prebuilt import create_react_agent
from ldai.tracker import TokenUsage
from ldai.providers.types import LDAIMetrics
from ldai_langchain import (
    create_langchain_model,
    get_tool_calls_from_response,
    sum_token_usage_from_messages,
)
from ldai_langchain.langchain_helper import build_tools

from orchestrators.dispatcher import _context_has_attr
from orchestrators.langgraph_runner import _content_to_text
from shared.tools import TOOL_REGISTRY


class _GraphState(TypedDict):
    """LangGraph-idiomatic shared state: one accumulating message history.

    `add_messages` merges parallel branches' messages after each superstep, so the
    synthesizer receives BOTH analyzers' full transcripts — the native context-management
    behavior this arm exists to measure.
    """

    messages: Annotated[list, add_messages]


async def run_graph(ai_client, graph_key, context, user_input, require_context_attr=None):
    """Run the LD agent graph with LangGraph as the orchestrator (native `StateGraph` walk).

    Same signature intent and return shape as ``dispatcher.execute_graph`` so the harness
    treats the arms interchangeably:
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

    # Enumerate nodes + adjacency from the LD edges — identical read to the dispatcher's,
    # so both arms execute the exact same drawn topology.
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

    outputs = {}        # node_key -> final text of that node's new messages
    judge_scores = {}
    path = []           # completion order
    totals = {"in": 0, "out": 0}
    model_used = {}

    def _make_node_fn(key, node):
        config = node.get_config()
        model_used["provider"] = config.provider.name if config.provider else ""
        model_used["name"] = config.model.name if config.model else ""
        # Same per-node agent as the dispatcher arm (create_react_agent + LD model/tools/
        # instructions) — the node executor is held constant; only the walk + state differ.
        agent = create_react_agent(
            create_langchain_model(config),
            build_tools(config, TOOL_REGISTRY),
            prompt=config.instructions,
        )

        async def node_fn(state):
            tracker = config.create_tracker()
            in_len = len(state["messages"])
            # Usage is summed over the NEW messages only: upstream AI messages in the shared
            # state carry their own usage_metadata and are already counted by their node.
            result = await tracker.track_metrics_of_async(
                lambda res: LDAIMetrics(
                    success=True,
                    tokens=sum_token_usage_from_messages(res.get("messages", [])[in_len:]),
                ),
                lambda: agent.ainvoke({"messages": state["messages"]}),
            )
            new_msgs = result.get("messages", [])[in_len:]
            for message in new_msgs:
                for name in get_tool_calls_from_response(message):
                    tracker.track_tool_call(name)
            out = _content_to_text(new_msgs[-1].content) if new_msgs else ""
            outputs[key] = out

            # Judge parity with the dispatcher: the judge gets the SOURCE PAPERS as input so
            # grounding checks run against ground truth, not the accumulated transcript.
            evaluator = getattr(config, "evaluator", None)
            if evaluator is not None:
                for r in await evaluator.evaluate(user_input, out):
                    if r.sampled and r.success:
                        tracker.track_judge_result(r)
                        judge_scores[r.metric_key] = r.score

            usage = sum_token_usage_from_messages(new_msgs)
            if usage:
                totals["in"] += usage.input or 0
                totals["out"] += usage.output or 0
            path.append(key)
            for p in preds[key]:
                graph_tracker.track_handoff_success(p, key)
            return {"messages": new_msgs}

        return node_fn

    # Compile the drawn topology into a native StateGraph: entry nodes hang off START,
    # sinks feed END, and the LD edges are the LangGraph edges. LangGraph's superstep
    # scheduler now owns fan-out, fan-in, and state merging. Multi-predecessor nodes use
    # LangGraph's idiomatic JOIN form — add_edge(list, node) — so the node fires ONCE
    # after ALL predecessors; separate add_edge calls would fire it once per edge.
    sg = StateGraph(_GraphState)
    for key, node in nodes.items():
        sg.add_node(key, _make_node_fn(key, node))
    for key in nodes:
        if not preds[key]:
            sg.add_edge(START, key)
        elif len(preds[key]) == 1:
            sg.add_edge(preds[key][0], key)
        else:
            sg.add_edge(list(preds[key]), key)  # join: wait for ALL predecessors
        if not succ[key]:
            sg.add_edge(key, END)
    compiled = sg.compile()

    start = time.monotonic()
    try:
        # The papers enter ONCE, as the initial user message; every node inherits them via
        # the shared history (vs the dispatcher re-injecting them per node). Treatment.
        await compiled.ainvoke({"messages": [{"role": "user", "content": user_input}]})

        duration_ms = int((time.monotonic() - start) * 1000)
        graph_tracker.track_duration(duration_ms)
        if totals["in"] or totals["out"]:
            graph_tracker.track_total_tokens(
                TokenUsage(input=totals["in"], output=totals["out"], total=totals["in"] + totals["out"])
            )
        graph_tracker.track_path(path)
        graph_tracker.track_invocation_success()
    except Exception:
        graph_tracker.track_invocation_failure()
        raise

    terminals = {k for k in nodes if not succ[k]}
    final_output = next((outputs.get(k, "") for k in reversed(path) if k in terminals), "")
    return {"output": final_output, "path": path, "judge_scores": judge_scores,
            "tokens": {"input": totals["in"], "output": totals["out"]}, "model": dict(model_used),
            "duration_ms": duration_ms}
