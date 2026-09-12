"""Weighted overall score.

Weights live on the workflow rubric rather than in one global constant,
because a structured extraction task and a customer-facing email do not
deserve the same weighting. Dimensions that are not applicable (typically
groundedness, when no reference material was supplied) are dropped and the
remaining weights renormalised, so an N/A never silently scores zero.
"""

DEFAULT_WEIGHTS: dict[str, float] = {
    "relevance": 0.30,
    "completeness": 0.25,
    "groundedness": 0.25,
    "format_compliance": 0.10,
    "safety": 0.10,
}


def normalise_weights(weights: dict[str, float] | None) -> dict[str, float]:
    weights = {k: float(v) for k, v in (weights or DEFAULT_WEIGHTS).items() if float(v) > 0}
    total = sum(weights.values())
    if total <= 0:
        return dict(DEFAULT_WEIGHTS)
    return {key: value / total for key, value in weights.items()}


def compute_overall(
    scores: dict[str, float | None],
    weights: dict[str, float] | None = None,
    *,
    safety_passed: bool = True,
    safety_checked: bool = True,
) -> float:
    """Combine available dimension scores into a 0-100 overall score.

    When safety could not be checked - no provider in the chain offers
    moderation - the dimension is dropped and the remaining weights are
    renormalised. Awarding full safety marks for a check that never ran would
    quietly inflate the score of exactly the configuration that deserves the
    most scrutiny.
    """
    weights = normalise_weights(weights)
    values = dict(scores)
    values["safety"] = (100.0 if safety_passed else 0.0) if safety_checked else None

    applicable = {
        key: weight
        for key, weight in weights.items()
        if values.get(key) is not None
    }
    if not applicable:
        return 0.0

    total_weight = sum(applicable.values())
    weighted = sum(values[key] * weight for key, weight in applicable.items())
    return round(weighted / total_weight, 2)
