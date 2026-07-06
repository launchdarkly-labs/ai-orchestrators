"""
OpenAI Agents runner.

The Agents SDK runs OpenAI models natively; the pinned Claude model runs through LiteLLM,
the SDK's adapter for other providers. Tools are bound with the SDK's `function_tool`.
Everything dynamic still comes from the LD node config; the dispatcher owns the graph walk.
"""

import os

from agents import Agent, ModelSettings, Runner, function_tool
from agents.extensions.models.litellm_model import LitellmModel
from ldai.providers.types import LDAIMetrics
from ldai_openai import get_ai_usage_from_response
from ldai_openai.openai_helper import get_tool_calls_from_run_items

from shared.tools import TOOL_REGISTRY


def _create_model(config):
    """Native OpenAI model string for OpenAI; everything else (incl. pinned Claude) via LiteLLM."""
    provider = (config.provider.name if config.provider else "").lower()
    model_id = config.model.name
    if provider == "openai":
        return model_id
    api_key = os.environ.get("ANTHROPIC_API_KEY") if provider == "anthropic" else None
    return LitellmModel(model=f"{provider}/{model_id}", api_key=api_key)


def _bind_tools(config):
    """Bind this node's attached tools (config.tools) with the SDK's function_tool."""
    return [function_tool(TOOL_REGISTRY[n]) for n in (config.tools or {}) if n in TOOL_REGISTRY]


def _model_settings(config):
    """Carry the LD config's generation params into the run so the LiteLLM-backed model honors
    the node's max_tokens/temperature instead of LiteLLM's defaults — otherwise the synthesizer's
    long report truncates and the framework comparison is confounded (a truncated report is also
    faster + cheaper, so it would skew latency/cost, not just quality)."""
    params = dict(config.model.to_dict().get("parameters") or {})
    max_tokens = params.get("max_tokens") or params.get("maxTokens")
    temperature = params.get("temperature")
    # GPT-5 and the o-series are reasoning models that reject a non-default temperature
    # ("Unsupported value: 'temperature'"), so omit it for them and let the model default hold.
    model_id = (config.model.name or "").lower()
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
        tokens=get_ai_usage_from_response(result),
        tool_calls=get_tool_calls_from_run_items(result.new_items) or None,
    )


async def invoke(agent, input_text, tracker):
    result = await tracker.track_metrics_of_async(
        _extract_metrics,
        lambda: Runner.run(agent, input_text, max_turns=20),
    )
    return (result.final_output or ""), get_ai_usage_from_response(result)
