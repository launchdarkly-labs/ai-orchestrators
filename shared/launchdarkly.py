"""
Shared LaunchDarkly initialization and configuration utilities.
Provides common functions for initializing LaunchDarkly clients and fetching agent configs.
"""

import os
import requests
from typing import Dict, List, Tuple, Any
import ldclient
from ldclient.config import Config
from launchdarkly_ai_server import init_client, inspect_config

# ConfigTracker replaces the retired `config.tracker`. It lives in ldai_compat because the
# orchestrator arms on this branch need the same tracker plus graph-level tracking; on main
# it is defined here instead. Same class, same event keys, one definition.
from shared.ldai_compat import ConfigTracker


async def init_launchdarkly_clients(sdk_key: str = None, send_events: bool = True, flush_interval: int = 5) -> Tuple[Any, Any]:
    """
    Initialize LaunchDarkly SDK and AI clients.

    Args:
        sdk_key: LaunchDarkly SDK key (defaults to env var LD_SDK_KEY)
        send_events: Whether to send events to LaunchDarkly
        flush_interval: Event flush interval in seconds

    Returns:
        Tuple of (ld_client, ld_client)

    The second element used to be an LDAIClient. There is no such object now --
    the AI SDK keeps a single global client, which this hands it -- so both
    elements are the same client and the tuple shape is kept only so the
    runners' unpacking still works.

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

    # Hand the client built here to the AI SDK rather than letting it build
    # its own, so AI reads and the runners' direct track() calls share one.
    await init_client(client=ld_client)
    return ld_client, ld_client


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
) -> Dict[str, Any]:
    """
    Create a LaunchDarkly context with standard attributes.

    Args:
        execution_id: Unique execution identifier (used as context key)
        orchestrator: Orchestrator name (optional)
        agent: Agent key (optional)
        **additional_attrs: Any additional attributes to set on the context

    Returns:
        A LaunchDarkly context dict -- contexts are plain dicts now, there is
        no builder.
    """
    context: Dict[str, Any] = {"kind": "user", "key": execution_id}

    if orchestrator:
        context["orchestrator"] = orchestrator

    if agent:
        context["agent"] = agent

    context.update(additional_attrs)

    return context


def build_agent_requests(items: List[Dict[str, Any]]) -> Tuple[List[str], Dict[str, str]]:
    """
    Build AI agent config requests from LaunchDarkly items.

    Args:
        items: List of items from LaunchDarkly API

    Returns:
        Tuple of (agent_keys list, agent_metadata dict mapping key -> name)

    These were AIAgentConfigRequest objects carrying a disabled default.
    Neither exists now -- configs are fetched a key at a time and there is no
    `default=` to attach -- so the first element is just the keys.
    """
    agent_keys = []
    agent_metadata = {}

    for item in items:
        key = item.get("key")
        if not key:
            continue
        name = (item.get("name") or key).strip()
        agent_metadata[key] = name
        agent_keys.append(key)

    return agent_keys, agent_metadata


async def fetch_agent_config(agent_key: str, context: Dict[str, Any]):
    """Fetch one agent config and a tracker for it.

    Returns (config, tracker), or (None, None) when the config is not served.
    inspect_config reads the variation without invoking a model, which is what
    these runners need: they drive their own frameworks and only want the
    model name, instructions, and parameters.
    """
    inspected = await inspect_config(agent_key, context)
    if not inspected["enabled"] or not inspected["config"]:
        return None, None
    config = inspected["config"]
    return config, ConfigTracker(agent_key, config, inspected["meta"] or {}, context)


async def fetch_agent_configs(agent_keys: List[str], context: Dict[str, Any]) -> Dict[str, Any]:
    """Fetch several agent configs.

    Replaces ai_client.agent_configs(), which took a batch of requests. The
    current SDK has no batch call, so this loops. Disabled or unserved keys are
    omitted, matching how callers already treat a missing entry.
    """
    configs: Dict[str, Any] = {}
    for key in agent_keys:
        config, tracker = await fetch_agent_config(key, context)
        if config is not None:
            configs[key] = {"config": config, "tracker": tracker}
    return configs