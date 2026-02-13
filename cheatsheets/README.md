# LaunchDarkly + Orchestrators Cheat Sheet

Route different orchestrators to different AI config variations.

## Test It

```bash
python test_all.py
```

Output:
```
[STRANDS]
  Prompt:  You are a helpful assistant running on Strands. Be concise and direct.

[LANGGRAPH]
  Prompt:  You are a helpful assistant running on LangGraph. Think step by step.

[LLAMAINDEX]
  Prompt:  You are a helpful assistant running on LlamaIndex. Focus on document understanding.

[LYZR]
  Prompt:  You are a helpful assistant running on Lyzr. Prioritize enterprise workflows.
```

## How It Works

```python
context = Context.builder("user-123").kind("user").set("orchestrator", "strands").build()
config = ai_client.config("orchestrator-config", context, default)
# -> Returns Strands variation
```

## Targeting Rules

| `orchestrator` | Variation |
|----------------|-----------|
| `strands` | Strands Variation |
| `langgraph` | LangGraph Variation |
| `llamaindex` | LlamaIndex Variation |
| `lyzr` | Lyzr Variation |

## Project

https://app.launchdarkly.com/projects/orchestrator-cheatsheet/ai-configs/orchestrator-config
