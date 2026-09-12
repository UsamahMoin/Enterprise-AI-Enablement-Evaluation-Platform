"use client";

import { Card, ScoreBar } from "@/components/ui";
import { duration, money, scoreTone } from "@/lib/format";
import type { Execution } from "@/types";

export function EvaluationPanel({ execution }: { execution: Execution }) {
  const evaluation = execution.evaluation;
  if (!evaluation) return null;

  return (
    <Card
      title="Evaluation"
      subtitle="Deterministic checks and a model-based judge. Your review below is the third layer."
    >
      <div className="flex items-baseline gap-3">
        <span className={`text-3xl font-semibold tabular-nums ${scoreTone(evaluation.overall_score)}`}>
          {evaluation.overall_score.toFixed(0)}
        </span>
        <span className="text-sm text-muted">/ 100 overall</span>
        <span
          className={`ml-auto rounded-md border px-2 py-0.5 text-xs font-medium ${
            !evaluation.safety_checked
              ? "border-amber-200 bg-amber-50 text-amber-900"
              : evaluation.safety_passed
                ? "border-emerald-200 bg-emerald-50 text-emerald-800"
                : "border-red-200 bg-red-50 text-red-800"
          }`}
          title={
            evaluation.safety_checked
              ? undefined
              : "No provider in the chain offers moderation, so this output was not screened."
          }
        >
          Safety{" "}
          {!evaluation.safety_checked ? "NOT CHECKED" : evaluation.safety_passed ? "PASS" : "FAIL"}
        </span>
      </div>

      <div className="mt-5 space-y-3">
        <ScoreBar label="Relevance" value={evaluation.relevance} />
        <ScoreBar label="Completeness" value={evaluation.completeness} />
        <ScoreBar label="Clarity" value={evaluation.clarity} />
        <ScoreBar label="Groundedness" value={evaluation.groundedness} />
        <ScoreBar label="Format compliance" value={evaluation.format_compliance} />
      </div>

      {!evaluation.safety_checked && (
        <p className="mt-3 rounded-lg border border-amber-200 bg-amber-50 px-3 py-2 text-xs text-amber-900">
          Safety was <strong>not checked</strong>: the provider handling this run has no
          moderation endpoint and no fallback moderator is configured. The dimension is dropped
          from the overall score rather than awarded full marks, so an unscreened run cannot
          outscore one that was screened.
        </p>
      )}

      {evaluation.groundedness === null && (
        <p className="mt-3 text-xs text-muted">
          Groundedness is N/A: this run supplied no reference material to check the output against.
          The platform reports that rather than guessing a score.
        </p>
      )}

      {evaluation.deterministic_checks.length > 0 && (
        <div className="mt-5">
          <p className="label">Deterministic checks</p>
          <ul className="mt-2 space-y-1.5">
            {evaluation.deterministic_checks.map((check) => (
              <li key={check.name} className="flex items-start gap-2 text-xs">
                <span
                  className={`mt-0.5 inline-block h-2 w-2 shrink-0 rounded-full ${
                    check.passed ? "bg-emerald-500" : "bg-red-500"
                  }`}
                />
                <span>
                  <span className="font-medium">{check.name.replace(/_/g, " ")}</span>
                  <span className="text-muted"> — {check.detail}</span>
                </span>
              </li>
            ))}
          </ul>
        </div>
      )}

      {evaluation.evaluation_reasoning && (
        <div className="mt-5">
          <p className="label">Judge reasoning</p>
          <p className="mt-1 text-xs text-muted">{evaluation.evaluation_reasoning}</p>
        </div>
      )}

      <dl className="mt-5 grid grid-cols-2 gap-3 border-t border-line pt-4 text-xs sm:grid-cols-4">
        <div>
          <dt className="text-muted">Latency</dt>
          <dd className="font-medium tabular-nums">{duration(execution.latency_ms)}</dd>
        </div>
        <div>
          <dt className="text-muted">Input tokens</dt>
          <dd className="font-medium tabular-nums">{execution.input_tokens.toLocaleString()}</dd>
        </div>
        <div>
          <dt className="text-muted">Output tokens</dt>
          <dd className="font-medium tabular-nums">{execution.output_tokens.toLocaleString()}</dd>
        </div>
        <div>
          <dt className="text-muted">Estimated cost</dt>
          <dd className="font-medium tabular-nums">{money(execution.estimated_cost, 4)}</dd>
        </div>
      </dl>
      <p className="mt-3 text-xs text-muted">
        Scored by {evaluation.evaluation_model || "the configured evaluation model"}
        {evaluation.evaluation_provider ? ` via the ${evaluation.evaluation_provider} provider` : ""}
        {evaluation.evaluation_provider && evaluation.evaluation_provider !== execution.provider
          ? " — an independent judge, since a model grading its own output shows self-preference bias"
          : ""}
        . A model judge is a signal, not ground truth — which is why your decision is recorded
        separately.
      </p>
    </Card>
  );
}
