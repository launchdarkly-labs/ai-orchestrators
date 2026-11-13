"""
Domain tool handlers for the research-gap-analysis graph.

`TOOL_REGISTRY` is a plain ``{name: callable}`` mapping — the shape the LD AI SDK takes for
``tool_handlers``. Each runner binds these to its framework:

- LangGraph: ``shared.ldai_compat.build_tools`` selects the callables this node's config
  attaches; the runner passes them to ``create_react_agent``.
- OpenAI Agents / Strands / Google ADK: bind with the framework's native wrapper
  (``function_tool`` / ``@tool`` / plain callables) in the runner's agent-builder.

The retired companion packages used to do the LangGraph and OpenAI Agents binding; the
current SDK ships no per-framework binder for the native path, so the runners do it.
"""

from .common import (
    TOOL_REGISTRY,
    fetch_paper,
)

__all__ = [
    "TOOL_REGISTRY",
    "fetch_paper",
]
