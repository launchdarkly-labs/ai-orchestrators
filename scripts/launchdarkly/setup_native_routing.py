#!/usr/bin/env python3
"""
Experiment B — native-model routing (DEVREL-741).

Experiment A pins claude-sonnet-4-5 on every node and swaps only the FRAMEWORK via the
`orchestrator` flag. Experiment B instead lets each framework run its provider's native
model, so the bake-off compares "each orchestrator at its best" rather than a held-constant
model. This script adds — on top of what bootstrap.py already created — one per-framework
model variation on EVERY graph node config, plus targeting rules that route by the
`orchestrator` context attribute:

    langgraph      -> anthropic / claude-sonnet-4-5   (the base variation, via fallthrough)
    openai-agents  -> openai    / gpt-4o
    google-adk     -> google    / gemini-2.5-pro
    strands        -> bedrock   / <claude on bedrock>

HOW the provider is set: the runners read `config.provider.name` at runtime, and the LD SDK
DERIVES provider from the variation's `modelConfigKey` (its catalog entry) — a variation-level
`provider` field is ignored by the API. So each variation just needs a valid catalog
modelConfigKey (e.g. `Gemini.gemini-2.5-pro`) and the right provider follows automatically;
without one, provider comes back empty and the runner misroutes. Find valid keys with:
  GET /api/v2/projects/{proj}/ai-configs/model-configs

Run AFTER bootstrap.py. Idempotent — re-running syncs variations and skips existing rules.

    python scripts/launchdarkly/setup_native_routing.py [manifest.yaml] [--dry-run]

⚠️  CONFIRM the model IDs in NATIVE_MODELS below exist in your LaunchDarkly model catalog
    and provider accounts before running. gpt-4o / gemini-2.5-pro are safe defaults; bump
    to your current flagship if desired. The Bedrock model id is account/region-specific —
    verify it against `aws bedrock list-inference-profiles`.
"""

import os
import sys
import time
from pathlib import Path

import requests
import yaml
from dotenv import load_dotenv

# The `orchestrator` flag value -> the native model that framework should run. langgraph is
# intentionally absent: it keeps the base claude variation, served by the fallthrough.
#   provider        -> written to the variation so the runner routes correctly (see module docstring)
#   modelId         -> config.model.name at runtime (what each runner hands to its SDK)
#   modelConfigKey  -> {Provider}.{model}; links LD pricing/catalog (cost in AI Insights)
#   maxOutput       -> clamp for the synthesizer's max_tokens so it never exceeds the model's
#                      output ceiling (a truncated/errored report would confound the experiment)
#   modelConfigKey  -> a VALID catalog key ({Provider}.{model}); the SDK derives provider from
#                      it (an explicit variation `provider` field is ignored) AND overrides
#                      model.name with the catalog's name. Verify each key exists via
#                      GET .../ai-configs/model-configs, or provider comes back empty.
#   modelId         -> informational (the SDK serves the catalog's model name at runtime).
#   maxOutput       -> clamp for the synthesizer's max_tokens (per the model's output ceiling).
#
# Experiment B = each orchestrator at its provider's cheapest RECENT model (a low-cost demo
# config; swap the modelConfigKeys below for flagships — e.g. Anthropic.claude-sonnet-5,
# OpenAI.gpt-5.1, Gemini.gemini-3-pro-preview — for a production-grade comparison). langgraph +
# strands share Claude Haiku 4.5 (direct API vs Bedrock — a clean same-model framework/runtime
# signal); OpenAI and Google run their cheap recent tiers. All four get an explicit variation +
# rule; the config fallthrough stays on the pinned claude-sonnet-4-5 so Experiment A is untouched.
# Note: gemini-2.5-flash runs on the Gemini FREE tier (no billing needed for the demo).
NATIVE_MODELS = {
    "langgraph": {
        "modelId": "claude-haiku-4-5-20251001",
        "modelConfigKey": "Anthropic.claude-haiku-4-5-20251001",  # -> provider Anthropic (direct API)
        "suffix": "anthropic",
        "label": "Claude Haiku 4.5",
        "maxOutput": 32000,
    },
    "openai-agents": {
        "modelId": "gpt-5-mini",
        "modelConfigKey": "OpenAI.gpt-5-mini",           # -> provider OpenAI (native in the runner)
        "suffix": "gpt",
        "label": "GPT-5 mini",
        "maxOutput": 32000,
    },
    "google-adk": {
        "modelId": "gemini-2.5-flash",
        "modelConfigKey": "Gemini.gemini-2.5-flash",     # -> provider Gemini (runner: google/gemini native)
        "suffix": "gemini",
        "label": "Gemini 2.5 Flash",
        "maxOutput": 32000,
    },
    "strands": {
        # Bedrock on-demand needs the region-prefixed inference-profile id; the strands runner
        # prepends the geo (us./eu./apac.) to the catalog's bare name automatically.
        "modelId": "anthropic.claude-haiku-4-5-20251001",
        "modelConfigKey": "Bedrock.anthropic.claude-haiku-4-5-20251001-v1:0",  # -> provider Bedrock
        "suffix": "bedrock",
        "label": "Claude Haiku 4.5 (Bedrock)",
        "maxOutput": 32000,
    },
}


