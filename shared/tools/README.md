# Shared tools

Domain tool handlers for the research-gap-analysis graph.

## Structure

- `common.py` — the three tool implementations the graph attaches (`cluster_approaches`,
  `detect_contradictions`, `identify_research_gaps`), plus `TOOL_REGISTRY`, a plain
  `{name: callable}` mapping.

## How tools reach the agents

The graph node configs declare which tools they use (`config.tools`). Each runner resolves
those names against `TOOL_REGISTRY` and binds the callables to its framework. **The SDK and
companion packages do the binding — there is no custom decorator factory:**

- **LangGraph / OpenAI Agents** — the companion packages bind them
  (`ldai_langchain.build_tools`, `ldai_openai.registry_value_to_agent_tool`). The canonical
  registry shape is `ldai.providers.types.ToolRegistry = Dict[str, Callable]`.
- **Strands / Google ADK** — no companion package, so bind with the framework's native
  `@tool` in the runner's agent-builder.

## Adding a tool

1. Implement it in `common.py` as a plain function.
2. Add it to `TOOL_REGISTRY`.
3. Attach its key to the relevant node(s) in `config/graph_experiment_manifest.yaml`
   (and re-run the bootstrap).
