"use client";

import { useState } from "react";

import { PageHeader, Shell } from "@/components/Shell";
import {
  AdoptionBar,
  Card,
  ErrorBox,
  Loading,
  ScoreBar,
  StatTile,
  Table,
} from "@/components/ui";
import { api } from "@/lib/api";
import { hours, money, percent, score, scoreTone } from "@/lib/format";
import { useAsync } from "@/lib/useAsync";
import { VersionComparisonCard } from "@/components/VersionComparison";

const TABS = ["Adoption", "Quality", "Cost", "Prompt versions"] as const;
type Tab = (typeof TABS)[number];

export default function AnalyticsPage() {
  return (
    <Shell>
      <Analytics />
    </Shell>
  );
}

function Analytics() {
  const [tab, setTab] = useState<Tab>("Adoption");
  const [days, setDays] = useState(30);

  return (
    <>
      <PageHeader
        title="Analytics"
        description="Whether anyone is actually benefiting — not how many prompts were sent."
        action={
          <select
            className="input w-40"
            value={days}
            onChange={(event) => setDays(Number(event.target.value))}
          >
            <option value={7}>Last 7 days</option>
            <option value={30}>Last 30 days</option>
            <option value={90}>Last 90 days</option>
          </select>
        }
      />

      <div className="mb-6 flex flex-wrap gap-1 border-b border-line">
        {TABS.map((item) => (
          <button
            key={item}
            type="button"
            onClick={() => setTab(item)}
            className={`-mb-px border-b-2 px-3 py-2 text-sm transition ${
              tab === item
                ? "border-brand-600 font-medium text-brand-700"
                : "border-transparent text-muted hover:text-ink"
            }`}
          >
            {item}
          </button>
        ))}
      </div>

      {tab === "Adoption" && <AdoptionTab days={days} />}
      {tab === "Quality" && <QualityTab days={days} />}
      {tab === "Cost" && <CostTab days={days} />}
      {tab === "Prompt versions" && <VersionsTab />}
    </>
  );
}

function AdoptionTab({ days }: { days: number }) {
  const summary = useAsync(() => api.adoption(days), [days]);
  const departments = useAsync(() => api.departments(days), [days]);

  return (
    <div className="space-y-6">
      {summary.loading && <Loading />}
      {summary.error && <ErrorBox message={summary.error} />}
      {summary.data && (
        <>
          <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
            <StatTile
              label="Adoption"
              value={percent(summary.data.adoption_rate, 1)}
              hint={`${summary.data.active_users} of ${summary.data.total_employees} employees active`}
            />
            <StatTile
              label="Effective adoption"
              value={percent(summary.data.effective_adoption_rate, 1)}
              hint={`${summary.data.effective_users} produced an output someone approved`}
            />
            <StatTile label="Workflow executions" value={summary.data.executions.toLocaleString()} />
            <StatTile label="Human approval" value={percent(summary.data.approval_rate, 1)} />
          </div>

          <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
            <StatTile
              label="Ever used the platform"
              value={summary.data.licensed_users}
              hint="Having access is not the same as using it"
            />
            <StatTile
              label="Estimated time saved"
              value={hours(summary.data.estimated_hours_saved)}
              hint="Approved outputs, against a per-workflow baseline"
            />
            <StatTile label="Estimated AI spend" value={money(summary.data.estimated_spend)} />
            <StatTile
              label="Cost per approved output"
              value={money(summary.data.cost_per_approved_output, 4)}
              hint={`vs ${money(summary.data.cost_per_execution, 4)} per execution`}
            />
          </div>

          <Card
            title="Usage vs effective usage"
            subtitle="Volume is not value. The second number only counts work a human accepted."
          >
            <div className="space-y-4">
              <Funnel
                label="Employees"
                value={summary.data.total_employees}
                total={summary.data.total_employees}
              />
              <Funnel
                label="Ever used the platform"
                value={summary.data.licensed_users}
                total={summary.data.total_employees}
              />
              <Funnel
                label="Active in this window"
                value={summary.data.active_users}
                total={summary.data.total_employees}
              />
              <Funnel
                label="Produced an approved output"
                value={summary.data.effective_users}
                total={summary.data.total_employees}
              />
            </div>
          </Card>
        </>
      )}

      {departments.loading && <Loading />}
      {departments.error && <ErrorBox message={departments.error} />}
      {departments.data && (
        <Card
          title="Department adoption"
          subtitle="Where enablement effort should go next."
        >
          <Table
            headers={["Department", "Adoption", "Active", "Executions", "Quality", "Approval", "Est. hours saved"]}
          >
            {departments.data.map((row) => (
              <tr key={row.department}>
                <td className="py-2.5 pr-4 font-medium">{row.department}</td>
                <td className="py-2.5 pr-4">
                  <AdoptionBar value={row.adoption_rate} />
                </td>
                <td className="py-2.5 pr-4 tabular-nums text-muted">
                  {row.active_users} / {row.headcount}
                </td>
                <td className="py-2.5 pr-4 tabular-nums">{row.executions}</td>
                <td className={`py-2.5 pr-4 tabular-nums font-medium ${scoreTone(row.average_quality)}`}>
                  {score(row.average_quality)}
                </td>
                <td className="py-2.5 pr-4 tabular-nums">{percent(row.approval_rate, 0)}</td>
                <td className="py-2.5 tabular-nums">{row.estimated_hours_saved.toFixed(1)}</td>
              </tr>
            ))}
          </Table>
        </Card>
      )}
    </div>
  );
}

