#!/usr/bin/env python3
"""Test all 4 orchestrators with AI metrics tracking."""
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
import anthropic

# Init LD
sdk_key = os.environ.get("LD_CHEATSHEET_SDK_KEY")
ldclient.set_config(Config(sdk_key=sdk_key))
ld_client = ldclient.get()
time.sleep(1)

ai_client = LDAIClient(ld_client)
default = AICompletionConfigDefault(enabled=False)
anthropic_client = anthropic.Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])

print("=" * 60)
print("LaunchDarkly Orchestrator Routing + Metrics Demo")
print("=" * 60)

for orchestrator in ["strands", "langgraph", "llamaindex", "lyzr"]:
    context = Context.builder(f"user-{orchestrator}").kind("user").set("orchestrator", orchestrator).build()
    config = ai_client.config("orchestrator-config", context, default)

    print(f"\n[{orchestrator.upper()}]")
    print(f"  Prompt: {config.messages[0].content[:50]}...")

    if config.enabled:
        # Track the AI call
        start_time = time.time()
        try:
            response = anthropic_client.messages.create(
                model="claude-3-haiku-20240307",
                max_tokens=256,
                system=config.messages[0].content,
                messages=[{"role": "user", "content": "What is 2+2? Reply in one word."}]
            )
            duration_ms = int((time.time() - start_time) * 1000)

            # Track metrics
            config.tracker.track_duration(duration_ms)
            config.tracker.track_tokens(TokenUsage(
                total=response.usage.input_tokens + response.usage.output_tokens,
                input=response.usage.input_tokens,
                output=response.usage.output_tokens
            ))
            config.tracker.track_success()

            print(f"  Response: {response.content[0].text}")
            print(f"  Tokens: {response.usage.input_tokens} in / {response.usage.output_tokens} out")
            print(f"  Duration: {duration_ms}ms")
            print(f"  [Metrics tracked]")

        except Exception as e:
            config.tracker.track_error()
            print(f"  Error: {e}")

# Flush events before exit
ld_client.flush()
time.sleep(2)  # Give time for events to send
ld_client.close()

print("\n" + "=" * 60)
print("Metrics sent to LaunchDarkly!")
print("Check: https://app.launchdarkly.com/projects/orchestrator-cheatsheet/ai-configs/orchestrator-config")
print("=" * 60)
