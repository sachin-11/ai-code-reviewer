# USD per 1M tokens: (input, output). Update when OpenAI's pricing changes.
PRICING_PER_MILLION_TOKENS = {
    "gpt-4o": (2.50, 10.00),
    "gpt-4o-mini": (0.15, 0.60),
}


def compute_cost(model: str, prompt_tokens: int, completion_tokens: int) -> float:
    input_price, output_price = PRICING_PER_MILLION_TOKENS.get(model, (0.0, 0.0))
    return (prompt_tokens / 1_000_000) * input_price + (completion_tokens / 1_000_000) * output_price


def cost_from_response(model: str, response) -> float:
    usage = getattr(response, "usage", None)
    if usage is None:
        return 0.0
    prompt_tokens = getattr(usage, "prompt_tokens", 0) or 0
    completion_tokens = getattr(usage, "completion_tokens", 0) or 0
    return compute_cost(model, prompt_tokens, completion_tokens)
