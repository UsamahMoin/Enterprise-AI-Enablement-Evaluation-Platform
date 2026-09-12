"use client";

import { PageHeader, Shell } from "@/components/Shell";
import { Badge, Card, EmptyState, ErrorBox, Loading, RiskBadge, Table } from "@/components/ui";
import { api } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { dateTime, titleCase } from "@/lib/format";
import { useAsync } from "@/lib/useAsync";

const RISK_TIERS = [
  {
    level: "LOW" as const,
    meaning: "A wrong answer costs a few minutes.",
    examples: "Meeting summaries, code explanation, ticket triage",
  },
  {
    level: "MEDIUM" as const,
    meaning: "A wrong answer reaches someone outside your team.",
    examples: "Customer replies, job descriptions, campaign copy",
  },
  {
    level: "HIGH" as const,
    meaning: "A wrong answer affects a person or a financial statement. Human review required.",
    examples: "Variance analysis, financial narrative, interview summaries",
  },
  {
    level: "PROHIBITED" as const,
    meaning: "The platform will not run it at all.",
    examples: "Automated adverse employment decisions",
  },
];

export default function GovernancePage() {
  return (
    <Shell>
      <Governance />
    </Shell>
  );
}

function Governance() {
  const { user } = useAuth();
  const violations = useAsync(() => api.violations(50), []);
  const policies = useAsync(
    () => (user?.system_role === "ADMIN" ? api.policies() : Promise.resolve([])),
    [user?.system_role],
  );

  return (
    <>
      <PageHeader
        title="Governance"
        description="Controls that run before a workflow reaches a model provider, and the audit trail they produce."
      />

      <div className="mb-6 grid gap-6 lg:grid-cols-[minmax(0,1fr)_minmax(0,1fr)]">
        <Card title="Risk tiers" subtitle="Every workflow carries one.">
          <ul className="space-y-3">
            {RISK_TIERS.map((tier) => (
              <li key={tier.level} className="flex gap-3">
                <div className="w-28 shrink-0">
                  <RiskBadge level={tier.level} />
                </div>
                <div>
                  <p className="text-sm">{tier.meaning}</p>
                  <p className="text-xs text-muted">{tier.examples}</p>
                </div>
              </li>
            ))}
          </ul>
        </Card>

        <Card title="Pre-execution pipeline">
          <ol className="space-y-2 text-sm">
            {[
              ["Input", "What the employee typed into the workflow form"],
              ["Sensitive-data check", "Government IDs, cards, keys, secrets, contact details"],
              ["Policy check", "Prohibited use cases and data-classification limits"],
              ["Moderation", "Provider moderation endpoint"],
              ["AI execution", "Only reached if every blocking control passes"],
              ["Output evaluation", "Deterministic checks, model judge, then human review"],
            ].map(([step, detail], index) => (
              <li key={step} className="flex gap-3">
                <span className="mt-0.5 flex h-5 w-5 shrink-0 items-center justify-center rounded-full bg-brand-50 text-xs font-semibold text-brand-700">
                  {index + 1}
                </span>
                <span>
                  <span className="font-medium">{step}</span>
                  <span className="block text-xs text-muted">{detail}</span>
                </span>
              </li>
            ))}
          </ol>
        </Card>
      </div>

      {user?.system_role === "ADMIN" && (
        <Card className="mb-6" title="Policies" subtitle="Changes take effect on the next run.">
          {policies.loading && <Loading />}
          {policies.error && <ErrorBox message={policies.error} />}
          {policies.data && (
            <Table headers={["Policy", "Severity", "Mode", "Status", ""]}>
              {policies.data.map((policy) => (
                <tr key={policy.id}>
                  <td className="py-3 pr-4">
                    <span className="font-medium">{policy.name}</span>
                    <span className="block max-w-xl text-xs text-muted">{policy.description}</span>
                  </td>
                  <td className="py-3 pr-4">
                    <RiskBadge level={policy.risk_level} />
                  </td>
                  <td className="py-3 pr-4 text-xs text-muted">
                    {policy.blocking ? "Blocking" : "Warn and log"}
                  </td>
                  <td className="py-3 pr-4">
                    <Badge
                      tone={
                        policy.enabled
                          ? "border-emerald-200 bg-emerald-50 text-emerald-800"
                          : "border-red-200 bg-red-50 text-red-800"
                      }
                    >
                      {policy.enabled ? "Enabled" : "Disabled"}
                    </Badge>
                  </td>
                  <td className="py-3">
                    <button
                      type="button"
                      className="text-sm text-brand-700 underline"
                      onClick={async () => {
                        await api.updatePolicy(policy.id, { enabled: !policy.enabled });
                        policies.reload();
                      }}
                    >
                      {policy.enabled ? "Disable" : "Enable"}
                    </button>
                  </td>
                </tr>
              ))}
            </Table>
          )}
        </Card>
      )}

      <Card
        title="Audit log"
        subtitle="Detection categories and counts only. The detected value is never stored or logged."
      >
        {violations.loading && <Loading />}
        {violations.error && <ErrorBox message={violations.error} />}
        {violations.data && violations.data.length === 0 && (
          <EmptyState>No policy violations recorded.</EmptyState>
        )}
        {violations.data && violations.data.length > 0 && (
          <Table headers={["When", "Workflow", "Policy", "Detected", "Severity", "Outcome"]}>
            {violations.data.map((violation) => (
              <tr key={violation.id}>
                <td className="py-2.5 pr-4 text-muted">{dateTime(violation.created_at)}</td>
                <td className="py-2.5 pr-4">{violation.workflow_name || "—"}</td>
                <td className="py-2.5 pr-4 text-muted">{titleCase(violation.policy_key)}</td>
                <td className="py-2.5 pr-4">
                  {violation.details.detections?.length
                    ? violation.details.detections
                        .map((detection) => `${detection.type}${detection.count > 1 ? ` ×${detection.count}` : ""}`)
                        .join(", ")
                    : "—"}
                </td>
                <td className="py-2.5 pr-4">{violation.severity}</td>
                <td className="py-2.5">
                  <Badge tone="border-red-200 bg-red-50 text-red-800">
                    {violation.blocked ? "Blocked" : "Logged"}
                  </Badge>
                </td>
              </tr>
            ))}
          </Table>
        )}
      </Card>

      <p className="mt-4 text-xs text-muted">
        Pattern matching catches structured identifiers. It does not catch a paragraph that
        identifies someone by circumstance, a screenshot, or a spreadsheet pasted as text. The
        control is a backstop, not a guarantee — see docs/responsible-ai.md.
      </p>
    </>
  );
}
