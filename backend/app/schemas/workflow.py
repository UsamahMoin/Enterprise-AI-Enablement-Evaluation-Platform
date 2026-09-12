from datetime import datetime

from pydantic import BaseModel, Field

from app.core.enums import DataClassification, RiskLevel, WorkflowStatus


class InputField(BaseModel):
    name: str
    label: str
    type: str = "text"  # text | textarea | select | checkbox | code
    required: bool = True
    options: list[str] = Field(default_factory=list)
    placeholder: str = ""
    help_text: str = ""


class WorkflowGuidance(BaseModel):
    when_to_use: list[str] = Field(default_factory=list)
    when_not_to_use: list[str] = Field(default_factory=list)
    good_input_example: str = ""
    poor_input_example: str = ""


class WorkflowVersionOut(BaseModel):
    id: str
    version: int
    system_prompt: str
    prompt_template: str
    model: str
    temperature: float
    evaluation_rubric: dict
    changelog: str
    is_active: bool
    created_at: datetime

    model_config = {"from_attributes": True}


class WorkflowVersionCreate(BaseModel):
    system_prompt: str
    prompt_template: str
    model: str | None = None
    temperature: float = 0.2
    evaluation_rubric: dict | None = None
    changelog: str = ""
    activate: bool = True


class WorkflowStats(BaseModel):
    executions: int = 0
    average_quality: float | None = None
    human_approval_rate: float | None = None


class WorkflowOut(BaseModel):
    id: str
    slug: str
    name: str
    description: str
    department: str
    target_role: str
    task_type: str
    risk_level: RiskLevel
    status: WorkflowStatus
    requires_human_review: bool
    allowed_data_classification: DataClassification
    expected_output_format: str
    estimated_manual_minutes: int
    estimated_assisted_minutes: int
    input_schema: list = Field(default_factory=list)
    guidance: dict = Field(default_factory=dict)
    current_version: int
    stats: WorkflowStats = Field(default_factory=WorkflowStats)

    model_config = {"from_attributes": True}


class WorkflowDetail(WorkflowOut):
    active_version: WorkflowVersionOut | None = None


class WorkflowCreate(BaseModel):
    slug: str
    name: str
    description: str = ""
    department: str
    target_role: str
    task_type: str = "generation"
    risk_level: RiskLevel = RiskLevel.LOW
    requires_human_review: bool = False
    allowed_data_classification: DataClassification = DataClassification.INTERNAL
    expected_output_format: str = "text"
    estimated_manual_minutes: int = 10
    estimated_assisted_minutes: int = 3
    input_schema: list[InputField] = Field(default_factory=list)
    guidance: WorkflowGuidance = Field(default_factory=WorkflowGuidance)
    system_prompt: str
    prompt_template: str
    model: str | None = None
    temperature: float = 0.2
    evaluation_rubric: dict | None = None


class WorkflowUpdate(BaseModel):
    name: str | None = None
    description: str | None = None
    status: WorkflowStatus | None = None
    risk_level: RiskLevel | None = None
    requires_human_review: bool | None = None
    allowed_data_classification: DataClassification | None = None
    estimated_manual_minutes: int | None = None
