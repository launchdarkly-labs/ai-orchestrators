#!/usr/bin/env python3
"""
AutoGen Research Gap Analysis
Fetches agent configs from LaunchDarkly once and tracks metrics
"""

import json
import argparse
import sys
import os
import time
import asyncio
import requests
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Tuple, Any

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

# AutoGen imports
from autogen_agentchat.agents import AssistantAgent
from autogen_agentchat.base import Handoff, TaskResult
from autogen_agentchat.teams import Swarm
from autogen_agentchat.conditions import TextMentionTermination, MaxMessageTermination
from autogen_agentchat.messages import TextMessage
from autogen_ext.models.anthropic import AnthropicChatCompletionClient

# Shared imports
from shared.metadata import create_execution_metadata, AgentConfig
from shared.launchdarkly import init_launchdarkly_clients, fetch_agent_configs_from_api, create_context, build_agent_requests
from shared.pricing import PRICING, calculate_cost
from shared.prompt import build_paper_prompt
from shared.metrics import track_generation_metrics, track_token_metrics, track_cost_metric
from factory import get_tool


def extract_usage_tokens(usage) -> Tuple[int, int]:
    """Extract input and output tokens from various usage formats."""
    if usage is None:
        return 0, 0

    if isinstance(usage, dict):
        prompt = usage.get("prompt_tokens", 0) or usage.get("input_tokens", 0)
        completion = usage.get("completion_tokens", 0) or usage.get("output_tokens", 0)
        return int(prompt), int(completion)

    # Handle object attributes
    prompt = getattr(usage, "prompt_tokens", None) or getattr(usage, "input_tokens", 0)
    completion = getattr(usage, "completion_tokens", None) or getattr(usage, "output_tokens", 0)
    return int(prompt or 0), int(completion or 0)


