import type {
  AdminOverview,
  AdoptionSummary,
  CostSummary,
  DepartmentAdoption,
  Evaluation,
  Execution,
  Feedback,
  GovernancePolicy,
  LoginResponse,
  PolicyViolation,
  ProviderSettings,
  QualitySummary,
  TrainingModule,
  User,
  UserDashboard,
  VersionComparison,
  Workflow,
  WorkflowDetail,
  WorkflowQuality,
  WorkflowVersion,
} from "@/types";

const BASE_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";
const TOKEN_KEY = "eail.token";
const USER_KEY = "eail.user";

export class ApiError extends Error {
  status: number;
  detail: unknown;

  constructor(status: number, message: string, detail?: unknown) {
    super(message);
    this.name = "ApiError";
    this.status = status;
    this.detail = detail;
  }
}

export function getToken(): string | null {
  if (typeof window === "undefined") return null;
  return window.localStorage.getItem(TOKEN_KEY);
}

export function storeSession(token: string, user: User): void {
  window.localStorage.setItem(TOKEN_KEY, token);
  window.localStorage.setItem(USER_KEY, JSON.stringify(user));
}

export function getStoredUser(): User | null {
  if (typeof window === "undefined") return null;
  const raw = window.localStorage.getItem(USER_KEY);
  if (!raw) return null;
  try {
    return JSON.parse(raw) as User;
  } catch {
    return null;
  }
}

export function clearSession(): void {
  window.localStorage.removeItem(TOKEN_KEY);
  window.localStorage.removeItem(USER_KEY);
}

async function request<T>(path: string, options: RequestInit = {}): Promise<T> {
  const token = getToken();
  const headers: Record<string, string> = {
    "Content-Type": "application/json",
    ...((options.headers as Record<string, string>) ?? {}),
  };
  if (token) headers.Authorization = `Bearer ${token}`;

  let response: Response;
  try {
    response = await fetch(`${BASE_URL}${path}`, { ...options, headers });
  } catch {
    throw new ApiError(0, `Cannot reach the API at ${BASE_URL}. Is the backend running?`);
  }

  if (response.status === 401 && typeof window !== "undefined") {
    clearSession();
    if (!window.location.pathname.startsWith("/login")) {
      window.location.href = "/login";
    }
  }

  if (!response.ok) {
    let detail: unknown;
    let message = `Request failed (${response.status})`;
    try {
      const body = await response.json();
      detail = body.detail ?? body;
      if (typeof body.detail === "string") message = body.detail;
      else if (body.detail?.message) message = body.detail.message;
    } catch {
      /* response had no JSON body */
    }
    throw new ApiError(response.status, message, detail);
  }

  if (response.status === 204) return undefined as T;
  return (await response.json()) as T;
}

export const api = {
  login: (email: string, password: string) =>
    request<LoginResponse>("/auth/login", {
      method: "POST",
      body: JSON.stringify({ email, password }),
    }),
  me: () => request<User>("/auth/me"),

  workflows: (params: Record<string, string> = {}) => {
    const query = new URLSearchParams(params).toString();
    return request<Workflow[]>(`/workflows${query ? `?${query}` : ""}`);
  },
  workflow: (id: string) => request<WorkflowDetail>(`/workflows/${id}`),
  workflowVersions: (id: string) => request<WorkflowVersion[]>(`/workflows/${id}/versions`),
  createVersion: (id: string, body: Record<string, unknown>) =>
    request<WorkflowVersion>(`/workflows/${id}/versions`, {
      method: "POST",
      body: JSON.stringify(body),
    }),

  execute: (workflowId: string, inputs: Record<string, unknown>, acknowledge = false) =>
    request<Execution>("/executions", {
      method: "POST",
      body: JSON.stringify({
        workflow_id: workflowId,
        inputs,
        acknowledge_warnings: acknowledge,
      }),
    }),
  executions: (params: Record<string, string> = {}) => {
    const query = new URLSearchParams(params).toString();
    return request<Execution[]>(`/executions${query ? `?${query}` : ""}`);
  },
  execution: (id: string) => request<Execution>(`/executions/${id}`),
  reevaluate: (id: string) => request<Evaluation>(`/executions/${id}/evaluate`, { method: "POST" }),
  feedback: (id: string, body: Record<string, unknown>) =>
    request<Feedback>(`/executions/${id}/feedback`, {
      method: "POST",
      body: JSON.stringify(body),
    }),

  myDashboard: (days = 30) => request<UserDashboard>(`/analytics/me?days=${days}`),
  adoption: (days = 30) => request<AdoptionSummary>(`/analytics/adoption?days=${days}`),
  departments: (days = 30) => request<DepartmentAdoption[]>(`/analytics/departments?days=${days}`),
  quality: (days = 30) => request<QualitySummary>(`/analytics/quality?days=${days}`),
  workflowQuality: (days = 30) => request<WorkflowQuality[]>(`/analytics/workflows?days=${days}`),
  cost: (days = 30) => request<CostSummary>(`/analytics/cost?days=${days}`),
  versionComparison: (workflowId: string) =>
    request<VersionComparison>(`/analytics/workflows/${workflowId}/versions`),

  adminOverview: (days = 30) => request<AdminOverview>(`/admin/overview?days=${days}`),
  policies: () => request<GovernancePolicy[]>("/admin/governance"),
  updatePolicy: (id: string, body: Record<string, unknown>) =>
    request<GovernancePolicy>(`/admin/governance/${id}`, {
      method: "PUT",
      body: JSON.stringify(body),
    }),
  violations: (limit = 50) => request<PolicyViolation[]>(`/admin/violations?limit=${limit}`),
  providers: () => request<ProviderSettings>("/admin/providers"),

  trainingModules: () => request<TrainingModule[]>("/training/modules"),
  completeModule: (id: string) =>
    request<{ completed: number; total: number }>(`/training/modules/${id}/complete`, {
      method: "POST",
    }),
};
