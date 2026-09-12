from datetime import datetime

from pydantic import BaseModel, Field

from app.core.enums import ExecutionStatus, FeedbackDecision


class ExecutionCreate(BaseModel):
    workflow_id: str
    inputs: dict = Field(default_factory=dict)
    # Set by the client after the user acknowledges a non-blocking warning.
    acknowledge_warnings: bool = False


class DeterministicCheckOut(BaseModel):
    name: str
    passed: bool
    score: float
    detail: str = ""


class EvaluationOut(BaseModel):
    id: str
    relevance: float | None = None
    completeness: float | None = None
    groundedness: float | None = None
    format_compliance: float | None = None
    clarity: float | None = None
    safety_passed: bool = True
    safety_checked: bool = True
    overall_score: float = 0.0
    deterministic_checks: list[DeterministicCheckOut] = Field(default_factory=list)
    evaluation_model: str = ""
    evaluation_provider: str = ""
    evaluation_reasoning: str = ""
    rubric_used: dict = Field(default_factory=dict)

    model_config = {"from_attributes": True}


class FeedbackCreate(BaseModel):
    decision: FeedbackDecision
    thumbs_up: bool | None = None
    rating: int | None = Field(default=None, ge=1, le=5)
    comment: str = ""


class FeedbackOut(BaseModel):
    id: str
    decision: FeedbackDecision
    thumbs_up: bool | None = None
    rating: int | None = None
    approved: bool
    edited: bool
    comment: str
    created_at: datetime

    model_config = {"from_attributes": True}


class GovernanceDetection(BaseModel):
    type: str
    label: str
    count: int
    field: str = ""


class GovernanceOut(BaseModel):
    allowed: bool
    blocked: bool = False
    reason: str = ""
    policy_key: str = ""
    detections: list[GovernanceDetection] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    requires_human_review: bool = False
    provider: str = ""
    effective_classification: str = ""
    moderation_checked: bool = True
    moderation_provider: str = ""


class ExecutionOut(BaseModel):
    id: str
    workflow_id: str
    workflow_name: str = ""
    workflow_version: int = 0
    user_id: str
    user_name: str = ""
    inputs: dict = Field(default_factory=dict)
    output: str = ""
    model: str = ""
    provider: str = ""
    input_tokens: int = 0
    output_tokens: int = 0
    latency_ms: int = 0
    estimated_cost: float = 0.0
    status: ExecutionStatus
    error: str | None = None
    blocked_reason: str | None = None
    created_at: datetime
    evaluation: EvaluationOut | None = None
    feedback: FeedbackOut | None = None
    governance: GovernanceOut | None = None

    model_config = {"from_attributes": True}
