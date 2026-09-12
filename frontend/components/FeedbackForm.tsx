"use client";

import { useState } from "react";

import { Card, ErrorBox } from "@/components/ui";
import { api } from "@/lib/api";
import type { Execution, FeedbackDecision } from "@/types";

const DECISIONS: { value: FeedbackDecision; label: string; hint: string }[] = [
  { value: "APPROVED", label: "Approve", hint: "Usable as it stands" },
  { value: "NEEDS_EDITING", label: "Needs editing", hint: "Useful, but you changed it" },
  { value: "REJECTED", label: "Reject", hint: "You would not use this" },
];

export function FeedbackForm({
  execution,
  onSubmitted,
}: {
  execution: Execution;
  onSubmitted: () => void;
}) {
  const [thumbsUp, setThumbsUp] = useState<boolean | null>(execution.feedback?.thumbs_up ?? null);
  const [rating, setRating] = useState<number | null>(execution.feedback?.rating ?? null);
  const [comment, setComment] = useState(execution.feedback?.comment ?? "");
  const [error, setError] = useState("");
  const [saving, setSaving] = useState(false);

  const existing = execution.feedback;

  async function submit(decision: FeedbackDecision) {
    setSaving(true);
    setError("");
    try {
      await api.feedback(execution.id, {
        decision,
        thumbs_up: thumbsUp,
        rating,
        comment,
      });
      onSubmitted();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not save your feedback");
    } finally {
      setSaving(false);
    }
  }

  return (
    <Card
      title="Your review"
      subtitle="Human evaluation is stored separately from the automated score so the two can be compared."
    >
      {existing && (
        <p className="mb-4 rounded-lg border border-line bg-canvas px-3 py-2 text-xs text-muted">
          You recorded <span className="font-medium text-ink">{existing.decision.replace("_", " ").toLowerCase()}</span>{" "}
          for this run. Submitting again replaces it.
        </p>
      )}

      <div className="flex flex-wrap items-center gap-4">
        <div>
          <p className="label">Was this useful?</p>
          <div className="mt-1 flex gap-2">
            <button
              type="button"
              onClick={() => setThumbsUp(true)}
              aria-pressed={thumbsUp === true}
              className={`btn-secondary px-3 py-1.5 ${thumbsUp === true ? "border-brand-500 bg-brand-50" : ""}`}
            >
              👍 Yes
            </button>
            <button
              type="button"
              onClick={() => setThumbsUp(false)}
              aria-pressed={thumbsUp === false}
              className={`btn-secondary px-3 py-1.5 ${thumbsUp === false ? "border-brand-500 bg-brand-50" : ""}`}
            >
              👎 No
            </button>
          </div>
        </div>

        <div>
          <p className="label">Quality (1–5)</p>
          <div className="mt-1 flex gap-1">
            {[1, 2, 3, 4, 5].map((value) => (
              <button
                key={value}
                type="button"
                onClick={() => setRating(value)}
                aria-pressed={rating === value}
                className={`h-9 w-9 rounded-lg border text-sm ${
                  rating === value
                    ? "border-brand-500 bg-brand-50 font-semibold text-brand-700"
                    : "border-line hover:bg-canvas"
                }`}
              >
                {value}
              </button>
            ))}
          </div>
        </div>
      </div>

      <label className="mt-4 block">
        <span className="label">Comment (optional)</span>
        <textarea
          className="input mt-1 h-20"
          value={comment}
          onChange={(event) => setComment(event.target.value)}
          placeholder="What did you change, and why?"
        />
      </label>

      {error && <div className="mt-3"><ErrorBox message={error} /></div>}

      <div className="mt-4 flex flex-wrap gap-2">
        {DECISIONS.map((decision) => (
          <button
            key={decision.value}
            type="button"
            disabled={saving}
            onClick={() => submit(decision.value)}
            className={decision.value === "APPROVED" ? "btn-primary" : "btn-secondary"}
            title={decision.hint}
          >
            {decision.label}
          </button>
        ))}
      </div>
    </Card>
  );
}
