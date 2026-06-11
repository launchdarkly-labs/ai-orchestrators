"""
Google ADK runner.

ADK is multi-agent-native (Gemini); Experiment A's pinned Claude model runs via
``LiteLlm``. ADK's runtime is session/event-based, so `invoke` runs the node's agent
through an `InMemoryRunner` and collects the final response + token usage from the event
stream. Tools are plain callables (ADK wraps them). The dispatcher owns the graph walk.
"""

import re

from google.adk.agents import Agent
from google.adk.models.lite_llm import LiteLlm
from google.adk.runners import InMemoryRunner
from google.genai import types

from ldai.tracker import TokenUsage
from ldai.providers.types import LDAIMetrics

from shared.tools import TOOL_REGISTRY

_APP = "gap-analysis"


def _model(config):
    """Native Gemini model string for Google; everything else (incl. pinned Claude) via LiteLlm.

    Forward the LD config's generation params (max_tokens, temperature) to litellm so the pinned
    model honors them instead of LiteLLM's defaults — otherwise the synthesizer's long report
    truncates and the comparison is confounded (a truncated report is also faster + cheaper)."""
    provider = (config.provider.name if config.provider else "").lower()
    model_id = config.model.name
    if provider in ("google", "gemini"):
        return model_id
    params = dict(config.model.to_dict().get("parameters") or {})
    kwargs = {}
    max_tokens = params.get("max_tokens") or params.get("maxTokens")
    if max_tokens:
        kwargs["max_tokens"] = int(max_tokens)
    if params.get("temperature") is not None:
        kwargs["temperature"] = params["temperature"]
    return LiteLlm(model=f"{provider}/{model_id}", **kwargs)


def _safe_name(key):
    # ADK agent names must be valid identifiers (no hyphens).
    return re.sub(r"[^a-zA-Z0-9_]", "_", key)


def _bind_tools(config):
    """Bind this node's attached tools (config.tools) as plain callables (ADK wraps them)."""
    return [TOOL_REGISTRY[n] for n in (config.tools or {}) if n in TOOL_REGISTRY]


def build_agent(node_key, config, instructions):
    return Agent(
        name=_safe_name(node_key),
        model=_model(config),
        instruction=instructions or "Process the input and respond.",
        tools=_bind_tools(config),
    )


async def invoke(agent, input_text, tracker):
    async def _run():
        runner = InMemoryRunner(agent=agent, app_name=_APP)
        session = await runner.session_service.create_session(app_name=_APP, user_id="harness")
        content = types.Content(role="user", parts=[types.Part(text=input_text)])
        final_text, in_tok, out_tok = "", 0, 0
        async for event in runner.run_async(
            user_id="harness", session_id=session.id, new_message=content
        ):
            um = getattr(event, "usage_metadata", None)
            if um:
                in_tok += getattr(um, "prompt_token_count", 0) or 0
                out_tok += getattr(um, "candidates_token_count", 0) or 0
            if event.is_final_response() and event.content and event.content.parts:
                final_text = event.content.parts[0].text or final_text
        return final_text, in_tok, out_tok

    text, in_tok, out_tok = await tracker.track_metrics_of_async(
        # No final-response event with content means the run produced nothing usable;
        # record it as a failed invocation rather than a silent success scored by the judge.
        lambda r: LDAIMetrics(
            success=bool((r[0] or "").strip()),
            tokens=TokenUsage(input=r[1], output=r[2], total=r[1] + r[2]) if (r[1] or r[2]) else None,
        ),
        _run,
    )
    return text, TokenUsage(input=in_tok, output=out_tok, total=in_tok + out_tok)
