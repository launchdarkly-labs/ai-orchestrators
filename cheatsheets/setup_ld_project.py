#!/usr/bin/env python3
"""
Set up LaunchDarkly project with 4 orchestrator variations and targeting.
"""
import os
import sys
import time
import requests
from pathlib import Path

# Load environment
from dotenv import load_dotenv
load_dotenv(Path(__file__).parent.parent / ".env")

API_TOKEN = os.environ.get("LD_API_KEY")
BASE_URL = "https://app.launchdarkly.com/api/v2"

HEADERS = {
    "Authorization": API_TOKEN,
    "Content-Type": "application/json"
}

PROJECT_KEY = "orchestrator-cheatsheet"
PROJECT_NAME = "Orchestrator Cheatsheet"
CONFIG_KEY = "orchestrator-config"
ENVIRONMENT = "production"


def create_project():
    """Create the project."""
    print("\n[1] Creating project...")

    url = f"{BASE_URL}/projects"
    payload = {
        "name": PROJECT_NAME,
        "key": PROJECT_KEY,
        "tags": ["ai-configs", "cheatsheet"]
    }

    resp = requests.post(url, headers=HEADERS, json=payload)

    if resp.status_code == 201:
        project = resp.json()
        print(f"    Created: {PROJECT_NAME}")

        # Extract SDK key
        envs = project.get("environments", {})
        if isinstance(envs, dict):
            envs = envs.get("items", [])
        for env in envs:
            if env["key"] == "production":
                sdk_key = env["apiKey"]
                print(f"    SDK Key: {sdk_key}")
                return sdk_key
    elif resp.status_code == 409:
        print(f"    Project already exists, fetching SDK key...")
        return get_sdk_key()
    else:
        print(f"    Error: {resp.status_code} - {resp.text}")
        sys.exit(1)


def get_sdk_key():
    """Get SDK key for existing project."""
    url = f"{BASE_URL}/projects/{PROJECT_KEY}?expand=environments"
    resp = requests.get(url, headers=HEADERS)

    if resp.status_code == 200:
        project = resp.json()
        envs = project.get("environments", {})
        if isinstance(envs, dict):
            envs = envs.get("items", [])
        for env in envs:
            if env["key"] == "production":
                return env["apiKey"]
    return None


def create_ai_config():
    """Create AI Config with 4 variations (one per orchestrator)."""
    print("\n[2] Creating AI Config with 4 variations...")

    url = f"{BASE_URL}/projects/{PROJECT_KEY}/ai-configs"

    # Define variations - one per orchestrator
    variations = [
        {
            "key": "strands-variation",
            "name": "Strands Variation",
            "messages": [{"role": "system", "content": "You are a helpful assistant running on Strands. Be concise and direct."}],
            "model": {"name": "anthropic/claude-sonnet-4-20250514"}
        },
        {
            "key": "langgraph-variation",
            "name": "LangGraph Variation",
            "messages": [{"role": "system", "content": "You are a helpful assistant running on LangGraph. Think step by step."}],
            "model": {"name": "anthropic/claude-sonnet-4-20250514"}
        },
        {
            "key": "llamaindex-variation",
            "name": "LlamaIndex Variation",
            "messages": [{"role": "system", "content": "You are a helpful assistant running on LlamaIndex. Focus on document understanding."}],
            "model": {"name": "anthropic/claude-sonnet-4-20250514"}
        },
        {
            "key": "lyzr-variation",
            "name": "Lyzr Variation",
            "messages": [{"role": "system", "content": "You are a helpful assistant running on Lyzr. Prioritize enterprise workflows."}],
            "model": {"name": "anthropic/claude-sonnet-4-20250514"}
        }
    ]

    payload = {
        "name": "Orchestrator Config",
        "key": CONFIG_KEY,
        "description": "AI Config with variations for each orchestrator framework",
        "tags": ["cheatsheet"],
        "variations": variations
    }

    resp = requests.post(url, headers=HEADERS, json=payload)

    if resp.status_code == 201:
        print(f"    Created AI Config: {CONFIG_KEY}")
        for v in variations:
            print(f"      - {v['name']}")
        return True
    elif resp.status_code == 409:
        print(f"    AI Config already exists")
        return True
    else:
        print(f"    Error: {resp.status_code} - {resp.text}")
        return False


