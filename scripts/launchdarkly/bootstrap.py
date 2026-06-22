#!/usr/bin/env python3
"""
Graph Experiment - LaunchDarkly Bootstrap Script
Creates the agent graph, node AI configs, tools, the orchestrator flag, and the
gap-quality judge from a manifest. Assumes the project already exists.
"""

import sys
import os
import yaml
import requests
import time
import json
from pathlib import Path
from dotenv import load_dotenv


class AgentGraphBootstrap:
    def __init__(self, api_key, base_url="https://app.launchdarkly.com"):
        self.api_key = api_key
        self.base_url = base_url
        self.headers = {
            "Authorization": api_key,
            "LD-API-Version": "beta",
            "Content-Type": "application/json"
        }

    def verify_project(self, project_key):
        """Confirm the (preconfigured) project exists.

        The bootstrap does not create projects — the user supplies the key of a project
        they have already set up (via LD_PROJECT_KEY or the manifest's project.key).
        We check it here so a bad key fails fast with a clear message instead of producing
        confusing 404s from every downstream config/graph/flag call.
        """
        check_url = f"{self.base_url}/api/v2/projects/{project_key}"
        response = requests.get(check_url, headers=self.headers, timeout=30)
        if response.status_code == 200:
            print(f"  ℹ️  Project '{project_key}' found")
            return True
        print(f"    ✗ Project '{project_key}' not found: {response.status_code} {response.text}")
        return False

    def create_tool(self, project_key, tool_data):
        """Create tool for AI agent function calling"""
        tool_key = tool_data["key"]

        # First check if tool already exists
        check_url = f"{self.base_url}/api/v2/projects/{project_key}/ai-tools/{tool_key}"
        check_response = requests.get(check_url, headers=self.headers, timeout=30)

        if check_response.status_code == 200:
            print(f"    ℹ️  Tool '{tool_key}' already exists")
            return check_response.json()

        # Try to create the tool
        url = f"{self.base_url}/api/v2/projects/{project_key}/ai-tools"

        payload = {
            "key": tool_data["key"],
            "name": tool_data["name"],
            "description": tool_data["description"],
            "type": tool_data.get("type", "function"),
            "schema": tool_data.get("schema", {})
        }

        print(f"  Creating tool '{tool_key}'...")
        response = requests.post(url, headers=self.headers, json=payload, timeout=30)

        if response.status_code in [200, 201]:
            print(f"    ✓ Tool '{tool_key}' created")
            time.sleep(0.5)
            return response.json()
        elif response.status_code == 409:
            print(f"    ℹ️  Tool '{tool_key}' already exists")
            return None
        else:
            print(f"    ✗ Failed to create tool: {response.text}")
            print(f"    Status Code: {response.status_code}")
            return None

    def create_ai_config(self, project_key, ai_config_data):
        """Create AI config WITHOUT inline variation (provider/model stored at config level)"""
        config_key = ai_config_data["key"]
        config_name = ai_config_data["name"]

        check_url = f"{self.base_url}/api/v2/projects/{project_key}/ai-configs/{config_key}"
        response = requests.get(check_url, headers=self.headers, timeout=30)

        if response.status_code == 200:
            print(f"  ℹ️  AI Config '{config_key}' already exists")
            return True
        else:
            print(f"  Creating AI Config '{config_key}'...")
            create_url = f"{self.base_url}/api/v2/projects/{project_key}/ai-configs"

            # Get provider and modelName from config level (NOT from variation).
            # The manifest sets these per node; the defaults match the pinned model.
            provider = ai_config_data.get("provider", "anthropic")
            model_id = ai_config_data.get("modelId", "claude-sonnet-4-5")

            # Create AI Config WITHOUT inline variation
            # This ensures provider/modelName are stored at config level where UI reads them
            payload = {
                "key": config_key,
                "name": config_name,
                "mode": "agent",
                "provider": {"name": provider},  # Use exact provider name from manifest
                "modelName": model_id
            }

            print(f"    Provider: {provider}")
            print(f"    Model: {model_id}")

            create_response = requests.post(create_url, headers=self.headers, json=payload, timeout=30)

            if create_response.status_code in [200, 201]:
                print(f"    ✓ AI Config '{config_key}' created with provider/model at config level")
                time.sleep(1)  # Give LD time to process
                return True
            else:
                print(f"    ✗ Failed to create AI Config: {create_response.text}")
                return False

    def create_or_update_variation(self, project_key, config_key, variation_data, manifest):
        """Create or update AI agent config variation with proper model configuration"""
        variation_key = variation_data["key"]

        # Get model configuration from variation
        model_config = variation_data.get("modelConfig", {})
        model_id = model_config.get("modelId", "")
        provider = model_config.get("provider", "")
        custom_params = variation_data.get("customParameters", {})

        # Create variation payload with proper model structure
        payload = {
            "key": variation_data["key"],
            "name": variation_data.get("name", variation_data["key"]),
            "instructions": variation_data.get("instructions", ""),
            "tools": [{"key": tool, "version": 1} for tool in variation_data.get("tools", [])]
        }

        # Add model configuration in the format LaunchDarkly expects
        if model_id:
            # Look up the correct model config key from manifest's modelConfigKeys mapping
            # This ensures we use the exact key that LaunchDarkly expects (e.g., "Anthropic.claude-sonnet-4-5")
            lookup_key = f"{provider}.{model_id}"
            model_config_keys = manifest.get("modelConfigKeys", {})

            # Try to find the correct key in the mapping
            if lookup_key in model_config_keys:
                model_config_key = model_config_keys[lookup_key]
                print(f"    Using mapped model config key: {model_config_key}")
            else:
                # Fallback: generate key if not in mapping (shouldn't happen with proper manifest)
                model_config_key = f"{provider}.{model_id.replace('/', '-')}"
                print(f"    WARNING: No mapping found for {lookup_key}, using generated: {model_config_key}")

            # The SDK reads model tuning params (temperature, max_tokens, …) from
            # model.parameters at runtime, so merge the manifest's customParameters there.
            model_parameters = dict(model_config.get("parameters", {}))
            model_parameters.update(custom_params)
            payload["model"] = {
                "modelName": model_id,
                "parameters": model_parameters,
                "custom": {}
            }
            payload["modelConfigKey"] = model_config_key

        print(f"  Processing variation '{variation_key}'...")
        print(f"    Model: {model_id}, Provider: {provider}")
        print(f"    Instructions: {len(variation_data.get('instructions', ''))} chars")
        print(f"    Tools: {len(variation_data.get('tools', []))} tools")

        # Try creating first
        create_url = f"{self.base_url}/api/v2/projects/{project_key}/ai-configs/{config_key}/variations"
        response = requests.post(create_url, headers=self.headers, json=payload, timeout=30)

        if response.status_code in [200, 201]:
            print(f"    ✓ Variation '{variation_key}' created")
            time.sleep(0.5)
            return response.json()
        elif response.status_code == 409:
            # Already exists — update via a plain (merge) PATCH. `instructions` is a
            # string field on the variation, not a semantic-patch op list.
            print(f"    ℹ️  Variation exists, updating...")
            patch_url = f"{self.base_url}/api/v2/projects/{project_key}/ai-configs/{config_key}/variations/{variation_key}"
            patch_body = {
                "instructions": variation_data.get("instructions", ""),
                "tools": [{"key": tool, "version": 1} for tool in variation_data.get("tools", [])],
            }
            if "model" in payload:
                # Re-apply model + parameters so a re-run propagates customParameters too.
                patch_body["model"] = payload["model"]
            if "modelConfigKey" in payload:
                # Keep the model-config linkage current — pricing (Cost in AI Insights)
                # is keyed on modelConfigKey.
                patch_body["modelConfigKey"] = payload["modelConfigKey"]
            patch_response = requests.patch(patch_url, headers=self.headers, json=patch_body, timeout=30)

            if patch_response.status_code == 200:
                print(f"    ✓ Variation '{variation_key}' updated")
                return patch_response.json()
            else:
                print(f"    ⚠️  Could not update: {patch_response.status_code} {patch_response.text}")
                return None
        else:
            print(f"    ✗ Failed: {response.text}")
            return None

    # Keep old method name for compatibility
    def create_variation(self, project_key, config_key, variation_data, manifest):
        return self.create_or_update_variation(project_key, config_key, variation_data, manifest)

    def get_targeting_variation_map(self, project_key, config_key):
        """Get targeting variation IDs (different from AI config variation IDs)"""
        url = f"{self.base_url}/api/v2/projects/{project_key}/ai-configs/{config_key}/targeting"
        response = requests.get(url, headers=self.headers, timeout=30)
        
        if response.status_code == 200:
            targeting_data = response.json()
            # Get variations from the targeting endpoint
            targeting_variations = targeting_data.get("variations", [])
            
            variation_map = {}
            for variation in targeting_variations:
                # Extract variation key from the value._ldMeta.variationKey field
                variation_value = variation.get("value", {})
                ld_meta = variation_value.get("_ldMeta", {})
                variation_key = ld_meta.get("variationKey")
                
                if variation_key:
                    variation_map[variation_key] = variation["_id"]
                    
            return variation_map
        else:
            print(f"    ✗ Failed to fetch targeting data: {response.text}")
            return {}

    def enable_config(self, project_key, config_key, default_variation_key):
        """Serve a real variation via fallthrough so the config is enabled.

        Required for agent-graph nodes: the SDK reports a graph as disabled unless
        ALL of its node configs are enabled. New AI configs have targeting on but
        their fallthrough points at the disabled stub variation (index 0), so we
        just repoint the fallthrough at the real variation.
        """
        var_map = self.get_targeting_variation_map(project_key, config_key)
        vid = var_map.get(default_variation_key)
        if not vid:
            print(f"    ✗ Cannot enable '{config_key}': variation '{default_variation_key}' not found")
            return None

        url = f"{self.base_url}/api/v2/projects/{project_key}/ai-configs/{config_key}/targeting"
        payload = {
            "environmentKey": "production",
            "instructions": [
                {"kind": "updateFallthroughVariationOrRollout", "variationId": vid},
            ],
        }
        response = requests.patch(url, headers=self.headers, json=payload, timeout=30)
        if response.status_code == 200:
            print(f"    ✓ Config '{config_key}' enabled (default variation: {default_variation_key})")
            time.sleep(0.5)
            return response.json()
        print(f"    ✗ Failed to enable config '{config_key}': {response.status_code} {response.text}")
        return None

    def create_flag(self, project_key, flag_data):
        """Create a feature flag (e.g. the multivariate `orchestrator` routing flag).

        The orchestrator flag is the experiment's treatment: the app evaluates it to
        route to a framework runner, and an experiment attaches to it to split traffic
        and attribute metrics per variation. Flags are created with targeting OFF.
        """
        flag_key = flag_data["key"]
        check = requests.get(
            f"{self.base_url}/api/v2/flags/{project_key}/{flag_key}",
            headers=self.headers, timeout=30,
        )
        if check.status_code == 200:
            print(f"  ℹ️  Flag '{flag_key}' already exists")
            return check.json()

        payload = {
            "key": flag_key,
            "name": flag_data.get("name", flag_key),
            "kind": flag_data.get("kind", "multivariate"),
            "temporary": flag_data.get("temporary", True),
            "tags": flag_data.get("tags", []),
            "variations": [
                {"value": v["value"], "name": v.get("name", v["value"])}
                for v in flag_data.get("variations", [])
            ],
        }
        print(f"  Creating flag '{flag_key}' ({len(payload['variations'])} variations)...")
        r = requests.post(
            f"{self.base_url}/api/v2/flags/{project_key}",
            headers=self.headers, json=payload, timeout=30,
        )
        if r.status_code in (200, 201):
            vals = [v["value"] for v in payload["variations"]]
            print(f"    ✓ Flag '{flag_key}' created: {vals}")
            print(f"    ℹ️  Flag is OFF by default — the experiment controls the split when started")
            time.sleep(0.5)
            return r.json()
        print(f"    ✗ Failed to create flag: {r.status_code} {r.text}")
        return None

    def create_agent_graph(self, project_key, graph_data):
        """Create an agent graph: root config + edges (handoffs), then enable it.

        Edges define the topology that the runtime dispatcher walks. Routing is
        read from edge.handoff at runtime — not hardcoded in the runners.
        """
        graph_key = graph_data["key"]
        root = graph_data["root"]
        base = f"{self.base_url}/api/v2/projects/{project_key}/agent-graphs"

        # 1. Create the graph with its root config (idempotent)
        check = requests.get(f"{base}/{graph_key}", headers=self.headers, timeout=30)
        if check.status_code == 200:
            print(f"  ℹ️  Agent graph '{graph_key}' already exists")
        else:
            payload = {
                "key": graph_key,
                "name": graph_data.get("name", graph_key),
                "rootConfigKey": root,
            }
            print(f"  Creating agent graph '{graph_key}' (root: {root})...")
            r = requests.post(base, headers=self.headers, json=payload, timeout=30)
            if r.status_code in (200, 201):
                print(f"    ✓ Agent graph '{graph_key}' created")
                time.sleep(1)
            else:
                print(f"    ✗ Failed to create agent graph: {r.status_code} {r.text}")
                return False

        # 2. Add edges (handoffs)
        edges = [
            {
                "key": e["key"],
                "sourceConfig": e["source"],
                "targetConfig": e["target"],
                "handoff": e.get("handoff", {}),
            }
            for e in graph_data.get("edges", [])
        ]
        if edges:
            r = requests.patch(
                f"{base}/{graph_key}",
                headers=self.headers,
                json={"rootConfigKey": root, "edges": edges},
                timeout=30,
            )
            if r.status_code in (200, 201):
                print(f"    ✓ Added {len(edges)} edge(s): " +
                      ", ".join(f"{e['source']}→{e['target']}" for e in graph_data.get("edges", [])))
                time.sleep(0.5)
            else:
                print(f"    ✗ Failed to add edges: {r.status_code} {r.text}")
                return False

        # 3. Enable the graph
        r = requests.patch(
            f"{base}/{graph_key}",
            headers=self.headers,
            json={"instructions": [{"kind": "turnTargetingOn"}]},
            timeout=30,
        )
        if r.status_code in (200, 201):
            print(f"    ✓ Agent graph '{graph_key}' enabled")
        else:
            print(f"    ⚠️  Could not enable graph (enable in UI): {r.status_code} {r.text}")
        # Link to the graph in the UI.
        print(
            f"    🔗 View: {self.base_url}/projects/{project_key}/ai/graphs/{graph_key}"
            f"?env=production&selected-env=production"
        )
        return True

    def create_judge_config(self, project_key, judge_data, manifest):
        """Create a judge-mode AI config + its rubric variation, then enable it.

        A judge config generates its own evaluation metric (evaluationMetricKey, e.g.
        $ld:ai:judge:gap-quality) — no separate custom metric. The harness invokes the
        judge via the SDK and records the score with tracker.track_judge_result. Created
        with the fallthrough at the disabled stub, so we repoint it at the rubric variation.
        """
        judge_key = judge_data["key"]
        base = f"{self.base_url}/api/v2/projects/{project_key}/ai-configs"

        # 1. Create the judge-mode config (idempotent)
        created = False
        check = requests.get(f"{base}/{judge_key}", headers=self.headers, timeout=30)
        if check.status_code == 200:
            print(f"  ℹ️  Judge config '{judge_key}' already exists")
        else:
            created = True
            payload = {
                "key": judge_key,
                "name": judge_data.get("name", judge_key),
                "mode": "judge",
                "tags": ["ai", "judge"],
                "evaluationMetricKey": judge_data["evaluationMetricKey"],
                "isInverted": judge_data.get("isInverted", False),
            }
            print(f"  Creating judge config '{judge_key}' (metric: {judge_data['evaluationMetricKey']})...")
            r = requests.post(base, headers=self.headers, json=payload, timeout=30)
            if r.status_code in (200, 201):
                print(f"    ✓ Judge config '{judge_key}' created")
                time.sleep(1)
            else:
                print(f"    ✗ Failed to create judge config: {r.status_code} {r.text}")
                return False

        # 2. Create the rubric variation (the evaluation prompt + judge model)
        provider = judge_data.get("provider", "anthropic")
        model_id = judge_data.get("modelId", "claude-sonnet-4-5")
        model_config_key = manifest.get("modelConfigKeys", {}).get(
            f"{provider}.{model_id}", f"{provider.title()}.{model_id}"
        )
        var_payload = {
            "key": "default",
            "name": "Default",
            "messages": [{"role": "system", "content": judge_data.get("instructions", "")}],
            "modelConfigKey": model_config_key,
            "model": {"modelName": model_id, "parameters": {"temperature": 0.0}},
        }
        r = requests.post(f"{base}/{judge_key}/variations", headers=self.headers, json=var_payload, timeout=30)
        if r.status_code in (200, 201):
            print(f"    ✓ Judge rubric variation 'default' created")
            time.sleep(0.5)
        elif r.status_code == 409:
            # Already exists — PATCH the rubric so manifest edits propagate on re-runs.
            patch = requests.patch(
                f"{base}/{judge_key}/variations/default",
                headers=self.headers,
                json={"messages": var_payload["messages"], "model": var_payload["model"]},
                timeout=30,
            )
            if patch.status_code == 200:
                print(f"    ✓ Judge rubric variation 'default' updated from manifest")
            else:
                print(f"    ⚠️  Judge variation exists but update failed: {patch.status_code} {patch.text}")
        else:
            print(f"    ✗ Failed to create judge variation: {r.status_code} {r.text}")
            return False

        # 3. Enable: repoint the fallthrough at the rubric variation — but ONLY on first
        # creation. On re-runs, leave the fallthrough alone so an operator's repoint to a
        # custom rubric variation (e.g. scripts/launchdarkly/update_judge.py) isn't silently
        # reverted; the 409-PATCH above still syncs the 'default' rubric from the manifest.
        if created:
            self.enable_config(project_key, judge_key, "default")
        else:
            print(f"    ℹ️  Judge fallthrough left as-is (re-run preserves any custom variation)")

        # 4. Attach the judge to the node(s) whose output it scores. Attaching registers
        #    the evaluation metric so it's selectable in the experiment.
        for target in judge_data.get("attach", []):
            self.attach_judge(
                project_key, target["config"], target["variation"],
                judge_key, target.get("samplingRate", 1.0),
            )
        return True

    def attach_judge(self, project_key, config_key, variation_key, judge_key, sampling_rate=1.0):
        """Attach a judge to a config variation (registers its evaluation metric).

        Sends the variation's modelConfigKey/model along with judgeConfiguration so the
        variation's model-config linkage — which pricing (Cost in AI Insights) is keyed
        on — stays intact through the update.
        """
        url = f"{self.base_url}/api/v2/projects/{project_key}/ai-configs/{config_key}/variations/{variation_key}"
        body = {"judgeConfiguration": {"judges": [{"judgeConfigKey": judge_key, "samplingRate": sampling_rate}]}}
        current = requests.get(url, headers=self.headers, timeout=30)
        if current.status_code == 200:
            cur = current.json()
            if isinstance(cur, list):
                cur = cur[0] if cur else {}
            if cur.get("modelConfigKey"):
                body["modelConfigKey"] = cur["modelConfigKey"]
            if cur.get("model"):
                body["model"] = cur["model"]
        else:
            print(f"    ⚠️  Could not read {config_key}/{variation_key} before judge attach "
                  f"({current.status_code}); attaching judge only. If Cost stops reporting for "
                  f"this config, run scripts/launchdarkly/fix_pricing.py")
        r = requests.patch(url, headers=self.headers, json=body, timeout=30)
        if r.status_code == 200:
            print(f"    ✓ Judge '{judge_key}' attached to {config_key}/{variation_key} ({int(sampling_rate*100)}% sampling)")
            return r.json()
        print(f"    ✗ Failed to attach judge: {r.status_code} {r.text}")
        return None


