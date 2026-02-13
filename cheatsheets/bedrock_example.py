#!/usr/bin/env python3
"""
AWS Bedrock + LaunchDarkly AI Config
Simplest possible implementation with automatic metrics tracking
"""
import os
import time
from pathlib import Path

from dotenv import load_dotenv
load_dotenv(Path(__file__).parent.parent / ".env")

import boto3
import ldclient
from ldclient import Context
from ldclient.config import Config
from ldai.client import LDAIClient, AICompletionConfigDefault


def run_bedrock_agent(prompt: str, orchestrator: str = "bedrock"):
    # 1. Initialize LaunchDarkly
    sdk_key = os.environ.get("LD_CHEATSHEET_SDK_KEY") or os.environ.get("LD_SDK_KEY")
    ldclient.set_config(Config(sdk_key=sdk_key))
    ld_client = ldclient.get()
    time.sleep(1)

    ai_client = LDAIClient(ld_client)

    # 2. Create context with orchestrator for routing
    context = (
        Context.builder(f"user-{orchestrator}")
        .kind("user")
        .set("orchestrator", orchestrator)
        .build()
    )

    # 3. Get AI config from LaunchDarkly
    default = AICompletionConfigDefault(enabled=False)
    config = ai_client.config("orchestrator-config", context, default)

    if not config.enabled:
        print("Config not enabled")
        ld_client.close()
        return None

    # 4. Initialize Bedrock client
    region = os.environ.get("AWS_DEFAULT_REGION", "us-west-2")
    bedrock = boto3.client("bedrock-runtime", region_name=region)

    # 5. Format messages for Bedrock Converse API
    system_prompt = config.messages[0].content if config.messages else ""

    # Bedrock expects specific message format
    messages = [
        {"role": "user", "content": [{"text": prompt}]}
    ]
    system = [{"text": system_prompt}]

    # 6. Call Bedrock with automatic metrics tracking
    # Use Claude on Bedrock (or Nova)
    model_id = "anthropic.claude-3-haiku-20240307-v1:0"  # or "amazon.nova-lite-v1:0"

    response = config.tracker.track_bedrock_converse_metrics(
        bedrock.converse(
            modelId=model_id,
            messages=messages,
            system=system,
            inferenceConfig={"maxTokens": 256, "temperature": 0.7}
        )
    )

    # 7. Extract response
    result = response["output"]["message"]["content"][0]["text"]

    # 8. Cleanup
    ld_client.flush()
    ld_client.close()

    return result


if __name__ == "__main__":
    print("=" * 60)
    print("BEDROCK + LAUNCHDARKLY TEST")
    print("=" * 60)

    result = run_bedrock_agent("What is 2+2? Reply in one word.")
    print(f"Response: {result}")
