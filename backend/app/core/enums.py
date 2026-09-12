"""Domain enumerations shared by models, schemas and services."""

from enum import StrEnum


class SystemRole(StrEnum):
    EMPLOYEE = "EMPLOYEE"
    MANAGER = "MANAGER"
    ADMIN = "ADMIN"


class RiskLevel(StrEnum):
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    PROHIBITED = "PROHIBITED"


class DataClassification(StrEnum):
    """Highest sensitivity of data a workflow is permitted to receive."""

    PUBLIC = "PUBLIC"
    INTERNAL = "INTERNAL"
    CONFIDENTIAL = "CONFIDENTIAL"
    RESTRICTED = "RESTRICTED"


class WorkflowStatus(StrEnum):
    DRAFT = "DRAFT"
    ACTIVE = "ACTIVE"
    DEPRECATED = "DEPRECATED"


class ExecutionStatus(StrEnum):
    PENDING = "PENDING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    BLOCKED = "BLOCKED"


class FeedbackDecision(StrEnum):
    APPROVED = "APPROVED"
    NEEDS_EDITING = "NEEDS_EDITING"
    REJECTED = "REJECTED"


class ViolationType(StrEnum):
    SENSITIVE_DATA = "SENSITIVE_DATA"
    PROHIBITED_USE = "PROHIBITED_USE"
    MODERATION = "MODERATION"
    DATA_CLASSIFICATION = "DATA_CLASSIFICATION"
