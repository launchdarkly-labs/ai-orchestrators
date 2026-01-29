"""
Shared tools for all orchestration frameworks.

This module provides framework-agnostic tool implementations and
a factory to automatically apply framework decorators.

Usage:
    # Recommended: Use the factory (automatic decoration)
    from tools.factory import get_tools, get_tool
    
    # Get all tools for Strands
    tools = get_tools('strands')
    
    # Get a specific tool for LangGraph
    letter_counter = get_tool('langgraph', 'letter_counter')
    
    # Manual approach (if you need more control)
    from tools.common import letter_counter as _letter_counter
    from strands import tool
    
    @tool
    def letter_counter(word: str, letter: str) -> int:
        return _letter_counter(word, letter)
"""

from .factory import get_tools, get_tool
from .common import letter_counter, word_counter

__all__ = [
    'get_tools',
    'get_tool',
    'letter_counter',
    'word_counter',
]
