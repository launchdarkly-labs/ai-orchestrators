#!/usr/bin/env python3
"""
Judge lab — iterate the gap-quality rubric cheaply until it DIFFERENTIATES.

The production judge is invoked through LaunchDarkly, so tuning its rubric there would mean a
full (expensive) graph run per iteration. Instead:

  generate : run the graph for a few (framework, topic) pairs and SAVE each report to disk.
             Expensive — do it once. Reports differ by model, so they're real material to judge.
  score    : re-judge the saved reports with the RUBRIC below (JUDGE_MODEL, called directly),
             print a framework×topic score table + the spread. Cheap — iterate the RUBRIC freely.

    python scripts/judge_lab.py generate [--topics N] [--papers-per-context K] [--concurrency C]
    python scripts/judge_lab.py score

Once a rubric spreads scores in line with what you'd rank by eye, paste RUBRIC into
config/graph_experiment_manifest.yaml (judge.instructions) and re-run bootstrap to push it live.
"""

import argparse
import asyncio
import importlib
import json
import os
import re
import sys
import warnings
from pathlib import Path
from statistics import mean, pstdev

project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))
from dotenv import load_dotenv
load_dotenv(project_root / ".env")
warnings.filterwarnings("ignore")

LAB_DIR = project_root / "results" / "judge_lab"
GRAPH_KEY = "research-gap-graph"
FRAMEWORKS = {
    "langgraph": "orchestrators.langgraph_runner",
    "strands": "orchestrators.strands_runner",
    "openai-agents": "orchestrators.openai_agents_runner",
    "google-adk": "orchestrators.google_adk_runner",
}

# ─── candidate rubric — EDIT FREELY, this is the whole point of the lab ───────────────────────
JUDGE_MODEL = "claude-sonnet-4-5"   # strong judge for reliable discrimination (swap as you like)
# Candidate C: combined — graded quality (rewards grounded depth) × faithfulness floor (penalizes
# fabrication). Fixes the deduction rubric's brevity bias AND the graded rubric's ceiling saturation.
RUBRIC = """You are an expert research methodologist scoring a RESEARCH GAP ANALYSIS report produced
from a fixed set of papers. A good report is COMPREHENSIVE AND GROUNDED: it surfaces specific,
evidence-based gaps and actionable directions across ALL the papers, without fabricating or over-claiming.
Reward grounded depth; penalize both shallowness and fabrication.

Step 1 — grounding defects (count each instance, cite it):
  H = claims/methods/findings/datasets attributed to the papers but not present, or citations that
      don't support the claim they're attached to.
  E = gaps or recommended directions drawn from general knowledge rather than grounded in cited
      evidence from the papers.
  faithfulness = max(0, 1 - 0.08*H - 0.05*E)

Step 2 — quality dimensions, each 0-4. Be STRICT: 4 is reserved for genuinely exceptional work;
most solid work is 2-3. Cite evidence for each score.
  COVERAGE: engages the ACTUAL papers thoroughly (all of them), not a subset.
  GAP_SPECIFICITY: gaps are concrete and tied to specific cited evidence, not generic/obvious.
  ACTIONABILITY: directions give concrete methods/datasets AND feasible first steps.
  SYNTHESIS: real cross-paper insight (contradictions, consensus, trends), not mere enumeration.
  quality = (COVERAGE + GAP_SPECIFICITY + ACTIONABILITY + SYNTHESIS) / 16

Step 3 — final = round(faithfulness * quality, 2)

List H and E with instances; the four 0-4 scores each with a one-line justification; the arithmetic;
then a FINAL line formatted EXACTLY as: SCORE: <number between 0.00 and 1.00>"""
# ──────────────────────────────────────────────────────────────────────────────────────────────


def _load_papers(fname, cap):
    path = project_root / "data" / fname
    data = json.load(open(path))
    papers = data if isinstance(data, list) else data.get("papers") or data.get("items") or []
    return papers[:cap] if cap is not None else papers


