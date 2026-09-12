"""Sensitive-data detection.

Deliberately conservative and pattern-based. This is a pre-flight control to
stop obvious sensitive values reaching a model provider - it is not a
complete DLP system, and the Responsible AI doc says so explicitly.

Detections record the *category and count* only. The matched value is never
stored or logged.
"""

import re
from dataclasses import dataclass

from app.core.enums import DataClassification


@dataclass(frozen=True)
class Detector:
    type: str
    label: str
    pattern: re.Pattern[str]
    # Lowest workflow classification that is still allowed to receive it.
    min_classification: DataClassification
    severity: str


def _luhn_valid(digits: str) -> bool:
    """Card-shaped numbers are only reported when they pass a Luhn check,
    which keeps long order numbers from generating false positives."""
    total = 0
    parity = len(digits) % 2
    for index, char in enumerate(digits):
        value = int(char)
        if index % 2 == parity:
            value *= 2
            if value > 9:
                value -= 9
        total += value
    return total % 10 == 0


DETECTORS: list[Detector] = [
    Detector(
        "SSN",
        "Social Security Number",
        re.compile(r"\b(?!000|666|9\d{2})\d{3}-(?!00)\d{2}-(?!0000)\d{4}\b"),
        DataClassification.RESTRICTED,
        "HIGH",
    ),
    Detector(
        "CREDIT_CARD",
        "Credit card number",
        re.compile(r"\b(?:\d[ -]*?){13,19}\b"),
        DataClassification.RESTRICTED,
        "HIGH",
    ),
    Detector(
        "API_KEY",
        "API key or token",
        re.compile(r"\b(?:sk-[A-Za-z0-9_-]{16,}|gh[pousr]_[A-Za-z0-9]{20,}|AKIA[0-9A-Z]{16})\b"),
        DataClassification.RESTRICTED,
        "HIGH",
    ),
    Detector(
        "SECRET",
        "Password or secret",
        re.compile(
            r"(?i)\b(?:password|passwd|secret|api[_-]?key|bearer)\b\s*[:=]\s*\S{6,}"
        ),
        DataClassification.RESTRICTED,
        "HIGH",
    ),
    Detector(
        "EMAIL",
        "Email address",
        re.compile(r"\b[\w.+-]+@[\w-]+\.[\w.]{2,}\b"),
        DataClassification.CONFIDENTIAL,
        "MEDIUM",
    ),
    Detector(
        "PHONE",
        "Phone number",
        re.compile(r"(?<!\d)(?:\+?1[ .-]?)?\(?\d{3}\)?[ .-]\d{3}[ .-]\d{4}(?!\d)"),
        DataClassification.CONFIDENTIAL,
        "MEDIUM",
    ),
]

_CLASSIFICATION_RANK = {
    DataClassification.PUBLIC: 0,
    DataClassification.INTERNAL: 1,
    DataClassification.CONFIDENTIAL: 2,
    DataClassification.RESTRICTED: 3,
}


@dataclass
class Detection:
    type: str
    label: str
    count: int
    severity: str
    min_classification: DataClassification
    field: str = ""


def scan_text(text: str, field: str = "") -> list[Detection]:
    """Return detections found in a single string."""
    findings: list[Detection] = []
    for detector in DETECTORS:
        matches = detector.pattern.findall(text or "")
        if detector.type == "CREDIT_CARD":
            matches = [
                match
                for match in matches
                if _luhn_valid(re.sub(r"\D", "", match)) and 13 <= len(re.sub(r"\D", "", match)) <= 19
            ]
        if matches:
            findings.append(
                Detection(
                    type=detector.type,
                    label=detector.label,
                    count=len(matches),
                    severity=detector.severity,
                    min_classification=detector.min_classification,
                    field=field,
                )
            )
    return findings


def scan_inputs(inputs: dict) -> list[Detection]:
    """Scan every string value of a workflow input payload."""
    findings: list[Detection] = []
    for key, value in (inputs or {}).items():
        if isinstance(value, str):
            findings.extend(scan_text(value, field=key))
    return findings


def exceeds_classification(
    detection: Detection, allowed: DataClassification
) -> bool:
    """True when the workflow is not cleared to receive this data category."""
    return _CLASSIFICATION_RANK[detection.min_classification] > _CLASSIFICATION_RANK[allowed]


def redact(text: str) -> str:
    """Replace detected values with category placeholders.

    Used for audit copies; the platform blocks rather than silently redacts
    user input, so the user always knows what happened.
    """
    result = text or ""
    for detector in DETECTORS:
        result = detector.pattern.sub(f"[REDACTED:{detector.type}]", result)
    return result
