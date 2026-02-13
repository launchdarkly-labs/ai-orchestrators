"""
LlamaIndex + LaunchDarkly AI Config
Simplest possible implementation
"""
import uuid
from llama_index.llms.anthropic import Anthropic
from llama_index.core.chat_engine import SimpleChatEngine
from ld_setup import init_ld, create_context, get_ai_config


def run_llamaindex_agent(prompt: str):
    # 1. Initialize LaunchDarkly
    ld_client, ai_client = init_ld()

    # 2. Create context with orchestrator for routing
    context = create_context(
        user_id=str(uuid.uuid4()),
        orchestrator="llamaindex"  # Routes to llamaindex-specific variation
    )

    # 3. Get AI config from LaunchDarkly
    config = get_ai_config(ai_client, "orchestrator-config", context)

    # 4. Build LLM from LD config
    llm = Anthropic(
        model=config.model.id if config.model else "claude-sonnet-4-5"
    )

    system_prompt = config.messages[0]["content"] if config.messages else ""

    # 5. Create chat engine
    chat_engine = SimpleChatEngine.from_defaults(
        llm=llm,
        system_prompt=system_prompt,
    )

    # 6. Run query
    response = chat_engine.chat(prompt)

    # 7. Track completion
    config.tracker.track_success()

    ld_client.close()
    return str(response)


if __name__ == "__main__":
    result = run_llamaindex_agent("Summarize the key benefits of feature flags")
    print(result)
