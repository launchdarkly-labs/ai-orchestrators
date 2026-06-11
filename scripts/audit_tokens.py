#!/usr/bin/env python3
"""
Token-extraction audit: run each framework over the SAME small paper set and print
per-node token usage side by side.

Same pinned model + same input means all four frameworks should report roughly similar
tokens. A large outlier usually means that runner's token extraction needs attention —
each framework surfaces usage in its own shape, and this audit checks our mapping of
each one into TokenUsage.

    uv run python scripts/audit_tokens.py                 # all four frameworks
    uv run python scripts/audit_tokens.py langgraph adk   # a subset
"""

import asyncio
import importlib
import json
import logging
import os
import sys
import time
import warnings
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

logging.getLogger("ldclient.util").setLevel(logging.ERROR)
warnings.filterwarnings("ignore")

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


async def audit(framework, ai_client, papers):
    runner = importlib.import_module(RUNNERS[framework])
    per_node = {}
    agent_keys = {}  # id(agent) -> node key, captured at build time

    # invoke() doesn't receive the node key, so capture it via build_agent: the dispatcher
    # builds each node's agent with its key, and we map the agent object back to it. (Labeling
    # by completion order would mislabel the concurrent analyzer/detector branches.)
    orig_build = runner.build_agent
    def capturing_build(node_key, config, instructions):
        agent = orig_build(node_key, config, instructions)
        agent_keys[id(agent)] = node_key
        return agent

    orig_invoke = runner.invoke
    async def capturing_invoke(agent, input_text, tracker):
        out, usage = await orig_invoke(agent, input_text, tracker)
        per_node[agent_keys.get(id(agent), f"node{len(per_node) + 1}")] = usage
        return out, usage

    rid = f"audit-{framework}"
    context = Context.create_multi(
        Context.builder(rid).kind("user").build(),
        Context.builder(rid).kind("request").build(),
    )
    result = await execute_graph(
        ai_client, GRAPH_KEY, context, build_paper_prompt(papers),
        capturing_build, capturing_invoke,
    )

    rows, t_in, t_out = [], 0, 0
    for node, u in per_node.items():
        i, o = (u.input or 0) if u else 0, (u.output or 0) if u else 0
        t_in += i
        t_out += o
        rows.append(f"      {node:<8} in={i:>7,}  out={o:>7,}  ({'MISSING' if u is None else 'ok'})")
    print(f"\n  {framework}  (path: {' > '.join(result['path'])})")
    print("\n".join(rows))
    print(f"      {'TOTAL':<8} in={t_in:>7,}  out={t_out:>7,}  all={t_in + t_out:,}")
    return framework, t_in + t_out


async def main():
    frameworks = sys.argv[1:] or list(RUNNERS)
    frameworks = [f if f in RUNNERS else None for f in frameworks]
    if None in frameworks:
        print(f"Unknown framework. Choose from {list(RUNNERS)}")
        return

    ldclient.set_config(Config(os.environ["LD_SDK_KEY"]))
    for _ in range(12):
        if ldclient.get().is_initialized():
            break
        time.sleep(0.5)
    ai_client = LDAIClient(ldclient.get())

    papers = load_papers(2)
    print(f"Auditing token extraction: {len(frameworks)} frameworks x same {len(papers)}-paper input")
    totals = {}
    for fw in frameworks:
        try:
            name, total = await audit(fw, ai_client, papers)
            totals[name] = total
        except Exception as e:
            print(f"\n  {fw}  FAILED: {str(e)[:150]}")

    if len(totals) > 1:
        lo, hi = min(totals.values()), max(totals.values())
        print("\n=== verdict ===")
        for fw, t in sorted(totals.items(), key=lambda kv: kv[1]):
            print(f"  {fw:<14} {t:>8,} tokens")
        spread = (hi - lo) / lo * 100 if lo else float("inf")
        print(f"  spread: {spread:.0f}%  ({'OK — comparable' if spread < 25 else 'BAD — extraction differs, fix the outliers'})")

    ldclient.get().flush()
    ldclient.get().close()


if __name__ == "__main__":
    asyncio.run(main())
