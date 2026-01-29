"""
Shared pricing information for all orchestrators.
Centralized pricing per 1K tokens for cost estimation across all models.
"""

# Pricing per 1K tokens for calculated_cost
PRICING = {
    # Claude models
    'claude-sonnet-4-5': {'input': 0.003, 'output': 0.015},
    'claude-3-5-sonnet-20241022': {'input': 0.003, 'output': 0.015},  # Keep for backward compatibility

    # OpenAI models
    'gpt-5': {'input': 0.015, 'output': 0.075},  # Estimated pricing for gpt-5
}


def calculate_cost(model_id: str, input_tokens: int, output_tokens: int) -> float:
    """
    Calculate cost based on model and token counts.

    Args:
        model_id: The model identifier
        input_tokens: Number of input tokens
        output_tokens: Number of output tokens

    Returns:
        Estimated cost in dollars
    """
    if model_id not in PRICING:
        return 0.0

    pricing = PRICING[model_id]
    input_cost = (input_tokens / 1000) * pricing['input']
    output_cost = (output_tokens / 1000) * pricing['output']
    return input_cost + output_cost