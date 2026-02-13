"""
LaunchDarkly AI SDK Setup - Shared across all orchestrators
"""
import os
import ldclient
from ldclient import Context
from ldclient.config import Config
from ldai.client import LDAIClient, AIConfigRequest


def init_ld(sdk_key: str = None):
    """Initialize LaunchDarkly clients."""
    sdk_key = sdk_key or os.getenv("LD_SDK_KEY")
    ldclient.set_config(Config(sdk_key=sdk_key))
    ld_client = ldclient.get()
    ai_client = LDAIClient(ld_client)
    return ld_client, ai_client


def create_context(user_id: str, orchestrator: str) -> Context:
    """
    Create context with orchestrator attribute for variation routing.

    Use targeting rules in LaunchDarkly to route:
      - orchestrator = "strands"    -> Variation A
      - orchestrator = "langgraph"  -> Variation B
      - orchestrator = "llamaindex" -> Variation C
    """
    return (
        Context.builder(user_id)
        .kind("user")
        .set("orchestrator", orchestrator)
        .build()
    )


def get_ai_config(ai_client: LDAIClient, config_key: str, context: Context):
    """Fetch AI config from LaunchDarkly."""
    from ldai.client import AICompletionConfigDefault
    default = AICompletionConfigDefault(enabled=False)
    return ai_client.config(config_key, context, default)
