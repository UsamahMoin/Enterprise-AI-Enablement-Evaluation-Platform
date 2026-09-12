"use client";

import Link from "next/link";
import { useParams } from "next/navigation";
import { useEffect, useMemo, useState } from "react";

import { EvaluationPanel } from "@/components/EvaluationPanel";
import { FeedbackForm } from "@/components/FeedbackForm";
import { PageHeader, Shell } from "@/components/Shell";
import {
  Badge,
  Card,
  ClassificationBadge,
  ErrorBox,
  Loading,
  RiskBadge,
} from "@/components/ui";
import { ApiError, api } from "@/lib/api";
import { useAsync } from "@/lib/useAsync";
import type { Execution, GovernanceResult, InputField, WorkflowDetail } from "@/types";

export default function WorkflowRunPage() {
  return (
    <Shell>
      <WorkflowRunner />
    </Shell>
  );
}

function WorkflowRunner() {
  const params = useParams<{ id: string }>();
  const id = params.id;
  const { data: workflow, error, loading } = useAsync(() => api.workflow(id), [id]);

  if (loading) return <Loading />;
  if (error) return <ErrorBox message={error} />;
  if (!workflow) return null;

  return <RunnerBody workflow={workflow} />;
}

function RunnerBody({ workflow }: { workflow: WorkflowDetail }) {
  const fields = useMemo<InputField[]>(() => workflow.input_schema ?? [], [workflow.input_schema]);
  const [values, setValues] = useState<Record<string, string | boolean>>({});
  const [running, setRunning] = useState(false);
  const [execution, setExecution] = useState<Execution | null>(null);
  const [blockedGovernance, setBlockedGovernance] = useState<GovernanceResult | null>(null);
  const [warning, setWarning] = useState<GovernanceResult | null>(null);
  const [error, setError] = useState("");

  useEffect(() => {
    const initial: Record<string, string | boolean> = {};
    for (const field of fields) {
      initial[field.name] = field.type === "checkbox" ? false : field.options?.[0] ?? "";
    }
    setValues(initial);
  }, [fields]);

  const prohibited = workflow.risk_level === "PROHIBITED";

  async function run(acknowledge = false) {
    setRunning(true);
    setError("");
    setBlockedGovernance(null);
    if (!acknowledge) setWarning(null);
    setExecution(null);

    try {
      const result = await api.execute(workflow.id, values, acknowledge);
      if (result.status === "BLOCKED") {
        setBlockedGovernance(
          result.governance ?? {
            allowed: false,
            blocked: true,
            reason: result.blocked_reason ?? "Blocked by policy.",
            policy_key: "",
            detections: [],
            warnings: [],
            requires_human_review: false,
            provider: result.provider,
            effective_classification: "",
            moderation_checked: true,
            moderation_provider: "",
          },
        );
      } else {
        setExecution(result);
      }
    } catch (err) {
      if (err instanceof ApiError && err.status === 409) {
        setWarning(err.detail as GovernanceResult);
      } else {
        setError(err instanceof Error ? err.message : "The workflow could not be run");
      }
    } finally {
      setRunning(false);
    }
  }

  async function refreshExecution() {
    if (!execution) return;
    setExecution(await api.execution(execution.id));
  }

  return (
    <>
      <PageHeader
        title={workflow.name}
        description={workflow.description}
        action={
          <Link href="/workflows" className="btn-secondary">
            Back to library
          </Link>
        }
      />

      <div className="mb-6 flex flex-wrap items-center gap-2">
        <RiskBadge level={workflow.risk_level} />
        <ClassificationBadge level={workflow.allowed_data_classification} />
        <Badge>{workflow.department}</Badge>
        <Badge>Version {workflow.current_version}</Badge>
        <Badge>{workflow.active_version?.model ?? "model not set"}</Badge>
        {workflow.requires_human_review && (
          <Badge tone="border-amber-200 bg-amber-50 text-amber-900">Human review required</Badge>
        )}
      </div>

      <div className="grid gap-6 lg:grid-cols-[minmax(0,1fr)_360px]">
        <div className="space-y-6">
          {prohibited ? (
            <ErrorBox message="This workflow is registered as a prohibited use case. It cannot be executed; it appears in the catalogue so the boundary is visible and auditable." />
          ) : (
            <Card title="Inputs">
              <form
                className="space-y-4"
                onSubmit={(event) => {
                  event.preventDefault();
                  void run(false);
                }}
              >
                {fields.map((field) => (
                  <Field
                    key={field.name}
                    field={field}
                    value={values[field.name]}
                    onChange={(value) =>
                      setValues((current) => ({ ...current, [field.name]: value }))
                    }
                  />
                ))}
                <button type="submit" className="btn-primary" disabled={running}>
                  {running ? "Running AI workflow..." : "Run workflow"}
                </button>
                {running && (
                  <p className="text-xs text-muted">
                    Model: {workflow.active_version?.model} · Workflow version{" "}
                    {workflow.active_version?.version} · Governance checks run before the request is
                    sent.
                  </p>
                )}
              </form>
            </Card>
          )}

          {error && <ErrorBox message={error} />}

          {blockedGovernance && (
            <GovernanceBlocked
              governance={blockedGovernance}
              onClear={() => {
                setValues((current) => {
                  const cleared = { ...current };
                  for (const detection of blockedGovernance.detections) {
                    if (detection.field && detection.field in cleared) cleared[detection.field] = "";
                  }
                  return cleared;
                });
                setBlockedGovernance(null);
              }}
              onCancel={() => setBlockedGovernance(null)}
            />
          )}

          {warning && (
            <GovernanceWarning
              governance={warning}
              running={running}
              onProceed={() => void run(true)}
              onCancel={() => setWarning(null)}
            />
          )}

          {execution && (
            <Card
              title="Output"
              subtitle={`Version ${execution.workflow_version} · ${execution.model} · ${execution.provider}`}
            >
              <pre className="max-h-[32rem] overflow-auto whitespace-pre-wrap rounded-lg bg-canvas p-4 font-mono text-xs leading-relaxed">
                {execution.output}
              </pre>
            </Card>
          )}

          {execution && <EvaluationPanel execution={execution} />}
          {execution && (
            <FeedbackForm execution={execution} onSubmitted={() => void refreshExecution()} />
          )}
        </div>

        <aside className="space-y-6">
          <GuidancePanel workflow={workflow} />
          <Card title="Governance" subtitle="Applied before every run">
            <ul className="space-y-2 text-xs text-muted">
              <li>
                Approved for{" "}
                <span className="font-medium text-ink">
                  {workflow.allowed_data_classification.toLowerCase()}
                </span>{" "}
                data. Higher-sensitivity categories are blocked before the request is sent.
              </li>
              <li>Input is screened for sensitive data and passed through content moderation.</li>
              <li>
                {workflow.requires_human_review
                  ? "A human approve / edit / reject decision is required before this output is used."
                  : "Human review is optional for this workflow, but always recorded when given."}
              </li>
            </ul>
          </Card>
          <Card title="This workflow" subtitle="Estimated time baseline">
            <dl className="space-y-2 text-sm">
              <Row label="Manual" value={`${workflow.estimated_manual_minutes} min`} />
              <Row label="With this workflow" value={`${workflow.estimated_assisted_minutes} min`} />
              <Row
                label="Estimated saving"
                value={`${workflow.estimated_manual_minutes - workflow.estimated_assisted_minutes} min`}
              />
            </dl>
            <p className="mt-3 text-xs text-muted">
              Credited only when a human approves the output.
            </p>
          </Card>
        </aside>
      </div>
    </>
  );
}

