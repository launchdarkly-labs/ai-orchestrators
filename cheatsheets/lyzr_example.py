"""
Lyzr + LaunchDarkly AI Config
Simplest possible implementation
"""
import uuid
from lyzr_agent_api import AgentAPI, ChatRequest
from ld_setup import init_ld, create_context, get_ai_config


def run_lyzr_agent(prompt: str):
    # 1. Initialize LaunchDarkly
    ld_client, ai_client = init_ld()

    # 2. Create context with orchestrator for routing
    context = create_context(
        user_id=str(uuid.uuid4()),
        orchestrator="lyzr"  # Routes to lyzr-specific variation
    )

    # 3. Get AI config from LaunchDarkly
    config = get_ai_config(ai_client, "orchestrator-config", context)

    # 4. Initialize Lyzr Agent API
    agent_api = AgentAPI()

    # 5. Create chat request with LD config
    system_prompt = config.messages[0]["content"] if config.messages else ""

    request = ChatRequest(
        user_id=str(uuid.uuid4()),
        agent_id="your-agent-id",  # Pre-configured in Lyzr platform
        message=prompt,
        system_prompt=system_prompt,
    )

    # 6. Run agent
    response = agent_api.chat(request)

    # 7. Track completion
    config.tracker.track_success()

    ld_client.close()
    return response.message


if __name__ == "__main__":
    result = run_lyzr_agent("Summarize the key benefits of feature flags")
    print(result)
