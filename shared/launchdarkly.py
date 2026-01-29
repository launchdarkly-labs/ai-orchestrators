"""
Shared LaunchDarkly initialization and configuration utilities.
Provides common functions for initializing LaunchDarkly clients and fetching agent configs.
"""

import os
import requests
from typing import Dict, List, Tuple, Any
import ldclient
from ldclient import Context
from ldclient.config import Config
from ldai.client import LDAIClient, AIAgentConfigRequest, AIAgentConfigDefault


def init_launchdarkly_clients(sdk_key: str = None, send_events: bool = True, flush_interval: int = 5) -> Tuple[Any, Any]:
    """
    Initialize LaunchDarkly SDK and AI clients.

    Args:
        sdk_key: LaunchDarkly SDK key (defaults to env var LD_SDK_KEY)
        send_events: Whether to send events to LaunchDarkly
        flush_interval: Event flush interval in seconds

    Returns:
        Tuple of (ld_client, ai_client)

    Raises:
        ValueError: If SDK key is not found
        RuntimeError: If LaunchDarkly fails to initialize
    """
    if not sdk_key:
        sdk_key = os.getenv('LD_SDK_KEY')
        if not sdk_key:
            raise ValueError("LD_SDK_KEY not found")

    config = Config(sdk_key=sdk_key, send_events=send_events, flush_interval=flush_interval)
    ldclient.set_config(config)
    ld_client = ldclient.get()

    # Wait for initialization (up to 5 seconds)
    import time
    for i in range(10):
        if ld_client.is_initialized():
            break
        time.sleep(0.5)

    if not ld_client.is_initialized():
        raise RuntimeError("LaunchDarkly failed to initialize after 5 seconds")

    ai_client = LDAIClient(ld_client)
    return ld_client, ai_client


def fetch_agent_configs_from_api(
    ld_api_key: str = None,
    project_key: str = None,
    timeout: int = 30
) -> List[Dict[str, Any]]:
    """
    Fetch agent configurations from LaunchDarkly API.

    Args:
        ld_api_key: LaunchDarkly API key (defaults to env var LD_API_KEY)
        project_key: LaunchDarkly project key (defaults to env var LAUNCHDARKLY_PROJECT_KEY)
        timeout: Request timeout in seconds

    Returns:
        List of agent configuration items from LaunchDarkly

    Raises:
        ValueError: If API key is not found
        RuntimeError: If no AI configs are found
        requests.exceptions.RequestException: If API request fails
    """
    if not ld_api_key:
        ld_api_key = os.getenv('LD_API_KEY')
        if not ld_api_key:
            raise ValueError("LD_API_KEY not found")

    if not project_key:
        project_key = os.getenv('LD_AGENTS_PROJECT_KEY', 'orchestrator-agents')

    url = f"https://app.launchdarkly.com/api/v2/projects/{project_key}/ai-configs"
    headers = {"Authorization": ld_api_key}

    response = requests.get(url, headers=headers, timeout=timeout)
    response.raise_for_status()
    data = response.json()
    items = data.get("items", [])

    if not items:
        raise RuntimeError(f"No AI configs found in project {project_key}")

    return items


def create_context(
    execution_id: str,
    orchestrator: str = None,
    agent: str = None,
    **additional_attrs
) -> Context:
    """
    Create a LaunchDarkly context with standard attributes.

    Args:
        execution_id: Unique execution identifier (used as context key)
        orchestrator: Orchestrator name (optional)
        agent: Agent key (optional)
        **additional_attrs: Any additional attributes to set on the context

    Returns:
        LaunchDarkly Context object
    """
    builder = Context.builder(execution_id).kind("user")

    if orchestrator:
        builder.set("orchestrator", orchestrator)

    if agent:
        builder.set("agent", agent)

    for key, value in additional_attrs.items():
        builder.set(key, value)

    return builder.build()


def build_agent_requests(items: List[Dict[str, Any]]) -> Tuple[List[Any], Dict[str, str]]:
    """
    Build AI agent config requests from LaunchDarkly items.

    Args:
        items: List of items from LaunchDarkly API

    Returns:
        Tuple of (agent_requests list, agent_metadata dict mapping key -> name)
    """
    agent_requests = []
    agent_metadata = {}

    for item in items:
        key = item.get("key")
        if not key:
            continue
        name = (item.get("name") or key).strip()
        agent_metadata[key] = name
        agent_requests.append(
            AIAgentConfigRequest(
                key=key,
                default_value=AIAgentConfigDefault(enabled=False)
            )
        )

    return agent_requests, agent_metadata