function Funnel({ label, value, total }: { label: string; value: number; total: number }) {
  const width = total ? (100 * value) / total : 0;
  return (
    <div>
      <div className="flex items-baseline justify-between text-sm">
        <span className="text-muted">{label}</span>
        <span className="font-semibold tabular-nums">{value}</span>
      </div>
      <div className="mt-1 h-2.5 w-full overflow-hidden rounded-full bg-line">
        <div className="h-full rounded-full bg-brand-500" style={{ width: `${width}%` }} />
      </div>
    </div>
  );
}

function QualityTab({ days }: { days: number }) {
  const quality = useAsync(() => api.quality(days), [days]);
  const workflows = useAsync(() => api.workflowQuality(days), [days]);

  return (
    <div className="space-y-6">
      {quality.loading && <Loading />}
      {quality.error && <ErrorBox message={quality.error} />}
      {quality.data && (
        <>
          <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
            <StatTile
              label="Overall AI quality"
              value={score(quality.data.overall_quality)}
              tone={scoreTone(quality.data.overall_quality)}
              hint={`${quality.data.evaluated_executions.toLocaleString()} evaluated executions`}
            />
            <StatTile label="Human approval" value={percent(quality.data.human_approval_rate, 1)} />
            <StatTile label="Safety pass rate" value={percent(quality.data.safety_pass_rate, 1)} />
            <StatTile
              label="Judge − human gap"
              value={
                quality.data.judge_human_gap === null
                  ? "—"
                  : `${quality.data.judge_human_gap > 0 ? "+" : ""}${quality.data.judge_human_gap.toFixed(1)}`
              }
              hint="Positive means the model judge is more generous than people"
            />
          </div>

          <div className="grid gap-6 lg:grid-cols-2">
            <Card title="Quality by dimension">
              <div className="space-y-3">
                <ScoreBar label="Relevance" value={quality.data.dimensions.relevance} />
                <ScoreBar label="Completeness" value={quality.data.dimensions.completeness} />
                <ScoreBar label="Groundedness" value={quality.data.dimensions.groundedness} />
                <ScoreBar label="Format compliance" value={quality.data.dimensions.format_compliance} />
                <ScoreBar label="Clarity" value={quality.data.dimensions.clarity} />
              </div>
            </Card>
            <Card title="Why both numbers are kept">
              <p className="text-sm text-muted">
                The overall score comes from a model judging another model&apos;s output. The
                approval rate comes from the person who had to use it. When those two diverge, the
                rubric is usually wrong — and you only see that divergence by measuring both.
              </p>
              <p className="mt-3 text-sm text-muted">
                Automated evaluation is what makes scoring every execution affordable. It is not
                ground truth, and this platform does not present it as such.
              </p>
            </Card>
          </div>
        </>
      )}

      {workflows.loading && <Loading />}
      {workflows.error && <ErrorBox message={workflows.error} />}
      {workflows.data && (
        <Card title="Quality by workflow" subtitle="Lowest first — this is the queue of work.">
          <Table headers={["Workflow", "Department", "Runs", "Quality", "Approval", "Spend", ""]}>
            {workflows.data.map((row) => (
              <tr key={row.workflow_id}>
                <td className="py-2.5 pr-4 font-medium">{row.name}</td>
                <td className="py-2.5 pr-4 text-muted">{row.department}</td>
                <td className="py-2.5 pr-4 tabular-nums">{row.executions}</td>
                <td className={`py-2.5 pr-4 font-semibold tabular-nums ${scoreTone(row.average_quality)}`}>
                  {score(row.average_quality)}
                </td>
                <td className="py-2.5 pr-4 tabular-nums">{percent(row.approval_rate, 0)}</td>
                <td className="py-2.5 pr-4 tabular-nums text-muted">{money(row.estimated_spend)}</td>
                <td className="py-2.5 text-xs">
                  {row.needs_attention && (
                    <span className="rounded-md border border-amber-200 bg-amber-50 px-2 py-0.5 text-amber-900">
                      Needs attention
                    </span>
                  )}
                </td>
              </tr>
            ))}
          </Table>
        </Card>
      )}
    </div>
  );
}

