"""
LangGraph + LaunchDarkly AI Config
Simplest possible implementation
"""
import uuid
from langchain_anthropic import ChatAnthropic
from langgraph.graph import StateGraph, START, END
from langgraph.graph.message import add_messages
from typing import Annotated, TypedDict
from ld_setup import init_ld, create_context, get_ai_config


class State(TypedDict):
    messages: Annotated[list, add_messages]


def run_langgraph_agent(prompt: str):
    # 1. Initialize LaunchDarkly
    ld_client, ai_client = init_ld()

    # 2. Create context with orchestrator for routing
    context = create_context(
        user_id=str(uuid.uuid4()),
        orchestrator="langgraph"  # Routes to langgraph-specific variation
    )

    # 3. Get AI config from LaunchDarkly
    config = get_ai_config(ai_client, "orchestrator-config", context)

    # 4. Build LLM from LD config
    llm = ChatAnthropic(
        model=config.model.id if config.model else "claude-sonnet-4-5"
    )

    system_prompt = config.messages[0]["content"] if config.messages else ""

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

    ld_client.close()
    return result["messages"][-1].content


if __name__ == "__main__":
    result = run_langgraph_agent("Summarize the key benefits of feature flags")
    print(result)
