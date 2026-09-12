"""Level 1 evaluation: deterministic checks.

No model involved. These are ordinary Python functions, so they are fast,
free, reproducible and testable - which is exactly why they run first.
"""

import ast
import json
import re
from dataclasses import dataclass


@dataclass
class CheckResult:
    name: str
    passed: bool
    score: float  # 0-100
    detail: str = ""

    def as_dict(self) -> dict:
        return {
            "name": self.name,
            "passed": self.passed,
            "score": round(self.score, 2),
            "detail": self.detail,
        }


CODE_FENCE = re.compile(r"```(?:[a-zA-Z0-9_+-]*)\n(.*?)```", re.DOTALL)


def extract_json(output: str) -> dict | list | None:
    """Parse JSON from raw output, tolerating a surrounding code fence."""
    candidate = output.strip()
    fenced = CODE_FENCE.search(candidate)
    if fenced:
        candidate = fenced.group(1).strip()
    try:
        return json.loads(candidate)
    except (json.JSONDecodeError, TypeError):
        return None


def extract_code(output: str) -> str | None:
    match = CODE_FENCE.search(output or "")
    return match.group(1) if match else None


def check_valid_json(output: str) -> CheckResult:
    parsed = extract_json(output)
    ok = parsed is not None
    return CheckResult(
        "valid_json",
        ok,
        100.0 if ok else 0.0,
        "Output parsed as JSON." if ok else "Output is not valid JSON.",
    )


def check_required_json_fields(output: str, required: list[str]) -> CheckResult:
    """Fraction of required top-level keys that are present and non-empty."""
    parsed = extract_json(output)
    if not isinstance(parsed, dict):
        return CheckResult(
            "required_json_fields", False, 0.0, "Output is not a JSON object."
        )
    present = [key for key in required if key in parsed and parsed[key] not in (None, "", [], {})]
    score = 100.0 * len(present) / len(required) if required else 100.0
    missing = sorted(set(required) - set(present))
    return CheckResult(
        "required_json_fields",
        not missing,
        score,
        "All required fields present." if not missing else f"Missing: {', '.join(missing)}",
    )


def check_required_sections(output: str, sections: list[str]) -> CheckResult:
    text = (output or "").lower()
    present = [section for section in sections if section.lower() in text]
    score = 100.0 * len(present) / len(sections) if sections else 100.0
    missing = sorted(set(sections) - set(present))
    return CheckResult(
        "required_sections",
        not missing,
        score,
        "All required sections present." if not missing else f"Missing: {', '.join(missing)}",
    )


def check_max_length(output: str, max_chars: int) -> CheckResult:
    length = len(output or "")
    ok = length <= max_chars
    # Degrade gradually rather than failing hard at max_chars + 1.
    overflow_ratio = 0.0 if ok else min(1.0, (length - max_chars) / max(1, max_chars))
    return CheckResult(
        "max_length",
        ok,
        100.0 if ok else max(0.0, 100.0 * (1 - overflow_ratio)),
        f"{length} characters (limit {max_chars}).",
    )


def check_prohibited_terms(output: str, terms: list[str]) -> CheckResult:
    text = (output or "").lower()
    hits = sorted({term for term in terms if term.lower() in text})
    return CheckResult(
        "prohibited_terms",
        not hits,
        100.0 if not hits else 0.0,
        "No prohibited terms found." if not hits else f"Found: {', '.join(hits)}",
    )


def check_python_syntax(output: str) -> CheckResult:
    code = extract_code(output) or output
    try:
        ast.parse(code)
    except SyntaxError as exc:
        return CheckResult("code_syntax", False, 0.0, f"Syntax error: {exc.msg} (line {exc.lineno}).")
    return CheckResult("code_syntax", True, 100.0, "Code parses as valid Python.")


def check_contains_code_block(output: str) -> CheckResult:
    ok = CODE_FENCE.search(output or "") is not None
    return CheckResult(
        "code_block_present",
        ok,
        100.0 if ok else 0.0,
        "Fenced code block found." if ok else "No fenced code block in output.",
    )


def check_test_coverage_concepts(output: str) -> CheckResult:
    """Heuristic: does the test output reason about more than the happy path?"""
    text = (output or "").lower()
    concepts = {
        "assertion": any(token in text for token in ("assert", "expect(")),
        "edge_case": any(token in text for token in ("empty", "none", "null", "zero", "boundary")),
        "error_case": any(token in text for token in ("raise", "pytest.raises", "throw", "error")),
        "multiple_tests": text.count("def test") >= 2 or text.count("it(") >= 2,
    }
    hit = sum(concepts.values())
    score = 100.0 * hit / len(concepts)
    missing = [name for name, ok in concepts.items() if not ok]
    return CheckResult(
        "test_coverage_concepts",
        hit == len(concepts),
        score,
        "Covers assertions, edge cases and error paths."
        if not missing
        else f"Not evidenced: {', '.join(missing)}",
    )


def check_min_words(output: str, minimum: int) -> CheckResult:
    words = len((output or "").split())
    ok = words >= minimum
    return CheckResult(
        "min_words",
        ok,
        100.0 if ok else 100.0 * words / max(1, minimum),
        f"{words} words (minimum {minimum}).",
    )


def run_deterministic_checks(output: str, config: dict) -> list[CheckResult]:
    """Execute the deterministic checks a workflow rubric asks for."""
    results: list[CheckResult] = []
    config = config or {}

    if config.get("expect_json"):
        results.append(check_valid_json(output))
    if config.get("required_json_fields"):
        results.append(check_required_json_fields(output, config["required_json_fields"]))
    if config.get("required_sections"):
        results.append(check_required_sections(output, config["required_sections"]))
    if config.get("max_chars"):
        results.append(check_max_length(output, int(config["max_chars"])))
    if config.get("min_words"):
        results.append(check_min_words(output, int(config["min_words"])))
    if config.get("prohibited_terms"):
        results.append(check_prohibited_terms(output, config["prohibited_terms"]))
    if config.get("expect_code"):
        results.append(check_contains_code_block(output))
        if str(config["expect_code"]).lower() in ("python", "true", "1"):
            results.append(check_python_syntax(output))
    if config.get("expect_test_concepts"):
        results.append(check_test_coverage_concepts(output))

    return results


def format_compliance_score(results: list[CheckResult]) -> float | None:
    """Mean of the deterministic checks, used as the format dimension."""
    if not results:
        return None
    return round(sum(result.score for result in results) / len(results), 2)