class NativeRoutingSetup:
    def __init__(self, api_key, base_url="https://app.launchdarkly.com", dry_run=False):
        self.base_url = base_url
        self.dry_run = dry_run
        self.headers = {
            "Authorization": api_key,
            "LD-API-Version": "beta",
            "Content-Type": "application/json",
        }

    # --- reads ---------------------------------------------------------------
    def get_config(self, project, config_key):
        r = requests.get(
            f"{self.base_url}/api/v2/projects/{project}/ai-configs/{config_key}",
            headers=self.headers, timeout=30,
        )
        return r.json() if r.status_code == 200 else None

    def get_targeting(self, project, config_key):
        r = requests.get(
            f"{self.base_url}/api/v2/projects/{project}/ai-configs/{config_key}/targeting",
            headers=self.headers, timeout=30,
        )
        return r.json() if r.status_code == 200 else None

    def _variation_index_and_ids(self, targeting):
        """Map variationKey -> (index, _id) from the targeting response (index is the basis
        for a rule's `variation` field; _id is needed for the fallthrough)."""
        out = {}
        for i, v in enumerate(targeting.get("variations", [])):
            vk = v.get("value", {}).get("_ldMeta", {}).get("variationKey")
            if vk:
                out[vk] = (i, v.get("_id"))
        return out

    # --- variation create/update --------------------------------------------
    def upsert_variation(self, project, config_key, base_var, spec):
        """Create (or update, on re-run) a per-framework variation that differs from the base
        ONLY in provider + model. Instructions/tools/other params are copied from the base so
        the experiment varies model, not prompt."""
        var_key = f"{config_key}-{spec['suffix']}"

        # Copy the base variation's generation params, then clamp max_tokens to the model's
        # output ceiling so the long synthesizer report doesn't error/truncate on this model.
        params = dict(base_var.get("model", {}).get("parameters") or {})
        if params.get("max_tokens"):
            params["max_tokens"] = min(int(params["max_tokens"]), spec["maxOutput"])

        payload = {
            "key": var_key,
            "name": f"{base_var.get('name', config_key)} — {spec['label']}",
            # instructions/tools held constant vs the base variation (agent mode)
            "instructions": base_var.get("instructions", ""),
            "tools": base_var.get("tools", []),
            # the variable that actually changes (provider is derived from modelConfigKey):
            "model": {"modelName": spec["modelId"], "parameters": params, "custom": {}},
            "modelConfigKey": spec["modelConfigKey"],
        }

        existing = {v.get("key") for v in (self.get_config(project, config_key) or {}).get("variations", [])}
        if self.dry_run:
            verb = "UPDATE" if var_key in existing else "CREATE"
            print(f"    [dry-run] {verb} variation '{var_key}' -> {spec['modelConfigKey']} "
                  f"(max_tokens={params.get('max_tokens', 'unset')})")
            return var_key

        vbase = f"{self.base_url}/api/v2/projects/{project}/ai-configs/{config_key}/variations"
        if var_key in existing:
            patch = {k: payload[k] for k in ("instructions", "tools", "model", "modelConfigKey")}
            r = requests.patch(f"{vbase}/{var_key}", headers=self.headers, json=patch, timeout=30)
            if r.status_code == 400 and patch.get("modelConfigKey"):
                # Same as create: an uncatalogued modelConfigKey (e.g. Bedrock/Gemini) 400s;
                # the model still runs from model.modelName, so re-sync without it.
                patch.pop("modelConfigKey")
                r = requests.patch(f"{vbase}/{var_key}", headers=self.headers, json=patch, timeout=30)
            ok = r.status_code == 200
            print(f"    {'✓ updated' if ok else '✗ update failed'} variation '{var_key}'"
                  + ("" if ok else f": {r.status_code} {r.text[:200]}"))
        else:
            r = requests.post(vbase, headers=self.headers, json=payload, timeout=30)
            if r.status_code == 400 and payload.get("modelConfigKey"):
                # modelConfigKey may not be in the catalog (common for Bedrock ids); the model
                # still runs from model.modelName — retry without it (cost just won't compute).
                print(f"    ⚠️  modelConfigKey '{payload['modelConfigKey']}' rejected; retrying without it")
                payload.pop("modelConfigKey")
                r = requests.post(vbase, headers=self.headers, json=payload, timeout=30)
            ok = r.status_code in (200, 201, 409)
            print(f"    {'✓ created' if ok else '✗ create failed'} variation '{var_key}' "
                  f"-> {spec['modelConfigKey']}"
                  + ("" if ok else f": {r.status_code} {r.text[:200]}"))
        time.sleep(0.3)
        return var_key

    def attach_judge(self, project, config_key, variation_key, judge_key, sampling_rate=1.0):
        """Attach the judge to a variation so its output is scored. Preserves the variation's
        modelConfigKey/model on the PATCH (cost/pricing is keyed on modelConfigKey). Without this,
        the per-framework synthesizer variations serve with NO judge and the experiment records no
        quality score — the judge in the manifest is attached only to the base claude variation."""
        if self.dry_run:
            print(f"    [dry-run] attach judge '{judge_key}' -> {config_key}/{variation_key}")
            return
        url = f"{self.base_url}/api/v2/projects/{project}/ai-configs/{config_key}/variations/{variation_key}"
        body = {"judgeConfiguration": {"judges": [{"judgeConfigKey": judge_key, "samplingRate": sampling_rate}]}}
        cur = requests.get(url, headers=self.headers, timeout=30)
        if cur.status_code == 200:
            c = cur.json()
            if isinstance(c, list):
                c = c[0] if c else {}
            if c.get("modelConfigKey"):
                body["modelConfigKey"] = c["modelConfigKey"]
            if c.get("model"):
                body["model"] = c["model"]
        r = requests.patch(url, headers=self.headers, json=body, timeout=30)
        ok = r.status_code == 200
        print(f"    {'✓ judge' if ok else '✗ judge failed'} '{judge_key}' -> {config_key}/{variation_key} "
              f"({int(sampling_rate * 100)}%)" + ("" if ok else f": {r.status_code} {r.text[:150]}"))
        time.sleep(0.3)

    # --- targeting -----------------------------------------------------------
    def _patch_targeting(self, project, config_key, instructions):
        """PATCH targeting with semantic-patch instruction(s). The instructions form REQUIRES
        the documented semantic-patch content-type — a plain application/json PATCH is accepted
        (200) but does NOT bind the rule's variation, silently leaving clause-only rules."""
        url = f"{self.base_url}/api/v2/projects/{project}/ai-configs/{config_key}/targeting"
        h = dict(self.headers)
        h["Content-Type"] = "application/json; domain-model=launchdarkly.semanticpatch"
        return requests.patch(url, headers=h,
                              json={"environmentKey": "production", "instructions": instructions}, timeout=30)

    def route(self, project, config_key, base_var_key):
        """Add orchestrator-attribute rules (idempotent) and point the fallthrough at the base
        (claude) variation so langgraph + any unmatched context serve Claude."""
        targeting = self.get_targeting(project, config_key)
        if not targeting:
            print(f"    ✗ Cannot read targeting for '{config_key}'")
            return
        idx = self._variation_index_and_ids(targeting)

        if self.dry_run:
            print(f"    [dry-run] replaceRules [] then re-add {len(NATIVE_MODELS)} orchestrator rules")
            for framework, spec in NATIVE_MODELS.items():
                print(f"    [dry-run]   orchestrator=={framework} -> {config_key}-{spec['suffix']}")
        else:
            # Rebuild from scratch so re-runs are idempotent AND heal any clause-only rules left
            # by an earlier plain-content-type PATCH. These node configs' rules are managed solely
            # by this script, so clearing all rules is safe.
            self._patch_targeting(project, config_key, [{"kind": "replaceRules", "rules": []}])
            for framework, spec in NATIVE_MODELS.items():
                var_key = f"{config_key}-{spec['suffix']}"
                if var_key not in idx:
                    print(f"    ✗ variation '{var_key}' not found in targeting; skipping rule")
                    continue
                instr = {
                    "kind": "addRule",
                    "clauses": [{"contextKind": "user", "attribute": "orchestrator",
                                 "op": "in", "values": [framework], "negate": False}],
                    # AI-config targeting addRule binds by variation UUID (not index), and REQUIRES
                    # the semantic-patch content-type (see _patch_targeting), else the variation is
                    # silently dropped and the rule serves nothing.
                    "variationId": idx[var_key][1],
                }
                r = self._patch_targeting(project, config_key, [instr])
                ok = r.status_code == 200
                print(f"    {'✓ routed' if ok else '✗ rule failed'} orchestrator=={framework} -> {var_key}"
                      + ("" if ok else f": {r.status_code} {r.text[:200]}"))
                time.sleep(0.3)

        # Fallthrough -> base claude variation (langgraph + default). Re-fetch for a fresh id.
        if self.dry_run:
            print(f"    [dry-run] fallthrough -> {base_var_key} (langgraph + default)")
            return
        idx = self._variation_index_and_ids(self.get_targeting(project, config_key))
        base_id = idx.get(base_var_key, (None, None))[1]
        if base_id:
            r = self._patch_targeting(project, config_key,
                                      [{"kind": "updateFallthroughVariationOrRollout", "variationId": base_id}])
            ok = r.status_code == 200
            print(f"    {'✓ fallthrough' if ok else '✗ fallthrough failed'} -> {base_var_key} (langgraph + default)"
                  + ("" if ok else f": {r.status_code} {r.text[:200]}"))


