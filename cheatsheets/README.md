# LaunchDarkly + Orchestrators Cheat Sheet

Route different orchestrators to different AI config variations.

## Test It

```bash
# With Anthropic API
python test_all_with_metrics.py

# With AWS Bedrock
export AWS_ACCESS_KEY_ID="..."
export AWS_SECRET_ACCESS_KEY="..."
export AWS_SESSION_TOKEN="..."  # if using SSO
export AWS_DEFAULT_REGION="us-west-2"
python test_all_with_metrics.py
```

Output:
```
[STRANDS]   -> "You are a helpful assistant running on Strands..."
[LANGGRAPH] -> "You are a helpful assistant running on LangGraph..."
[LLAMAINDEX]-> "You are a helpful assistant running on LlamaIndex..."
[LYZR]      -> "You are a helpful assistant running on Lyzr..."
```

## How It Works

```python
# Set orchestrator in context
context = Context.builder("user-123").kind("user").set("orchestrator", "strands").build()

# Get variation for that orchestrator
config = ai_client.config("orchestrator-config", context, default)
# -> Returns Strands variation with its system prompt
```

## Targeting Rules

| `orchestrator` | Variation |
|----------------|-----------|
| `strands` | Strands Variation |
| `langgraph` | LangGraph Variation |
| `llamaindex` | LlamaIndex Variation |
| `lyzr` | Lyzr Variation |

## Files

| File | Description |
|------|-------------|
| `test_all_with_metrics.py` | Test all orchestrators (auto-detects Bedrock vs Anthropic) |
| `bedrock_example.py` | AWS Bedrock standalone example |
| `strands_example.py` | Strands framework example |
| `langgraph_example.py` | LangGraph framework example |
| `llamaindex_example.py` | LlamaIndex framework example |
| `lyzr_example.py` | Lyzr platform example |

## Project

https://app.launchdarkly.com/projects/orchestrator-cheatsheet/ai-configs/orchestrator-config
