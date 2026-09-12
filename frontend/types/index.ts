export type SystemRole = "EMPLOYEE" | "MANAGER" | "ADMIN";
export type RiskLevel = "LOW" | "MEDIUM" | "HIGH" | "PROHIBITED";
export type DataClassification = "PUBLIC" | "INTERNAL" | "CONFIDENTIAL" | "RESTRICTED";
export type ExecutionStatus = "PENDING" | "COMPLETED" | "FAILED" | "BLOCKED";
export type FeedbackDecision = "APPROVED" | "NEEDS_EDITING" | "REJECTED";

export interface User {
  id: string;
  email: string;
  name: string;
  job_role: string;
  system_role: SystemRole;
  department_id: string | null;
  department_name: string | null;
}

export interface LoginResponse {
  access_token: string;
  token_type: string;
  user: User;
}

export interface InputField {
  name: string;
  label: string;
  type: "text" | "textarea" | "select" | "checkbox" | "code";
  required: boolean;
  options?: string[];
  placeholder?: string;
  help_text?: string;
}

export interface WorkflowGuidance {
  when_to_use?: string[];
  when_not_to_use?: string[];
  good_input_example?: string;
  poor_input_example?: string;
}

export interface WorkflowStats {
  executions: number;
  average_quality: number | null;
  human_approval_rate: number | null;
}

export interface Workflow {
  id: string;
  slug: string;
  name: string;
  description: string;
  department: string;
  target_role: string;
  task_type: string;
  risk_level: RiskLevel;
  status: "DRAFT" | "ACTIVE" | "DEPRECATED";
  requires_human_review: boolean;
  allowed_data_classification: DataClassification;
  expected_output_format: string;
  estimated_manual_minutes: number;
  estimated_assisted_minutes: number;
  input_schema: InputField[];
  guidance: WorkflowGuidance;
  current_version: number;
  stats: WorkflowStats;
}

export interface WorkflowVersion {
  id: string;
  version: number;
  system_prompt: string;
  prompt_template: string;
  model: string;
  provider: string | null;
  temperature: number;
  evaluation_rubric: Record<string, unknown>;
  changelog: string;
  is_active: boolean;
  created_at: string;
}

export interface WorkflowDetail extends Workflow {
  active_version: WorkflowVersion | null;
}

export interface DeterministicCheck {
  name: string;
  passed: boolean;
  score: number;
  detail: string;
}

export interface Evaluation {
  id: string;
  relevance: number | null;
  completeness: number | null;
  groundedness: number | null;
  format_compliance: number | null;
  clarity: number | null;
  safety_passed: boolean;
  safety_checked: boolean;
  overall_score: number;
  deterministic_checks: DeterministicCheck[];
  evaluation_model: string;
  evaluation_provider: string;
  evaluation_reasoning: string;
}

export interface Feedback {
  id: string;
  decision: FeedbackDecision;
  thumbs_up: boolean | null;
  rating: number | null;
  approved: boolean;
  edited: boolean;
  comment: string;
  created_at: string;
}

export interface GovernanceDetection {
  type: string;
  label: string;
  count: number;
  field: string;
}

export interface GovernanceResult {
  allowed: boolean;
  blocked: boolean;
  reason: string;
  policy_key: string;
  detections: GovernanceDetection[];
  warnings: string[];
  requires_human_review: boolean;
  provider: string;
  effective_classification: string;
  moderation_checked: boolean;
  moderation_provider: string;
}

export interface Execution {
  id: string;
  workflow_id: string;
  workflow_name: string;
  workflow_version: number;
  user_id: string;
  user_name: string;
  inputs: Record<string, unknown>;
  output: string;
  model: string;
  provider: string;
  input_tokens: number;
  output_tokens: number;
  latency_ms: number;
  estimated_cost: number;
  status: ExecutionStatus;
  error: string | null;
  blocked_reason: string | null;
  created_at: string;
  evaluation: Evaluation | null;
  feedback: Feedback | null;
  governance: GovernanceResult | null;
}

export interface UserDashboard {
  workflows_completed: number;
  estimated_hours_saved: number;
  average_evaluation_score: number | null;
  human_approval_rate: number | null;
  estimated_cost: number;
  training_completed: number;
  training_total: number;
}

export interface AdoptionSummary {
  total_employees: number;
  licensed_users: number;
  active_users: number;
  effective_users: number;
  adoption_rate: number;
  effective_adoption_rate: number;
  executions: number;
  approval_rate: number;
  estimated_minutes_saved: number;
  estimated_hours_saved: number;
  estimated_spend: number;
  cost_per_execution: number;
  cost_per_approved_output: number;
}

export interface DepartmentAdoption {
  department: string;
  headcount: number;
  active_users: number;
  adoption_rate: number;
  executions: number;
  average_quality: number | null;
  approval_rate: number | null;
  estimated_hours_saved: number;
  estimated_spend: number;
}

export interface QualitySummary {
  overall_quality: number | null;
  dimensions: {
    relevance: number | null;
    completeness: number | null;
    groundedness: number | null;
    format_compliance: number | null;
    clarity: number | null;
  };
  human_approval_rate: number | null;
  evaluated_executions: number;
  safety_pass_rate: number | null;
  judge_human_gap: number | null;
}

export interface WorkflowQuality {
  workflow_id: string;
  name: string;
  department: string;
  executions: number;
  average_quality: number | null;
  approval_rate: number | null;
  estimated_spend: number;
  needs_attention: boolean;
  attention_reason: string;
}

export interface CostBucket {
  label: string;
  spend: number;
  executions: number;
  cost_per_execution: number;
}

export interface CostSummary {
  total_spend: number;
  executions: number;
  approved_executions: number;
  cost_per_execution: number;
  cost_per_approved_output: number;
  by_department: CostBucket[];
  by_workflow: CostBucket[];
  by_model: CostBucket[];
}

export interface VersionQuality {
  version: number;
  executions: number;
  average_quality: number | null;
  relevance: number | null;
  completeness: number | null;
  groundedness: number | null;
  format_compliance: number | null;
  approval_rate: number | null;
  average_cost: number;
  average_latency_ms: number;
  changelog: string;
}

export interface VersionComparison {
  workflow_id: string;
  workflow_name: string;
  versions: VersionQuality[];
  recommendation: string;
}

export interface GovernancePolicy {
  id: string;
  key: string;
  name: string;
  description: string;
  risk_level: RiskLevel;
  enabled: boolean;
  blocking: boolean;
  config: Record<string, unknown>;
}

export interface PolicyViolation {
  id: string;
  policy_key: string;
  violation_type: string;
  severity: string;
  blocked: boolean;
  details: { detections?: { type: string; count: number; field: string }[]; reason?: string };
  workflow_name: string;
  user_name: string;
  created_at: string;
}

export interface AdminOverview {
  adoption: AdoptionSummary;
  quality: QualitySummary;
  top_workflows: WorkflowQuality[];
  needs_attention: WorkflowQuality[];
  blocked_requests: number;
}

export interface ProviderInfo {
  name: string;
  configured: boolean;
  supports_moderation: boolean;
  max_data_classification: string;
  keeps_data_in_house: boolean;
  description: string;
  error: string;
  is_default: boolean;
  is_judge: boolean;
  reachable: boolean | null;
  models: string[];
}

export interface ProviderSettings {
  generation_provider: string;
  evaluation_provider: string;
  moderation_provider: string;
  moderation_fail_closed: boolean;
  providers: ProviderInfo[];
}

export interface TrainingModule {
  id: string;
  slug: string;
  title: string;
  summary: string;
  body: string;
  minutes: number;
  order_index: number;
  completed: boolean;
}
