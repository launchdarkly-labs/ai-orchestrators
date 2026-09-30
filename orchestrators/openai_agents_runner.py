"""
OpenAI Agents runner.

The Agents SDK runs OpenAI models natively; the pinned Claude model runs through LiteLLM,
the SDK's adapter for other providers. Tools are bound with the SDK's `function_tool`.
Everything dynamic still comes from the LD node config; the dispatcher owns the graph walk.

The usage + tool-call readers used to come from the `ldai_openai` companion package, which
the current SDK generation does not replace. They now live in `shared.ldai_compat`, ported
from that package's last release.
"""

import os

from agents import Agent, ModelSettings, Runner, function_tool
from agents.extensions.models.litellm_model import LitellmModel
from shared.ldai_compat import (
    LDAIMetrics,
    model_name,
    model_parameters,
    openai_agents_usage,
    provider_name,
    tool_names,
    tool_names_from_run_items,
)
from shared.tools import TOOL_REGISTRY


def _create_model(config):
    """Native OpenAI model string for OpenAI; everything else (incl. pinned Claude) via LiteLLM."""
    provider = provider_name(config).lower()
    model_id = model_name(config)
    if provider == "openai":
        return model_id
    api_key = os.environ.get("ANTHROPIC_API_KEY") if provider == "anthropic" else None
    return LitellmModel(model=f"{provider}/{model_id}", api_key=api_key)


def _bind_tools(config):
    """Bind this node's attached tools with the SDK's function_tool."""
    return [function_tool(TOOL_REGISTRY[n]) for n in tool_names(config) if n in TOOL_REGISTRY]


def _model_settings(config):
    """Carry the LD config's generation params into the run so the LiteLLM-backed model honors
    the node's max_tokens/temperature instead of LiteLLM's defaults — otherwise the synthesizer's
    long report truncates and the framework comparison is confounded (a truncated report is also
    faster + cheaper, so it would skew latency/cost, not just quality)."""
    params = model_parameters(config)
    max_tokens = params.get("max_tokens") or params.get("maxTokens")
    temperature = params.get("temperature")
    # GPT-5 and the o-series are reasoning models that reject a non-default temperature
    # ("Unsupported value: 'temperature'"), so omit it for them and let the model default hold.
    model_id = model_name(config).lower()
    if model_id.startswith("gpt-5") or model_id.startswith(("o1", "o3", "o4")):
        temperature = None
    # Token usage flows automatically on this path (litellm reports response.usage by
    # default for non-streaming calls), so no usage settings are needed here.
    return ModelSettings(
        temperature=temperature,
        max_tokens=int(max_tokens) if max_tokens else None,
    )


def build_agent(node_key, config, instructions):
    return Agent(
        name=node_key,
        instructions=instructions,
        model=_create_model(config),
        model_settings=_model_settings(config),
        tools=_bind_tools(config),
    )


def _extract_metrics(result):
    return LDAIMetrics(
        success=True,
        tokens=openai_agents_usage(result),
        tool_calls=tool_names_from_run_items(result.new_items) or None,
    )


async def invoke(agent, input_text, tracker):
    result = await tracker.track_metrics_of_async(
        _extract_metrics,
        lambda: Runner.run(agent, input_text, max_turns=20),
    )
    return (result.final_output or ""), openai_agents_usage(result)
