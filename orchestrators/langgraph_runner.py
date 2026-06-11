"""
LangGraph runner.

Per-node agent builder + invoke for the shared dispatcher. Everything dynamic comes
from the LD node config: the model (`create_langchain_model`), the attached tools
(`build_tools` binds the node's `config.tools` to the registry callables), and the
instructions (with routes injected by the dispatcher). The dispatcher owns the walk.
"""

from langgraph.prebuilt import create_react_agent
from ldai_langchain import (
    create_langchain_model,
    get_tool_calls_from_response,
    sum_token_usage_from_messages,
)
from ldai_langchain.langchain_helper import build_tools
from ldai.providers.types import LDAIMetrics

from shared.tools import TOOL_REGISTRY


def _content_to_text(content):
    """Coerce a LangChain message's ``content`` to a plain string.

    Most providers return a ``str``, but Anthropic can return a list of content blocks;
    the dispatcher needs a ``str`` for route extraction, so join the text parts.
    """
    if isinstance(content, str):
        return content
    return "".join(b.get("text", "") if isinstance(b, dict) else "" for b in content or [])


def build_agent(node_key, config, instructions):
    """Build a LangChain ReAct agent from an LD node config."""
    llm = create_langchain_model(config)
    tools = build_tools(config, TOOL_REGISTRY)  # binds only this node's attached tools
    return create_react_agent(llm, tools, prompt=instructions)


async def invoke(agent, input_text, tracker):
    """Invoke the agent; `track_metrics_of_async` records duration + success + tokens."""
    result = await tracker.track_metrics_of_async(
        lambda res: LDAIMetrics(success=True, tokens=sum_token_usage_from_messages(res.get("messages", []))),
        lambda: agent.ainvoke({"messages": [{"role": "user", "content": input_text}]}),
    )
    messages = result.get("messages", [])
    for message in messages:
        for name in get_tool_calls_from_response(message):
            tracker.track_tool_call(name)
    text = _content_to_text(messages[-1].content) if messages else ""
    return text, sum_token_usage_from_messages(messages)