async def generate(args):
    import time
    import ldclient
    from ldclient import Context
    from ldclient.config import Config
    from ldai.client import LDAIClient
    from shared.prompt import build_paper_prompt
    from orchestrators.dispatcher import execute_graph

    topics = sorted(p.name for p in (project_root / "data").glob("*_papers.json")
                    if not p.name.startswith("combined"))[:args.topics]
    if not topics:
        sys.exit("No topic files in data/")
    LAB_DIR.mkdir(parents=True, exist_ok=True)

    ldclient.set_config(Config(os.environ["LD_SDK_KEY"], send_events=False))  # lab: no LD metrics
    for _ in range(20):
        if ldclient.get().is_initialized():
            break
        time.sleep(0.5)
    ai_client = LDAIClient(ldclient.get())
    sem = asyncio.Semaphore(max(1, args.concurrency))

    async def one(topic, fw):
        async with sem:
            papers = _load_papers(topic, args.papers_per_context)
            rid = f"lab-{topic}-{fw}"
            ctx = Context.create_multi(
                Context.builder(rid).kind("user").set("orchestrator", fw).build(),
                Context.builder(rid).kind("request").set("orchestrator", fw).build())
            runner = importlib.import_module(FRAMEWORKS[fw])
            try:
                res = await execute_graph(ai_client, GRAPH_KEY, ctx, build_paper_prompt(papers),
                                          runner.build_agent, runner.invoke,
                                          require_context_attr="orchestrator")
            except Exception as e:
                print(f"  ✗ {topic}/{fw}: {str(e)[:120]}")
                return
            stem = topic.removesuffix("_papers.json").removesuffix("_")
            out = LAB_DIR / f"{stem}__{fw}.json"
            json.dump({"topic": topic, "framework": fw, "papers": papers, "report": res["output"]},
                      open(out, "w"))
            print(f"  ✓ saved {out.name}  ({len((res['output'] or '')):,} chars)")

    print(f"Generating {len(topics)} topic(s) × {len(FRAMEWORKS)} frameworks -> {LAB_DIR}/")
    await asyncio.gather(*(one(t, fw) for t in topics for fw in FRAMEWORKS))
    ldclient.get().flush(); ldclient.get().close()


def score(args):
    import anthropic
    from shared.prompt import build_paper_prompt

    files = sorted(LAB_DIR.glob("*.json"))
    if not files:
        sys.exit(f"No saved reports in {LAB_DIR} — run `generate` first.")
    client = anthropic.Anthropic()
    print(f"Scoring {len(files)} report(s) with {JUDGE_MODEL}\n")

    rows = {}  # topic -> {framework: score}
    for f in files:
        d = json.load(open(f))
        prompt = (f"=== SOURCE PAPERS ===\n{build_paper_prompt(d['papers'])}\n\n"
                  f"=== REPORT ===\n{d['report']}")
        resp = client.messages.create(
            model=JUDGE_MODEL, max_tokens=2000, system=RUBRIC,
            messages=[{"role": "user", "content": prompt}])
        text = "".join(b.text for b in resp.content if getattr(b, "type", "") == "text")
        m = re.search(r"SCORE:\s*([0-9]*\.?[0-9]+)", text)
        s = float(m.group(1)) if m else None
        rows.setdefault(d["topic"], {})[d["framework"]] = s
        print(f"  {d['topic']:<32} {d['framework']:<14} -> {s}")

    fws = list(FRAMEWORKS)
    print("\n=== score table (topic × framework) ===")
    print(f"  {'topic':<28} " + " ".join(f"{fw:>13}" for fw in fws))
    all_scores = []
    for topic, sc in sorted(rows.items()):
        cells = " ".join(f"{(sc.get(fw) if sc.get(fw) is not None else '—'):>13}" for fw in fws)
        print(f"  {topic:<28} {cells}")
        all_scores += [v for v in sc.values() if v is not None]
    if all_scores:
        print(f"\n  spread: min={min(all_scores):.2f} max={max(all_scores):.2f} "
              f"range={max(all_scores) - min(all_scores):.2f} stdev={pstdev(all_scores):.3f} "
              f"(n={len(all_scores)}) — wider range/stdev = more differentiation")


def main():
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="mode", required=True)
    g = sub.add_parser("generate")
    g.add_argument("--topics", type=int, default=1, help="how many topic files to use (default 1)")
    g.add_argument("--papers-per-context", type=int, default=20,
                   help="cap papers/run for a faster/cheaper lab (default 20; None-ish=full via 0<)")
    g.add_argument("--concurrency", type=int, default=2)
    sub.add_parser("score")
    args = ap.parse_args()
    if args.mode == "generate":
        asyncio.run(generate(args))
    else:
        score(args)


if __name__ == "__main__":
    main()
