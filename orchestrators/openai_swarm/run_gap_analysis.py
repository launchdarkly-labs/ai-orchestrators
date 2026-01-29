#!/usr/bin/env python3
"""
Run research gap analysis using OpenAI Swarm orchestrator.
Processes papers through the multi-agent system to generate gap analysis report with metadata.

GOAL: MINIMAL CODE - Show how clean it is when agent configs come from LaunchDarkly!
Target: < 180 lines (Refined Strands: 299 lines = 40% reduction)

OpenAI Swarm should be the CLEANEST, SIMPLEST implementation of all frameworks.
"""

import json
import sys
import os
import argparse
from pathlib import Path
from datetime import datetime
from dotenv import load_dotenv

# Load environment variables
project_root = Path(__file__).parent.parent.parent
load_dotenv(project_root / '.env')

# Add parent directories to path
sys.path.insert(0, str(project_root))
sys.path.insert(0, str(project_root / 'shared'))
sys.path.insert(0, str(project_root / 'shared' / 'tools'))

# Shared imports
from shared.metadata import create_execution_metadata, AgentConfig
from shared.launchdarkly import init_launchdarkly_clients, fetch_agent_configs_from_api, create_context, build_agent_requests
from shared.pricing import PRICING, calculate_cost
from shared.prompt import build_paper_prompt
from shared.metrics import track_generation_metrics, track_token_metrics, track_cost_metric
from shared.tools import common as common_tools

# LaunchDarkly imports
from ldai.client import AIAgentConfigDefault
from ldai.tracker import TokenUsage


def init_tracking_clients():
    """Initialize LaunchDarkly standard and AI clients for dual tracking."""
    return init_launchdarkly_clients()




def get_agent_config_with_tracker(ai_client, agent_key: str, context, orchestrator_name: str):
    """Fetch agent config from LaunchDarkly AI SDK with tracker for dual tracking."""
    config = ai_client.agent_config(
        key=agent_key,
        context=context,
        default_value=AIAgentConfigDefault(enabled=False)
    )
    return config, config.tracker




