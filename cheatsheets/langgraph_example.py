#!/usr/bin/env python3
"""
LangGraph + LaunchDarkly AI Config
"""
import os
import time
from pathlib import Path
from typing import Annotated, TypedDict

from dotenv import load_dotenv
load_dotenv(Path(__file__).parent.parent / ".env")

import ldclient
from ldclient import Context
from ldclient.config import Config
from ldai.client import LDAIClient, AICompletionConfigDefault

from langchain_anthropic import ChatAnthropic
from langgraph.graph import StateGraph, START, END
from langgraph.graph.message import add_messages


class State(TypedDict):
    messages: Annotated[list, add_messages]


def run_langgraph_agent(prompt: str):
    # 1. Initialize LaunchDarkly
    sdk_key = os.environ.get("LD_CHEATSHEET_SDK_KEY") or os.environ.get("LD_SDK_KEY")
    ldclient.set_config(Config(sdk_key=sdk_key))
    ld_client = ldclient.get()
    time.sleep(1)

    ai_client = LDAIClient(ld_client)

    # 2. Create context with orchestrator for routing
    context = (
        Context.builder("langgraph-user")
        .kind("user")
        .set("orchestrator", "langgraph")
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
    llm = ChatAnthropic(model="claude-3-haiku-20240307")

    # 5. Define graph node
    def chat(state: State):
        messages = [{"role": "system", "content": system_prompt}] + state["messages"]
        response = llm.invoke(messages)
        return {"messages": [response]}

    # 6. Build and compile graph
    graph = StateGraph(State)
    graph.add_node("chat", chat)
    graph.add_edge(START, "chat")
    graph.add_edge("chat", END)
    app = graph.compile()

    # 7. Run graph
    result = app.invoke({"messages": [{"role": "user", "content": prompt}]})

    # 8. Track completion
    config.tracker.track_success()

    ld_client.flush()
    ld_client.close()
    return result["messages"][-1].content


if __name__ == "__main__":
    print("=" * 60)
    print("LANGGRAPH + LAUNCHDARKLY TEST")
    print("=" * 60)

    result = run_langgraph_agent("What is 2+2? Reply in one word.")
    print(f"\nResponse: {result}")
