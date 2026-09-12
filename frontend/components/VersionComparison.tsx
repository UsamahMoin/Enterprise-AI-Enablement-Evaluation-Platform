"use client";

import { Card, ErrorBox, Loading, Table } from "@/components/ui";
import { api } from "@/lib/api";
import { money, percent, score, scoreTone } from "@/lib/format";
import { useAsync } from "@/lib/useAsync";

export function VersionComparisonCard({ workflowId }: { workflowId: string }) {
  const { data, error, loading } = useAsync(
    () => api.versionComparison(workflowId),
    [workflowId],
  );

  if (loading) return <Loading />;
  if (error) return <ErrorBox message={error} />;
  if (!data) return null;

  return (
    <>
      <Card title={data.workflow_name}>
        <Table
          headers={[
            "Version",
            "Runs",
            "Quality",
            "Relevance",
            "Completeness",
            "Groundedness",
            "Approval",
            "Avg cost",
            "Avg latency",
          ]}
        >
          {data.versions.map((version) => (
            <tr key={version.version}>
              <td className="py-2.5 pr-4 font-medium">v{version.version}</td>
              <td className="py-2.5 pr-4 tabular-nums text-muted">{version.executions}</td>
              <td className={`py-2.5 pr-4 font-semibold tabular-nums ${scoreTone(version.average_quality)}`}>
                {score(version.average_quality)}
              </td>
              <td className="py-2.5 pr-4 tabular-nums">{score(version.relevance)}</td>
              <td className="py-2.5 pr-4 tabular-nums">{score(version.completeness)}</td>
              <td className="py-2.5 pr-4 tabular-nums">{score(version.groundedness)}</td>
              <td className="py-2.5 pr-4 tabular-nums">{percent(version.approval_rate, 0)}</td>
              <td className="py-2.5 pr-4 tabular-nums text-muted">
                {money(version.average_cost, 5)}
              </td>
              <td className="py-2.5 tabular-nums text-muted">
                {(version.average_latency_ms / 1000).toFixed(1)}s
              </td>
            </tr>
          ))}
        </Table>

        {data.recommendation && (
          <div className="mt-5 rounded-lg border border-line bg-canvas p-4">
            <p className="label">Read-out</p>
            <p className="mt-1 text-sm">{data.recommendation}</p>
          </div>
        )}
      </Card>

      <Card title="What changed between versions">
        <ul className="space-y-3">
          {data.versions.map((version) => (
            <li key={version.version} className="border-l-2 border-line pl-3">
              <p className="text-sm font-medium">v{version.version}</p>
              <p className="text-xs text-muted">{version.changelog || "No changelog recorded."}</p>
            </li>
          ))}
        </ul>
      </Card>
    </>
  );
}
