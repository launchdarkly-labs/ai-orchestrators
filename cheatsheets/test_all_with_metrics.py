#!/usr/bin/env python3
"""Test all orchestrators with AI metrics tracking - supports both Anthropic API and AWS Bedrock."""
import os
import time
from pathlib import Path

from dotenv import load_dotenv
load_dotenv(Path(__file__).parent.parent / ".env")

import ldclient
from ldclient import Context
from ldclient.config import Config
from ldai.client import LDAIClient, AICompletionConfigDefault
from ldai.tracker import TokenUsage

# Init LD
sdk_key = os.environ.get("LD_CHEATSHEET_SDK_KEY")
ldclient.set_config(Config(sdk_key=sdk_key))
ld_client = ldclient.get()
time.sleep(1)

ai_client = LDAIClient(ld_client)
default = AICompletionConfigDefault(enabled=False)

# Check which provider to use
USE_BEDROCK = os.environ.get("AWS_ACCESS_KEY_ID") is not None

if USE_BEDROCK:
    import boto3
    region = os.environ.get("AWS_DEFAULT_REGION", "us-west-2")
    bedrock = boto3.client("bedrock-runtime", region_name=region)
    print(f"Using AWS Bedrock (region: {region})")
else:
    import anthropic
    anthropic_client = anthropic.Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])
    print("Using Anthropic API")

print("=" * 60)
print("LaunchDarkly Orchestrator Routing + Metrics Demo")
print("=" * 60)

for orchestrator in ["strands", "langgraph", "llamaindex", "lyzr", "bedrock"]:
    context = Context.builder(f"user-{orchestrator}").kind("user").set("orchestrator", orchestrator).build()
    config = ai_client.config("orchestrator-config", context, default)

    print(f"\n[{orchestrator.upper()}]")
    print(f"  Prompt: {config.messages[0].content[:50]}...")

    if config.enabled:
        start_time = time.time()
        try:
            if USE_BEDROCK:
                # AWS Bedrock with automatic metrics tracking
                messages = [{"role": "user", "content": [{"text": "What is 2+2? Reply in one word."}]}]
                system = [{"text": config.messages[0].content}]

                response = config.tracker.track_bedrock_converse_metrics(
                    bedrock.converse(
                        modelId="anthropic.claude-3-haiku-20240307-v1:0",
                        messages=messages,
                        system=system,
                        inferenceConfig={"maxTokens": 256, "temperature": 0.7}
                    )
                )
                result = response["output"]["message"]["content"][0]["text"]
                input_tokens = response["usage"]["inputTokens"]
                output_tokens = response["usage"]["outputTokens"]
            else:
                # Anthropic API with manual metrics tracking
                response = anthropic_client.messages.create(
                    model="claude-3-haiku-20240307",
                    max_tokens=256,
                    system=config.messages[0].content,
                    messages=[{"role": "user", "content": "What is 2+2? Reply in one word."}]
                )
                result = response.content[0].text
                input_tokens = response.usage.input_tokens
                output_tokens = response.usage.output_tokens

                # Manual tracking for Anthropic
                duration_ms = int((time.time() - start_time) * 1000)
                config.tracker.track_duration(duration_ms)
                config.tracker.track_tokens(TokenUsage(
                    total=input_tokens + output_tokens,
                    input=input_tokens,
                    output=output_tokens
                ))
                config.tracker.track_success()

            print(f"  Response: {result}")
            print(f"  Tokens: {input_tokens} in / {output_tokens} out")
            print(f"  [Metrics tracked]")

        except Exception as e:
            config.tracker.track_error()
            print(f"  Error: {e}")

# Flush events before exit
ld_client.flush()
time.sleep(2)
ld_client.close()

print("\n" + "=" * 60)
print("Metrics sent to LaunchDarkly!")
print("Check: https://app.launchdarkly.com/projects/orchestrator-cheatsheet/ai-configs/orchestrator-config")
print("=" * 60)
