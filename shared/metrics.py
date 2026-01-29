"""
Shared metrics tracking utilities for all orchestrators.
Provides consistent LaunchDarkly custom metric tracking across all implementations.
"""

from typing import Dict, Any, Optional
from ldclient import Context


def track_generation_metrics(
    ld_client,
    context: Context,
    agent_key: str,
    model: str,
    duration_ms: float,
    orchestrator: str
) -> None:
    """
    Track generation count and duration metrics.

    Args:
        ld_client: LaunchDarkly client
        context: LaunchDarkly context
        agent_key: Agent identifier
        model: Model identifier
        duration_ms: Generation duration in milliseconds
        orchestrator: Orchestrator name
    """
    # Track generation count
    ld_client.track(
        "ai.generation.count",
        context=context,
        data={"orchestrator": orchestrator, "agent": agent_key, "model": model},
        metric_value=1
    )

    # Track generation duration
    ld_client.track(
        "ai.generation.duration_ms",
        context=context,
        data={"orchestrator": orchestrator, "agent": agent_key, "model": model},
        metric_value=duration_ms
    )


def track_token_metrics(
    ld_client,
    context: Context,
    agent_key: str,
    model: str,
    input_tokens: int,
    output_tokens: int,
    orchestrator: str
) -> None:
    """
    Track token usage metrics.

    Args:
        ld_client: LaunchDarkly client
        context: LaunchDarkly context
        agent_key: Agent identifier
        model: Model identifier
        input_tokens: Number of input tokens
        output_tokens: Number of output tokens
        orchestrator: Orchestrator name
    """
    # Track total tokens
    ld_client.track(
        "ai.tokens.total",
        context=context,
        data={"orchestrator": orchestrator, "agent": agent_key, "model": model},
        metric_value=input_tokens + output_tokens
    )

    # Track input tokens
    ld_client.track(
        "ai.tokens.input",
        context=context,
        data={"orchestrator": orchestrator, "agent": agent_key, "model": model},
        metric_value=input_tokens
    )

    # Track output tokens
    ld_client.track(
        "ai.tokens.output",
        context=context,
        data={"orchestrator": orchestrator, "agent": agent_key, "model": model},
        metric_value=output_tokens
    )


def track_cost_metric(
    ld_client,
    context: Context,
    agent_key: str,
    model: str,
    cost: float,
    orchestrator: str
) -> None:
    """
    Track calculated cost metric.

    Args:
        ld_client: LaunchDarkly client
        context: LaunchDarkly context
        agent_key: Agent identifier
        model: Model identifier
        cost: Calculated cost in dollars
        orchestrator: Orchestrator name
    """
    ld_client.track(
        "ai.calculated_cost",
        context=context,
        data={"orchestrator": orchestrator, "agent": agent_key, "model": model},
        metric_value=cost
    )


def track_all_metrics(
    ld_client,
    context: Context,
    agent_key: str,
    model: str,
    input_tokens: int,
    output_tokens: int,
    cost: float,
    duration_ms: float,
    orchestrator: str
) -> None:
    """
    Track all metrics at once for convenience.

    Args:
        ld_client: LaunchDarkly client
        context: LaunchDarkly context
        agent_key: Agent identifier
        model: Model identifier
        input_tokens: Number of input tokens
        output_tokens: Number of output tokens
        cost: Calculated cost in dollars
        duration_ms: Generation duration in milliseconds
        orchestrator: Orchestrator name
    """
    # Track generation metrics
    track_generation_metrics(
        ld_client=ld_client,
        context=context,
        agent_key=agent_key,
        model=model,
        duration_ms=duration_ms,
        orchestrator=orchestrator
    )

    # Track token metrics
    track_token_metrics(
        ld_client=ld_client,
        context=context,
        agent_key=agent_key,
        model=model,
        input_tokens=input_tokens,
        output_tokens=output_tokens,
        orchestrator=orchestrator
    )

    # Track cost metric
    track_cost_metric(
        ld_client=ld_client,
        context=context,
        agent_key=agent_key,
        model=model,
        cost=cost,
        orchestrator=orchestrator
    )