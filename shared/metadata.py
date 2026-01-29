"""
Execution metadata tracking for multi-orchestrator comparison.
Captures orchestrator info, models, prompts, and timing for reproducibility.
"""

from datetime import datetime, timezone
from typing import Dict, List, Optional
from dataclasses import dataclass, field
import json


@dataclass
class AgentConfig:
    """Configuration for a single agent in the swarm."""
    key: str  # LaunchDarkly key (e.g., "paper-reader")
    name: str
    role: str
    model: str
    provider: str
    temperature: float
    tools: List[str]
    instructions_preview: str  # First 200 chars of instructions
    tokens_used: int = 0  # Tokens used by this agent during execution

    def to_dict(self) -> Dict:
        return {
            "key": self.key,
            "name": self.name,
            "role": self.role,
            "model": self.model,
            "provider": self.provider,
            "temperature": self.temperature,
            "tools": self.tools,
            "instructions_preview": self.instructions_preview,
            "tokens_used": self.tokens_used
        }


@dataclass
class ExecutionMetadata:
    """Metadata about a swarm execution for comparison across orchestrators."""
    # Execution info
    orchestrator_name: str  # "Strands", "CrewAI", "LangGraph", "AutoGen"
    orchestrator_version: str
    execution_id: str
    timestamp: str
    execution_time_seconds: float
    total_iterations: int

    # Agent configurations
    agents: List[AgentConfig] = field(default_factory=list)

    # Token usage
    total_tokens: int = 0  # Total tokens used across all agents
    tokens_by_model: Dict[str, int] = field(default_factory=dict)  # Tokens per model type

    # System info
    python_version: Optional[str] = None
    platform: Optional[str] = None

    # Task info
    task_description: str = "Research Gap Analysis"
    input_papers_count: int = 0

    def to_dict(self) -> Dict:
        """Convert to dictionary for serialization."""
        return {
            "orchestrator": {
                "name": self.orchestrator_name,
                "version": self.orchestrator_version,
                "execution_id": self.execution_id
            },
            "execution": {
                "timestamp": self.timestamp,
                "execution_time_seconds": self.execution_time_seconds,
                "total_iterations": self.total_iterations,
                "total_tokens": self.total_tokens,
                "tokens_by_model": self.tokens_by_model
            },
            "agents": [agent.to_dict() for agent in self.agents],
            "system": {
                "python_version": self.python_version,
                "platform": self.platform
            },
            "task": {
                "description": self.task_description,
                "input_papers_count": self.input_papers_count
            }
        }

    def to_json(self, indent: int = 2) -> str:
        """Convert to JSON string."""
        return json.dumps(self.to_dict(), indent=indent)

    def to_report_section(self) -> str:
        """Generate formatted markdown section for inclusion in reports."""
        lines = [
            "=== EXECUTION METADATA ===",
            "",
            f"Generated: {self.timestamp}",
            f"Orchestrator: {self.orchestrator_name} {self.orchestrator_version}",
            f"Execution ID: {self.execution_id}",
            f"Execution Time: {self.execution_time_seconds:.2f} seconds",
            f"Total Iterations: {self.total_iterations}",
            f"Input Papers: {self.input_papers_count}",
            "",
        ]

        # Token usage summary
        if self.total_tokens > 0:
            lines.append("Token Usage:")
            lines.append(f"  Total Tokens: {self.total_tokens:,}")
            if self.tokens_by_model:
                lines.append("  By Model:")
                for model, tokens in sorted(self.tokens_by_model.items()):
                    lines.append(f"    - {model}: {tokens:,} tokens")
            lines.append("")

        lines.append("Agent Configuration:")

        for i, agent in enumerate(self.agents, 1):
            lines.append(f"  {i}. {agent.name}")
            lines.append(f"     Role: {agent.role}")
            lines.append(f"     Model: {agent.model} ({agent.provider})")
            lines.append(f"     Temperature: {agent.temperature}")
            if agent.tokens_used > 0:
                lines.append(f"     Tokens Used: {agent.tokens_used:,}")
            if agent.tools:
                lines.append(f"     Tools: {', '.join(agent.tools)}")
            lines.append(f"     Instructions: {agent.instructions_preview}...")
            lines.append("")

        if self.python_version or self.platform:
            lines.append("System Info:")
            if self.python_version:
                lines.append(f"  Python: {self.python_version}")
            if self.platform:
                lines.append(f"  Platform: {self.platform}")
            lines.append("")

        return "\n".join(lines)

    def add_tokens(self, agent_name: str, tokens: int, model: str = None):
        """
        Add token usage for a specific agent.

        Args:
            agent_name: Name of the agent that used tokens
            tokens: Number of tokens used
            model: Model name (optional, will use agent's model if not provided)
        """
        # Update agent's token count
        for agent in self.agents:
            if agent.name == agent_name or agent.key == agent_name:
                agent.tokens_used += tokens
                # Use agent's model if not provided
                if model is None:
                    model = agent.model
                break

        # Update total tokens
        self.total_tokens += tokens

        # Update tokens by model
        if model and model != "unknown":
            self.tokens_by_model[model] = self.tokens_by_model.get(model, 0) + tokens


def create_execution_metadata(
    orchestrator_name: str,
    orchestrator_version: str,
    execution_time_seconds: float,
    total_iterations: int,
    agents: List[AgentConfig],
    input_papers_count: int = 0
) -> ExecutionMetadata:
    """
    Create execution metadata with automatically generated ID and timestamp.

    Args:
        orchestrator_name: Name of orchestration framework (e.g., "Strands")
        orchestrator_version: Version string (e.g., "1.0.0")
        execution_time_seconds: Total execution time
        total_iterations: Number of agent iterations
        agents: List of agent configurations
        input_papers_count: Number of papers analyzed

    Returns:
        ExecutionMetadata instance
    """
    import platform
    import sys
    import uuid

    now = datetime.now(timezone.utc)

    return ExecutionMetadata(
        orchestrator_name=orchestrator_name,
        orchestrator_version=orchestrator_version,
        execution_id=str(uuid.uuid4())[:8],
        timestamp=now.strftime("%Y-%m-%d %H:%M:%S UTC"),
        execution_time_seconds=execution_time_seconds,
        total_iterations=total_iterations,
        agents=agents,
        python_version=f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}",
        platform=platform.system(),
        input_papers_count=input_papers_count
    )
