#!/usr/bin/env python3
"""
Bootstrap the LINEAR agent graph for the handoff arm (Experiment C — routing paradigm).

The main `research-gap-graph` is a DIAMOND (intake → [approach-analyzer ∥
contradiction-detector] → gap-synthesizer) drawn for the structural dispatcher's parallel
fan-out. Handoff orchestrators (OpenAI Agents SDK) route SEQUENTIALLY — one agent transfers
to one agent — so they cannot traverse that fan-out. Main's swarm tutorial made handoffs
walk by drawing a linear CHAIN and writing handoff-aware prompts; this reproduces that shape.

This creates a second graph, `research-gap-graph-linear`, that:
  * reuses the EXACT SAME node AI configs (intake / approach-analyzer /
    contradiction-detector / gap-synthesizer) — same prompts, models, tools, judge; only the
    topology differs, so the workload is held constant, only the walk shape changes;
  * wires them as a chain intake → approach-analyzer → contradiction-detector →
    gap-synthesizer;
  * puts handoff data on each edge (a description naming the next agent) — the field the SDK
    exposes as `edge.handoff`, which the managed OpenAI runner and our native runner can use
    to drive the transfer.

Routing to it lives in LaunchDarkly: the `graph-key` flag (bootstrap_graph_key_flag.py)
targets the orchestrator attribute and serves this graph's key to `openai-agents-native`,
so that arm walks the chain while every structural arm keeps walking the diamond.

    python scripts/launchdarkly/bootstrap_linear_graph.py [--dry-run]

Run AFTER bootstrap.py (the node configs must already exist). Idempotent — re-running skips
the graph if it exists and re-syncs edges.
"""

import os
import sys
from pathlib import Path

from dotenv import load_dotenv

sys.path.insert(0, str(Path(__file__).parent))
from bootstrap import AgentGraphBootstrap  # noqa: E402

project_root = Path(__file__).parent.parent.parent
load_dotenv(project_root / ".env")

GRAPH_KEY = "research-gap-graph-linear"

# The chain. Each edge carries handoff data (a description naming the next agent) so a
# handoff-routing runner has an explicit transfer target — the diamond's edges are bare
# because the structural dispatcher never reads handoff.
GRAPH_DATA = {
    "key": GRAPH_KEY,
    "name": "Research Gap Graph (linear / handoff chain)",
    "root": "intake",
    "edges": [
        {
            "key": "intake-to-analyzer",
            "source": "intake",
            "target": "approach-analyzer",
            "handoff": {"description": "Hand off to the approach analyzer once intake is done."},
        },
        {
            "key": "analyzer-to-detector",
            "source": "approach-analyzer",
            "target": "contradiction-detector",
            "handoff": {"description": "Hand off to the contradiction detector once the approach analysis is written."},
        },
        {
            "key": "detector-to-synthesizer",
            "source": "contradiction-detector",
            "target": "gap-synthesizer",
            "handoff": {"description": "Hand off to the gap synthesizer once contradictions are written."},
        },
    ],
}


def main():
    dry_run = "--dry-run" in sys.argv
    api_key = os.environ.get("LD_API_KEY")
    project = os.environ.get("LD_PROJECT_KEY", "graph-experiments")
    if not api_key:
        sys.exit("LD_API_KEY is not set (needed for the REST API)")

    print(f"Linear handoff graph → project '{project}', graph '{GRAPH_KEY}'")
    print("  chain: intake → approach-analyzer → contradiction-detector → gap-synthesizer")
    print("  (reuses the existing node configs — nothing about them changes)")
    if dry_run:
        for e in GRAPH_DATA["edges"]:
            print(f"    [dry-run] edge {e['source']} → {e['target']}  handoff={e['handoff']}")
        print("✨ Dry run — no changes made.")
        return

    bootstrap = AgentGraphBootstrap(api_key)
    if not bootstrap.verify_project(project):
        sys.exit(1)
    ok = bootstrap.create_agent_graph(project, GRAPH_DATA)
    if not ok:
        sys.exit("✗ Failed to create the linear graph")
    print()
    print("Next:")
    print("  • Smoke the handoff arm on the chain:")
    print("      python orchestrators/verify_run.py openai-agents-native")
    print("    (the graph-key flag routes openai-agents-native → this graph — run bootstrap_graph_key_flag.py)")


if __name__ == "__main__":
    main()