def setup_targeting():
    """Set up targeting rules to route each orchestrator to its variation."""
    print("\n[3] Setting up targeting rules...")

    # First, get current config to find variation IDs
    url = f"{BASE_URL}/projects/{PROJECT_KEY}/ai-configs/{CONFIG_KEY}"
    resp = requests.get(url, headers=HEADERS)

    if resp.status_code != 200:
        print(f"    Error getting config: {resp.text}")
        return False

    config = resp.json()

    # Map variation keys to their index (0-based)
    variation_map = {}
    for i, v in enumerate(config.get("variations", [])):
        variation_map[v["key"]] = i

    # Define targeting rules
    orchestrators = ["strands", "langgraph", "llamaindex", "lyzr"]
    rules = []

    for orchestrator in orchestrators:
        variation_key = f"{orchestrator}-variation"
        variation_idx = variation_map.get(variation_key)

        if variation_idx is not None:
            rules.append({
                "clauses": [{
                    "contextKind": "user",
                    "attribute": "orchestrator",
                    "op": "in",
                    "values": [orchestrator]
                }],
                "variation": variation_idx,
                "description": f"Route {orchestrator} to its variation"
            })

    # Use semantic patch to update targeting
    url = f"{BASE_URL}/projects/{PROJECT_KEY}/ai-configs/{CONFIG_KEY}"

    # Build semantic patch instructions
    patch_body = {
        "environmentKey": ENVIRONMENT,
        "instructions": [
            {"kind": "turnFlagOn"},
            {"kind": "replaceRules", "rules": rules},
            {"kind": "updateFallthroughVariationOrRollout", "variationId": 0}
        ]
    }

    patch_headers = {**HEADERS, "Content-Type": "application/json; domain-model=launchdarkly.semanticpatch"}
    resp = requests.patch(url, headers=patch_headers, json=patch_body)

    if resp.status_code in [200, 204]:
        print(f"    Targeting enabled with {len(rules)} rules:")
        for orchestrator in orchestrators:
            print(f"      orchestrator={orchestrator} -> {orchestrator}-variation")
        return True
    else:
        print(f"    Error: {resp.status_code} - {resp.text[:200]}")
        return False


def test_config(sdk_key: str):
    """Test the config by fetching it with different orchestrator contexts."""
    print("\n[4] Testing configuration...")

    import ldclient
    from ldclient import Context
    from ldclient.config import Config
    from ldai.client import LDAIClient, AICompletionConfigDefault

    # Initialize
    ldclient.set_config(Config(sdk_key=sdk_key))
    ld_client = ldclient.get()

    # Wait for init
    for _ in range(10):
        if ld_client.is_initialized():
            break
        time.sleep(0.5)

    if not ld_client.is_initialized():
        print("    Failed to initialize LD client")
        return

    ai_client = LDAIClient(ld_client)

    # Test each orchestrator
    orchestrators = ["strands", "langgraph", "llamaindex", "lyzr"]

    # Default fallback config
    default = AICompletionConfigDefault(enabled=False)

    for orchestrator in orchestrators:
        context = (
            Context.builder(f"test-{orchestrator}")
            .kind("user")
            .set("orchestrator", orchestrator)
            .build()
        )

        config = ai_client.config(CONFIG_KEY, context, default)

        if config and config.enabled:
            # Extract first few words of system prompt
            prompt_preview = ""
            if config.messages:
                prompt_preview = config.messages[0].get("content", "")[:50] + "..."
            print(f"    {orchestrator}: {prompt_preview}")
        else:
            print(f"    {orchestrator}: NOT ENABLED or not found")

    ld_client.close()
    print("\n[OK] Setup complete!")


def main():
    print("=" * 60)
    print("LaunchDarkly Orchestrator Project Setup")
    print("=" * 60)

    # Step 1: Create project
    sdk_key = create_project()

    # Step 2: Create AI Config
    create_ai_config()

    # Step 3: Setup targeting
    setup_targeting()

    # Step 4: Test
    if sdk_key:
        test_config(sdk_key)

    print("\n" + "=" * 60)
    print(f"Project: https://app.launchdarkly.com/projects/{PROJECT_KEY}")
    print(f"AI Config: https://app.launchdarkly.com/projects/{PROJECT_KEY}/ai-configs/{CONFIG_KEY}")
    print("=" * 60)


if __name__ == "__main__":
    main()
