#!/usr/bin/env python3
"""
Lyzr + LaunchDarkly AI Config

Lyzr is an enterprise AI agent platform. This example shows how to:
1. Get config from LaunchDarkly (system prompt, model settings)
2. Use that config with Lyzr's platform or as a fallback with direct LLM calls

For Lyzr platform: https://www.lyzr.ai/
"""
import os
import time
from pathlib import Path

from dotenv import load_dotenv
load_dotenv(Path(__file__).parent.parent / ".env")

import ldclient
from ldclient import Context
from ldclient.config import Config
from ldai.client import LDAIClient, AICompletionConfigDefault


def run_lyzr_agent(prompt: str):
    # 1. Initialize LaunchDarkly
    sdk_key = os.environ.get("LD_CHEATSHEET_SDK_KEY") or os.environ.get("LD_SDK_KEY")
    ldclient.set_config(Config(sdk_key=sdk_key))
    ld_client = ldclient.get()
    time.sleep(1)

    ai_client = LDAIClient(ld_client)

    # 2. Create context with orchestrator for routing
    context = (
        Context.builder("lyzr-user")
        .kind("user")
        .set("orchestrator", "lyzr")  # Routes to lyzr-specific variation
        .build()
    )

    # 3. Get AI config from LaunchDarkly
    default = AICompletionConfigDefault(enabled=False)
    config = ai_client.config("orchestrator-config", context, default)

    if not config.enabled:
        print("Config not enabled")
        ld_client.close()
        return None

    system_prompt = config.messages[0].content if config.messages else ""
    print(f"System prompt from LD: {system_prompt}")

    # 4. Option A: Use Lyzr platform (if you have access)
    # from lyzr_agent_api import AgentAPI, ChatRequest
    # agent_api = AgentAPI(api_key=os.environ["LYZR_API_KEY"])
    # response = agent_api.chat(ChatRequest(
    #     agent_id="your-agent-id",
    #     message=prompt,
    #     system_prompt=system_prompt
    # ))

    # 4. Option B: Fallback to direct LLM call (for testing)
    # Using Bedrock if AWS creds available, otherwise Anthropic
    if os.environ.get("AWS_ACCESS_KEY_ID"):
        import boto3
        bedrock = boto3.client("bedrock-runtime", region_name=os.environ.get("AWS_DEFAULT_REGION", "us-west-2"))

        response = config.tracker.track_bedrock_converse_metrics(
            bedrock.converse(
                modelId="anthropic.claude-3-haiku-20240307-v1:0",
                messages=[{"role": "user", "content": [{"text": prompt}]}],
                system=[{"text": system_prompt}],
                inferenceConfig={"maxTokens": 256}
            )
        )
        result = response["output"]["message"]["content"][0]["text"]
    else:
        import anthropic
        from ldai.tracker import TokenUsage

        client = anthropic.Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])
        start = time.time()

        response = client.messages.create(
            model="claude-3-haiku-20240307",
            max_tokens=256,
            system=system_prompt,
            messages=[{"role": "user", "content": prompt}]
        )

        config.tracker.track_duration(int((time.time() - start) * 1000))
        config.tracker.track_tokens(TokenUsage(
            total=response.usage.input_tokens + response.usage.output_tokens,
            input=response.usage.input_tokens,
            output=response.usage.output_tokens
        ))
        config.tracker.track_success()

        result = response.content[0].text

    # 5. Cleanup
    ld_client.flush()
    ld_client.close()

    return result


if __name__ == "__main__":
    print("=" * 60)
    print("LYZR + LAUNCHDARKLY TEST")
    print("=" * 60)

    result = run_lyzr_agent("What is 2+2? Reply in one word.")
    print(f"\nResponse: {result}")
