#!/usr/bin/env python3
"""
Strands Research Gap Analysis
Fetches agent configs from LaunchDarkly once and tracks metrics
"""

import json
import argparse
import sys
import os
import time
import asyncio
import logging
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Any, Tuple

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

# Strands imports
from strands import Agent
from strands.multiagent import Swarm
from strands.models.anthropic import AnthropicModel
from strands.agent.conversation_manager.sliding_window_conversation_manager import (
    SlidingWindowConversationManager
)
from strands.types.exceptions import MaxTokensReachedException

# Shared imports
from shared.metadata import create_execution_metadata, AgentConfig
from shared.launchdarkly import init_launchdarkly_clients, fetch_agent_configs_from_api, create_context, build_agent_requests
from shared.pricing import PRICING, calculate_cost
from shared.prompt import build_paper_prompt
from shared.metrics import track_generation_metrics, track_token_metrics, track_cost_metric
from factory import get_tool
from shared.tools import common as common_tools

# Enable debug logs
logging.getLogger("strands.multiagent").setLevel(logging.DEBUG)
logging.basicConfig(
    format="%(levelname)s | %(name)s | %(message)s",
    handlers=[logging.StreamHandler()]
)


def extract_usage_tokens(usage) -> Tuple[int, int]:
    """Extract input and output tokens from various usage formats."""
    if usage is None:
        return 0, 0

    if isinstance(usage, dict):
        prompt = usage.get("inputTokens", 0) or usage.get("input_tokens", 0)
        completion = usage.get("outputTokens", 0) or usage.get("output_tokens", 0)
        total = usage.get("totalTokens", 0) or usage.get("total_tokens", 0)

        # If only total is provided, estimate split
        if total > 0 and prompt == 0 and completion == 0:
            prompt = int(total * 0.7)  # Estimate 70% input
            completion = total - prompt

        return int(prompt), int(completion)

    # Handle object attributes
    prompt = getattr(usage, "inputTokens", None) or getattr(usage, "input_tokens", 0)
    completion = getattr(usage, "outputTokens", None) or getattr(usage, "output_tokens", 0)
    return int(prompt or 0), int(completion or 0)


def node_result_to_text(node_result) -> str:
    """Extract text content from a NodeResult object."""
    if node_result is None:
        return ""

    # Try to get result directly
    if hasattr(node_result, "result") and node_result.result:
        result = node_result.result
        if isinstance(result, str):
            return result.strip()
        if hasattr(result, "text"):
            return str(result.text).strip()
        if hasattr(result, "content"):
            return str(result.content).strip()
        result_str = str(result).strip()
        if result_str and result_str != "None":
            return result_str

    # Try agent_result
    if hasattr(node_result, "agent_result") and node_result.agent_result:
        agent_result = node_result.agent_result
        if hasattr(agent_result, "text"):
            return str(agent_result.text).strip()
        if hasattr(agent_result, "content"):
            return str(agent_result.content).strip()
        if hasattr(agent_result, "messages"):
            messages = _extract_messages(agent_result.messages)
            if messages:
                return "\n".join(messages).strip()

    # Try messages directly on node_result
    if hasattr(node_result, "messages"):
        messages = _extract_messages(node_result.messages)
        if messages:
            return "\n".join(messages).strip()

    # Try output attribute
    if hasattr(node_result, "output"):
        return str(node_result.output).strip()

    # Last resort: convert entire object to string
    full_str = str(node_result).strip()
    if full_str and full_str != "None" and "NodeResult" not in full_str:
        return full_str

    return ""


def _extract_messages(messages) -> List[str]:
    """Helper to extract text from messages."""
    result = []
    for msg in messages:
        if hasattr(msg, "text"):
            result.append(str(msg.text))
        elif hasattr(msg, "content"):
            result.append(str(msg.content))
        elif isinstance(msg, str):
            result.append(msg)
    return result


