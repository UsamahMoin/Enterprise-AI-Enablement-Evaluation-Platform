"use client";

import Link from "next/link";
import { useEffect } from "react";
import { useRouter } from "next/navigation";

import { PageHeader, Shell } from "@/components/Shell";
import { Card, ErrorBox, Loading, StatTile, Table } from "@/components/ui";
import { api } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { hours, money, percent, score, scoreTone } from "@/lib/format";
import { useAsync } from "@/lib/useAsync";

export default function AdminPage() {
  return (
    <Shell>
      <AdminOverviewPage />
    </Shell>
  );
}

function AdminOverviewPage() {
  const { user } = useAuth();
  const router = useRouter();
  const { data, error, loading } = useAsync(() => api.adminOverview(30), []);

  useEffect(() => {
    if (user && user.system_role !== "ADMIN") router.replace("/dashboard");
  }, [user, router]);

  if (user && user.system_role !== "ADMIN") return null;

  return (
    <>
      <PageHeader
        title="Enterprise AI overview"
        description="Acme Corp, last 30 days."
      />

      {loading && <Loading />}
      {error && <ErrorBox message={error} />}
      {data && (
        <div className="space-y-6">
          <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-6">
            <StatTile label="Active users" value={data.adoption.active_users} />
            <StatTile label="Adoption" value={percent(data.adoption.adoption_rate, 1)} />
            <StatTile label="Executions" value={data.adoption.executions.toLocaleString()} />
            <StatTile label="Approval rate" value={percent(data.adoption.approval_rate, 1)} />
            <StatTile
              label="Average quality"
              value={score(data.quality.overall_quality)}
              tone={scoreTone(data.quality.overall_quality)}
            />
            <StatTile label="Estimated spend" value={money(data.adoption.estimated_spend)} />
          </div>

          <div className="grid gap-6 lg:grid-cols-2">
            <Card title="Most used workflows">
              <Table headers={["Workflow", "Runs", "Quality", "Approval"]}>
                {data.top_workflows.map((row) => (
                  <tr key={row.workflow_id}>
                    <td className="py-2.5 pr-4 font-medium">{row.name}</td>
                    <td className="py-2.5 pr-4 tabular-nums">{row.executions}</td>
                    <td className={`py-2.5 pr-4 tabular-nums ${scoreTone(row.average_quality)}`}>
                      {score(row.average_quality)}
                    </td>
                    <td className="py-2.5 tabular-nums">{percent(row.approval_rate, 0)}</td>
                  </tr>
                ))}
              </Table>
            </Card>

            <Card
              title="Workflows requiring attention"
              subtitle="Below the 80-point quality or 80% approval threshold."
            >
              {data.needs_attention.length === 0 ? (
                <p className="text-sm text-muted">
                  Nothing is below threshold in this window.
                </p>
              ) : (
                <ul className="space-y-3">
                  {data.needs_attention.map((row) => (
                    <li key={row.workflow_id} className="rounded-lg border border-amber-200 bg-amber-50 p-3">
                      <div className="flex items-center justify-between gap-3">
                        <span className="text-sm font-medium text-amber-900">{row.name}</span>
                        <span className={`text-sm font-semibold tabular-nums ${scoreTone(row.average_quality)}`}>
                          {score(row.average_quality)}
                        </span>
                      </div>
                      <p className="mt-1 text-xs text-amber-900">{row.attention_reason}</p>
                      <Link
                        href="/analytics"
                        className="mt-2 inline-block text-xs text-amber-900 underline"
                      >
                        Compare prompt versions →
                      </Link>
                    </li>
                  ))}
                </ul>
              )}
            </Card>
          </div>

          <div className="grid gap-6 lg:grid-cols-3">
            <StatTile
              label="Effective adoption"
              value={percent(data.adoption.effective_adoption_rate, 1)}
              hint={`${data.adoption.effective_users} of ${data.adoption.active_users} active users produced an approved output`}
            />
            <StatTile
              label="Estimated time saved"
              value={hours(data.adoption.estimated_hours_saved)}
              hint="Approved outputs only"
            />
            <StatTile
              label="Requests blocked by policy"
              value={data.blocked_requests}
              hint="All time"
            />
          </div>

          <Card title="Judge vs human">
            <p className="text-sm text-muted">
              The model judge scores{" "}
              <span className="font-medium text-ink">{score(data.quality.overall_quality)}</span>{" "}
              on average; people approve{" "}
              <span className="font-medium text-ink">
                {percent(data.quality.human_approval_rate, 1)}
              </span>{" "}
              of reviewed outputs. Both are kept because neither is ground truth on its own.
            </p>
          </Card>
        </div>
      )}
    </>
  );
}
