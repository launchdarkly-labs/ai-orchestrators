#!/usr/bin/env python3
"""
Author the handoff-routing prompts into the OpenAI node-config variations (Experiment C).

Prompts live in LaunchDarkly, never in the runner. The OpenAI handoff arm walks the linear
chain (research-gap-graph-linear): intake → approach-analyzer → contradiction-detector →
gap-synthesizer. Handoff orchestration only traverses when each non-terminal agent's prompt
tells it to hand off — so this script APPENDS a routing addendum to each OpenAI variation
(`{config}-gpt`) that the openai-agents / openai-agents-native arms serve:

  * non-terminal nodes: "do your task in full, then call transfer_to_<next> to hand off";
  * terminal node (gap-synthesizer): "synthesize everything into the final report; do not
    hand off" — AND the gap-quality judge is (re)attached so the report is scored.

The addendum is appended to whatever instructions the variation already has (created by
setup_native_routing from the base prompt), so the domain prompt is preserved. Idempotent —
re-running detects the marker and skips.

    python scripts/launchdarkly/bootstrap_openai_handoff_prompts.py [--dry-run]

Run AFTER setup_native_routing.py (which creates the -gpt variations and first attaches the
judge) and bootstrap_linear_graph.py.
"""

import os
import re
import sys
from pathlib import Path

import requests
from dotenv import load_dotenv

project_root = Path(__file__).parent.parent.parent
load_dotenv(project_root / ".env")

SUFFIX = "gpt"                      # the OpenAI variation suffix (setup_native_routing NATIVE_MODELS)
JUDGE_KEY = "gap-quality-judge"
MARKER = "<!-- handoff-routing -->"  # idempotency sentinel appended with the addendum

# Linear chain: config -> (next config key, human name for the prompt). Terminal has no next.
CHAIN = {
    "intake": ("approach-analyzer", "the approach analyzer"),
    "approach-analyzer": ("contradiction-detector", "the contradiction detector"),
    "contradiction-detector": ("gap-synthesizer", "the gap synthesizer"),
    "gap-synthesizer": (None, None),
}


def _transfer_tool(next_key):
    # The Agents SDK generates the handoff tool name from the agent name (our node key),
    # sanitizing non-identifier chars to underscores: approach-analyzer -> transfer_to_approach_analyzer.
    return "transfer_to_" + re.sub(r"[^a-zA-Z0-9_]", "_", next_key)


def _addendum(config_key):
    next_key, next_name = CHAIN[config_key]
    if next_key is None:
        return (
            f"\n\n{MARKER}\n"
            "You are the FINAL step in this sequential pipeline. The conversation above contains "
            "the source papers and every prior agent's analysis. Synthesize all of it into your "
            "complete final report now, as your response. Do not hand off to anyone. Do NOT ask "
            "for clarification or whether anything else is needed — write the report."
        )
    tool = _transfer_tool(next_key)
    return (
        f"\n\n{MARKER}\n"
        "You are one step in a sequential multi-agent pipeline. Complete the task above in full, "
        f"then hand off by calling the `{tool}` tool to pass control to {next_name}. Put your "
        f"COMPLETE analysis in the `findings` argument of `{tool}` — calling `{tool}` with your "
        "findings IS how you finish your turn and deliver your work to the next agent. Do not end "
        f"your turn without calling `{tool}`, and do not write the final report yourself. Do NOT "
        "ask for clarification or whether anything else is needed — complete your task and hand off."
    )


class VariationEditor:
    def __init__(self, api_key, project, dry_run=False):
        self.base = "https://app.launchdarkly.com"
        self.project = project
        self.dry_run = dry_run
        self.headers = {"Authorization": api_key, "LD-API-Version": "beta",
                        "Content-Type": "application/json"}

    def get_variation(self, config_key, var_key):
        r = requests.get(f"{self.base}/api/v2/projects/{self.project}/ai-configs/{config_key}",
                         headers=self.headers, timeout=30)
        if r.status_code != 200:
            return None
        for v in r.json().get("variations", []):
            if v.get("key") == var_key:
                return v
        return None

    def patch_variation(self, config_key, var_key, body):
        url = f"{self.base}/api/v2/projects/{self.project}/ai-configs/{config_key}/variations/{var_key}"
        r = requests.patch(url, headers=self.headers, json=body, timeout=30)
        return r.status_code == 200, r

    def run(self):
        any_err = False
        for config_key in CHAIN:
            var_key = f"{config_key}-{SUFFIX}"
            v = self.get_variation(config_key, var_key)
            if v is None:
                print(f"  ✗ variation '{var_key}' not found on '{config_key}' "
                      f"(run setup_native_routing.py first)")
                any_err = True
                continue

            instructions = v.get("instructions") or ""
            is_terminal = CHAIN[config_key][0] is None
            body = {}

            # Re-appliable: strip any prior addendum (everything from the marker on) and
            # rebuild, so re-running updates the routing text instead of duplicating it.
            base_instr = instructions.split(MARKER)[0].rstrip()
            new_instr = base_instr + _addendum(config_key)
            if new_instr != instructions:
                body["instructions"] = new_instr
                # Preserve model binding on the PATCH (pricing/routing keys on modelConfigKey).
                if v.get("modelConfigKey"):
                    body["modelConfigKey"] = v["modelConfigKey"]
                if v.get("model"):
                    body["model"] = v["model"]
            else:
                print(f"  ℹ️  '{var_key}' routing prompt already current")

            # Ensure the judge is attached to the TERMINAL variation so its report is scored.
            if is_terminal:
                judges = (v.get("judgeConfiguration") or {}).get("judges") or []
                has_judge = any(j.get("judgeConfigKey") == JUDGE_KEY for j in judges)
                if has_judge:
                    print(f"  ℹ️  judge already attached to '{var_key}'")
                else:
                    body["judgeConfiguration"] = {"judges": [{"judgeConfigKey": JUDGE_KEY, "samplingRate": 1.0}]}
                    if v.get("modelConfigKey"):
                        body["modelConfigKey"] = v["modelConfigKey"]
                    if v.get("model"):
                        body["model"] = v["model"]

            if not body:
                continue
            if self.dry_run:
                acts = []
                if "instructions" in body:
                    acts.append("append handoff addendum")
                if "judgeConfiguration" in body:
                    acts.append(f"attach judge '{JUDGE_KEY}'")
                print(f"  [dry-run] {var_key}: " + " + ".join(acts))
                continue
            ok, r = self.patch_variation(config_key, var_key, body)
            acts = [a for a, k in (("prompt", "instructions"), ("judge", "judgeConfiguration")) if k in body]
            print(f"  {'✓' if ok else '✗'} {var_key}: {' + '.join(acts)}"
                  + ("" if ok else f"  ({r.status_code} {r.text[:160]})"))
            any_err = any_err or not ok
        return not any_err


def main():
    dry_run = "--dry-run" in sys.argv
    api_key = os.environ.get("LD_API_KEY")
    project = os.environ.get("LD_PROJECT_KEY", "graph-experiments")
    if not api_key:
        sys.exit("LD_API_KEY is not set (needed for the REST API)")
    print(f"OpenAI handoff prompts + judge → project '{project}', variations '*-{SUFFIX}'")
    ok = VariationEditor(api_key, project, dry_run).run()
    if dry_run:
        print("✨ Dry run — no changes made.")
        return
    if not ok:
        sys.exit("✗ One or more variations failed to update")
    print("\n✓ Done. Smoke it: python orchestrators/verify_run.py openai-agents-native")


if __name__ == "__main__":
    main()