async def run_strands_swarm(
    prompt: str,
    execution_id: str,
    orchestrator: str = "strands"
) -> Dict[str, Any]:
    """
    Main function to run Strands swarm with proper LaunchDarkly integration.

    Returns dict with results, metrics, and metadata.
    """

    # Initialize LaunchDarkly clients
    ld_client, ai_client = init_launchdarkly_clients()

    # Fetch agent list from LaunchDarkly API
    items = fetch_agent_configs_from_api()
    print(f"Found {len(items)} AI config(s) in LaunchDarkly")

    # Create THE context - use execution_id as key for proper tracking
    context = create_context(execution_id, orchestrator=orchestrator)

    # Build requests for all agents
    agent_requests, agent_metadata = build_agent_requests(items)

    # Fetch all configs in one call with our context
    fetched_configs = ai_client.agent_configs(agent_requests, context)

    # Create conversation managers with different settings
    cm_default = SlidingWindowConversationManager(
        window_size=int(os.getenv("STRANDS_WINDOW_SIZE", "30")),
        should_truncate_results=True,
        per_turn=True,
    )

    # Tighter context for the final synthesizer to reduce token pressure
    cm_synth = SlidingWindowConversationManager(
        window_size=int(os.getenv("STRANDS_SYNTH_WINDOW_SIZE", "20")),
        should_truncate_results=True,
        per_turn=True,
    )

    # Process configs and create agents
    agents = []
    agent_dict = {}
    agent_configs = []
    name_to_key = {}
    enabled_keys = []
    entry_point = None

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

        # Get model info
        model_id = config.model.name if config.model else "claude-sonnet-4-5"

        # Strip provider prefix if present
        if model_id.startswith("anthropic/"):
            model_id = model_id.replace("anthropic/", "")

        # Get tools from config
        config_dict = config.to_dict()
        model_params = config_dict.get('model', {}).get('parameters', {})
        tool_configs = model_params.get('tools', [])

        # Extract max_tokens from LaunchDarkly config (supporting both snake_case and camelCase)
        # If not set in LaunchDarkly, use the Claude Sonnet maximum (64k tokens)
        max_tokens = model_params.get("max_tokens") or model_params.get("maxTokens") or 64000

        # Check if this is a synthesizer agent
        is_synthesizer = 'synthesizer' in name.lower() or 'gap' in name.lower()

        # Pass through all other model parameters (temperature, stop sequences, etc.)
        params = {
            k: v for k, v in model_params.items()
            if k not in {"tools", "max_tokens", "maxTokens"}
        } or None

        # Load tools dynamically
        tools = []
        tool_names = []
        for tool_config in tool_configs:
            tool_name = tool_config.get('name') if isinstance(tool_config, dict) else str(tool_config)

            try:
                tool_def = getattr(common_tools, tool_name, None)
                if tool_def and getattr(tool_def, "_is_handoff_tool", False):
                    print(f"    ℹ️  Skipping '{tool_name}' (provided by Strands Swarm)")
                    continue
                tool_func = get_tool('strands', tool_name)
                if tool_func:
                    tools.append(tool_func)
                    tool_names.append(tool_name)
                    print(f"    ✓ Loaded tool: {tool_name}")
                else:
                    print(f"    ⚠️  Tool '{tool_name}' not found for {name}")
            except Exception as e:
                print(f"    ⚠️  Could not load tool '{tool_name}': {e}")

        # Note: Agents without tools are allowed (e.g., Paper Reader reads pre-formatted text)
        if not tools:
            print(f"    ℹ️  No tools configured for agent '{name}' (tool-free agent)")

        # Add output budget constraint for synthesizer to prevent max_tokens issues
        instructions = config.instructions
        if is_synthesizer:
            instructions += (
                "\n\nOUTPUT BUDGET:\n"
                "- Produce a COMPLETE report in <= 1800 words\n"
                "- Use bullet points and tables over long prose\n"
                "- If approaching the limit, compress remaining sections\n"
                "- DO NOT exceed the budget - finish cleanly"
            )

        # Choose appropriate conversation manager
        conversation_manager = cm_synth if is_synthesizer else cm_default

        # Create agent with LaunchDarkly config and all parameters
        anthropic_model = AnthropicModel(
            model_id=model_id,
            max_tokens=int(max_tokens),
            params=params  # Pass through temperature, stop sequences, etc.
        )
        agent = Agent(
            name=name,
            model=anthropic_model,
            system_prompt=instructions,
            tools=tools,
            conversation_manager=conversation_manager
        )

        agents.append(agent)

        # Store agent info for metrics
        agent_dict[key] = {
            'name': name,
            'model_id': model_id,
            'tools': tools
        }

        # Store agent configuration for metadata
        agent_configs.append(AgentConfig(
            key=key,
            name=name,
            role=name,
            model=model_id,
            provider=config.provider.name if config.provider else 'anthropic',
            temperature=0.0,
            tools=tool_names,
            instructions_preview=config.instructions[:200] if config.instructions else ''
        ))

        # Set entry point to first enabled agent
        if entry_point is None:
            entry_point = agent
            entry_point_key = key

        print(f"  ✓ Prepared {name} ({key}): {len(tools)} tools, model: {model_id}")

    if not agents:
        raise RuntimeError("No enabled agents found")

    print(f"Created {len(agents)} Strands agents")

    # Create Strands swarm with increased limits for long reports
    swarm = Swarm(
        agents,
        entry_point=entry_point,
        max_handoffs=50,          # Increased for complex analyses
        max_iterations=60,        # Increased for multi-step research
        execution_timeout=1800.0,  # 30 minutes total
        node_timeout=900.0,       # 15 minutes per agent (for long synthesis)
        repetitive_handoff_detection_window=0,  # Disabled until stable
        repetitive_handoff_min_unique_agents=0
    )

    # Initialize metrics tracking
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

    # Track executed agents
    executed_agents = set()

    # Run the swarm
    print("\n🚀 Running Strands swarm...")
    start_time = time.time()

    result = None
    swarm_error = None

    try:
        result = await swarm.invoke_async(prompt)
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

    # Extract metrics from result
    iterations = 0
    output = ""
    transcript = []  # Capture all agent outputs
    truncation_warnings = []  # Track any truncations
    errors_by_agent = {}  # Track exceptions by agent

    if result is not None:
        # Extract result details
        iterations = result.execution_count if hasattr(result, 'execution_count') else 0

        # Extract per-agent metrics and build transcript
        if hasattr(result, 'results'):
            # First pass: Look for Research Gap Synthesizer output
            for agent_name, node_result in result.results.items():
                # Map agent name to key
                agent_key = name_to_key.get(agent_name, agent_name)

                # IMPORTANT: Check if result is an Exception (agent failed)
                if isinstance(node_result.result, Exception):
                    error_msg = str(node_result.result)
                    errors_by_agent[agent_key] = error_msg
                    transcript.append(f"\n=== {agent_name} ===\n[ERROR]: {error_msg}")

                    # Still track metrics for duration
                    if agent_key in per_agent_metrics:
                        duration = (node_result.execution_time or 0) / 1000.0
                        per_agent_metrics[agent_key] = {
                            'input_tokens': 0,
                            'output_tokens': 0,
                            'total_tokens': 0,
                            'duration': duration,
                            'time_to_first_token': None,
                            'error': error_msg
                        }
                        executed_agents.add(agent_key)
                    continue

                # Extract the actual text output using robust helper
                agent_output = node_result_to_text(node_result)

                # Add to transcript if we got meaningful output
                if agent_output and len(agent_output) > 50:
                    transcript.append(f"\n=== {agent_name} ===\n{agent_output}")

                    # Check if this is the gap synthesizer and use as primary output
                    if ('gap' in agent_name.lower() or 'synthesizer' in agent_name.lower()) and not output:
                        output = agent_output
                        print(f"📄 Found output from {agent_name} ({len(agent_output)} chars)")

                # Check for truncation (max_tokens reached)
                if hasattr(node_result, "stop_reason"):
                    if node_result.stop_reason == "max_tokens":
                        truncation_warnings.append(f"⚠️  {agent_name} was truncated (max_tokens reached)")
                        print(f"⚠️  {agent_name} output was truncated due to max_tokens")

                # Track metrics if this is one of our agents
                if agent_key in per_agent_metrics:
                    # Extract token usage
                    usage = node_result.accumulated_usage or {}
                    input_tokens, output_tokens = extract_usage_tokens(usage)
                    total_tokens = input_tokens + output_tokens

                    # Extract duration (convert ms to seconds)
                    duration = (node_result.execution_time or 0) / 1000.0

                    # Track time to first token (estimated from execution start)
                    if agent_key == entry_point_key:
                        ttft = duration * 0.1  # Estimate 10% of duration for first token
                    else:
                        ttft = duration * 0.2  # Estimate 20% for subsequent agents

                    per_agent_metrics[agent_key] = {
                        'input_tokens': input_tokens,
                        'output_tokens': output_tokens,
                        'total_tokens': total_tokens,
                        'duration': duration,
                        'time_to_first_token': ttft if duration > 0 else None
                    }

                    executed_agents.add(agent_key)

        # If no gap synthesizer output, use full transcript
        if not output and transcript:
            output = "\n".join(transcript)
            print(f"📄 Using full transcript ({len(output)} chars)")

        # Get final output from last node if still no output
        if not output:
            last_completed = None
            if hasattr(result, 'node_history') and result.node_history:
                last_completed = result.node_history[-1].node_id

            if last_completed and hasattr(result, 'results') and last_completed in result.results:
                node_result = result.results[last_completed]
                output = node_result_to_text(node_result)
                if output:
                    print(f"📄 Using output from last node: {last_completed}")

    # Print truncation warnings if any
    if truncation_warnings:
        print("\n" + "\n".join(truncation_warnings))

    if not output:
        if swarm_error:
            output = f"Swarm failed before final output. Error: {swarm_error}"
            # Add any successful agent outputs we collected
            if transcript:
                output += "\n\n=== Partial Results from Completed Agents ===\n"
                output += "\n".join(transcript)
        elif errors_by_agent.get('gap-synthesizer'):
            # Synthesizer failed but other agents succeeded - use their outputs
            output = "Research Gap Synthesizer failed due to token limit. Using outputs from completed agents:\n"
            output += "\n".join(transcript) if transcript else "No agent outputs captured."
        else:
            # This should never happen now with robust extraction
            output = "No agent output could be extracted. Check the transcript file for details."

    # Track metrics using BOTH AI SDK and custom events
    print("\n📊 Tracking metrics to LaunchDarkly...")

    for agent_key in executed_agents:
        metrics = per_agent_metrics.get(agent_key, {})
        error_msg = errors_by_agent.get(agent_key)

        # Only skip if truly never ran AND no error
        if metrics['total_tokens'] == 0 and not error_msg and metrics['duration'] == 0:
            continue

        # Create context with both orchestrator AND agent explicitly
        agent_context = create_context(execution_id, orchestrator=orchestrator, agent=agent_key)

        # 1. AI SDK tracking for AI Config Monitoring dashboard
        # Get FRESH config and tracker for this specific agent
        # This is REQUIRED per LaunchDarkly docs - must not reuse trackers
        fresh_config = ai_client.agent_config(
            key=agent_key,
            context=agent_context,  # Use context with both orchestrator and agent
            default_value=AIAgentConfigDefault(enabled=False)
        )

        # Use the fresh tracker from this new config evaluation
        tracker = fresh_config.tracker

        # Track tokens - AI SDK automatically adds agent attribute
        tracker.track_tokens(TokenUsage(
            input=metrics['input_tokens'],
            output=metrics['output_tokens'],
            total=metrics['total_tokens']
        ))

        # Track duration
        if metrics['duration'] > 0:
            tracker.track_duration(metrics['duration'])

        # Track time to first token if available
        if metrics['time_to_first_token'] is not None:
            tracker.track_time_to_first_token(metrics['time_to_first_token'])

        # Track success/error - SDK automatically tracks errors when model calls fail
        # Note: track_error() doesn't take arguments, it just marks as failed
        if error_msg or swarm_error:
            tracker.track_error()
        else:
            tracker.track_success()

        # 2. Custom track events with our context for custom metrics
        # These will have orchestrator and agent in context attributes

        # Get model_id from agent_dict which we already populated
        model_id = agent_dict.get(agent_key, {}).get('model_id')

        # Track generation metrics
        if metrics['duration'] > 0:
            track_generation_metrics(
                ld_client=ld_client,
                context=agent_context,
                agent_key=agent_key,
                model=model_id,
                duration_ms=metrics['duration'] * 1000,  # Convert to ms
                orchestrator=orchestrator
            )

        # Track token metrics
        if metrics['total_tokens'] > 0:
            track_token_metrics(
                ld_client=ld_client,
                context=agent_context,
                agent_key=agent_key,
                model=model_id,
                input_tokens=metrics['input_tokens'],
                output_tokens=metrics['output_tokens'],
                orchestrator=orchestrator
            )

        # Calculate and track cost
        if model_id and model_id in PRICING:
            calculated_cost = calculate_cost(model_id, metrics['input_tokens'], metrics['output_tokens'])
            track_cost_metric(
                ld_client=ld_client,
                context=agent_context,
                agent_key=agent_key,
                model=model_id,
                cost=calculated_cost,
                orchestrator=orchestrator
            )

        print(f"  ✓ Tracked {agent_metadata[agent_key]}: {metrics['total_tokens']} tokens, ttft: {metrics['time_to_first_token']:.2f}s" if metrics['time_to_first_token'] else f"  ✓ Tracked {agent_metadata[agent_key]}: {metrics['total_tokens']} tokens")

    # Flush events to ensure delivery
    ld_client.flush()

    # Close clients
    ld_client.close()

    # Return results
    return {
        'execution_id': execution_id,
        'execution_time': execution_time,
        'iterations': iterations,
        'per_agent_metrics': per_agent_metrics,
        'agent_metadata': agent_metadata,
        'agent_configs': agent_configs,
        'agent_dict': agent_dict,
        'final_output': output,
        'executed_agents': executed_agents,
        'enabled_keys': enabled_keys,
        'transcript': transcript,  # Include full transcript for debugging
        'truncation_warnings': truncation_warnings  # Include any truncation warnings
    }


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(description="Run Strands gap analysis")
    parser.add_argument("--papers-json", type=str, required=True, help="Path to papers JSON")
    args = parser.parse_args()

    print("╔═══════════════════════════════════════════════════════╗")
    print("║  Research Gap Analysis - Strands                      ║")
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

    # Format prompt (Strands includes ArXiv ID)
    prompt = build_paper_prompt(papers, include_arxiv=True)

    # Generate execution ID
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    execution_id = f"strands-{timestamp}"

    try:
        # Run the swarm
        result = asyncio.run(run_strands_swarm(
            prompt=prompt,
            execution_id=execution_id,
            orchestrator="strands"
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
        print(f"Iterations: {result['iterations']}")

        # Create execution metadata
        metadata = create_execution_metadata(
            orchestrator_name="Strands",
            orchestrator_version="1.0.0",
            execution_time_seconds=result['execution_time'],
            total_iterations=result['iterations'],
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
        results_dir = project_root / "results" / "strands"
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

        # Save transcript if available
        if result.get('transcript'):
            transcript_file = results_dir / f"{timestamp}_{execution_id}_transcript.txt"
            with open(transcript_file, 'w') as f:
                f.write("STRANDS AGENT TRANSCRIPT\n")
                f.write("="*60 + "\n")
                f.write(f"Execution ID: {execution_id}\n")
                f.write(f"Total Agents: {len(result['executed_agents'])}\n")
                f.write("="*60 + "\n")
                f.write("\n".join(result['transcript']))
                if result.get('truncation_warnings'):
                    f.write("\n\nTRUNCATION WARNINGS:\n")
                    f.write("\n".join(result['truncation_warnings']))
            print(f"🧾 Transcript saved: {transcript_file}")

    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()

    print()


if __name__ == "__main__":
    main()