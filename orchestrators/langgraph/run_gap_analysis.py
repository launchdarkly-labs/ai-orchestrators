#!/usr/bin/env python3
"""
LangGraph Research Gap Analysis
Fetches agent configs from LaunchDarkly once and tracks metrics
"""

import json
import argparse
import sys
import os
import time
import asyncio
import re
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Any, Tuple, Optional, Annotated

# Load environment variables
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))
sys.path.insert(0, str(project_root / 'shared'))
sys.path.insert(0, str(project_root / 'shared' / 'tools'))

from dotenv import load_dotenv
load_dotenv(project_root / '.env')

# LaunchDarkly imports
from ldai.client import AIAgentConfigDefault
from ldai.tracker import TokenUsage

# LangGraph imports
from langchain.chat_models import init_chat_model
from langchain.agents import create_agent
from langgraph_swarm import create_swarm, create_handoff_tool

# Shared imports
from shared.metadata import create_execution_metadata, AgentConfig
from shared.launchdarkly import init_launchdarkly_clients, fetch_agent_configs_from_api, create_context, build_agent_requests
from shared.pricing import PRICING, calculate_cost
from shared.prompt import build_paper_prompt
from shared.metrics import track_generation_metrics, track_token_metrics, track_cost_metric
from factory import get_tool


def extract_usage_tokens(message: Any) -> Tuple[int, int]:
    """Extract input and output tokens from various usage formats."""
    usage = None

    if isinstance(message, dict):
        usage = message.get("usage_metadata")
        if not usage:
            response_meta = message.get("response_metadata") or {}
            # Different providers use different field names:
            # - Anthropic: usage_metadata
            # - OpenAI: usage
            # - Some providers: token_usage
            usage = (
                response_meta.get("usage")
                or response_meta.get("token_usage")
                or response_meta.get("usage_metadata")
            )
            if usage is None and isinstance(response_meta, dict):
                # Anthropic uses input_tokens/output_tokens
                # OpenAI uses prompt_tokens/completion_tokens
                input_tokens = response_meta.get("input_tokens") or response_meta.get("prompt_tokens") or 0
                output_tokens = response_meta.get("output_tokens") or response_meta.get("completion_tokens") or 0
                return int(input_tokens), int(output_tokens)

        if not usage:
            extra = message.get("additional_kwargs") or {}
            # Some providers put usage data in additional_kwargs under various names
            usage = extra.get("usage") or extra.get("token_usage") or extra.get("usage_metadata")

    else:
        if hasattr(message, "usage_metadata") and message.usage_metadata:
            usage = message.usage_metadata
        elif hasattr(message, "response_metadata") and message.response_metadata:
            meta = message.response_metadata
            if isinstance(meta, dict):
                # Check various possible locations for usage data
                usage = meta.get("usage") or meta.get("token_usage") or meta.get("usage_metadata")
                if usage is None:
                    # Try direct token fields if no usage object found
                    input_tokens = meta.get("input_tokens") or meta.get("prompt_tokens") or 0
                    output_tokens = meta.get("output_tokens") or meta.get("completion_tokens") or 0
                    return int(input_tokens), int(output_tokens)

        if not usage and hasattr(message, "additional_kwargs"):
            extra = message.additional_kwargs or {}
            if isinstance(extra, dict):
                # Last resort: check additional_kwargs for usage data
                usage = extra.get("usage") or extra.get("token_usage") or extra.get("usage_metadata")

    if isinstance(usage, dict):
        # Extract tokens from usage dict - handle both naming conventions
        input_tokens = usage.get("input_tokens") or usage.get("prompt_tokens") or 0
        output_tokens = usage.get("output_tokens") or usage.get("completion_tokens") or 0
        return int(input_tokens), int(output_tokens)

    return 0, 0


def map_provider_to_langchain(provider_name: Optional[str]) -> Optional[str]:
    """Map LaunchDarkly provider names to LangChain providers."""
    if not provider_name:
        return None
    mapping = {
        "gemini": "google_genai",
    }
    lower_provider = provider_name.lower()
    return mapping.get(lower_provider, lower_provider)


