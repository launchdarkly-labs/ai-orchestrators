#!/usr/bin/env python3
"""
Bootstrap the `graph-key` flag — LD-native topology routing.

LD agent graphs are single-shape (no variations, no targeting), so a graph can't self-select
by context. Instead, a SEPARATE ordinary string flag picks which graph key the harness reads.
Evaluated on the same context as the running `orchestrator` experiment — serving one flag
while experimenting on another is exactly what LD does, and it keeps the routing decision in
LaunchDarkly (editable in the UI) instead of a hardcoded dict in code.

    graph-key (string flag), targeted on the `orchestrator` context attribute:
      orchestrator == openai-agents-native  ->  "research-gap-graph-linear"  (handoff chain)
      fallthrough (everyone else)            ->  "research-gap-graph"         (structural diamond)

The harness evaluates this flag AFTER the orchestrator value is set on the context, so the
targeting resolves the right graph for each arm — 4 arms on the diamond, the handoff arm on
the linear chain, all inside one experiment on the orchestrator flag.

    python scripts/launchdarkly/bootstrap_graph_key_flag.py [--dry-run]

Idempotent — re-running syncs the variations/rule/fallthrough.
"""

import os
import sys

import requests
from dotenv import load_dotenv
from pathlib import Path

load_dotenv(Path(__file__).parent.parent.parent / ".env")

FLAG_KEY = "graph-key"
DIAMOND = "research-gap-graph"
LINEAR = "research-gap-graph-linear"
LINEAR_ARMS = ["openai-agents-native"]  # arms routed to the linear (handoff) graph


class GraphKeyFlag:
    def __init__(self, api_key, project, dry_run=False):
        self.base = "https://app.launchdarkly.com"
        self.project = project
        self.dry_run = dry_run
        self.headers = {"Authorization": api_key, "Content-Type": "application/json"}
        self.sp_headers = dict(self.headers,
                               **{"Content-Type": "application/json; domain-model=launchdarkly.semanticpatch"})

    def get_flag(self):
        r = requests.get(f"{self.base}/api/v2/flags/{self.project}/{FLAG_KEY}", headers=self.headers, timeout=30)
        return r.json() if r.status_code == 200 else None

    def create_flag(self):
        payload = {
            "key": FLAG_KEY,
            "name": "Graph key (topology router)",
            "kind": "multivariate",
            "temporary": True,
            "tags": ["experiment", "orchestrator", "graph-routing"],
            "variations": [
                {"value": DIAMOND, "name": "Diamond (structural)"},
                {"value": LINEAR, "name": "Linear (handoff chain)"},
            ],
        }
        r = requests.post(f"{self.base}/api/v2/flags/{self.project}", headers=self.headers, json=payload, timeout=30)
        return r.status_code in (200, 201), r

    def _var_ids(self, flag):
        # map variation value -> _id (semantic-patch rules/fallthrough reference variation _id)
        out = {}
        for v in flag.get("variations", []):
            out[v.get("value")] = v.get("_id")
        return out

    def set_targeting(self, flag):
        ids = self._var_ids(flag)
        linear_id, diamond_id = ids.get(LINEAR), ids.get(DIAMOND)
        if not (linear_id and diamond_id):
            print(f"    ✗ could not resolve variation ids: {ids}")
            return False
        instructions = [
            {"kind": "turnFlagOn"},
            {"kind": "replaceRules", "rules": [
                {"variationId": linear_id,
                 "clauses": [{"contextKind": "user", "attribute": "orchestrator",
                              "op": "in", "values": LINEAR_ARMS, "negate": False}]}
            ]},
            {"kind": "updateFallthroughVariationOrRollout", "variationId": diamond_id},
        ]
        r = requests.patch(f"{self.base}/api/v2/flags/{self.project}/{FLAG_KEY}", headers=self.sp_headers,
                           json={"environmentKey": "production", "instructions": instructions}, timeout=30)
        return r.status_code == 200, r

    def run(self):
        print(f"graph-key flag → project '{self.project}'")
        print(f"  orchestrator in {LINEAR_ARMS} -> {LINEAR}")
        print(f"  fallthrough                    -> {DIAMOND}")
        if self.dry_run:
            print("✨ Dry run — no changes made.")
            return True
        flag = self.get_flag()
        if flag is None:
            ok, r = self.create_flag()
            print(f"  {'✓ created' if ok else '✗ create failed'} flag '{FLAG_KEY}'"
                  + ("" if ok else f": {r.status_code} {r.text[:160]}"))
            if not ok:
                return False
            flag = self.get_flag()
        else:
            print(f"  ℹ️  flag '{FLAG_KEY}' already exists — syncing targeting")
        ok, r = self.set_targeting(flag)
        print(f"  {'✓ targeting on + rule + fallthrough' if ok else '✗ targeting failed'}"
              + ("" if ok else f": {r.status_code} {r.text[:200]}"))
        return ok


def main():
    dry_run = "--dry-run" in sys.argv
    api_key = os.environ.get("LD_API_KEY")
    project = os.environ.get("LD_PROJECT_KEY", "graph-experiments")
    if not api_key:
        sys.exit("LD_API_KEY is not set (needed for the REST API)")
    ok = GraphKeyFlag(api_key, project, dry_run).run()
    if not dry_run and not ok:
        sys.exit("✗ Failed to set up the graph-key flag")
    if not dry_run:
        print("\n✓ Done. The harness reads graph-key per request (see run_experiment.py).")


if __name__ == "__main__":
    main()
