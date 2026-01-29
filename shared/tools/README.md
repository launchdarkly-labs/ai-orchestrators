# Shared Tools

This directory contains tools that can be used across all orchestration frameworks.

## Structure

- `common.py` - Framework-agnostic tool implementations (all tool logic lives here)
- `factory.py` - Automatic tool decorator factory (applies framework decorators programmatically)

## Philosophy

All tool logic is defined in `common.py` with normal function names. The `factory.py` module automatically applies the correct framework decorator, eliminating the need to manually wrap tools in each agent. This keeps:
- Tool logic in one place (no duplication)
- Framework dependencies separate (no need to import all frameworks)
- Agents simple (just call `get_tool()` or `get_tools()`)
- No manual wrapping needed (decorators applied automatically)

## Adding New Tools

1. **Define the tool logic** in `common.py`:

```python
def my_new_tool(input: str) -> str:
    """Tool description."""
    # Tool logic here
    return result
```

That's it! The tool is automatically available to all frameworks via the factory.

## Using Tools in Agents

### Recommended: Use the Factory (Automatic)

```python
from tools.factory import get_tool, get_tools

# Get a specific tool (automatically decorated for your framework)
letter_counter = get_tool('strands', 'letter_counter')

# Or get all tools at once
all_tools = get_tools('strands')
```

### Strands Example

```python
from strands import Agent
from strands_tools import calculator, current_time
from tools.factory import get_tool

# Automatically get shared tools (no manual wrapping needed!)
letter_counter = get_tool('strands', 'letter_counter')

agent = Agent(tools=[calculator, current_time, letter_counter])
```

### LangGraph Example

```python
from tools.factory import get_tool

# Automatically get shared tools (no manual wrapping needed!)
letter_counter = get_tool('langgraph', 'letter_counter')
word_counter = get_tool('langgraph', 'word_counter')

# Use with LangGraph
tools = [letter_counter, word_counter]
```

### Get All Tools at Once

```python
from tools.factory import get_tools

# Get all tools from common.py, automatically decorated
all_tools = get_tools('strands')  # or 'langgraph'
```

### Manual Approach (If You Need More Control)

If you need custom behavior, you can still manually wrap tools:

```python
from strands import tool
from tools.common import my_new_tool as _my_new_tool

@tool
def my_new_tool(input: str) -> str:
    """Tool description."""
    return _my_new_tool(input)
```

**Key Point:** No manual wrapping needed! Just call `get_tool()` or `get_tools()` with your framework name, and the decorator is applied automatically.