def run_openai_swarm():
    """Run OpenAI Swarm gap analysis with LaunchDarkly tracking."""
    import time
    from collections import defaultdict
    from typing import get_origin, get_args
    import inspect
    import swarm.core as swarm_core
    import swarm.util as swarm_util

    parser = argparse.ArgumentParser(description="Run OpenAI Swarm gap analysis")
    parser.add_argument("--papers-json", type=str, required=True, help="Path to JSON papers dataset to format.")
    args = parser.parse_args()

    print("╔═══════════════════════════════════════════════════════╗")
    print("║  Research Gap Analysis - OpenAI Swarm Orchestrator    ║")
    print("╚═══════════════════════════════════════════════════════╝\n")

    papers_file = Path(args.papers_json)
    if not papers_file.exists():
        print(f"❌ Papers JSON not found: {papers_file}")
        return

    with open(papers_file) as f:
        papers = json.load(f)

    if not papers:
        print("❌ No papers in dataset")
        return

    print(f"📚 Loaded {len(papers)} papers")
    print()

    print("Papers to analyze:")
    for idx, paper in enumerate(papers, 1):
        print(f"  [{idx}] {paper['title'][:70]}...")
        print(f"      Authors: {paper['authors'][:50]}")
        print(f"      Published: {paper['published']}")
    print()

    # Format prompt
    prompt = build_paper_prompt(papers, include_arxiv=True)
    if not prompt.strip():
        print("❌ Papers JSON produced empty prompt.")
        return

    print("="*60)
    print("🔄 Starting OpenAI Swarm...")
    print("="*60)
    print()

    # Initialize LaunchDarkly tracking clients
    print("📡 Initializing LaunchDarkly tracking clients...")
    ld_client, ai_client = init_tracking_clients()
    print("✓ Tracking clients initialized\n")

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    execution_id = f"openai-swarm-{timestamp}"

    # Fetch agent list from LaunchDarkly API
    items = fetch_agent_configs_from_api()
    print(f"Found {len(items)} AI config(s) in LaunchDarkly")

    # Build requests for all agents
    agent_requests, agent_metadata = build_agent_requests(items)

    name_by_key = {item["key"]: item["name"] for item in items}
    key_by_name = {item["name"]: item["key"] for item in items}

    # Create THE context - use execution_id as key for proper tracking
    context = create_context(execution_id, orchestrator="openai_swarm")

    # Get all configs using the agent requests
    configs = ai_client.agent_configs(agent_requests, context)

    agent_configs_with_trackers = {}
    agents = []
    enabled_keys = []
    agent_specs = []

    print("📡 Fetching agent configs with trackers from LaunchDarkly AI SDK...")
    for item in items:
        agent_key = item["key"]
        config = configs.get(agent_key)
        if not config or not config.enabled:
            continue

        enabled_keys.append(agent_key)
        model_id = config.model.name if config.model else 'unknown'

        # Create context for this agent
        agent_context = create_context(execution_id, orchestrator="openai_swarm", agent=agent_key)

        agent_configs_with_trackers[agent_key] = {
            'config': config,
            'tracker': config.tracker,
            'context': agent_context
        }

        config_dict = config.to_dict()
        tools = []
        if 'model' in config_dict and 'parameters' in config_dict['model']:
            tools_data = config_dict['model']['parameters'].get('tools', [])
            for tool in tools_data:
                if isinstance(tool, dict):
                    tools.append(tool.get('name', str(tool)))
                else:
                    tools.append(str(tool))

        instructions = config.instructions if hasattr(config, 'instructions') else ''

        agents.append(AgentConfig(
            key=agent_key,
            name=name_by_key.get(agent_key, agent_key),
            role=name_by_key.get(agent_key, agent_key),
            model=model_id,
            provider=config.provider.name if config.provider else 'unknown',
            temperature=0.0,
            tools=tools,
            instructions_preview=instructions[:200] if instructions else ''
        ))

        agent_specs.append({
            "key": agent_key,
            "name": name_by_key.get(agent_key, agent_key),
            "instructions": instructions or "",
            "tools": tools,
        })

        print(f"  ✓ Fetched config + tracker for {agent_key}")

    if not agent_specs:
        print("❌ No enabled agent configs found in LaunchDarkly.")
        return

    entry_point_key = enabled_keys[0]
    print(f"✓ Found {len(agent_specs)} enabled agent configs\n")

    # Create swarm helper function (merged from swarm_factory.py)
    def create_swarm_from_launchdarkly(agent_specs, entry_point_key: str):
        """
        Creates an OpenAI Swarm with agents dynamically fetched from LaunchDarkly.

        Args:
            agent_specs: List of agent specifications
            entry_point_key: Agent key to use as entry point

        Returns:
            Tuple of (Swarm client, entry_agent, agent_dict)
        """
        from swarm import Swarm, Agent

        if not agent_specs:
            raise RuntimeError("No agent specs provided for swarm creation.")

        # Import tool factory for dynamic loading
        from factory import get_tool

        # First pass: Create Agent objects without handoffs
        agent_dict = {}
        agents_by_key = {}
        agent_specs_by_key = {}

        for spec in agent_specs:
            # Get tools for this agent using factory - NO hardcoded names
            agent_tools = []
            handoff_tool_name = None
            for tool_name in spec.get("tools", []):
                try:
                    tool_func = get_tool('openai_swarm', tool_name)
                    if tool_func:
                        tool_def = getattr(common_tools, tool_name, None)
                        if tool_def and getattr(tool_def, "_is_handoff_tool", False):
                            handoff_tool_name = tool_name
                            print(f"    ℹ️  Using '{tool_name}' as handoff tool for {spec['name']}")
                        else:
                            agent_tools.append(tool_func)
                            print(f"    ✓ Loaded tool '{tool_name}' for {spec['name']}")
                    else:
                        print(f"    ⚠️  Tool '{tool_name}' not found in factory for {spec['name']}")
                except Exception as e:
                    print(f"    ⚠️  Could not load tool '{tool_name}' for {spec['name']}: {e}")

            # Create agent without handoffs initially (will add handoffs in second pass)
            instructions = spec.get("instructions") or ""
            agent = Agent(
                name=spec["name"],
                instructions=instructions or f"You are {spec['name']}",
                functions=agent_tools  # Will add handoffs later
            )

            # Use config.key directly from LaunchDarkly instead of hardcoded mapping
            agent_dict[spec["key"]] = agent
            agents_by_key[spec["key"]] = agent
            agent_specs_by_key[spec["key"]] = {
                "key": spec["key"],
                "name": spec["name"],
                "handoff_tool_name": handoff_tool_name,
            }

            print(f"    ✓ Created agent: {spec['name']}")

        # Second pass: Create handoff router from LaunchDarkly tool name
        name_to_agent = {agent.name: agent for agent in agent_dict.values()}
        key_to_agent = {key: agent for key, agent in agent_dict.items()}

        for agent_key, agent in agent_dict.items():
            spec = agent_specs_by_key.get(agent_key, {})
            handoff_tool_name = spec.get("handoff_tool_name")
            if not handoff_tool_name:
                if len(agent_dict) > 1:
                    print(f"⚠️  No handoff tool configured for {agent.name}; handoff will be unavailable.")
                continue

            def create_handoff_router(tool_name):
                def handoff_router(agent_name: str, message: str = ""):
                    """Transfer control to another agent."""
                    target = key_to_agent.get(agent_name) or name_to_agent.get(agent_name)
                    if not target:
                        raise ValueError(f"Unknown agent: {agent_name}")
                    return target
                handoff_router.__name__ = tool_name
                return handoff_router

            handoff_func = create_handoff_router(handoff_tool_name)
            agent.functions = (agent.functions or []) + [handoff_func]
            print(f"    ✓ Added handoff tool '{handoff_tool_name}' to {agent.name}")

        # Determine entry point
        entry_agent = agents_by_key.get(entry_point_key)
        if not entry_agent:
            print(f"⚠️  Entry point '{entry_point_key}' not found, using first agent")
            entry_agent = list(agent_dict.values())[0]

        print(f"✓ Entry point: {entry_agent.name}")

        # Create Swarm client
        client = Swarm()

        return client, entry_agent, agent_dict

    def function_to_json_with_items(func) -> dict:
        """Patch Swarm tool schemas to include array items."""
        type_map = {
            str: "string",
            int: "integer",
            float: "number",
            bool: "boolean",
            list: "array",
            dict: "object",
            type(None): "null",
        }

        signature = inspect.signature(func)
        parameters = {}
        for param in signature.parameters.values():
            param_type = param.annotation
            origin = get_origin(param_type)
            args = get_args(param_type)

            if param_type == list or origin == list:
                item_type = args[0] if args else str
                item_type_name = type_map.get(item_type, "string")
                parameters[param.name] = {
                    "type": "array",
                    "items": {"type": item_type_name}
                }
            else:
                param_type_name = type_map.get(param_type, "string")
                parameters[param.name] = {"type": param_type_name}

        required = [
            param.name
            for param in signature.parameters.values()
            if param.default == inspect._empty
        ]

        return {
            "type": "function",
            "function": {
                "name": func.__name__,
                "description": func.__doc__ or "",
                "parameters": {
                    "type": "object",
                    "properties": parameters,
                    "required": required,
                },
            },
        }

    result = None
    swarm_error = None
    execution_time = 0.0
    iterations = 0
    output = ""
    per_agent_metrics = {key: {"input_tokens": 0, "output_tokens": 0, "total_tokens": 0, "duration": 0.0} for key in enabled_keys}
    executed_agents = set()

    try:
        print("🔨 Creating OpenAI Swarm from LaunchDarkly configs...")
        swarm_util.function_to_json = function_to_json_with_items
        swarm_core.function_to_json = function_to_json_with_items

        client, entry_agent, agent_dict = create_swarm_from_launchdarkly(
            agent_specs=agent_specs,
            entry_point_key=entry_point_key
        )
        print("✓ Swarm created successfully\n")

        original_get_chat_completion = client.get_chat_completion

        def tracked_get_chat_completion(agent, history, context_variables, model_override, stream, debug):
            start_call = time.time()
            completion = original_get_chat_completion(
                agent=agent,
                history=history,
                context_variables=context_variables,
                model_override=model_override,
                stream=stream,
                debug=debug,
            )
            duration = time.time() - start_call
            agent_key = key_by_name.get(agent.name, agent.name)
            usage = getattr(completion, "usage", None)
            if usage:
                input_tokens = int(getattr(usage, "prompt_tokens", 0))
                output_tokens = int(getattr(usage, "completion_tokens", 0))
                total_tokens = int(getattr(usage, "total_tokens", input_tokens + output_tokens))
            else:
                input_chars = sum(len(msg.get("content", "")) for msg in history if isinstance(msg, dict))
                output_content = getattr(completion.choices[0].message, "content", "") or ""
                input_tokens = int(input_chars / 4)
                output_tokens = int(len(output_content) / 4)
                total_tokens = input_tokens + output_tokens

            metrics = per_agent_metrics.setdefault(agent_key, {"input_tokens": 0, "output_tokens": 0, "total_tokens": 0, "duration": 0.0})
            metrics["input_tokens"] += input_tokens
            metrics["output_tokens"] += output_tokens
            metrics["total_tokens"] += total_tokens
            metrics["duration"] += duration
            executed_agents.add(agent_key)
            return completion

        client.get_chat_completion = tracked_get_chat_completion

        print("🚀 Running swarm...")
        start_time = time.time()
        result = client.run(agent=entry_agent, messages=[{"role": "user", "content": prompt}])
        execution_time = time.time() - start_time

    except Exception as e:
        swarm_error = e
        execution_time = time.time() - start_time if 'start_time' in locals() else 0.0
        print(f"❌ Error running swarm: {e}")
        import traceback
        traceback.print_exc()

    print("\n" + "="*60)
    print("✨ Gap analysis complete!")
    print("="*60 + "\n")

    if result is not None and hasattr(result, "messages"):
        for msg in result.messages:
            if msg.get("role") == "assistant" and msg.get("content"):
                output = msg["content"]
        iterations = sum(1 for msg in result.messages if msg.get("role") == "assistant")

    if not output:
        if swarm_error:
            output = f"Swarm failed before final output. Error: {swarm_error}"
        else:
            output = "No final agent output available."

    print(output + "\n")

    for agent_key, agent_data in agent_configs_with_trackers.items():
        context = agent_data['context']
        config = agent_data['config']
        model_id = config.model.name if config and hasattr(config, 'model') else 'unknown'

        metrics = per_agent_metrics.get(agent_key, {})
        input_tokens = int(metrics.get("input_tokens", 0))
        output_tokens = int(metrics.get("output_tokens", 0))
        total_tokens = int(metrics.get("total_tokens", 0))
        duration = float(metrics.get("duration", 0.0))
        cost = calculate_cost(model_id, input_tokens, output_tokens)

        # Skip agents that didn't run
        if total_tokens == 0:
            continue

        # Get FRESH config and tracker for this specific agent
        # This is REQUIRED per LaunchDarkly docs - must not reuse trackers
        fresh_config = ai_client.agent_config(
            key=agent_key,
            context=context,  # Use context with both orchestrator and agent
            default_value=AIAgentConfigDefault(enabled=False)
        )

        # Use the fresh tracker from this new config evaluation
        tracker = fresh_config.tracker

        # Track tokens - AI SDK automatically adds agent attribute
        tracker.track_tokens(TokenUsage(input=input_tokens, output=output_tokens, total=total_tokens))

        # Track duration
        if duration > 0:
            tracker.track_duration(duration)

        # Track time to first token if available (estimate as 10% of duration)
        if duration > 0 and agent_key in executed_agents:
            ttft = duration * 0.1  # Estimate 10% of duration for first token
            tracker.track_time_to_first_token(ttft)

        # Track success/error
        if swarm_error:
            tracker.track_error()
        else:
            tracker.track_success()

        # Debug logging to verify correct values
        print(f"   DEBUG: Tracking metrics for {agent_key}:")
        print(f"      Tokens: {total_tokens}")
        print(f"      Duration: {duration:.3f}s")
        print(f"      Cost: ${cost:.4f}")

        # Track generation metrics
        if duration > 0:
            track_generation_metrics(
                ld_client=ld_client,
                context=context,
                agent_key=agent_key,
                model=model_id,
                duration_ms=duration * 1000,  # Convert to ms
                orchestrator="openai_swarm"
            )

        # Track token metrics
        if total_tokens > 0:
            track_token_metrics(
                ld_client=ld_client,
                context=context,
                agent_key=agent_key,
                model=model_id,
                input_tokens=input_tokens,
                output_tokens=output_tokens,
                orchestrator="openai_swarm"
            )

        # Track cost metric
        if model_id and model_id in PRICING:
            track_cost_metric(
                ld_client=ld_client,
                context=context,
                agent_key=agent_key,
                model=model_id,
                cost=cost,
                orchestrator="openai_swarm"
            )

    print("  ✓ Tracked to AI Config Monitoring")
    ld_client.flush()

    print(f"📊 Execution time: {execution_time:.2f}s")
    print(f"🔄 Total iterations: {iterations}\n")

    metadata = create_execution_metadata(
        orchestrator_name="OpenAI-Swarm",
        orchestrator_version="1.0.0",
        execution_time_seconds=execution_time,
        total_iterations=iterations,
        agents=agents,
        input_papers_count=len(papers)
    )

    for agent_key, metrics in per_agent_metrics.items():
        metadata.add_tokens(
            agent_name=name_by_key.get(agent_key, agent_key),
            tokens=int(metrics.get("total_tokens", 0))
        )

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    results_dir = project_root / "results" / "openai_swarm"
    results_dir.mkdir(parents=True, exist_ok=True)
    report_file = results_dir / f"{timestamp}_{execution_id}_report.txt"

    execution_summary_lines = ["=== AGENT EXECUTION ===", ""]
    for agent_key in enabled_keys:
        agent_name = name_by_key.get(agent_key, agent_key)
        metrics = per_agent_metrics.get(agent_key, {})
        total_tokens = int(metrics.get("total_tokens", 0))
        duration = float(metrics.get("duration", 0.0))
        ran = "yes" if agent_key in executed_agents else "no"
        execution_summary_lines.append(
            f"- {agent_name} [{agent_key}]: ran={ran}, tokens={total_tokens}, duration={duration:.2f}s"
        )
    execution_summary = "\n".join(execution_summary_lines)

    with open(report_file, 'w') as f:
        f.write(metadata.to_report_section())
        f.write("\n\n")
        f.write(execution_summary)
        f.write("\n\n")
        f.write(output)

    print(f"📝 Report saved to: {report_file}")

    metadata_file = results_dir / f"{timestamp}_{execution_id}_metadata.json"
    with open(metadata_file, 'w') as f:
        f.write(metadata.to_json())
    print(f"📊 Metadata saved to: {metadata_file}")

    print("\n🔒 Closing LaunchDarkly client...")
    ld_client.close()
    print("✓ Client closed\n")


if __name__ == "__main__":
    run_openai_swarm()