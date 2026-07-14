#!/usr/bin/env python3
"""
Experiment C — add the native-orchestrator arms to the `orchestrator` flag.

Experiments A/B swap which FRAMEWORK executes nodes under the shared dispatcher walk.
Experiment C varies the ORCHESTRATOR itself: the same drawn graph, walked by each
framework's native multi-agent machinery. This script adds one flag variation per native
arm — nothing else changes:

    langgraph-native       LangGraph StateGraph owns the walk (structural, superstep ∥,
                           shared accumulating message state)
    strands-native         Strands Graph owns the walk (structural, dependency-driven,
                           fresh "task + dependency outputs" input per node)
    openai-agents-native   Agents SDK handoffs own the walk (MODEL-decided, sequential,
                           full-conversation transfer — drawn edges become options)
    google-adk-native      ADK workflow agents own the walk (levels → Sequential/Parallel,
                           one shared session)
    langgraph-managed      the LD SDK's create_agent_graph().run() (zero-code baseline,
                           handoff-tool routing)

ADDITIVE + IDEMPOTENT: existing variations (langgraph / strands / openai-agents /
google-adk) are untouched; re-running skips variations that already exist. Node configs
need no changes — setup_native_routing's rules already match the `-native` values
(NATIVE_ARM_ALIASES), so C runs in either of the two model modes its toggle provides:

    # pairs mode: each native arm on its framework's native model (strands-native -> Nova),
    # so each dispatcher-vs-native PAIR holds the model constant
    python scripts/launchdarkly/setup_native_routing.py

    # pinned mode: ONE model on every arm — pure cross-orchestrator isolation
    # (must be the Anthropic pin: the langgraph arms have only langchain-anthropic)
    python scripts/launchdarkly/setup_native_routing.py --pin anthropic

    python scripts/launchdarkly/add_experiment_c_arms.py [--dry-run]

Then restart the experiment iteration so shapes' data don't mix, and drive matched
traffic with:

    python scripts/run_experiment.py --arms langgraph langgraph-native strands-native \\
        openai-agents-native google-adk-native langgraph-managed
"""

import os
import sys
from pathlib import Path

import requests
from dotenv import load_dotenv

project_root = Path(__file__).parent.parent.parent
load_dotenv(project_root / ".env")

FLAG_KEY = "orchestrator"

C_ARMS = [
    {"value": "langgraph-native", "name": "LangGraph (native walk)"},
    {"value": "strands-native", "name": "Strands (native walk)"},
    {"value": "openai-agents-native", "name": "OpenAI Agents (native handoffs)"},
    {"value": "google-adk-native", "name": "Google ADK (native workflow agents)"},
    {"value": "langgraph-managed", "name": "LangGraph (LD managed runner)"},
]


def main():
    dry_run = "--dry-run" in sys.argv
    api_key = os.environ.get("LD_API_KEY")
    project = os.environ.get("LD_PROJECT_KEY", "graph-experiments")
    if not api_key:
        sys.exit("LD_API_KEY is not set (needed for the REST API)")
    headers = {"Authorization": api_key, "Content-Type": "application/json"}
    url = f"https://app.launchdarkly.com/api/v2/flags/{project}/{FLAG_KEY}"

    r = requests.get(url, headers=headers, timeout=30)
    if r.status_code != 200:
        sys.exit(f"Could not read flag '{FLAG_KEY}': {r.status_code} {r.text[:200]}")
    existing = {v.get("value") for v in r.json().get("variations", [])}
    print(f"Flag '{FLAG_KEY}' has {len(existing)} variations: {sorted(existing)}")

    to_add = [arm for arm in C_ARMS if arm["value"] not in existing]
    if not to_add:
        print("✓ All Experiment C arms already present — nothing to do.")
        return
    for arm in to_add:
        print(f"  + {arm['value']}  ({arm['name']})")
    if dry_run:
        print("✨ Dry run complete — no changes made.")
        return

    patch = [{"op": "add", "path": "/variations/-", "value": arm} for arm in to_add]
    resp = requests.patch(url, headers=headers, json=patch, timeout=30)
    if resp.status_code == 200:
        print(f"✓ Added {len(to_add)} variation(s) to '{FLAG_KEY}'.")
        print()
        print("Next:")
        print("  • Pick a model mode (pairs: setup_native_routing.py — strands-native runs Nova;")
        print("    pinned: setup_native_routing.py --pin anthropic — one model everywhere).")
        print("  • Smoke the routes: python orchestrators/verify_run.py c")
        print("  • Restart the experiment iteration before driving C traffic (don't mix shapes).")
    else:
        # A running experiment iteration on the flag can block variation edits — surface it.
        sys.exit(f"✗ Patch failed: {resp.status_code} {resp.text[:400]}\n"
                 "  (If an experiment iteration is running on this flag, stop it first, "
                 "then re-run this script.)")


if __name__ == "__main__":
    main()
