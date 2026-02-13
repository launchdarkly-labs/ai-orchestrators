#!/usr/bin/env python3
"""
LlamaIndex + LaunchDarkly AI Config
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

from llama_index.llms.anthropic import Anthropic
from llama_index.core.chat_engine import SimpleChatEngine


def run_llamaindex_agent(prompt: str):
    # 1. Initialize LaunchDarkly
    sdk_key = os.environ.get("LD_CHEATSHEET_SDK_KEY") or os.environ.get("LD_SDK_KEY")
    ldclient.set_config(Config(sdk_key=sdk_key))
    ld_client = ldclient.get()
    time.sleep(1)

    ai_client = LDAIClient(ld_client)

    # 2. Create context with orchestrator for routing
    context = (
        Context.builder("llamaindex-user")
        .kind("user")
        .set("orchestrator", "llamaindex")
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

    # 4. Build LLM from LD config
    llm = Anthropic(model="claude-3-haiku-20240307")

    # 5. Create chat engine
    chat_engine = SimpleChatEngine.from_defaults(
        llm=llm,
        system_prompt=system_prompt,
    )

    # 6. Run query
    response = chat_engine.chat(prompt)

    # 7. Track completion
    config.tracker.track_success()

    ld_client.flush()
    ld_client.close()
    return str(response)


if __name__ == "__main__":
    print("=" * 60)
    print("LLAMAINDEX + LAUNCHDARKLY TEST")
    print("=" * 60)

    result = run_llamaindex_agent("What is 2+2? Reply in one word.")
    print(f"\nResponse: {result}")
