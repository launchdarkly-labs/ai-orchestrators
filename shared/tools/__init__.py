"""
Domain tool handlers for the research-gap-analysis graph.

`TOOL_REGISTRY` is a plain ``{name: callable}`` mapping — the shape the LD AI SDK's
``ToolRegistry`` (``ldai.providers.types.ToolRegistry``) expects. Each runner binds
these to its framework:

- LangGraph / OpenAI Agents: the companion packages do it
  (``ldai_langchain.build_tools`` / ``ldai_openai.registry_value_to_agent_tool``).
- Strands / Google ADK: bind with the framework's native ``@tool`` in the runner's
  agent-builder.

No custom per-framework decorator factory is needed — the SDK + companion packages
handle binding.
"""

from .common import (
    TOOL_REGISTRY,
    fetch_paper,
)

__all__ = [
    "TOOL_REGISTRY",
    "fetch_paper",
]