function CostTab({ days }: { days: number }) {
  const cost = useAsync(() => api.cost(days), [days]);

  return (
    <div className="space-y-6">
      {cost.loading && <Loading />}
      {cost.error && <ErrorBox message={cost.error} />}
      {cost.data && (
        <>
          <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
            <StatTile label="Total AI spend" value={money(cost.data.total_spend)} />
            <StatTile label="Executions" value={cost.data.executions.toLocaleString()} />
            <StatTile
              label="Cost per execution"
              value={money(cost.data.cost_per_execution, 4)}
            />
            <StatTile
              label="Cost per approved output"
              value={money(cost.data.cost_per_approved_output, 4)}
              hint={`${cost.data.approved_executions.toLocaleString()} approved`}
            />
          </div>

          <div className="grid gap-6 lg:grid-cols-3">
            <CostBreakdown title="By department" rows={cost.data.by_department} />
            <CostBreakdown title="By workflow" rows={cost.data.by_workflow} />
            <CostBreakdown
              title="By model"
              rows={cost.data.by_model}
              subtitle="Is the expensive model earning its place on this workflow?"
            />
          </div>
        </>
      )}
    </div>
  );
}

function CostBreakdown({
  title,
  rows,
  subtitle,
}: {
  title: string;
  rows: { label: string; spend: number; executions: number; cost_per_execution: number }[];
  subtitle?: string;
}) {
  const max = Math.max(...rows.map((row) => row.spend), 0.0001);
  return (
    <Card title={title} subtitle={subtitle}>
      <ul className="space-y-3">
        {rows.slice(0, 8).map((row) => (
          <li key={row.label}>
            <div className="flex items-baseline justify-between gap-3 text-sm">
              <span className="truncate">{row.label}</span>
              <span className="font-semibold tabular-nums">{money(row.spend)}</span>
            </div>
            <div className="mt-1 h-1.5 w-full overflow-hidden rounded-full bg-line">
              <div
                className="h-full rounded-full bg-brand-500"
                style={{ width: `${(100 * row.spend) / max}%` }}
              />
            </div>
            <p className="mt-0.5 text-xs text-muted">
              {row.executions.toLocaleString()} runs · {money(row.cost_per_execution, 4)} each
            </p>
          </li>
        ))}
      </ul>
    </Card>
  );
}

function VersionsTab() {
  const workflows = useAsync(() => api.workflows(), []);
  const [selected, setSelected] = useState<string>("");

  const options = (workflows.data ?? []).filter((workflow) => workflow.current_version > 1);
  const active = selected || options[0]?.id || "";

  return (
    <div className="space-y-6">
      <Card
        title="Prompt version comparison"
        subtitle="Versions are compared on the executions they actually produced, so a prompt change is judged on evidence."
      >
        {workflows.loading && <Loading />}
        {options.length === 0 && !workflows.loading && (
          <p className="text-sm text-muted">No workflow has more than one version yet.</p>
        )}
        {options.length > 0 && (
          <select
            className="input w-full max-w-sm"
            value={active}
            onChange={(event) => setSelected(event.target.value)}
          >
            {options.map((workflow) => (
              <option key={workflow.id} value={workflow.id}>
                {workflow.name} ({workflow.current_version} versions)
              </option>
            ))}
          </select>
        )}
      </Card>

      {active && <VersionComparisonCard workflowId={active} />}
    </div>
  );
}
