#!/usr/bin/env python3
"""
Toggle the model each node variation serves — the ONLY difference between the two experiments.

Both shared experiments run the SAME graphs, orchestrators, routing (the `orchestrator` +
`graph-key` flags), prompts, and judge. They differ in exactly one field: the model on each
node variation. This script flips that field IN PLACE, preserving `instructions` (including the
handoff prompts on the `*-gpt` variations), `tools`, and the attached judge — so switching
experiments never re-applies prompts or re-runs routing.

    --native   each provider variation on its own model, langgraph-managed's on Haiku:
                 *-gpt      -> OpenAI.gpt-5.4-mini
                 *-gemini   -> Gemini.gemini-3-flash-preview
                 *-bedrock  -> Bedrock.amazon.nova-2-lite-v1:0
                 *-anthropic-> Anthropic.claude-haiku-4-5-20251001   (its native model)
    --pin      every variation on ONE model (default Haiku), isolating the orchestrator

Why not `setup_native_routing.py --pin`? That repoints targeting at the base `*-anthropic`
variation, so the handoff arms lose their `*-gpt` prompts and bail. This patches the model
only and leaves targeting/prompts untouched — the prompt-preserving toggle the two experiments
need.

    python scripts/launchdarkly/set_node_models.py --native   [--dry-run]
    python scripts/launchdarkly/set_node_models.py --pin       [--dry-run]   # Haiku on every arm

Idempotent — re-running re-asserts the same model on each variation.
"""

import os
import sys
import time
from pathlib import Path

import requests
import yaml
from dotenv import load_dotenv

load_dotenv(Path(__file__).parent.parent.parent / ".env", override=True)

# suffix -> (modelConfigKey, modelName) for the native experiment. Keys verified against the
# LD model catalog (GET .../ai-configs/model-configs); a missing key means no cost pricing.
NATIVE = {
    "gpt": ("OpenAI.gpt-5.4-mini", "gpt-5.4-mini"),
    "gemini": ("Gemini.gemini-3-flash-preview", "gemini-3-flash-preview"),
    "bedrock": ("Bedrock.amazon.nova-2-lite-v1:0", "amazon.nova-2-lite-v1:0"),
    "anthropic": ("Anthropic.claude-haiku-4-5-20251001", "claude-haiku-4-5-20251001"),
}
HAIKU = ("Anthropic.claude-haiku-4-5-20251001", "claude-haiku-4-5-20251001")
SUFFIXES = tuple(NATIVE)

BASE = "https://app.launchdarkly.com/api/v2"


def target_model(suffix, native):
    """The (modelConfigKey, modelName) a variation should serve in the chosen experiment."""
    return NATIVE[suffix] if native else HAIKU


def main():
    argv = sys.argv[1:]
    dry = "--dry-run" in argv
    native = "--native" in argv
    pin = "--pin" in argv
    if native == pin:  # need exactly one mode
        sys.exit("Choose exactly one: --native (per-provider models) or --pin (Haiku everywhere)")

    api_key = os.environ.get("LD_API_KEY")
    if not api_key:
        sys.exit("LD_API_KEY is not set (needed for the REST API)")
    proj = os.environ.get("LD_PROJECT_KEY", "graph-experiments")
    H = {"Authorization": api_key, "LD-API-Version": "beta", "Content-Type": "application/json"}

    manifest = yaml.safe_load(open(Path(__file__).parent.parent.parent / "config" / "graph_experiment_manifest.yaml"))
    configs = [c["key"] for c in manifest["project"]["ai_config"]]

    mode = "NATIVE (per-provider models)" if native else "PIN (Haiku on every arm)"
    print(f"Set node models -> {mode}   project '{proj}'" + ("   [DRY RUN]" if dry else ""))

    changed = 0
    for ck in configs:
        r = requests.get(f"{BASE}/projects/{proj}/ai-configs/{ck}", headers=H, timeout=30)
        if r.status_code != 200:
            print(f"  ✗ {ck}: read failed {r.status_code}")
            continue
        for v in r.json().get("variations", []):
            vk = v.get("key", "")
            suffix = next((s for s in SUFFIXES if vk.endswith("-" + s)), None)
            if not suffix:
                continue
            mck, mname = target_model(suffix, native)
            cur = v.get("modelConfigKey") or ""
            # Preserve the variation's existing generation params (max_tokens, etc.); change
            # only the model. Sending just model + modelConfigKey on the PATCH leaves
            # instructions/tools/judge untouched.
            params = dict((v.get("model") or {}).get("parameters") or {})
            if cur == mck:
                continue  # already on the target model
            if dry:
                print(f"  [dry-run] {vk:34} {cur or '(none)'} -> {mck}")
                changed += 1
                continue
            patch = {"model": {"modelName": mname, "parameters": params, "custom": {}},
                     "modelConfigKey": mck}
            pr = requests.patch(f"{BASE}/projects/{proj}/ai-configs/{ck}/variations/{vk}",
                                headers=H, json=patch, timeout=30)
            if pr.status_code == 400 and "modelConfigKey" in patch:
                # Bedrock/preview keys occasionally 400 on catalog validation; the model still
                # runs from modelName — retry without the catalog key (cost just won't price).
                patch.pop("modelConfigKey")
                pr = requests.patch(f"{BASE}/projects/{proj}/ai-configs/{ck}/variations/{vk}",
                                    headers=H, json=patch, timeout=30)
            # LD's management API rate-limits bursts (429); back off and retry a few times.
            for attempt in range(5):
                if pr.status_code != 429:
                    break
                time.sleep(2 * (attempt + 1))
                pr = requests.patch(f"{BASE}/projects/{proj}/ai-configs/{ck}/variations/{vk}",
                                    headers=H, json=patch, timeout=30)
            ok = pr.status_code == 200
            print(f"  {'✓' if ok else '✗'} {vk:34} {cur or '(none)'} -> {mck}"
                  + ("" if ok else f"  [{pr.status_code} {pr.text[:120]}]"))
            changed += ok
            time.sleep(0.5)  # gentle pacing so the whole sweep stays under the rate limit

    print(f"\n{'Would change' if dry else 'Changed'} {changed} variation(s).")
    if not dry:
        print("Next: smoke the arms (verify_run.py c), then START A FRESH LD ITERATION before "
              "driving traffic — otherwise this experiment's data mixes with the previous model's.")


if __name__ == "__main__":
    main()
