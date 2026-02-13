#!/usr/bin/env python3
"""Test all 5 orchestrators getting their configs from LaunchDarkly."""
import os
import sys
import time
from pathlib import Path

from dotenv import load_dotenv
load_dotenv(Path(__file__).parent.parent / ".env")

import ldclient
from ldclient import Context
from ldclient.config import Config
from ldai.client import LDAIClient, AICompletionConfigDefault

# Init
sdk_key = os.environ.get("LD_CHEATSHEET_SDK_KEY") or os.environ.get("LD_SDK_KEY")
ldclient.set_config(Config(sdk_key=sdk_key))
ld_client = ldclient.get()
time.sleep(1)

ai_client = LDAIClient(ld_client)
default = AICompletionConfigDefault(enabled=False)

print("=" * 60)
print("LaunchDarkly Orchestrator Routing Demo")
print("=" * 60)

for orchestrator in ["strands", "langgraph", "llamaindex", "lyzr", "bedrock"]:
    context = Context.builder(f"user-{orchestrator}").kind("user").set("orchestrator", orchestrator).build()
    config = ai_client.config("orchestrator-config", context, default)

    print(f"\n[{orchestrator.upper()}]")
    print(f"  Enabled: {config.enabled}")
    print(f"  Model:   {config.model.name if config.model else 'N/A'}")
    print(f"  Prompt:  {config.messages[0].content if config.messages else 'N/A'}")

ld_client.close()
print("\n" + "=" * 60)
