"use client";

import Link from "next/link";

import { PageHeader, Shell } from "@/components/Shell";
import { Card, ErrorBox, Loading, RiskBadge, StatTile } from "@/components/ui";
import { api } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { hours, money, percent, score, scoreTone } from "@/lib/format";
import { useAsync } from "@/lib/useAsync";

export default function DashboardPage() {
  return (
    <Shell>
      <DashboardContent />
    </Shell>
  );
}

function DashboardContent() {
  const { user } = useAuth();
  const stats = useAsync(() => api.myDashboard(30), []);
  const recommended = useAsync(() => api.workflows({ recommended: "true" }), []);

  if (!user) return null;

  return (
    <>
      <PageHeader
        title={`Welcome, ${user.name.split(" ")[0]}`}
        description={`${user.job_role}${user.department_name ? ` · ${user.department_name}` : ""}. These are the AI workflows approved for your role.`}
      />

      <section className="mb-8">
        <h2 className="mb-3 text-sm font-semibold">Recommended workflows</h2>
        {recommended.loading && <Loading />}
        {recommended.error && <ErrorBox message={recommended.error} />}
        {recommended.data && recommended.data.length === 0 && (
          <p className="text-sm text-muted">
            No workflows are published for your role yet. Browse the{" "}
            <Link href="/workflows" className="text-brand-700 underline">
              full library
            </Link>
            .
          </p>
        )}
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
          {recommended.data
            ?.filter((workflow) => workflow.status === "ACTIVE")
            .map((workflow) => (
              <Link
                key={workflow.id}
                href={`/workflows/${workflow.id}`}
                className="card transition hover:border-brand-500"
              >
                <div className="flex items-start justify-between gap-3">
                  <h3 className="text-sm font-semibold">{workflow.name}</h3>
                  <RiskBadge level={workflow.risk_level} />
                </div>
                <p className="mt-2 text-xs text-muted">{workflow.description}</p>
                <dl className="mt-4 flex flex-wrap gap-x-6 gap-y-1 text-xs">
                  <div>
                    <dt className="text-muted">Est. time saved</dt>
                    <dd className="font-medium">
                      {workflow.estimated_manual_minutes - workflow.estimated_assisted_minutes} min
                    </dd>
                  </div>
                  <div>
                    <dt className="text-muted">Avg quality</dt>
                    <dd className={`font-medium ${scoreTone(workflow.stats.average_quality)}`}>
                      {score(workflow.stats.average_quality)}
                    </dd>
                  </div>
                  <div>
                    <dt className="text-muted">Runs</dt>
                    <dd className="font-medium">{workflow.stats.executions}</dd>
                  </div>
                </dl>
              </Link>
            ))}
        </div>
      </section>

      <section>
        <h2 className="mb-3 text-sm font-semibold">Your last 30 days</h2>
        {stats.loading && <Loading />}
        {stats.error && <ErrorBox message={stats.error} />}
        {stats.data && (
          <>
            <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-5">
              <StatTile label="Workflows completed" value={stats.data.workflows_completed} />
              <StatTile
                label="Estimated time saved"
                value={hours(stats.data.estimated_hours_saved)}
                hint="Approved outputs only"
              />
              <StatTile
                label="Average evaluation score"
                value={score(stats.data.average_evaluation_score)}
                tone={scoreTone(stats.data.average_evaluation_score)}
              />
              <StatTile
                label="Your approval rate"
                value={percent(stats.data.human_approval_rate, 0)}
                hint="Runs you accepted as-is"
              />
              <StatTile label="Estimated AI cost" value={money(stats.data.estimated_cost)} />
            </div>
            <Card className="mt-4" title="Enablement progress">
              <p className="text-sm">
                Training completed:{" "}
                <span className="font-semibold">
                  {stats.data.training_completed} / {stats.data.training_total}
                </span>
              </p>
              <div className="mt-2 h-1.5 w-full max-w-sm overflow-hidden rounded-full bg-line">
                <div
                  className="h-full rounded-full bg-brand-500"
                  style={{
                    width: `${
                      stats.data.training_total
                        ? (100 * stats.data.training_completed) / stats.data.training_total
                        : 0
                    }%`,
                  }}
                />
              </div>
              <Link href="/learning" className="mt-3 inline-block text-sm text-brand-700 underline">
                Open the learning centre
              </Link>
            </Card>
            <p className="mt-3 text-xs text-muted">
              Time saved is an estimate: each workflow stores a manual-time baseline, and only
              outputs a human approved are credited against it. It is not a measured productivity
              gain.
            </p>
          </>
        )}
      </section>
    </>
  );
}
