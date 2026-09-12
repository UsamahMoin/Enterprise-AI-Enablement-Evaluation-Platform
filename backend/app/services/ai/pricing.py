"""Token pricing table used for cost estimation.

Prices are USD per 1M tokens and are an *estimate* recorded at execution
time; they are configuration, not a billing source of truth.
"""

PRICING: dict[str, tuple[float, float]] = {
    # model: (input per 1M, output per 1M)
    "gpt-4.1": (2.00, 8.00),
    "gpt-4.1-mini": (0.40, 1.60),
    "gpt-4.1-nano": (0.10, 0.40),
    "gpt-4o": (2.50, 10.00),
    "gpt-4o-mini": (0.15, 0.60),
    "stub-model": (0.15, 0.60),
}

DEFAULT_PRICE = (0.40, 1.60)


def estimate_cost(model: str, input_tokens: int, output_tokens: int) -> float:
    """Return the estimated USD cost of a single call."""
    price_in, price_out = PRICING.get(model, DEFAULT_PRICE)
    cost = (input_tokens / 1_000_000) * price_in + (output_tokens / 1_000_000) * price_out
    return round(cost, 6)
