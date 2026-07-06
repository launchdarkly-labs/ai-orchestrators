#!/usr/bin/env python3
"""
Read LaunchDarkly's own computed dollar cost from AI Insights (the get-ai-config-metrics REST
endpoint). This is the SDK-inaccessible data — the server-side AI SDK only writes events and
evaluates configs; aggregated cost/metrics are REST-only.

    GET /api/v2/projects/{projectKey}/ai-configs/{configKey}/metrics?from&to&env

IMPORTANT: this endpoint aggregates PER CONFIG across all variations — it cannot break cost down
by variation, so it gives total spend per node config (all frameworks combined), not per-arm cost.
For per-orchestrator cost, use the custom `ai-graph-cost-usd` metric in the experiment instead.

    python scripts/launchdarkly/fetch_costs.py [--hours 24] [--env production]
"""

import argparse
import os

import requests
import yaml
from pathlib import Path
from datetime import datetime, timezone, timedelta
from dotenv import load_dotenv


def main():
    load_dotenv()
    ap = argparse.ArgumentParser()
    ap.add_argument("--hours", type=int, default=24, help="look-back window in hours (default 24)")
    ap.add_argument("--env", default="production")
    args = ap.parse_args()

    api_key = os.getenv("LD_API_KEY")
    project = os.getenv("LD_PROJECT_KEY", "graph-experiments")
    if not api_key:
        print("❌ LD_API_KEY not set (see .env)")
        return
    base = "https://app.launchdarkly.com"
    headers = {"Authorization": api_key, "LD-API-Version": "beta"}

    # Milliseconds since epoch, without Date.now-style helpers that vary per run.
    now = datetime.now(timezone.utc)
    to_ms = int(now.timestamp() * 1000)
    from_ms = int((now - timedelta(hours=args.hours)).timestamp() * 1000)

    # The graph's node configs + the judge (from the manifest, so it tracks any renames).
    manifest = yaml.safe_load(open(Path(__file__).parent.parent.parent / "config/graph_experiment_manifest.yaml"))
    config_keys = [c["key"] for c in manifest["project"]["ai_config"]]
    if manifest["project"].get("judge"):
        config_keys.append(manifest["project"]["judge"]["key"])

    print(f"AI cost — project '{project}', env '{args.env}', last {args.hours}h")
    print("(per config, ALL variations combined — not per-orchestrator)\n")
    print(f"  {'config':<24} {'in $':>10} {'out $':>10} {'total $':>10} {'in tok':>10} {'out tok':>10}")
    grand = 0.0
    for ck in config_keys:
        r = requests.get(
            f"{base}/api/v2/projects/{project}/ai-configs/{ck}/metrics",
            headers=headers, params={"from": from_ms, "to": to_ms, "env": args.env}, timeout=30,
        )
        if r.status_code != 200:
            print(f"  {ck:<24} (no data / {r.status_code})")
            continue
        m = r.json()
        ic, oc = m.get("inputCost", 0) or 0, m.get("outputCost", 0) or 0
        it, ot = m.get("inputTokens", 0) or 0, m.get("outputTokens", 0) or 0
        grand += ic + oc
        print(f"  {ck:<24} {ic:>10.4f} {oc:>10.4f} {ic + oc:>10.4f} {it:>10} {ot:>10}")
    print(f"\n  {'TOTAL':<24} {'':>10} {'':>10} {grand:>10.4f}  USD")


if __name__ == "__main__":
    main()