function Row({ label, value }: { label: string; value: string }) {
  return (
    <div className="flex justify-between gap-4">
      <dt className="text-muted">{label}</dt>
      <dd className="font-medium tabular-nums">{value}</dd>
    </div>
  );
}

function Field({
  field,
  value,
  onChange,
}: {
  field: InputField;
  value: string | boolean | undefined;
  onChange: (value: string | boolean) => void;
}) {
  const id = `field-${field.name}`;

  if (field.type === "checkbox") {
    return (
      <label htmlFor={id} className="flex items-start gap-2 text-sm">
        <input
          id={id}
          type="checkbox"
          checked={Boolean(value)}
          onChange={(event) => onChange(event.target.checked)}
          className="mt-0.5"
        />
        <span>
          {field.label}
          {field.help_text && <span className="block text-xs text-muted">{field.help_text}</span>}
        </span>
      </label>
    );
  }

  return (
    <label htmlFor={id} className="block">
      <span className="label">
        {field.label}
        {!field.required && <span className="ml-1 normal-case text-muted">(optional)</span>}
      </span>
      {field.type === "select" ? (
        <select
          id={id}
          className="input mt-1"
          value={String(value ?? "")}
          onChange={(event) => onChange(event.target.value)}
        >
          {(field.options ?? []).map((option) => (
            <option key={option} value={option}>
              {option}
            </option>
          ))}
        </select>
      ) : (
        <textarea
          id={id}
          required={field.required}
          className={`input mt-1 ${field.type === "code" ? "h-56 font-mono" : "h-32"}`}
          value={String(value ?? "")}
          placeholder={field.placeholder}
          onChange={(event) => onChange(event.target.value)}
        />
      )}
      {field.help_text && <span className="mt-1 block text-xs text-muted">{field.help_text}</span>}
    </label>
  );
}

