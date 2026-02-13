"""
Strands + LaunchDarkly AI Config
Simplest possible implementation
"""
import uuid
from strands import Agent
from strands.models.anthropic import AnthropicModel
from ld_setup import init_ld, create_context, get_ai_config


def run_strands_agent(prompt: str):
    # 1. Initialize LaunchDarkly
    ld_client, ai_client = init_ld()

    # 2. Create context with orchestrator for routing
    context = create_context(
        user_id=str(uuid.uuid4()),
        orchestrator="strands"  # Routes to strands-specific variation
    )

    # 3. Get AI config from LaunchDarkly
    config = get_ai_config(ai_client, "orchestrator-config", context)

    # 4. Build Strands agent from LD config
    model = AnthropicModel(
        model_id=config.model.id if config.model else "claude-sonnet-4-5"
    )

    agent = Agent(
        model=model,
        system_prompt=config.messages[0]["content"] if config.messages else "",
    )

    # 5. Run agent
    response = agent(prompt)

    # 6. Track completion
    config.tracker.track_success()

    ld_client.close()
    return response


if __name__ == "__main__":
    result = run_strands_agent("Summarize the key benefits of feature flags")
    print(result)
