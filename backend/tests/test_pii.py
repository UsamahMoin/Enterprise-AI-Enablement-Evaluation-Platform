"""Sensitive-data detector tests. Every value here is synthetic."""

import pytest

from app.core.enums import DataClassification
from app.services.governance.pii import exceeds_classification, redact, scan_inputs, scan_text


@pytest.mark.parametrize(
    "text,expected",
    [
        ("My SSN is 123-45-6789", "SSN"),
        ("card 4111 1111 1111 1111 on file", "CREDIT_CARD"),
        ("key sk-abcdefghijklmnop1234", "API_KEY"),
        ("AKIAIOSFODNN7EXAMPLE", "API_KEY"),
        ("password: hunter2000", "SECRET"),
        ("write to alex.rivera@acme-demo.test", "EMAIL"),
        ("call 555-010-4477", "PHONE"),
    ],
)
def test_detects_each_category(text, expected):
    assert expected in {finding.type for finding in scan_text(text)}


def test_clean_text_produces_no_findings():
    assert scan_text("Refactor the billing module and add tests for the retry path.") == []


def test_card_shaped_numbers_must_pass_luhn():
    """Order numbers and long ids should not be reported as payment cards."""
    assert "CREDIT_CARD" not in {f.type for f in scan_text("order 1234567890123456")}
    assert "CREDIT_CARD" in {f.type for f in scan_text("4111111111111111")}


def test_counts_multiple_occurrences():
    findings = scan_text("a@x.test and b@y.test and c@z.test")
    email = next(f for f in findings if f.type == "EMAIL")
    assert email.count == 3


def test_scan_inputs_records_the_field_name():
    findings = scan_inputs({"notes": "SSN 123-45-6789", "language": "Python"})
    assert findings[0].field == "notes"


def test_classification_gate():
    """An SSN is over the line for an INTERNAL workflow; an email is not, and
    is warned about instead. On a PUBLIC workflow the email is over the line too."""
    ssn = scan_text("123-45-6789")[0]
    email = scan_text("a@b.test")[0]

    assert exceeds_classification(ssn, DataClassification.INTERNAL) is True
    assert exceeds_classification(ssn, DataClassification.RESTRICTED) is False
    assert exceeds_classification(email, DataClassification.INTERNAL) is False
    assert exceeds_classification(email, DataClassification.PUBLIC) is True


def test_redaction_replaces_the_value_with_its_category():
    redacted = redact("SSN 123-45-6789 and mail a@b.test")
    assert "123-45-6789" not in redacted
    assert "a@b.test" not in redacted
    assert "[REDACTED:SSN]" in redacted
