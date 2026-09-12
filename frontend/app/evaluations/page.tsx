"use client";

import { useState } from "react";

import { EvaluationPanel } from "@/components/EvaluationPanel";
import { FeedbackForm } from "@/components/FeedbackForm";
import { PageHeader, Shell } from "@/components/Shell";
import { Badge, Card, EmptyState, ErrorBox, Loading, Table } from "@/components/ui";
import { api } from "@/lib/api";
import { dateTime, money, score, scoreTone } from "@/lib/format";
import { useAsync } from "@/lib/useAsync";
import type { Execution } from "@/types";

export default function EvaluationsPage() {
  return (
    <Shell>
      <RunHistory />
    </Shell>
  );
}

function RunHistory() {
  const { data, error, loading, reload } = useAsync(() => api.executions({ limit: "50" }), []);
  const [selected, setSelected] = useState<Execution | null>(null);

  async function open(execution: Execution) {
    setSelected(await api.execution(execution.id));
  }

  return (
    <>
      <PageHeader
        title="My runs"
        description="Every execution with its automated score and your review. Runs blocked by governance are listed too — they are part of the record."
      />

      {loading && <Loading />}
      {error && <ErrorBox message={error} />}
      {data && data.length === 0 && (
        <EmptyState>
          No runs yet. Pick a workflow from the library and run it — the result will appear here.
        </EmptyState>
      )}

      {data && data.length > 0 && (
        <Card>
          <Table headers={["Workflow", "When", "Status", "Score", "Your review", "Cost", ""]}>
            {data.map((execution) => (
              <tr key={execution.id}>
                <td className="py-2.5 pr-4">
                  <span className="font-medium">{execution.workflow_name}</span>
                  <span className="block text-xs text-muted">v{execution.workflow_version}</span>
                </td>
                <td className="py-2.5 pr-4 text-muted">{dateTime(execution.created_at)}</td>
                <td className="py-2.5 pr-4">
                  <StatusBadge status={execution.status} />
                </td>
                <td className={`py-2.5 pr-4 font-medium tabular-nums ${scoreTone(execution.evaluation?.overall_score ?? null)}`}>
                  {score(execution.evaluation?.overall_score ?? null)}
                </td>
                <td className="py-2.5 pr-4 text-muted">
                  {execution.feedback
                    ? execution.feedback.decision.replace("_", " ").toLowerCase()
                    : "—"}
                </td>
                <td className="py-2.5 pr-4 tabular-nums text-muted">
                  {money(execution.estimated_cost, 4)}
                </td>
                <td className="py-2.5">
                  <button
                    type="button"
                    className="text-sm text-brand-700 underline"
                    onClick={() => void open(execution)}
                  >
                    View
                  </button>
                </td>
              </tr>
            ))}
          </Table>
        </Card>
      )}

      {selected && (
        <div className="mt-6 space-y-6">
          <div className="flex items-center justify-between">
            <h2 className="text-sm font-semibold">
              {selected.workflow_name} · {dateTime(selected.created_at)}
            </h2>
            <button type="button" className="btn-secondary" onClick={() => setSelected(null)}>
              Close
            </button>
          </div>

          {selected.status === "BLOCKED" ? (
            <ErrorBox message={selected.blocked_reason ?? "Blocked by governance policy."} />
          ) : (
            <>
              <Card title="Output">
                <pre className="max-h-96 overflow-auto whitespace-pre-wrap rounded-lg bg-canvas p-4 font-mono text-xs">
                  {selected.output}
                </pre>
              </Card>
              <EvaluationPanel execution={selected} />
              <FeedbackForm
                execution={selected}
                onSubmitted={async () => {
                  setSelected(await api.execution(selected.id));
                  reload();
                }}
              />
            </>
          )}
        </div>
      )}
    </>
  );
}

function StatusBadge({ status }: { status: Execution["status"] }) {
  if (status === "BLOCKED") {
    return <Badge tone="border-red-200 bg-red-50 text-red-800">Blocked</Badge>;
  }
  if (status === "FAILED") {
    return <Badge tone="border-amber-200 bg-amber-50 text-amber-900">Failed</Badge>;
  }
  return <Badge tone="border-emerald-200 bg-emerald-50 text-emerald-800">Completed</Badge>;
}
