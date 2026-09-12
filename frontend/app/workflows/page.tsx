"use client";

import Link from "next/link";
import { useMemo, useState } from "react";

import { PageHeader, Shell } from "@/components/Shell";
import { Badge, ClassificationBadge, ErrorBox, Loading, RiskBadge } from "@/components/ui";
import { api } from "@/lib/api";
import { percent, score, scoreTone, titleCase } from "@/lib/format";
import { useAsync } from "@/lib/useAsync";
import type { Workflow } from "@/types";

const ALL = "All";

export default function WorkflowsPage() {
  return (
    <Shell>
      <WorkflowLibrary />
    </Shell>
  );
}

function WorkflowLibrary() {
  const { data, error, loading } = useAsync(() => api.workflows(), []);
  const [department, setDepartment] = useState(ALL);
  const [role, setRole] = useState(ALL);
  const [taskType, setTaskType] = useState(ALL);
  const [risk, setRisk] = useState(ALL);
  const [status, setStatus] = useState(ALL);

  const options = useMemo(() => {
    const unique = (values: string[]) => [ALL, ...Array.from(new Set(values)).sort()];
    return {
      departments: unique((data ?? []).map((item) => item.department)),
      roles: unique((data ?? []).map((item) => item.target_role)),
      taskTypes: unique((data ?? []).map((item) => item.task_type)),
      risks: unique((data ?? []).map((item) => item.risk_level)),
      statuses: unique((data ?? []).map((item) => item.status)),
    };
  }, [data]);

  const filtered = (data ?? []).filter(
    (workflow) =>
      (department === ALL || workflow.department === department) &&
      (role === ALL || workflow.target_role === role) &&
      (taskType === ALL || workflow.task_type === taskType) &&
      (risk === ALL || workflow.risk_level === risk) &&
      (status === ALL || workflow.status === status),
  );

  return (
    <>
      <PageHeader
        title="Workflow library"
        description="Every workflow is an approved, versioned task with a risk classification, a data-classification limit and its own evaluation rubric."
      />

      <div className="mb-6 flex flex-wrap gap-3">
        <Filter label="Department" value={department} onChange={setDepartment} options={options.departments} />
        <Filter label="Role" value={role} onChange={setRole} options={options.roles} />
        <Filter label="Task type" value={taskType} onChange={setTaskType} options={options.taskTypes} />
        <Filter label="Risk" value={risk} onChange={setRisk} options={options.risks} />
        <Filter label="Status" value={status} onChange={setStatus} options={options.statuses} />
      </div>

      {loading && <Loading />}
      {error && <ErrorBox message={error} />}
      {data && (
        <>
          <p className="mb-3 text-xs text-muted">
            {filtered.length} of {data.length} workflows
          </p>
          <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-3">
            {filtered.map((workflow) => (
              <WorkflowCard key={workflow.id} workflow={workflow} />
            ))}
          </div>
        </>
      )}
    </>
  );
}

function Filter({
  label,
  value,
  onChange,
  options,
}: {
  label: string;
  value: string;
  onChange: (value: string) => void;
  options: string[];
}) {
  return (
    <label className="text-xs">
      <span className="label">{label}</span>
      <select
        className="input mt-1 w-44"
        value={value}
        onChange={(event) => onChange(event.target.value)}
      >
        {options.map((option) => (
          <option key={option} value={option}>
            {option === ALL ? ALL : titleCase(option)}
          </option>
        ))}
      </select>
    </label>
  );
}

function WorkflowCard({ workflow }: { workflow: Workflow }) {
  const prohibited = workflow.risk_level === "PROHIBITED";
  return (
    <article className="card flex flex-col">
      <div className="flex items-start justify-between gap-3">
        <h3 className="text-sm font-semibold">{workflow.name}</h3>
        <RiskBadge level={workflow.risk_level} />
      </div>
      <p className="mt-2 flex-1 text-xs text-muted">{workflow.description}</p>

      <div className="mt-3 flex flex-wrap gap-1.5">
        <Badge>{workflow.department}</Badge>
        <ClassificationBadge level={workflow.allowed_data_classification} />
        {workflow.requires_human_review && (
          <Badge tone="border-amber-200 bg-amber-50 text-amber-900">Human review required</Badge>
        )}
        {workflow.status !== "ACTIVE" && <Badge>{titleCase(workflow.status)}</Badge>}
      </div>

      <dl className="mt-4 grid grid-cols-3 gap-2 border-t border-line pt-3 text-xs">
        <div>
          <dt className="text-muted">Quality</dt>
          <dd className={`font-semibold ${scoreTone(workflow.stats.average_quality)}`}>
            {score(workflow.stats.average_quality)}
          </dd>
        </div>
        <div>
          <dt className="text-muted">Approval</dt>
          <dd className="font-semibold">{percent(workflow.stats.human_approval_rate, 0)}</dd>
        </div>
        <div>
          <dt className="text-muted">Runs</dt>
          <dd className="font-semibold">{workflow.stats.executions}</dd>
        </div>
      </dl>

      {prohibited ? (
        <p className="mt-4 rounded-lg border border-red-200 bg-red-50 px-3 py-2 text-xs text-red-800">
          Registered as a prohibited use case. Blocked before generation — listed so the boundary is
          visible and auditable.
        </p>
      ) : (
        <Link href={`/workflows/${workflow.id}`} className="btn-primary mt-4 w-full">
          Run workflow
        </Link>
      )}
    </article>
  );
}
