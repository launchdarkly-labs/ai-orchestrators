#!/usr/bin/env python3
"""
Medical Diagnosis Swarm - LaunchDarkly Bootstrap Script
Creates tools, AI agent configs, and variations programmatically.
"""

import sys
import os
import yaml
import requests
import time
import json
from pathlib import Path
from dotenv import load_dotenv


class MedicalDiagnosisBootstrap:
    def __init__(self, api_key, base_url="https://app.launchdarkly.com"):
        self.api_key = api_key
        self.base_url = base_url
        self.headers = {
            "Authorization": api_key,
            "LD-API-Version": "beta",
            "Content-Type": "application/json"
        }

    def create_segment(self, project_key, segment_data):
        """Create user segment for targeting using two-step process"""
        url = f"{self.base_url}/api/v2/segments/{project_key}/production"

        # Step 1: Create empty segment (LaunchDarkly ignores rules in POST)
        payload = {
            "key": segment_data["key"],
            "name": segment_data["key"].replace("-", " ").title()
        }

        response = requests.post(url, headers=self.headers, json=payload, timeout=30)

        if response.status_code in [200, 201]:
            print(f"    ✓ Empty segment '{segment_data['key']}' created")
            time.sleep(0.5)
            # Step 2: Add rules via semantic patch
            return self.add_segment_rules(project_key, segment_data)
        elif response.status_code == 409:
            print(f"    ℹ️  Segment '{segment_data['key']}' already exists, adding rules...")
            return self.add_segment_rules(project_key, segment_data)
        else:
            print(f"    ✗ Failed to create segment: {response.text}")
            return None

    def add_segment_rules(self, project_key, segment_data):
        """Add rules to existing segment using semantic patch"""
        segment_key = segment_data["key"]
        url = f"{self.base_url}/api/v2/segments/{project_key}/production/{segment_key}"

        # Build instructions for semantic patch
        instructions = []

        # Each segment should have one rule with multiple clauses
        if segment_data.get("rules"):
            clauses = []
            for clause in segment_data["rules"]:
                clauses.append({
                    "attribute": clause["attribute"],
                    "op": clause["op"],
                    "values": clause["values"],
                    "contextKind": clause["contextKind"],
                    "negate": clause["negate"]
                })

            instructions.append({
                "kind": "addRule",
                "clauses": clauses
            })

        payload = {
            "environmentKey": "production",
            "instructions": instructions
        }

        print(f"    Adding {len(instructions)} rules to segment '{segment_key}'")

        # Use semantic patch headers for segment rule updates
        patch_headers = self.headers.copy()
        patch_headers["Content-Type"] = "application/json; domain-model=launchdarkly.semanticpatch"

        response = requests.patch(url, headers=patch_headers, json=payload, timeout=30)

        if response.status_code == 200:
            result = response.json()
            rules_count = len(result.get("rules", []))
            print(f"    ✓ Rules added to segment '{segment_key}' (final count: {rules_count})")
            time.sleep(0.5)
            return result
        else:
            print(f"    ✗ Failed to add rules to segment '{segment_key}': {response.text}")
            return None

    def create_project(self, project_key, project_name):
        """Create LaunchDarkly project if it doesn't exist"""
        # Check if project exists
        check_url = f"{self.base_url}/api/v2/projects/{project_key}"
        check_response = requests.get(check_url, headers=self.headers, timeout=30)

        if check_response.status_code == 200:
            print(f"  ℹ️  Project '{project_key}' already exists")
            return True

        # Create project
        url = f"{self.base_url}/api/v2/projects"
        payload = {
            "key": project_key,
            "name": project_name,
            "environments": [
                {
                    "key": "production",
                    "name": "Production",
                    "color": "417505"
                }
            ]
        }

        print(f"  Creating project '{project_key}'...")
        response = requests.post(url, headers=self.headers, json=payload, timeout=30)

        if response.status_code in [200, 201]:
            print(f"    ✓ Project '{project_key}' created")
            time.sleep(1)
            return True
        else:
            print(f"    ✗ Failed to create project: {response.text}")
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

            # Get provider and modelName from config level (NOT from variation)
            provider = ai_config_data.get("provider", "Bedrock")
            model_id = ai_config_data.get("modelId", "anthropic.claude-3-5-sonnet-20241022-v2:0")

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

            payload["model"] = {
                "modelName": model_id,
                "parameters": model_config.get("parameters", {}),
                "custom": {}
            }
            payload["modelConfigKey"] = model_config_key

        # Add custom parameters if provided
        if custom_params:
            payload["parameters"] = custom_params

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
            # Already exists, try to update via patch
            print(f"    ℹ️  Variation exists, updating...")

            # For updates, we use semantic patch format
            patch_instructions = []

            # Update instructions
            patch_instructions.append({
                "kind": "updateInstructions",
                "value": variation_data.get("instructions", "")
            })

            # Update tools
            patch_instructions.append({
                "kind": "updateTools",
                "value": [{"key": tool, "version": 1} for tool in variation_data.get("tools", [])]
            })

            patch_url = f"{self.base_url}/api/v2/projects/{project_key}/ai-configs/{config_key}/variations/{variation_key}"
            patch_response = requests.patch(
                patch_url,
                headers=self.headers,
                json={"instructions": patch_instructions},
                timeout=30
            )

            if patch_response.status_code == 200:
                print(f"    ✓ Variation '{variation_key}' updated")
                return patch_response.json()
            else:
                print(f"    ⚠️  Could not update: {patch_response.text}")
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

    def update_targeting(self, project_key, config_key, targeting_data):
        """Update AI Config targeting rules using correct semantic patch format"""
        # First get the targeting variation IDs (these are different from AI config variation IDs)
        targeting_variation_map = self.get_targeting_variation_map(project_key, config_key)
        if not targeting_variation_map:
            print(f"    ✗ Could not get targeting variation map for '{config_key}'")
            return None
            
        print(f"    Available targeting variations: {list(targeting_variation_map.keys())}")
        
        url = f"{self.base_url}/api/v2/projects/{project_key}/ai-configs/{config_key}/targeting"
        
        instructions = []
        
        # Add targeting rules
        for rule in targeting_data.get("rules", []):
            variation_key = rule.get("variation")
            targeting_variation_id = targeting_variation_map.get(variation_key)

            if not targeting_variation_id:
                print(f"    ⚠  Variation '{variation_key}' not found in targeting variations")
                continue

            # Check if this is a segment-based rule or direct attribute rule
            if "segments" in rule:
                # Create add rule instruction for each segment (segment-based)
                for segment in rule.get("segments", []):
                    instruction = {
                        "kind": "addRule",
                        "clauses": [
                            {
                                "attribute": "segmentMatch",
                                "op": "segmentMatch",
                                "values": [segment],
                                "contextKind": "user"
                            }
                        ],
                        "variationId": targeting_variation_id
                    }
                    instructions.append(instruction)
                    print(f"    Added rule: segment '{segment}' -> variation '{variation_key}'")
            elif "clauses" in rule:
                # Handle manifest-style rules with clauses array
                rule_clauses = []
                for clause in rule.get("clauses", []):
                    rule_clause = {
                        "attribute": clause.get("attribute", "orchestrator"),
                        "op": clause.get("op", "in"),
                        "values": clause.get("values", []),
                        "contextKind": clause.get("contextKind", "user")
                    }
                    rule_clauses.append(rule_clause)

                instruction = {
                    "kind": "addRule",
                    "clauses": rule_clauses,
                    "variationId": targeting_variation_id
                }
                instructions.append(instruction)

                # Log what we're adding for debugging
                for clause in rule_clauses:
                    attr = clause['attribute']
                    values = clause['values']
                    print(f"    Added rule: {attr} in {values} -> variation '{variation_key}'")
            elif "orchestrator" in rule:
                # Legacy: Direct attribute matching for orchestrator (backward compatibility)
                instruction = {
                    "kind": "addRule",
                    "clauses": [
                        {
                            "attribute": "orchestrator",
                            "op": "in",
                            "values": [rule["orchestrator"]],
                            "contextKind": "user"
                        }
                    ],
                    "variationId": targeting_variation_id
                }
                instructions.append(instruction)
                print(f"    Added rule: orchestrator='{rule['orchestrator']}' -> variation '{variation_key}'")
        
        # Set fallthrough variation (required)
        fallthrough_variation_key = targeting_data.get("defaultVariation")
        fallthrough_variation_id = targeting_variation_map.get(fallthrough_variation_key)
        
        if fallthrough_variation_id:
            instructions.append({
                "kind": "updateFallthroughVariationOrRollout",
                "variationId": fallthrough_variation_id
            })
            print(f"    Set fallthrough to variation '{fallthrough_variation_key}'")
        else:
            print(f"    ⚠  Fallthrough variation '{fallthrough_variation_key}' not found")
            return None
        
        payload = {
            "environmentKey": "production",
            "instructions": instructions
        }
        
        print(f"  Updating targeting with {len(instructions)} instructions...")
        response = requests.patch(url, headers=self.headers, json=payload, timeout=30)

        if response.status_code == 200:
            print(f"    ✓ Targeting updated (configs must be turned ON manually in UI)")
            return response.json()
        else:
            print(f"    ✗ Failed to update targeting: {response.text}")
            return None