function GovernanceBlocked({
  governance,
  onClear,
  onCancel,
}: {
  governance: GovernanceResult;
  onClear: () => void;
  onCancel: () => void;
}) {
  return (
    <div className="rounded-xl border border-red-200 bg-red-50 p-5">
      <h3 className="text-sm font-semibold text-red-900">
        Potential sensitive information detected
      </h3>
      {governance.detections.length > 0 && (
        <ul className="mt-3 space-y-1 text-sm text-red-900">
          {governance.detections.map((detection) => (
            <li key={`${detection.type}-${detection.field}`}>
              <span className="font-medium">{detection.label}</span>
              {detection.field && <span className="text-red-700"> in “{detection.field}”</span>}
              {detection.count > 1 && <span className="text-red-700"> ×{detection.count}</span>}
            </li>
          ))}
        </ul>
      )}
      <p className="mt-3 text-sm text-red-900">{governance.reason}</p>
      <p className="mt-2 text-xs text-red-800">
        The request was not sent to the AI provider, and the input was not stored. The audit record
        keeps the category and count only — never the value.
      </p>
      <div className="mt-4 flex gap-2">
        <button type="button" onClick={onClear} className="btn-primary">
          Remove data
        </button>
        <button type="button" onClick={onCancel} className="btn-secondary">
          Cancel
        </button>
      </div>
    </div>
  );
}

function GovernanceWarning({
  governance,
  running,
  onProceed,
  onCancel,
}: {
  governance: GovernanceResult;
  running: boolean;
  onProceed: () => void;
  onCancel: () => void;
}) {
  return (
    <div className="rounded-xl border border-amber-200 bg-amber-50 p-5">
      <h3 className="text-sm font-semibold text-amber-900">Check before you run this</h3>
      <ul className="mt-3 list-disc space-y-1 pl-5 text-sm text-amber-900">
        {governance.warnings?.map((warning) => <li key={warning}>{warning}</li>)}
      </ul>
      <div className="mt-4 flex gap-2">
        <button type="button" onClick={onProceed} className="btn-primary" disabled={running}>
          {running ? "Running..." : "Run anyway"}
        </button>
        <button type="button" onClick={onCancel} className="btn-secondary">
          Edit input
        </button>
      </div>
    </div>
  );
}

function GuidancePanel({ workflow }: { workflow: WorkflowDetail }) {
  const guidance = workflow.guidance ?? {};
  const hasContent =
    (guidance.when_to_use?.length ?? 0) > 0 || (guidance.when_not_to_use?.length ?? 0) > 0;
  if (!hasContent) return null;

  return (
    <Card title="Learn how to use this workflow">
      {guidance.when_to_use && guidance.when_to_use.length > 0 && (
        <>
          <p className="label">When to use it</p>
          <ul className="mt-1 space-y-1 text-sm">
            {guidance.when_to_use.map((item) => (
              <li key={item} className="flex gap-2">
                <span className="text-emerald-600">✓</span>
                <span>{item}</span>
              </li>
            ))}
          </ul>
        </>
      )}
      {guidance.when_not_to_use && guidance.when_not_to_use.length > 0 && (
        <>
          <p className="label mt-4">When not to use it</p>
          <ul className="mt-1 space-y-1 text-sm">
            {guidance.when_not_to_use.map((item) => (
              <li key={item} className="flex gap-2">
                <span className="text-red-600">✗</span>
                <span>{item}</span>
              </li>
            ))}
          </ul>
        </>
      )}
      {guidance.good_input_example && (
        <div className="mt-4">
          <p className="label">Example of a good input</p>
          <p className="mt-1 text-xs text-muted">{guidance.good_input_example}</p>
        </div>
      )}
      {guidance.poor_input_example && (
        <div className="mt-3">
          <p className="label">Example of a poor input</p>
          <p className="mt-1 text-xs text-muted">{guidance.poor_input_example}</p>
        </div>
      )}
    </Card>
  );
}
