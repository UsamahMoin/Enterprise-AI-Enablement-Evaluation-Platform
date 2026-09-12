"""Evaluation-layer tests: deterministic checks and weighted scoring."""

import pytest

from app.services.evaluation.deterministic import (
    check_max_length,
    check_prohibited_terms,
    check_python_syntax,
    check_required_json_fields,
    check_required_sections,
    check_valid_json,
    extract_json,
    format_compliance_score,
    run_deterministic_checks,
)
from app.services.evaluation.scoring import compute_overall, normalise_weights


def test_valid_json_accepts_a_fenced_block():
    assert check_valid_json('```json\n{"a": 1}\n```').passed is True
    assert check_valid_json("not json at all").passed is False


def test_extract_json_returns_none_for_prose():
    assert extract_json("Here is a summary of the meeting.") is None


def test_required_fields_scores_the_fraction_present():
    output = '{"summary": "s", "recommendations": []}'
    # An empty list counts as absent: the field carries no content.
    result = check_required_json_fields(output, ["summary", "recommendations"])
    assert result.score == 50.0
    assert "recommendations" in result.detail

    full = '{"summary": "s", "recommendations": ["do the thing"]}'
    assert check_required_json_fields(full, ["summary", "recommendations"]).score == 100.0


def test_required_sections_is_case_insensitive():
    result = check_required_sections("SUMMARY\n...\nDrivers\n...", ["summary", "drivers"])
    assert result.passed is True


def test_max_length_degrades_rather_than_failing_hard():
    just_over = check_max_length("x" * 110, 100)
    way_over = check_max_length("x" * 300, 100)
    assert just_over.passed is False
    assert just_over.score > way_over.score
    assert way_over.score == 0.0


def test_prohibited_terms_fails_closed():
    assert check_prohibited_terms("As an AI, I cannot help", ["as an ai"]).passed is False
    assert check_prohibited_terms("Happy to help.", ["as an ai"]).passed is True


def test_python_syntax_check():
    assert check_python_syntax("```python\ndef f():\n    return 1\n```").passed is True
    assert check_python_syntax("```python\ndef f(:\n```").passed is False


def test_run_deterministic_checks_only_runs_what_the_rubric_asks_for():
    checks = run_deterministic_checks(
        '{"summary": "s"}', {"expect_json": True, "required_json_fields": ["summary"]}
    )
    assert {check.name for check in checks} == {"valid_json", "required_json_fields"}
    assert run_deterministic_checks("anything", {}) == []


def test_format_compliance_is_the_mean_of_the_checks():
    checks = run_deterministic_checks(
        '{"summary": "s", "decisions": []}',
        {"expect_json": True, "required_json_fields": ["summary", "decisions"]},
    )
    # valid_json 100, required fields 50 -> 75
    assert format_compliance_score(checks) == 75.0
    assert format_compliance_score([]) is None


def test_weights_are_normalised():
    weights = normalise_weights({"relevance": 2, "completeness": 2})
    assert weights == {"relevance": 0.5, "completeness": 0.5}
    assert sum(normalise_weights(None).values()) == pytest.approx(1.0)


def test_missing_dimensions_are_renormalised_not_scored_zero():
    """A groundedness of None means 'not applicable', never 'failed'."""
    scores = {"relevance": 90.0, "completeness": 90.0, "groundedness": None}
    weights = {"relevance": 0.3, "completeness": 0.3, "groundedness": 0.4}

    assert compute_overall(scores, weights, safety_passed=True) == 90.0
    # If N/A were treated as zero the score would collapse to 54.
    assert compute_overall(scores, weights, safety_passed=True) > 54


def test_safety_failure_pulls_the_score_down():
    scores = {"relevance": 100.0}
    weights = {"relevance": 0.5, "safety": 0.5}
    assert compute_overall(scores, weights, safety_passed=True) == 100.0
    assert compute_overall(scores, weights, safety_passed=False) == 50.0


def test_overall_is_zero_when_nothing_is_applicable():
    assert compute_overall({"relevance": None}, {"relevance": 1.0}, safety_passed=True) == 0.0
