# Shared tools

Domain tool handlers for the research-gap-analysis graph.

## Structure

- `common.py` — the three tool implementations the graph attaches (`cluster_approaches`,
  `detect_contradictions`, `identify_research_gaps`), plus `TOOL_REGISTRY`, a plain
  `{name: callable}` mapping.

## How tools reach the agents

The graph node configs declare which tools they use. Each runner resolves those names against
`TOOL_REGISTRY` and binds the callables to its framework. **Each runner binds with its own
framework's native wrapper — there is no custom decorator factory:**

- **LangGraph** — `shared.ldai_compat.build_tools` selects the callables the node's config
  attaches; the runner hands them to `create_react_agent`. The registry shape is a plain
  `Dict[str, Callable]`, which is also what the SDK takes for `tool_handlers`.
- **OpenAI Agents / Strands / Google ADK** — bind with the framework's native wrapper
  (`function_tool` / `@tool` / plain callables) in the runner's agent-builder.

The retired companion packages used to bind for LangGraph and OpenAI Agents. The current SDK
binds tools only inside its own execution paths, which these native arms bypass by design,
so the runners bind them.

Tool definitions arrive under `model.parameters.tools` on the wire; `ldai_compat.tool_names`
reads that and the validated top-level `tools` object, so either shape resolves.

## Adding a tool

1. Implement it in `common.py` as a plain function.
2. Add it to `TOOL_REGISTRY`.
3. Attach its key to the relevant node(s) in `config/graph_experiment_manifest.yaml`
   (and re-run the bootstrap).