def main():
    load_dotenv()
    args = [a for a in sys.argv[1:] if not a.startswith("-")]
    dry_run = "--dry-run" in sys.argv

    api_key = os.getenv("LD_API_KEY")
    if not api_key:
        print("❌ LD_API_KEY not set (see .env)")
        return

    config_dir = Path(__file__).parent.parent.parent / "config"
    manifest_path = Path(args[0]) if args else config_dir / "graph_experiment_manifest.yaml"
    if not manifest_path.exists():
        print(f"❌ Manifest not found: {manifest_path}")
        return
    manifest = yaml.safe_load(open(manifest_path))
    project = os.getenv("LD_PROJECT_KEY") or manifest["project"]["key"]

    print("╔═══════════════════════════════════════════════════════╗")
    print("║  Experiment B — native-model routing per orchestrator ║")
    print("╚═══════════════════════════════════════════════════════╝")
    print(f"📦 Project: {project}   🌍 production" + ("   [DRY RUN — no writes]" if dry_run else ""))
    print("Routing (by `orchestrator` context attribute):")
    for fw, spec in NATIVE_MODELS.items():
        print(f"    {fw:<14} -> {spec['modelConfigKey']}")
    print("    (fallthrough    -> base claude-sonnet-4-5 variation — Experiment A / unmatched)")
    print()

    setup = NativeRoutingSetup(api_key, dry_run=dry_run)

    # The manifest attaches the judge only to the base variation; mirror it onto every per-framework
    # variation of the same config, or the experiment records NO quality score for the served arms.
    judge_def = manifest["project"].get("judge") or {}
    judge_key = judge_def.get("key")
    judge_targets = {t["config"]: t.get("samplingRate", 1.0) for t in judge_def.get("attach", [])}

    for ai_config in manifest["project"]["ai_config"]:
        config_key = ai_config["key"]
        base_variation = ai_config["variations"][0]
        base_var_key = base_variation["key"]
        # Read the live base variation so copied instructions/params match what's actually served
        # (the UI may have been edited since bootstrap). Fall back to the manifest if unreadable.
        live = setup.get_config(project, config_key)
        base_live = next((v for v in (live or {}).get("variations", []) if v.get("key") == base_var_key), None)
        if base_live:
            base_src = {
                "name": base_live.get("name", base_var_key),
                "instructions": base_live.get("instructions", ""),
                "tools": base_live.get("tools", []),
                "model": base_live.get("model", {}),
            }
        else:
            print(f"⚠️  '{config_key}': could not read live base variation '{base_var_key}'; using manifest values")
            base_src = {
                "name": base_variation.get("name", base_var_key),
                "instructions": base_variation.get("instructions", ""),
                "tools": [{"key": t, "version": 1} for t in base_variation.get("tools", [])],
                "model": {"parameters": base_variation.get("customParameters", {})},
            }

        print(f"🤖 {config_key} (base: {base_var_key})")
        created = [setup.upsert_variation(project, config_key, base_src, spec)
                   for spec in NATIVE_MODELS.values()]
        setup.route(project, config_key, base_var_key)
        # If the judge scores this config's output, attach it to each per-framework variation too.
        if judge_key and config_key in judge_targets:
            for vk in created:
                setup.attach_judge(project, config_key, vk, judge_key, judge_targets[config_key])
        print()

    print("✨ Done." if not dry_run else "✨ Dry run complete — no changes made.")
    print()
    print("Next:")
    print("  • Smoke test each route (no experiment needed):")
    print("      python orchestrators/verify_run.py all")
    print("  • run_experiment.py sets orchestrator=<resolved framework> on the context after the")
    print("    flag eval, so the randomized experiment routes each node to its native model.")
    print("  • For a fair cost/latency read, confirm each model id is priced in your LD model catalog.")


if __name__ == "__main__":
    main()
