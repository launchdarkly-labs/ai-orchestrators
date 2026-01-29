"""
Tool factory that programmatically applies framework decorators.

This module automatically decorates tools from common.py with the
appropriate framework decorator, eliminating the need to manually
wrap each tool in each agent file.
"""

import inspect
from typing import Callable, List, Any


def _get_decorator_for_framework(framework: str):
    """
    Get the tool decorator for a specific framework.

    Args:
        framework: Framework name ('strands', 'langgraph', 'autogen', 'crewai', etc.)

    Returns:
        The tool decorator function for the framework
    """
    if framework == 'strands':
        from strands import tool
        return tool
    elif framework == 'langgraph':
        from langchain_core.tools import tool
        return tool
    elif framework == 'crewai':
        # CrewAI uses its own tool decorator from crewai.tools
        from crewai.tools import tool
        return tool
    elif framework == 'autogen':
        # AutoGen doesn't use decorators - return identity function
        # Tools are registered separately using register_for_execution/register_for_llm
        return lambda func: func
    elif framework == 'openai_swarm':
        # OpenAI Swarm uses plain functions - return identity function
        return lambda func: func
    else:
        raise ValueError(f"Unknown framework: {framework}. Supported: 'strands', 'langgraph', 'crewai', 'autogen', 'openai_swarm'")


def get_tools(framework: str) -> List[Any]:
    """
    Get all tools decorated for the specified framework.

    Args:
        framework: Framework name ('strands', 'langgraph', etc.)

    Returns:
        List of decorated tool objects ready to use with the framework
    """
    from shared.tools import common
    
    decorator = _get_decorator_for_framework(framework)
    tools = []
    
    # Get all functions from common module that look like tools
    # (not private, callable, not the module itself)
    for name in dir(common):
        if name.startswith('_'):
            continue
            
        obj = getattr(common, name)
        if inspect.isfunction(obj) and obj.__module__ == common.__name__:
            # Apply the framework decorator
            decorated_tool = decorator(obj)
            tools.append(decorated_tool)
    
    return tools


def get_tool(framework: str, tool_name: str) -> Any:
    """
    Get a specific tool decorated for the specified framework.

    Args:
        framework: Framework name ('strands', 'langgraph', etc.)
        tool_name: Name of the tool function in common.py

    Returns:
        Decorated tool object ready to use with the framework
    """
    from shared.tools import common
    
    if not hasattr(common, tool_name):
        raise ValueError(f"Tool '{tool_name}' not found in tools.common")
    
    tool_func = getattr(common, tool_name)
    if not inspect.isfunction(tool_func):
        raise ValueError(f"'{tool_name}' is not a function")
    
    decorator = _get_decorator_for_framework(framework)
    return decorator(tool_func)