def main():
    load_dotenv()

    print("╔═══════════════════════════════════════════════════════╗")
    print("║  AI Agent Orchestrator - LaunchDarkly Bootstrap       ║")
    print("╚═══════════════════════════════════════════════════════╝")
    print()
    print("This script creates, in your existing project (set via LD_PROJECT_KEY):")
    print("  • Tools + AI agent node configs from the manifest")
    print("  • The agent graph (nodes + handoff edges)")
    print("  • The orchestrator routing flag + the gap-quality judge")
    print()

    api_key = os.getenv("LD_API_KEY")
    if not api_key:
        print("❌ LD_API_KEY environment variable not set")
        print("   Get your API key from: https://app.launchdarkly.com/settings/authorization")
        print("   Then add it to your .env file")
        return

    # Manifest: a path passed on the command line, else the default in config/.
    config_dir = Path(__file__).parent.parent.parent / "config"
    manifest_path = Path(sys.argv[1]) if len(sys.argv) > 1 else config_dir / "graph_experiment_manifest.yaml"
    if not manifest_path.exists():
        print(f"❌ Manifest not found: {manifest_path}")
        return
    print(f"Using manifest: {manifest_path}")
    print()

    with open(manifest_path) as f:
        manifest = yaml.safe_load(f)

    # LD_PROJECT_KEY (if set) overrides the manifest's project key, letting a user
    # point the bootstrap at a different project without editing the manifest.
    project_key = os.getenv("LD_PROJECT_KEY") or manifest["project"]["key"]
    bootstrap = AgentGraphBootstrap(api_key)

    print(f"📦 Project: {project_key}")
    print(f"🌍 Environment: production")
    print()

    # Step 0: Verify the supplied (preconfigured) project exists. The bootstrap does not
    # create projects — set up the project first via the LaunchDarkly MCP server, a skill,
    # or the UI, then pass its key via LD_PROJECT_KEY or the manifest's project.key.
    print(f"📁 Using project '{project_key}'...")
    if not bootstrap.verify_project(project_key):
        print()
        print(f"❌ Project '{project_key}' not found. Set it up first (LaunchDarkly MCP /")
        print("   skill / UI), then set LD_PROJECT_KEY to its key. Exiting.")
        return
    print()

    # Step 1: Create tools
    print("🛠️  Creating paper analysis tools...")
    for tool in manifest["project"]["tool"]:
        bootstrap.create_tool(project_key, tool)
    print()

    # Step 2: Create AI configs + variations, then enable each on its default variation
    # (the agent graph reports disabled unless every node config is enabled).
    print("🤖 Creating AI agent configs...")
    for ai_config in manifest["project"]["ai_config"]:
        config_key = ai_config["key"]

        if not bootstrap.create_ai_config(project_key, ai_config):
            print(f"❌ Failed to create AI Config '{config_key}'. Continuing...")
            continue

        print(f"🎨 Creating variations for '{config_key}'...")
        for variation in ai_config["variations"]:
            bootstrap.create_variation(project_key, config_key, variation, manifest)

        if ai_config.get("variations"):
            print(f"🟢 Enabling '{config_key}'...")
            bootstrap.enable_config(project_key, config_key, ai_config["variations"][0]["key"])
        print()

    # Step 3: Create the agent graph (nodes + edges + enable), if the manifest defines one
    graph_def = manifest["project"].get("agent_graph")
    if graph_def:
        print("🕸️  Creating agent graph (topology + handoff edges)...")
        bootstrap.create_agent_graph(project_key, graph_def)
        print()

    # Step 4: Create experiment flags (e.g. the orchestrator routing flag)
    for flag in manifest["project"].get("flag", []):
        print("🚩 Creating experiment flag...")
        bootstrap.create_flag(project_key, flag)
        print()

    # Step 5: Create the custom judge config (the guardrail/secondary metric)
    judge_def = manifest["project"].get("judge")
    if judge_def:
        print("⚖️  Creating custom judge config...")
        bootstrap.create_judge_config(project_key, judge_def, manifest)
        print()

    print("✨ Bootstrap complete!")
    print()
    graph_key = (manifest["project"].get("agent_graph") or {}).get("key", "")
    print("📝 Next steps:")
    print(
        f"   1. View the agent graph: {bootstrap.base_url}/projects/{project_key}"
        f"/ai/graphs/{graph_key}?env=production&selected-env=production"
    )
    print(f"   2. Make sure your .env has:")
    print(f"      LD_PROJECT_KEY={project_key}")
    print(f"      LD_SDK_KEY=your-server-sdk-key")
    print("   3. Create the experiment in the UI: treatment = the 'orchestrator' flag,")
    print("      primary metric = end-to-end graph latency, secondaries = the gap-quality")
    print("      judge (guardrail) + total tokens (cost), then start an iteration.")
    print("   4. Drive traffic: python scripts/run_experiment.py")
    print()
    print("🔄 To make changes:")
    print("   • Edit the configs / graph / flag in the LaunchDarkly UI (instructions, models, edges).")
    print("   • This manifest is for initial setup only.")


if __name__ == "__main__":
    main()