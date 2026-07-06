#!/usr/bin/env python3
"""
Create the custom dollar-cost metric for the orchestrator experiment.

LaunchDarkly's auto-generated AI metrics are token/duration only — there is NO dollar-cost
metric, and the get-ai-config-metrics REST endpoint can't break cost down by variation. So the
harness computes each run's GRAPH cost (node tokens × the served model's catalog price) and
tracks it as this custom numeric metric, which IS selectable as an experiment primary and gives
a fair cross-model cost ranking (raw token counts aren't, since per-token prices differ by model).

Randomization unit = "user" to MATCH the gap-quality judge + token metrics (all user-unit), so a
single experiment can carry cost (primary) + judge (guardrail) + tokens together. (Graph latency
is request-unit and lives in a separate, request-randomized experiment.)

    python scripts/launchdarkly/create_cost_metric.py
"""

import os
import sys

import requests
from dotenv import load_dotenv

METRIC_KEY = "ai-graph-cost-usd"          # must match COST_METRIC in scripts/run_experiment.py
EVENT_KEY = "ai-graph-cost-usd"           # the ld.track() event name the harness emits


def main():
    load_dotenv()
    api_key = os.getenv("LD_API_KEY")
    project = os.getenv("LD_PROJECT_KEY", "graph-experiments")
    if not api_key:
        print("❌ LD_API_KEY not set (see .env)")
        return
    base = "https://app.launchdarkly.com"
    headers = {"Authorization": api_key, "LD-API-Version": "beta", "Content-Type": "application/json"}

    check = requests.get(f"{base}/api/v2/metrics/{project}/{METRIC_KEY}", headers=headers, timeout=30)
    if check.status_code == 200:
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
        "eventKey": EVENT_KEY,
        "successCriteria": "LowerThanBaseline",   # cheaper wins
        "analysisType": "mean",
        "unitAggregationType": "average",
        "randomizationUnits": ["user"],           # match the judge + token metrics
        "tags": ["ai", "cost", "experiment"],
    }
    r = requests.post(f"{base}/api/v2/metrics/{project}", headers=headers, json=payload, timeout=30)
    if r.status_code in (200, 201):
        print(f"✓ Created metric '{METRIC_KEY}' (numeric, USD, user-unit, lower-is-better)")
        print("  Select it as the experiment PRIMARY; keep the gap-quality judge as a guardrail.")
    else:
        print(f"✗ Failed to create metric: {r.status_code} {r.text[:400]}")
        sys.exit(1)


if __name__ == "__main__":
    main()