def main():
    load_dotenv()

    print("╔═══════════════════════════════════════════════════════╗")
    print("║  AI Agent Orchestrator - LaunchDarkly Bootstrap       ║")
    print("╚═══════════════════════════════════════════════════════╝")
    print()
    print("This script will create:")
    print("  • 1 project (orchestrator-agents)")
    print("  • Tools, AI agent configs, and variations from manifest")
    print("  • Default targeting setup")
    print()

    api_key = os.getenv("LD_API_KEY")
    if not api_key:
        print("❌ LD_API_KEY environment variable not set")
        print("   Get your API key from: https://app.launchdarkly.com/settings/authorization")
        print("   Then add it to your .env file")
        return

    # Check for manifest file (support both research gap and paper impact)
    # Look in config/ directory for manifest files
    config_dir = Path(__file__).parent.parent.parent / "config"

    manifest_options = [
        ("research_gap_manifest.yaml", "Research Gap Analysis"),
        ("research_gap_manifest_robust.yaml", "Research Gap Analysis (Robust)"),
        ("paper_impact_manifest.yaml", "Paper Impact Prediction"),
        ("medical_diagnosis_manifest.yaml", "Medical Diagnosis (legacy)")
    ]

    manifest_path = None
    manifest_type = None

    # Check for command line argument
    if len(sys.argv) > 1:
        arg_path = Path(sys.argv[1])
        if arg_path.exists():
            manifest_path = arg_path
            manifest_type = f"Custom ({arg_path.name})"
            print(f"Using manifest from command line: {manifest_path}")
            print()

    # Only show menu if no command line argument provided
    if manifest_path is None:
        print("Available manifests:")
        for i, (filename, description) in enumerate(manifest_options, 1):
            path = config_dir / filename
            if path.exists():
                print(f"  {i}. {description} ({filename})")
                if manifest_path is None:
                    manifest_path = path
                    manifest_type = description

        if manifest_path is None:
            print()
            print("❌ No manifest files found in config/ directory")
            print("   Expected: research_gap_manifest.yaml or paper_impact_manifest.yaml")
            return

        print()
        choice = input(f"Select manifest (1-{len([o for o in manifest_options if (config_dir / o[0]).exists()])}) or press Enter for default: ").strip()

        if choice.isdigit():
            idx = int(choice) - 1
            existing_manifests = [(p, d) for p, d in manifest_options if (config_dir / p).exists()]
            if 0 <= idx < len(existing_manifests):
                manifest_path = config_dir / existing_manifests[idx][0]
                manifest_type = existing_manifests[idx][1]

        print(f"Using: {manifest_type}")
    print()

    with open(manifest_path) as f:
        manifest = yaml.safe_load(f)

    project_key = manifest["project"]["key"]
    bootstrap = MedicalDiagnosisBootstrap(api_key)

    print(f"📦 Project: {project_key}")
    print(f"🌍 Environment: production")
    print()

    # Step 0: Create project if it doesn't exist
    print("📁 Creating project...")
    if not bootstrap.create_project(project_key, "Paper Impact Prediction Orchestrator"):
        print()
        print("❌ Failed to create project. Exiting.")
        return
    print()

    # Step 1: Create tools
    print("🛠️  Creating paper analysis tools...")
    for tool in manifest["project"]["tool"]:
        bootstrap.create_tool(project_key, tool)
    print()

    # Step 2: Create segments (required for targeting rules)
    if "segment" in manifest["project"]:
        print("📦 Creating segments for targeting rules...")
        for segment in manifest["project"]["segment"]:
            bootstrap.create_segment(project_key, segment)
        print()

    # Step 3: Create AI configs and variations
    print("🤖 Creating AI agent configs...")
    for ai_config in manifest["project"]["ai_config"]:
        config_key = ai_config["key"]

        if not bootstrap.create_ai_config(project_key, ai_config):
            print(f"❌ Failed to create AI Config '{config_key}'. Continuing...")
            continue

        # Create variations for this config
        print(f"🎨 Creating variations for '{config_key}'...")
        for variation in ai_config["variations"]:
            bootstrap.create_variation(project_key, config_key, variation, manifest)

        # Update targeting
        print(f"🎯 Updating targeting for '{config_key}'...")
        if "targeting" in ai_config:
            bootstrap.update_targeting(project_key, config_key, ai_config["targeting"])
        print()

    print("✨ Bootstrap complete!")
    print()
    print("📝 Next steps:")
    print(f"   1. Verify in LaunchDarkly: {bootstrap.base_url}/default/{project_key}/production/ai-configs")
    print(f"   2. Update your .env file:")
    print(f"      LAUNCHDARKLY_PROJECT_KEY={project_key}")
    print(f"      LD_API_KEY=your-api-key")
    print(f"      LAUNCHDARKLY_SDK_KEY=your-sdk-key")
    print(f"   3. Run your swarm: python -u strands/my_agent/swarm_example.py")
    print()
    print("🔄 To make changes:")
    print("   • Use LaunchDarkly UI to update instructions, models, etc.")
    print("   • This manifest is for initial setup only")


if __name__ == "__main__":
    main()