def normalize_agent_name_for_tool(agent_name: str) -> str:
    """Normalize agent names to match LangGraph handoff tool naming."""
    return re.sub(r"\s+", "_", agent_name.strip()).lower()


def build_handoff_tools(
    requested_tool_names: List[str],
    agent_name: str,
    all_agent_names: List[str],
) -> List[Any]:
    """Create handoff tools based on LaunchDarkly tool configuration."""
    if not requested_tool_names:
        return []

    requested_set = {name for name in requested_tool_names if isinstance(name, str)}
    allow_all = "handoff_to_agent" in requested_set

    handoff_tools = []
    for target_name in all_agent_names:
        if target_name == agent_name:
            continue

        tool_name = f"transfer_to_{normalize_agent_name_for_tool(target_name)}"
        if allow_all or tool_name in requested_set:
            handoff_tools.append(
                create_handoff_tool(
                    agent_name=target_name,
                    name=tool_name,
                    description=f"Transfer control to {target_name}.",
                )
            )

    return handoff_tools


# Track metrics post-execution from messages following LaunchDarkly LangGraph pattern


async def run_langgraph_swarm(
    prompt: str,
    execution_id: str,
    orchestrator: str = "langgraph"
) -> Dict[str, Any]:
    """
    Main function to run LangGraph swarm with proper LaunchDarkly integration.

    Returns dict with results, metrics, and metadata.
    """

    # Initialize LaunchDarkly clients
    ld_client, ai_client = init_launchdarkly_clients()

    # Fetch agent list from LaunchDarkly API
    items = fetch_agent_configs_from_api()
    print(f"Found {len(items)} AI config(s) in LaunchDarkly")

    # Use items directly from LaunchDarkly without hardcoded sorting
    items_sorted = items

    # Create THE context - use execution_id as key for proper tracking
    context = create_context(execution_id, orchestrator=orchestrator)

    # Build requests for all agents
    agent_requests, agent_metadata = build_agent_requests(items_sorted)

    # Fetch all configs in one call with our context
    fetched_configs = ai_client.agent_configs(agent_requests, context)

    # Process configs and create agents
    agent_dict = {}
    agent_configs = []
    agent_configs_by_key = {}
    name_to_key = {}
    enabled_keys = []

    for key, name in agent_metadata.items():
        config = fetched_configs.get(key)

        if not config or not config.enabled:
            print(f"  ⚠️  Skipping disabled agent: {key}")
            continue

        if not config.instructions:
            print(f"  ⚠️  Skipping agent without instructions: {key}")
            continue

        enabled_keys.append(key)
        name_to_key[name] = key

        # Get model info from LaunchDarkly config
        model_id = config.model.name if config.model else "claude-sonnet-4-5"

        # Strip provider prefix if present
        if model_id.startswith("anthropic/"):
            model_id = model_id.replace("anthropic/", "")

        # Use the model from LaunchDarkly directly
        langchain_model_id = model_id  # Use what LaunchDarkly provides

        # For pricing, map to our pricing key format
        if "sonnet" in model_id.lower() and "4-5" in model_id:
            pricing_model_id = "claude-sonnet-4-5"
        else:
            pricing_model_id = model_id

        print(f"    📌 Model from LaunchDarkly: {model_id} -> LangChain: {langchain_model_id}")

        # Get tools from config
        config_dict = config.to_dict()
        model_params = config_dict.get('model', {}).get('parameters', {})
        tool_configs = model_params.get('tools', [])

        # Load tools dynamically
        tools = []
        tool_names = []
        requested_tool_names = []
        for tool_config in tool_configs:
            tool_name = tool_config.get('name') if isinstance(tool_config, dict) else str(tool_config)
            requested_tool_names.append(tool_name)

            # Skip handoff tools - handled dynamically using agent names from LaunchDarkly
            if tool_name == 'handoff_to_agent' or tool_name.startswith('transfer_to_'):
                print(f"    ⏭️  Skipping {tool_name} (will use LangGraph handoff tools)")
                continue

            try:
                tool_func = get_tool('langgraph', tool_name)
                if tool_func:
                    tools.append(tool_func)
                    tool_names.append(tool_name)
                    print(f"    ✓ Loaded tool: {tool_name}")
                else:
                    print(f"    ⚠️  Tool '{tool_name}' not found for {name}")
            except Exception as e:
                print(f"    ⚠️  Could not load tool '{tool_name}': {e}")

        # Store agent info for creation
        agent_dict[key] = {
            'name': name,
            'model_id': model_id,
            'langchain_model_id': langchain_model_id,  # Model ID for LangChain
            'pricing_model_id': pricing_model_id,  # Store the pricing key separately
            'config': config,
            'tools': tools,
            'tool_names': tool_names,
            'requested_tool_names': requested_tool_names,
            'provider': config.provider.name if config.provider else 'anthropic',
        }

        # Get instructions from config
        instructions = config.instructions

        # Store agent configuration for metadata
        agent_config = AgentConfig(
            key=key,
            name=name,
            role=name,
            model=model_id,
            provider=config.provider.name if config.provider else 'anthropic',
            temperature=0.0,
            tools=tool_names,
            instructions_preview=(instructions[:200] if instructions else '')
        )
        agent_configs.append(agent_config)
        agent_configs_by_key[key] = agent_config

        print(f"  ✓ Prepared {name} ({key}): {len(tools)} tools, model: {model_id}")

    if not agent_dict:
        raise RuntimeError("No enabled agents found")

    print(f"Created {len(agent_dict)} LangGraph agents")

    agent_names = [info['name'] for info in agent_dict.values()]
    name_to_key = {info['name']: key for key, info in agent_dict.items()}
    print(f"✓ Loaded agent names from LaunchDarkly: {', '.join(agent_names)}")

    # Create LangGraph agents
    executed_agents = set()
    per_agent_metrics = {
        key: {
            'input_tokens': 0,
            'output_tokens': 0,
            'total_tokens': 0,
            'duration': 0.0,
            'time_to_first_token': None
        }
        for key in enabled_keys
    }

    langraph_agents = []
    agent_trackers = {}

    for key, info in agent_dict.items():
        # Map provider to LangChain
        langchain_provider = map_provider_to_langchain(info['provider'])

        # Create LLM using the langchain model ID
        llm = init_chat_model(
            model=info['langchain_model_id'],
            model_provider=langchain_provider,
            temperature=0.0,
        )

        # Get instructions from config
        instructions = info['config'].instructions or ""

        # Build handoff tools based on LaunchDarkly tool config
        handoff_tools = build_handoff_tools(
            requested_tool_names=info.get('requested_tool_names', []),
            agent_name=info['name'],
            all_agent_names=agent_names,
        )
        handoff_tool_names = [tool.name for tool in handoff_tools]
        if handoff_tool_names:
            print(f"    ↪️  Added handoff tools for {info['name']}: {', '.join(handoff_tool_names)}")

        # Update metadata with actual tools used
        agent_config = agent_configs_by_key.get(key)
        if agent_config is not None:
            agent_config.tools = info['tool_names'] + handoff_tool_names

        # Create base agent with tools including handoff tools
        base_agent = create_agent(
            model=llm,
            tools=info['tools'] + handoff_tools,
            system_prompt=instructions,
            name=info['name'],
        )

        # Create context with agent for tracking
        agent_context = create_context(execution_id, orchestrator=orchestrator, agent=key)

        # Get FRESH tracker for this agent
        fresh_config = ai_client.agent_config(
            key=key,
            context=agent_context,
            default_value=AIAgentConfigDefault(enabled=False)
        )

        # Store tracker for metrics extraction
        agent_trackers[info['name']] = {
            'tracker': fresh_config.tracker,
            'agent_key': key,
            'model_id': info['model_id']
        }

        langraph_agents.append(base_agent)

    # First enabled agent is the entry point
    entry_point_key = enabled_keys[0]
    entry_agent_name = agent_dict.get(entry_point_key, {}).get('name', agent_names[0])
    print(f"📍 Entry point set to: {entry_agent_name} ({entry_point_key})")

    print(f"\n🔄 Creating swarm with {len(langraph_agents)} agents, entry point: {entry_agent_name}")

    swarm_graph = create_swarm(
        langraph_agents,
        default_active_agent=entry_agent_name,
        max_agent_calls=20  # Limit to prevent infinite loops
    )
    swarm = swarm_graph.compile()

    # Run the swarm
    print("\n🚀 Running LangGraph swarm...")
    start_time = time.time()

    recursion_limit = int(os.getenv("LANGGRAPH_RECURSION_LIMIT", "30"))
    invoke_config = {
        "recursion_limit": recursion_limit,
        "configurable": {"thread_id": execution_id}
    }

    print(f"📋 Configuration: recursion_limit={recursion_limit}")

    result = None
    swarm_error = None

    try:
        result = swarm.invoke(
            {"messages": [{"role": "user", "content": prompt}]},
            invoke_config
        )
        execution_time = time.time() - start_time
    except Exception as e:
        swarm_error = e
        execution_time = time.time() - start_time
        print("="*60)
        print("❌ EXECUTION FAILED")
        print("="*60)
        print(f"\nError: {e}")
        import traceback
        traceback.print_exc()
        print()

    # Extract output and metrics
    messages = []
    final_output = ""

    if result:
        messages = result.get("messages", [])

        # Extract metrics from messages
        debug = os.getenv("DEBUG", "").lower() in ["true", "1", "yes"]

        print(f"\n📊 Total messages generated: {len(messages)}")
        if debug:
            print("   Analyzing messages for token usage...")

        # Track which agents ran based on message content
        # In LangGraph swarm, agents execute in the order defined by the workflow
        # Messages after the user message are from agents in sequence

        current_agent_index = 0
        for i, msg in enumerate(messages):
            # Skip the initial user message
            if i == 0:
                # First message is typically the user input
                if debug:
                    print(f"   Message {i}: User input message")
                continue

            # Check if this message has usage metadata (indicates AI response)
            has_usage = False
            input_tokens = 0
            output_tokens = 0

            # Check for usage_metadata directly on the message (LangGraph pattern)
            if hasattr(msg, "usage_metadata") and msg.usage_metadata:
                usage_data = msg.usage_metadata
                input_tokens = usage_data.get("input_tokens", 0) or usage_data.get("prompt_tokens", 0)
                output_tokens = usage_data.get("output_tokens", 0) or usage_data.get("completion_tokens", 0)
                has_usage = True
            else:
                # Try extract_usage_tokens as fallback
                input_tokens, output_tokens = extract_usage_tokens(msg)
                if input_tokens > 0 or output_tokens > 0:
                    has_usage = True

            # If this message has usage data, it's from an agent
            if has_usage:
                total_tokens = input_tokens + output_tokens

                agent_key = None
                agent_name = None

                if isinstance(msg, dict):
                    agent_name = msg.get("name")
                elif hasattr(msg, "name"):
                    agent_name = msg.name

                if not agent_name and hasattr(msg, "additional_kwargs"):
                    extra = msg.additional_kwargs or {}
                    if isinstance(extra, dict):
                        agent_name = extra.get("name")

                if agent_name and agent_name in name_to_key:
                    agent_key = name_to_key[agent_name]
                elif current_agent_index < len(enabled_keys):
                    # Fallback: assign by order if no agent name is available
                    agent_key = enabled_keys[current_agent_index]
                    agent_name = agent_dict[agent_key]['name']
                    current_agent_index += 1

                if agent_key:
                    # Track this agent as executed
                    executed_agents.add(agent_key)
                    metrics = per_agent_metrics[agent_key]
                    metrics['input_tokens'] += input_tokens
                    metrics['output_tokens'] += output_tokens
                    metrics['total_tokens'] += total_tokens

                    if debug:
                        print(f"📊 Message {i} from {agent_name} [{agent_key}]: {input_tokens} input, {output_tokens} output tokens")
                elif debug:
                    print(f"   ⚠️  Message {i} has {total_tokens} tokens but no agent match found")
            else:
                # No usage data - might be a tool call or other message type
                if debug:
                    msg_type = getattr(msg, 'type', 'unknown')
                    print(f"   Message {i}: Non-AI message (type: {msg_type})")

        # Estimate duration for each agent that ran (divide total time by number of agents)
        if executed_agents:
            avg_duration = execution_time / len(executed_agents)
            for agent_key in executed_agents:
                per_agent_metrics[agent_key]['duration'] = avg_duration
                if per_agent_metrics[agent_key]['time_to_first_token'] is None:
                    per_agent_metrics[agent_key]['time_to_first_token'] = avg_duration * 0.1

        # Get final output from messages
        for msg in reversed(messages):
            if hasattr(msg, "content"):
                final_output = str(msg.content).strip()
                if final_output:
                    break
            elif isinstance(msg, dict) and "content" in msg:
                final_output = str(msg["content"]).strip()
                if final_output:
                    break

    if not final_output:
        if swarm_error:
            final_output = f"Swarm failed before final output. Error: {swarm_error}"
        else:
            final_output = "No final agent output available."

    # Track metrics using AI SDK and custom events
    print("\n📊 Tracking metrics to LaunchDarkly...")
    debug = os.getenv("DEBUG", "").lower() in ["true", "1", "yes"]

    for key in enabled_keys:
        metrics = per_agent_metrics.get(key, {})

        # Track all agents including zero-token ones for visibility

        # Create context with orchestrator and agent
        agent_context = create_context(execution_id, orchestrator=orchestrator, agent=key)

        model_id = agent_dict.get(key, {}).get('model_id')

        # Get fresh tracker for this specific agent
        fresh_config = ai_client.agent_config(
            key=key,
            context=agent_context,
            default_value=AIAgentConfigDefault(enabled=False)
        )
        tracker = fresh_config.tracker

        # Determine if this agent actually ran
        agent_ran = key in executed_agents

        if tracker:
            # Track with AI SDK native tracking
            if agent_ran and metrics['total_tokens'] > 0:
                # Track tokens
                tracker.track_tokens(TokenUsage(
                    input=metrics['input_tokens'],
                    output=metrics['output_tokens'],
                    total=metrics['total_tokens']
                ))

                # Track duration if available
                if metrics['duration'] > 0:
                    tracker.track_duration(metrics['duration'])

                # Track time to first token if available
                if metrics['time_to_first_token']:
                    tracker.track_time_to_first_token(metrics['time_to_first_token'])

                # Track success for agents that ran
                tracker.track_success()
            elif agent_ran:
                # Agent ran but no tokens
                tracker.track_success()
            else:
                # Agent didn't run - skip tracking
                pass

        # Track custom metrics only for agents that ran
        if agent_ran and metrics['total_tokens'] > 0:
            # Track token metrics
            track_token_metrics(
                ld_client=ld_client,
                context=agent_context,
                agent_key=key,
                model=model_id,
                input_tokens=metrics['input_tokens'],
                output_tokens=metrics['output_tokens'],
                orchestrator=orchestrator
            )
            # Track generation metrics
            if metrics['duration'] > 0:
                track_generation_metrics(
                    ld_client=ld_client,
                    context=agent_context,
                    agent_key=key,
                    model=model_id,
                    duration_ms=metrics['duration'] * 1000,  # Convert to ms
                    orchestrator=orchestrator
                )

            # Calculate and track cost using pricing_model_id
            pricing_model_id = agent_dict.get(key, {}).get('pricing_model_id')
            if pricing_model_id and pricing_model_id in PRICING:
                calculated_cost = calculate_cost(pricing_model_id, metrics['input_tokens'], metrics['output_tokens'])
                track_cost_metric(
                    ld_client=ld_client,
                    context=agent_context,
                    agent_key=key,
                    model=model_id,  # Use original model_id for tracking
                    cost=calculated_cost,
                    orchestrator=orchestrator
                )
                if debug and calculated_cost > 0:
                    print(f"      💰 Cost calculated: ${calculated_cost:.6f} for {metrics['total_tokens']} tokens")

        # Log tracking status only for agents that ran
        if agent_ran and metrics['total_tokens'] > 0:
            if metrics['time_to_first_token']:
                print(f"  ✓ Tracked {agent_metadata[key]}: {metrics['total_tokens']} tokens, ttft: {metrics['time_to_first_token']:.2f}s")
            else:
                print(f"  ✓ Tracked {agent_metadata[key]}: {metrics['total_tokens']} tokens")

    # Flush events to ensure delivery
    ld_client.flush()

    # Close clients
    ld_client.close()

    # Return results
    return {
        'execution_id': execution_id,
        'execution_time': execution_time,
        'message_count': len(messages),
        'per_agent_metrics': per_agent_metrics,
        'agent_metadata': agent_metadata,
        'agent_configs': agent_configs,
        'agent_dict': agent_dict,
        'final_output': final_output,
        'executed_agents': executed_agents,
        'enabled_keys': enabled_keys
    }


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(description="Run LangGraph gap analysis")
    parser.add_argument("--papers-json", type=str, required=True, help="Path to papers JSON")
    args = parser.parse_args()

    print("╔═══════════════════════════════════════════════════════╗")
    print("║  Research Gap Analysis - LangGraph                    ║")
    print("╚═══════════════════════════════════════════════════════╝")
    print()

    # Load papers
    papers_file = Path(args.papers_json)
    if not papers_file.exists():
        print(f"❌ Papers JSON not found: {papers_file}")
        return

    with open(papers_file) as f:
        papers = json.load(f)

    print(f"📚 Loaded {len(papers)} papers\n")

    # Format prompt (LangGraph includes ArXiv ID)
    prompt = build_paper_prompt(papers, include_arxiv=True)

    # Generate execution ID
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    execution_id = f"langgraph-{timestamp}"

    try:
        # Run the swarm
        result = asyncio.run(run_langgraph_swarm(
            prompt=prompt,
            execution_id=execution_id,
            orchestrator="langgraph"
        ))

        print("\n" + "="*60)
        print("✨ Gap analysis complete!")
        print("="*60)

        # Display summary
        total_input = sum(m['input_tokens'] for m in result['per_agent_metrics'].values())
        total_output = sum(m['output_tokens'] for m in result['per_agent_metrics'].values())
        total_tokens = sum(m['total_tokens'] for m in result['per_agent_metrics'].values())

        print(f"\nExecution ID: {result['execution_id']}")
        print(f"Total tokens: {total_tokens:,} (in: {total_input:,}, out: {total_output:,})")
        print(f"Execution time: {result['execution_time']:.2f}s")
        print(f"Messages: {result['message_count']}")

        # Create execution metadata
        metadata = create_execution_metadata(
            orchestrator_name="LangGraph",
            orchestrator_version="1.0.0",
            execution_time_seconds=result['execution_time'],
            total_iterations=result['message_count'],
            agents=result['agent_configs'],
            input_papers_count=len(papers)
        )

        # Add token counts to metadata
        for agent_key, metrics in result['per_agent_metrics'].items():
            metadata.add_tokens(
                agent_name=result['agent_metadata'].get(agent_key, agent_key),
                tokens=metrics['total_tokens']
            )

        # Save results
        results_dir = project_root / "results" / "langgraph"
        results_dir.mkdir(parents=True, exist_ok=True)
        report_file = results_dir / f"{timestamp}_{execution_id}_report.txt"

        # Build execution summary
        execution_summary_lines = ["=== AGENT EXECUTION ===", ""]
        for agent_key in result['enabled_keys']:
            agent_name = result['agent_metadata'].get(agent_key, agent_key)
            metrics = result['per_agent_metrics'].get(agent_key, {})
            total_tokens = metrics['total_tokens']
            duration = metrics['duration']
            ran = "yes" if agent_key in result['executed_agents'] else "no"
            execution_summary_lines.append(
                f"- {agent_name} [{agent_key}]: ran={ran}, tokens={total_tokens}, duration={duration:.2f}s"
            )
        execution_summary = "\n".join(execution_summary_lines)

        with open(report_file, 'w') as f:
            f.write(metadata.to_report_section())
            f.write("\n\n")
            f.write(execution_summary)
            f.write("\n\n")
            f.write(result['final_output'])

        print(f"\n📝 Report saved to: {report_file}")

        metadata_file = results_dir / f"{timestamp}_{execution_id}_metadata.json"
        with open(metadata_file, 'w') as f:
            f.write(metadata.to_json())

        print(f"📊 Metadata saved to: {metadata_file}")

    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()

    print()


if __name__ == "__main__":
    main()