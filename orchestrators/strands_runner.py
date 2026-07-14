"""
Strands runner.

Per-node agent builder + invoke for the shared dispatcher. Strands binds directly: a
small provider-aware factory builds the model from the LD node config, and tools attach
with Strands' native ``@tool``. Everything dynamic comes from the LD node config (model,
attached tools, instructions); the dispatcher owns the walk.
"""

import os

from strands import Agent, tool as strands_tool
from strands.models.anthropic import AnthropicModel
from strands.models.openai import OpenAIModel
from strands.models.bedrock import BedrockModel
from ldai.tracker import TokenUsage
from ldai.providers.types import LDAIMetrics

from shared.tools import TOOL_REGISTRY


def _create_strands_model(config):
    """Map an LD node config to the matching Strands model class."""
    provider = (config.provider.name if config.provider else "").lower()
    model_id = config.model.name
    params = dict(config.model.to_dict().get("parameters") or {})
    params.pop("tools", None)  # tools live on config.tools, not model params

    if provider == "anthropic":
        # Default to 64k output so the synthesizer's long report isn't truncated.
        max_tokens = int(params.pop("max_tokens", None) or params.pop("maxTokens", None) or 64000)
        return AnthropicModel(model_id=model_id, max_tokens=max_tokens, params=params or None)
    if provider == "openai":
        return OpenAIModel(model_id=model_id, params=params or None)
    # Bedrock fallback (Strands via AWS). Any non-anthropic/openai provider (e.g. LD's "Bedrock")
    # lands here. Forward the LD config's max_tokens — Bedrock's converse default is tiny, and a
    # truncated agent loop raises Strands' unrecoverable MaxTokensReachedException (the synthesizer's
    # long report can't fit); default to 32k (Nova 2 Lite's max output) when the config doesn't say.
    region = params.pop("region_name", None) or os.environ.get("AWS_REGION") or "us-west-2"
    max_tokens = int(params.pop("max_tokens", None) or params.pop("maxTokens", None) or 32000)
    temperature = params.get("temperature")
    kwargs = {"max_tokens": max_tokens}
    if temperature is not None:
        kwargs["temperature"] = temperature
    return BedrockModel(model_id=_bedrock_profile_id(model_id, region), region_name=region, **kwargs)


def _bedrock_profile_id(model_id, region):
    """Bedrock serves newer foundation models (Claude 3.5+, Nova, Llama 3.x) on-demand ONLY via a
    cross-region inference profile, whose id is the bare model id with a geo prefix (us./eu./apac.).
    LD's model catalog stores the BARE id (e.g. anthropic.claude-sonnet-4-5-20250929-v1:0), so
    invoking it directly raises a ValidationException. Prepend the geo for the region if absent."""
    if model_id.split(".", 1)[0] in ("us", "eu", "apac"):
        return model_id  # already an inference-profile id
    geo = "eu" if region.startswith("eu-") else "apac" if region.startswith("ap-") else "us"
    return f"{geo}.{model_id}"


def _bind_tools(config):
    """Bind this node's attached tools (config.tools) with Strands' native @tool."""
    return [strands_tool(TOOL_REGISTRY[n]) for n in (config.tools or {}) if n in TOOL_REGISTRY]


def build_agent(node_key, config, instructions):
    """Build a Strands Agent from an LD node config."""
    return Agent(
        name=node_key,
        model=_create_strands_model(config),
        system_prompt=instructions or "Process the input and respond.",
        tools=_bind_tools(config),
        callback_handler=None,
    )


def _message_text(result):
    """Concatenate the text blocks of a Strands result message.

    The final message's content is a list of blocks; the first block is not guaranteed
    to be text (it can lead with a toolUse/toolResult block, or be empty), so indexing
    ``content[0]["text"]`` blindly raises KeyError/IndexError. Join every text block.
    """
    content = (getattr(result, "message", None) or {}).get("content") or []
    return "".join(b["text"] for b in content if isinstance(b, dict) and "text" in b)


def _usage(result):
    usage = getattr(result.metrics, "accumulated_usage", {}) or {}
    in_tok = usage.get("inputTokens", 0)
    out_tok = usage.get("outputTokens", 0)
    total = usage.get("totalTokens", 0) or (in_tok + out_tok)
    return in_tok, out_tok, total


def _extract_metrics(result):
    in_tok, out_tok, total = _usage(result)
    tool_calls = []
    for tool_name, tm in (result.metrics.tool_metrics or {}).items():
        tool_calls.extend([tool_name] * tm.call_count)
    return LDAIMetrics(
        success=True,
        tokens=TokenUsage(input=in_tok, output=out_tok, total=total) if total else None,
        tool_calls=tool_calls or None,
    )


async def invoke(agent, input_text, tracker):
    """Invoke the agent; `track_metrics_of_async` records duration + success + tokens."""
    result = await tracker.track_metrics_of_async(
        _extract_metrics,
        lambda: agent.invoke_async(input_text),
    )
    text = _message_text(result)
    in_tok, out_tok, total = _usage(result)
    return text, TokenUsage(input=in_tok, output=out_tok, total=total)
