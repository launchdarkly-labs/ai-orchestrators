#!/usr/bin/env python3
"""
Repair utility: restore the modelConfigKey on any AI config variation that's missing it.

Pricing (the Cost column in AI Insights) is keyed on the variation's modelConfigKey. If a
config shows $0 cost despite real token traffic, its variation has likely lost that
linkage; this walks every config in the project and restores it from the manifest's
modelConfigKeys mapping.

    uv run python scripts/launchdarkly/fix_pricing.py
"""

import os
import sys
from pathlib import Path

import requests
import yaml
from dotenv import load_dotenv

project_root = Path(__file__).parent.parent.parent
load_dotenv(project_root / ".env")


def main():
    H = {"Authorization": os.environ["LD_API_KEY"], "LD-API-Version": "beta",
         "Content-Type": "application/json"}
    proj = os.environ.get("LD_PROJECT_KEY")
    if not proj:
        sys.exit("LD_PROJECT_KEY is not set in .env — refusing to run against /projects/None/.")
    manifest = yaml.safe_load(open(project_root / "config" / "graph_experiment_manifest.yaml"))
    mck = manifest.get("modelConfigKeys", {})
    base = f"https://app.launchdarkly.com/api/v2/projects/{proj}/ai-configs"

    # Page through all configs (a single capped GET silently misses configs past the limit).
    configs, offset, limit = [], 0, 50
    while True:
        r = requests.get(f"{base}?limit={limit}&offset={offset}", headers=H, timeout=30)
        if r.status_code != 200:
            sys.exit(f"Failed to list configs: {r.status_code} {r.text[:200]}")
        batch = r.json().get("items", [])
        configs.extend(batch)
        if len(batch) < limit:
            break
        offset += limit
    fixed = ok = 0
    for cfg in configs:
        key = cfg["key"]
        detail = requests.get(f"{base}/{key}", headers=H, timeout=30).json()
        for v in detail.get("variations", []):
            vkey = v.get("key")
            model_name = (v.get("model") or {}).get("modelName") or (v.get("model") or {}).get("name")
            if v.get("modelConfigKey"):
                ok += 1
                continue
            if not model_name:
                print(f"  ? {key}/{vkey}: no model name — skipped")
                continue
            # Restore from the manifest mapping (provider.model -> key), fallback Anthropic.<model>
            mc = next((val for k, val in mck.items() if k.endswith(f".{model_name}")), f"Anthropic.{model_name}")
            r = requests.patch(f"{base}/{key}/variations/{vkey}", headers=H,
                               json={"modelConfigKey": mc}, timeout=30)
            if r.status_code == 200:
                print(f"  ✓ {key}/{vkey}: restored modelConfigKey={mc}")
                fixed += 1
            else:
                print(f"  ✗ {key}/{vkey}: {r.status_code} {r.text[:150]}")
    print(f"\n{fixed} variation(s) repaired, {ok} already OK. "
          f"Cost in AI Insights prices from the next events onward.")


if __name__ == "__main__":
    main()
