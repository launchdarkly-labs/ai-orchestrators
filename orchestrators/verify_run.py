"""
Smoke test: run a framework over a tiny paper set against the live graph.

    python orchestrators/verify_run.py langgraph     # one framework
    python orchestrators/verify_run.py all            # all four, with a summary
    python orchestrators/verify_run.py                # no arg == all four

Confirms the framework executes the shared graph (whatever shape the LD edges define),
routing read from the LD edges, and that metrics land in AgentControl.
"""

import asyncio
import importlib
import json
import os
import sys
import time
from pathlib import Path

project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from dotenv import load_dotenv
load_dotenv(project_root / ".env")

import ldclient
from ldclient import Context
from ldclient.config import Config
from ldai.client import LDAIClient

from shared.prompt import build_paper_prompt
from orchestrators.dispatcher import execute_graph

RUNNERS = {
    "langgraph": "orchestrators.langgraph_runner",
    "strands": "orchestrators.strands_runner",
    "openai-agents": "orchestrators.openai_agents_runner",
    "google-adk": "orchestrators.google_adk_runner",
}
GRAPH_KEY = "research-gap-graph"


def load_papers(n=2):
    data = json.load(open(project_root / "data" / "combined_ai_agent_papers.json"))
    papers = data if isinstance(data, list) else data.get("papers") or data.get("items") or []
    return papers[:n]


async def smoke(framework, ai_client, papers):
    """Run one framework over the shared graph; return True on success."""
    runner = importlib.import_module(RUNNERS[framework])
    user_input = build_paper_prompt(papers)
    # Multi-context: "user" keeps user-unit metrics populating, "request" is the per-run unit
    # for AI/graph latency + token metrics (and the experiment's randomization unit).
    rid = f"verify-{framework}"
    context = Context.create_multi(
        Context.builder(rid).kind("user").set("orchestrator", framework).build(),
        Context.builder(rid).kind("request").set("orchestrator", framework).build(),
    )
    print(f"\n▶ Running '{framework}' over {len(papers)} papers on graph '{GRAPH_KEY}'...")
    try:
        result = await execute_graph(
            ai_client, GRAPH_KEY, context, user_input, runner.build_agent, runner.invoke,
            require_context_attr="orchestrator",
        )
    except Exception as e:
        print(f"  ✗ {framework} FAILED: {str(e)[:200]}")
        return False
    print("  ✓ PATH :", " -> ".join(result["path"]))
    snippet = (result["output"] or "")[:300].replace("\n", "\n    ")
    print(f"  ✓ OUTPUT (first 300 chars):\n    {snippet}")
    return True


async def main():
    arg = sys.argv[1] if len(sys.argv) > 1 else "all"
    frameworks = list(RUNNERS) if arg == "all" else [arg]
    unknown = [f for f in frameworks if f not in RUNNERS]
    if unknown:
        print(f"Unknown framework {unknown}. Choose one of {list(RUNNERS)}, or 'all'.")
        return

    ldclient.set_config(Config(os.environ["LD_SDK_KEY"]))
    for _ in range(12):
        if ldclient.get().is_initialized():
            break
        time.sleep(0.5)
    ai_client = LDAIClient(ldclient.get())

    papers = load_papers(2)
    results = {}
    for fw in frameworks:
        results[fw] = await smoke(fw, ai_client, papers)

    # Flush before close — short-lived scripts lose trailing events otherwise.
    ldclient.get().flush()
    ldclient.get().close()

    if len(frameworks) > 1:
        print("\n=== smoke summary ===")
        for fw in frameworks:
            print(f"  {'✓' if results[fw] else '✗'} {fw}")
    if not all(results.values()):
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
