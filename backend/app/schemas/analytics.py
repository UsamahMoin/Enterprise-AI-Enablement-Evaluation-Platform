from pydantic import BaseModel, Field


class AdoptionSummary(BaseModel):
    total_employees: int
    licensed_users: int
    active_users: int
    effective_users: int
    adoption_rate: float
    effective_adoption_rate: float
    executions: int
    approval_rate: float
    estimated_minutes_saved: int
    estimated_hours_saved: float
    estimated_spend: float
    cost_per_execution: float
    cost_per_approved_output: float


class DepartmentAdoption(BaseModel):
    department: str
    headcount: int
    active_users: int
    adoption_rate: float
    executions: int
    average_quality: float | None = None
    approval_rate: float | None = None
    estimated_hours_saved: float = 0.0
    estimated_spend: float = 0.0


class QualityDimension(BaseModel):
    relevance: float | None = None
    completeness: float | None = None
    groundedness: float | None = None
    format_compliance: float | None = None
    clarity: float | None = None


class QualitySummary(BaseModel):
    overall_quality: float | None = None
    dimensions: QualityDimension = Field(default_factory=QualityDimension)
    human_approval_rate: float | None = None
    evaluated_executions: int = 0
    safety_pass_rate: float | None = None
    # Gap between the model judge and human approval - neither is ground truth.
    judge_human_gap: float | None = None


class WorkflowQuality(BaseModel):
    workflow_id: str
    name: str
    department: str
    executions: int
    average_quality: float | None = None
    approval_rate: float | None = None
    estimated_spend: float = 0.0
    needs_attention: bool = False
    attention_reason: str = ""


class CostByBucket(BaseModel):
    label: str
    spend: float
    executions: int
    cost_per_execution: float


class CostSummary(BaseModel):
    total_spend: float
    executions: int
    approved_executions: int
    cost_per_execution: float
    cost_per_approved_output: float
    by_department: list[CostByBucket] = Field(default_factory=list)
    by_workflow: list[CostByBucket] = Field(default_factory=list)
    by_model: list[CostByBucket] = Field(default_factory=list)


class UserDashboard(BaseModel):
    workflows_completed: int
    estimated_hours_saved: float
    average_evaluation_score: float | None = None
    human_approval_rate: float | None = None
    estimated_cost: float
    training_completed: int
    training_total: int


class VersionQuality(BaseModel):
    version: int
    executions: int
    average_quality: float | None = None
    relevance: float | None = None
    completeness: float | None = None
    groundedness: float | None = None
    format_compliance: float | None = None
    approval_rate: float | None = None
    average_cost: float = 0.0
    average_latency_ms: float = 0.0
    changelog: str = ""


class VersionComparison(BaseModel):
    workflow_id: str
    workflow_name: str
    versions: list[VersionQuality] = Field(default_factory=list)
    recommendation: str = ""
