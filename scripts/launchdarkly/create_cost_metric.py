#!/usr/bin/env python3
"""
Create the custom dollar-cost metric for the orchestrator experiment.

LaunchDarkly has no built-in dollar-cost metric, so the harness computes each run's GRAPH cost
(node tokens × the served model's catalog price) and tracks it as this numeric metric — a fair
cross-model ranking (raw token counts aren't, since per-token prices differ by model). Latency
does NOT need a custom metric: the experiment is request-randomized, so it uses the BUILT-IN
Graph latency (request-unit) directly.

Randomization unit = "request" (the natural per-run unit; matches the built-in latency/duration
metrics). Set the gap-quality judge to request-unit too so cost + latency + quality share one
request-randomized experiment.

    python scripts/launchdarkly/create_cost_metric.py

Key must match COST_METRIC in scripts/run_experiment.py.
"""

import os
import sys

import requests
from dotenv import load_dotenv

METRIC_KEY = "ai-graph-cost-usd"          # must match COST_METRIC in scripts/run_experiment.py


def main():
    load_dotenv()
    api_key = os.getenv("LD_API_KEY")
    project = os.getenv("LD_PROJECT_KEY", "graph-experiments")
    if not api_key:
        print("❌ LD_API_KEY not set (see .env)")
        return
    base = "https://app.launchdarkly.com"
    headers = {"Authorization": api_key, "LD-API-Version": "beta", "Content-Type": "application/json"}

    if requests.get(f"{base}/api/v2/metrics/{project}/{METRIC_KEY}", headers=headers, timeout=30).status_code == 200:
        print(f"ℹ️  Metric '{METRIC_KEY}' already exists")
        return
    payload = {
        "key": METRIC_KEY,
        "name": "AI graph cost (USD)",
        "description": "Per-run graph cost in USD (node input/output tokens × the served model's "
                       "catalog price). Emitted by scripts/run_experiment.py. Lower is better.",
        "kind": "custom",
        "isNumeric": True,
        "unit": "USD",
        "eventKey": METRIC_KEY,                    # the ld.track() event name
        "successCriteria": "LowerThanBaseline",    # cheaper wins
        "analysisType": "mean",
        "unitAggregationType": "average",
        "randomizationUnits": ["request"],         # natural per-run unit; matches built-in latency
        # Count only units that emitted a cost event — matches LD's autogen AI metrics. WITHOUT
        # this (default {disabled: False, value: 0}) LD imputes 0 for every exposed unit with no
        # event, inflating sample size to the exposure count AND deflating the mean.
        "eventDefault": {"disabled": True},
        "tags": ["ai", "cost", "experiment"],
    }
    r = requests.post(f"{base}/api/v2/metrics/{project}", headers=headers, json=payload, timeout=30)
    if r.status_code in (200, 201):
        print(f"✓ Created metric '{METRIC_KEY}' (USD, numeric, request-unit, lower-is-better)")
        print("  Primary = AI graph cost (USD); guardrail = Gap-quality; secondary = built-in Graph latency.")
    else:
        print(f"✗ Failed to create '{METRIC_KEY}': {r.status_code} {r.text[:300]}")
        sys.exit(1)


if __name__ == "__main__":
    main()