async def run_autogen_swarm(
    prompt: str,
    execution_id: str,
    orchestrator: str = "autogen"
) -> Dict[str, Any]:
    """
    Main function to run AutoGen swarm with proper LaunchDarkly integration.

    Returns dict with results, metrics, and metadata.
    """
    print(f"🚀 Starting AutoGen swarm with execution_id: {execution_id}")

    print("🔄 Initializing LaunchDarkly clients...")
    # Initialize LaunchDarkly clients
    ld_client, ai_client = init_launchdarkly_clients()

    print("🔄 Fetching agent configs from LaunchDarkly API...")
    # Fetch agent list from LaunchDarkly API
    items = fetch_agent_configs_from_api()
    print(f"Found {len(items)} AI config(s) in LaunchDarkly")

    # Create THE context - use execution_id as key for proper tracking
    context = create_context(execution_id, orchestrator=orchestrator)

    # Build requests for all agents
    agent_requests, agent_metadata = build_agent_requests(items)

    # Fetch all configs in one call with our context
    fetched_configs = ai_client.agent_configs(agent_requests, context)

    # Process configs and create agents
    agents = []
    agent_dict = {}
    key_to_name = {}
    name_to_key = {}
    enabled_keys = []

    # Get Anthropic API key
    anthropic_api_key = os.getenv('ANTHROPIC_API_KEY')
    if not anthropic_api_key:
        raise ValueError("ANTHROPIC_API_KEY not found")

    for key, name in agent_metadata.items():
        config = fetched_configs.get(key)

        if not config or not config.enabled:
            print(f"  ⚠️  Skipping disabled agent: {key}")
            continue

        if not config.instructions:
            print(f"  ⚠️  Skipping agent without instructions: {key}")
            continue

        enabled_keys.append(key)

        # Get model info
        model_id = config.model.name if config.model else "claude-sonnet-4-5"

        # Strip provider prefix if present
        if model_id.startswith("anthropic/"):
            model_id = model_id.replace("anthropic/", "")

        # Don't store tracker - we'll get fresh ones when tracking
        # Per LaunchDarkly docs: trackers must not be reused

        # Get tools from config
        config_dict = config.to_dict()
        model_params = config_dict.get('model', {}).get('parameters', {})
        tool_configs = model_params.get('tools', [])

        # Load tools dynamically
        tools = []
        handoff_tool_name = None

        for tool_config in tool_configs:
            tool_name = tool_config.get('name') if isinstance(tool_config, dict) else str(tool_config)

            try:
                tool_func = get_tool('autogen', tool_name)
                if tool_func:
                    if getattr(tool_func, "_is_handoff_tool", False):
                        handoff_tool_name = tool_name
                        print(f"    ℹ️  Using '{tool_name}' as handoff for {name}")
                    else:
                        tools.append(tool_func)
                        print(f"    ✓ Loaded tool: {tool_name}")
                else:
                    print(f"    ⚠️  Tool '{tool_name}' not found for {name}")
            except Exception as e:
                print(f"    ⚠️  Could not load tool '{tool_name}': {e}")

        # Create safe agent name identifier
        agent_id = name.replace(' ', '_').replace('-', '_')
        key_to_name[key] = agent_id
        name_to_key[agent_id] = key

        # Store agent info for creation
        agent_dict[key] = {
            'name': name,
            'agent_id': agent_id,
            'model_id': model_id,
            'instructions': config.instructions,
            'tools': tools,
            'tool_names': [getattr(t, '__name__', str(t)) for t in tools],  # Store tool names for metadata
            'handoff_tool_name': handoff_tool_name or "transfer_to_agent"
        }

        print(f"  ✓ Prepared {name} ({key}): {len(tools)} tools, model: {model_id}")

    if not agent_dict:
        raise RuntimeError("No valid agents found")

    # Set entry point to first enabled agent from LaunchDarkly configuration
    # The order is determined by LaunchDarkly's targeting rules and configuration
    entry_point_key = enabled_keys[0]
    print(f"📍 Entry point set to: {agent_metadata.get(entry_point_key, entry_point_key)}")

    # Create AutoGen agents with handoffs
    autogen_agents = []

    for key, agent_info in agent_dict.items():
        # Create model client
        model_client = AnthropicChatCompletionClient(
            model=agent_info['model_id'],
            api_key=anthropic_api_key
        )

        # Create handoffs to other agents
        handoffs = []
        handoff_name = agent_info['handoff_tool_name']

        for other_key, other_info in agent_dict.items():
            if other_key != key:  # Don't handoff to self
                handoffs.append(
                    Handoff(
                        target=other_info['agent_id'],
                        name=f"{handoff_name}_{other_info['agent_id']}",
                        description=f"Transfer to {other_info['name']} for {other_key.replace('-', ' ')} tasks."
                    )
                )

        # Create agent
        agent = AssistantAgent(
            name=agent_info['agent_id'],
            model_client=model_client,
            tools=agent_info['tools'] if agent_info['tools'] else None,
            system_message=agent_info['instructions'],
            description=agent_info['name'],
            handoffs=handoffs if handoffs else None
        )

        autogen_agents.append(agent)

    print(f"Created {len(autogen_agents)} AutoGen agents")

    # Create Swarm with higher message limit to handle long reports
    termination = TextMentionTermination("TERMINATE") | MaxMessageTermination(max_messages=100)
    team = Swarm(
        participants=autogen_agents,
        termination_condition=termination
    )

    # Initialize metrics tracking
    per_agent_metrics = {
        key: {
            'input_tokens': 0,
            'output_tokens': 0,
            'total_tokens': 0,
            'message_count': 0,
            'duration': 0.0,
            'time_to_first_token': None,
            'first_response_time': None
        }
        for key in agent_dict.keys()
    }

    # Run the swarm
    print("\n🚀 Running AutoGen swarm...")
    start_time = time.time()
    max_stream_messages = int(os.getenv("AUTOGEN_MAX_MESSAGES", "200"))
    max_stream_seconds = int(os.getenv("AUTOGEN_MAX_SECONDS", "900"))

    messages = []
    message_contents = []  # Store content separately for final output
    agent_timings = {}
    last_agent = None
    last_timestamp = start_time
    last_usage_by_agent = {}
    task_result = None  # Store the final TaskResult

    # Track message flow
    async for msg in team.run_stream(task=prompt):
        # Check if this is the final TaskResult
        if isinstance(msg, TaskResult):
            task_result = msg
            print(f"✅ Swarm completed with stop reason: {task_result.stop_reason}")
            break

        current_time = time.time()
        if len(messages) >= max_stream_messages:
            print(f"🛑 Reached AUTOGEN_MAX_MESSAGES={max_stream_messages}. Stopping stream.")
            break
        if current_time - start_time > max_stream_seconds:
            print(f"🛑 Reached AUTOGEN_MAX_SECONDS={max_stream_seconds}. Stopping stream.")
            break

        # Extract agent name from message
        agent_name = None
        content = ""
        usage = None
        msg_type = getattr(msg, "type", "") or msg.__class__.__name__
        if isinstance(msg_type, str) and "StreamingChunk" in msg_type:
            # Ignore streaming chunks to avoid duplicate usage and runaway counts.
            continue

        if hasattr(msg, "chat_message") and msg.chat_message:
            chat = msg.chat_message
            agent_name = getattr(chat, "source", None) or getattr(chat, "name", None)
            content = str(getattr(chat, "content", ""))
            # AutoGen stores usage data in the message's usage field, not models_usage
            usage = getattr(chat, "usage", None) or getattr(chat, "models_usage", None)
        elif hasattr(msg, 'source'):
            agent_name = str(msg.source)
            content = str(getattr(msg, 'content', msg))
            # Check both usage and models_usage for compatibility
            usage = getattr(msg, 'usage', None) or getattr(msg, 'models_usage', None)
        elif hasattr(msg, 'name'):
            agent_name = str(msg.name)
            content = str(getattr(msg, 'content', ""))
            # Also check for usage on the message itself
            if not usage:
                usage = getattr(msg, 'usage', None)

        # Track timing
        if last_agent and last_agent != agent_name:
            elapsed = current_time - last_timestamp
            if last_agent not in agent_timings:
                agent_timings[last_agent] = 0.0
            agent_timings[last_agent] += elapsed
            last_timestamp = current_time

        last_agent = agent_name

        # Map agent name to key and track tokens
        if agent_name:
            # Try to find the key for this agent
            agent_key = None
            for key, info in agent_dict.items():
                if info['agent_id'] == agent_name or info['name'] == agent_name:
                    agent_key = key
                    break

            if agent_key and agent_key in per_agent_metrics:
                input_tokens, output_tokens = extract_usage_tokens(usage)
                if usage and (input_tokens > 0 or output_tokens > 0):
                    prev_in, prev_out = last_usage_by_agent.get(agent_key, (0, 0))
                    delta_in = max(0, input_tokens - prev_in)
                    delta_out = max(0, output_tokens - prev_out)
                    last_usage_by_agent[agent_key] = (input_tokens, output_tokens)
                    input_tokens, output_tokens = delta_in, delta_out

                # Debug: Print if we actually got usage data
                if usage and (input_tokens > 0 or output_tokens > 0):
                    print(f"    📊 Got usage from {agent_name}: in={input_tokens}, out={output_tokens}")

                # Estimate if no usage data
                if input_tokens == 0 and output_tokens == 0 and content:
                    words = len(content.split())
                    output_tokens = int(words * 1.3)
                    print(f"    ⚠️  Estimated tokens for {agent_name}: {output_tokens} (no usage metadata)")

                per_agent_metrics[agent_key]['input_tokens'] += input_tokens
                per_agent_metrics[agent_key]['output_tokens'] += output_tokens
                per_agent_metrics[agent_key]['total_tokens'] += (input_tokens + output_tokens)
                per_agent_metrics[agent_key]['message_count'] += 1

                # Track time to first token (first output from this agent)
                if per_agent_metrics[agent_key]['first_response_time'] is None and output_tokens > 0:
                    per_agent_metrics[agent_key]['first_response_time'] = current_time
                    per_agent_metrics[agent_key]['time_to_first_token'] = current_time - start_time

        # Store message and content separately
        messages.append(msg)
        if content and content.strip():
            message_contents.append({
                'agent_name': agent_name,
                'content': content
            })

    # Final timing update
    if last_agent:
        elapsed = time.time() - last_timestamp
        if last_agent not in agent_timings:
            agent_timings[last_agent] = 0.0
        agent_timings[last_agent] += elapsed

    # Map timing to agent keys
    for agent_name, duration in agent_timings.items():
        for key, info in agent_dict.items():
            if info['agent_id'] == agent_name or info['name'] == agent_name:
                per_agent_metrics[key]['duration'] = duration
                break

    execution_time = time.time() - start_time

    # Add prompt tokens to entry point if missing
    if entry_point_key in per_agent_metrics and per_agent_metrics[entry_point_key]['input_tokens'] == 0:
        prompt_tokens = int(len(prompt.split()) * 1.3)
        per_agent_metrics[entry_point_key]['input_tokens'] = prompt_tokens
        per_agent_metrics[entry_point_key]['total_tokens'] += prompt_tokens

    # Mark agents with no activity as potential errors (except if they're just not needed)
    for key, metrics in per_agent_metrics.items():
        if metrics['message_count'] == 0 and metrics['total_tokens'] == 0:
            # Agent didn't run at all - this could be normal or an error
            # We'll mark it as successful unless there was a swarm-level error
            pass  # For now, we assume it's normal if agent wasn't needed

    # Track metrics using BOTH AI SDK and custom events
    print("\n📊 Tracking metrics to LaunchDarkly...")

    for key, metrics in per_agent_metrics.items():
        # Skip agents that didn't run (no generation to track)
        if metrics['total_tokens'] == 0:
            continue

        # Create context with both orchestrator AND agent explicitly
        agent_context = create_context(execution_id, orchestrator=orchestrator, agent=key)

        # 1. AI SDK tracking for AI Config Monitoring dashboard
        # Get FRESH config and tracker for this specific agent
        # This is REQUIRED per LaunchDarkly docs - must not reuse trackers
        fresh_config = ai_client.agent_config(
            key=key,
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

        # Track success - SDK automatically tracks errors when model calls fail
        tracker.track_success()

        # 2. Custom track events with our context for custom metrics
        # These will have orchestrator and agent in context attributes

        # Get model_id from agent_dict which we already populated
        model_id = agent_dict.get(key, {}).get('model_id')

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

        # Track token metrics
        if metrics['total_tokens'] > 0:
            track_token_metrics(
                ld_client=ld_client,
                context=agent_context,
                agent_key=key,
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
                agent_key=key,
                model=model_id,
                cost=calculated_cost,
                orchestrator=orchestrator
            )

        print(f"  ✓ Tracked {agent_metadata[key]}: {metrics['total_tokens']} tokens, ttft: {metrics['time_to_first_token']:.2f}s" if metrics['time_to_first_token'] else f"  ✓ Tracked {agent_metadata[key]}: {metrics['total_tokens']} tokens")

    # Flush events to ensure delivery
    ld_client.flush()

    # Extract final output from TaskResult if available, otherwise fall back to message_contents
    final_output = ""

    if task_result and task_result.messages:
        # Helper functions
        def is_real_text(m) -> bool:
            """Check if message is a real TextMessage with content"""
            return isinstance(m, TextMessage) and isinstance(m.content, str) and m.content.strip()

        def strip_trailing_terminate(s: str) -> str:
            """Remove TERMINATE suffix from content"""
            return s.rstrip().removesuffix("TERMINATE").rstrip()

        # Find the gap synthesizer agent ID
        gap_synthesizer_key = None
        gap_synthesizer_id = None
        for key, info in agent_dict.items():
            if 'gap' in key.lower() or 'synthesizer' in info['name'].lower():
                gap_synthesizer_key = key
                gap_synthesizer_id = info['agent_id']
                break

        # 1) Prefer gap synthesizer agent's messages
        if gap_synthesizer_id:
            final_texts = [
                m.content for m in task_result.messages
                if is_real_text(m) and hasattr(m, 'source') and m.source == gap_synthesizer_id
                and not m.content.strip().startswith("Transferred to")
                and not m.content.strip().startswith("[Function")
            ]

            # Join multiple chunks if present
            if final_texts:
                final_output = "\n\n".join(strip_trailing_terminate(t) for t in final_texts)
                print(f"📄 Extracted {len(final_texts)} message(s) from gap synthesizer")

        # 2) Fallback: collect all agents' substantial text
        if not final_output:
            all_texts = []
            for m in task_result.messages:
                if is_real_text(m) and hasattr(m, 'source'):
                    content = m.content.strip()
                    if not content.startswith("Transferred to") and not content.startswith("[Function") and len(content) > 100:
                        source = getattr(m, 'source', 'unknown')
                        # Add agent header for context
                        agent_name = agent_metadata.get(name_to_key.get(source, ''), source)
                        all_texts.append(f"## {agent_name}\n\n{strip_trailing_terminate(content)}")

            if all_texts:
                final_output = "\n\n---\n\n".join(all_texts)
                print(f"📄 Collected output from {len(all_texts)} agent(s)")

    # 3) Ultimate fallback: use message_contents as before
    if not final_output and message_contents:
        final_outputs = []
        seen_content = set()

        for msg_data in message_contents:
            content = msg_data.get('content', '').strip()
            if content and content not in seen_content:
                if not content.startswith("Transferred to") and not content.startswith("[Function"):
                    if any(keyword in content.lower() for keyword in ['research gap', 'recommendation', 'finding', 'analysis', 'conclusion']):
                        final_outputs.append(content)
                        seen_content.add(content)

        if final_outputs:
            final_output = "\n\n".join(final_outputs)
            print(f"📄 Extracted output from message_contents (fallback)")

    if not final_output:
        final_output = "No analysis output captured. Check transcript for details."

    # Save transcript if TaskResult is available
    transcript_data = None
    if task_result and task_result.messages:
        # Prepare transcript data for JSON serialization
        transcript_data = []
        for msg in task_result.messages:
            msg_data = {
                'type': msg.__class__.__name__,
                'content': getattr(msg, 'content', ''),
                'source': getattr(msg, 'source', ''),
            }
            # Add any other relevant fields
            if hasattr(msg, 'models_usage'):
                msg_data['models_usage'] = msg.models_usage
            transcript_data.append(msg_data)

    # Close clients
    ld_client.close()

    # Return results
    return {
        'execution_id': execution_id,
        'execution_time': execution_time,
        'message_count': len(messages),
        'per_agent_metrics': per_agent_metrics,
        'agent_metadata': agent_metadata,
        'agent_dict': agent_dict,  # Include for cost calculation
        'final_output': final_output,
        'transcript': transcript_data  # Include transcript for saving
    }


def main():
    """Main entry point."""
    print("Starting AutoGen main...")
    parser = argparse.ArgumentParser(description="Run AutoGen gap analysis")
    parser.add_argument("--papers-json", type=str, required=True, help="Path to papers JSON")
    args = parser.parse_args()

    print("╔═══════════════════════════════════════════════════════╗")
    print("║  Research Gap Analysis - AutoGen                      ║")
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

    # Format prompt
    prompt = build_paper_prompt(papers, include_arxiv=False)

    # Generate execution ID
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    execution_id = f"autogen-{timestamp}"

    try:
        # Run the swarm
        result = asyncio.run(run_autogen_swarm(
            prompt=prompt,
            execution_id=execution_id,
            orchestrator="autogen"
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

        # Create agent configs for metadata
        from shared.metadata import create_execution_metadata, AgentConfig

        agent_configs = []
        for key, info in result['agent_dict'].items():
            name = result['agent_metadata'].get(key, key)
            agent_configs.append(AgentConfig(
                key=key,
                name=name,
                role=name,
                model=info['model_id'],
                provider='anthropic',  # AutoGen uses Anthropic
                temperature=0.0,
                tools=info.get('tool_names', [t.__name__ for t in info.get('tools', [])]) if 'tool_names' in info or 'tools' in info else [],
                instructions_preview=info['instructions'][:200] if info.get('instructions') else ''
            ))

        # Create execution metadata
        metadata = create_execution_metadata(
            orchestrator_name="AutoGen",
            orchestrator_version="1.0.0",
            execution_time_seconds=result['execution_time'],
            total_iterations=result['message_count'],
            agents=agent_configs,
            input_papers_count=len(papers)
        )

        # Add token counts to metadata
        for agent_key, metrics in result['per_agent_metrics'].items():
            metadata.add_tokens(
                agent_name=result['agent_metadata'].get(agent_key, agent_key),
                tokens=metrics['total_tokens']
            )

        # Save results
        project_root = Path(__file__).parent.parent.parent
        results_dir = project_root / "results" / "autogen"
        results_dir.mkdir(parents=True, exist_ok=True)

        # Build execution summary
        execution_summary_lines = ["=== AGENT EXECUTION ===", ""]
        for key in result['agent_metadata'].keys():
            name = result['agent_metadata'].get(key, key)
            metrics = result['per_agent_metrics'].get(key, {})
            total_tokens = metrics['total_tokens']
            duration = metrics['duration']
            ran = "yes" if total_tokens > 0 else "no"
            execution_summary_lines.append(
                f"- {name} [{key}]: ran={ran}, tokens={total_tokens}, duration={duration:.2f}s"
            )
        execution_summary = "\n".join(execution_summary_lines)

        report_file = results_dir / f"{timestamp}_{execution_id}_report.txt"
        with open(report_file, 'w') as f:
            f.write(metadata.to_report_section())
            f.write("\n\n")
            f.write(execution_summary)
            f.write("\n\n")
            f.write(result['final_output'])

        print(f"\n📝 Report saved to: {report_file}")

        # Save metadata JSON
        metadata_file = results_dir / f"{timestamp}_{execution_id}_metadata.json"
        with open(metadata_file, 'w') as f:
            f.write(metadata.to_json())

        print(f"📊 Metadata saved to: {metadata_file}")

        # Save transcript if available for debugging
        if result.get('transcript'):
            transcript_file = results_dir / f"{timestamp}_{execution_id}_transcript.json"
            with open(transcript_file, 'w') as f:
                json.dump(result['transcript'], f, indent=2, default=str)
            print(f"🧾 Transcript saved: {transcript_file}")

    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    print("AutoGen script starting...")
    main()