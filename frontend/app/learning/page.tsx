"use client";

import { useState } from "react";

import { PageHeader, Shell } from "@/components/Shell";
import { Card, ErrorBox, Loading } from "@/components/ui";
import { api } from "@/lib/api";
import { useAsync } from "@/lib/useAsync";
import type { TrainingModule } from "@/types";

export default function LearningPage() {
  return (
    <Shell>
      <LearningCentre />
    </Shell>
  );
}

function LearningCentre() {
  const { data, error, loading, reload } = useAsync(() => api.trainingModules(), []);
  const [open, setOpen] = useState<TrainingModule | null>(null);

  const completed = data?.filter((module) => module.completed).length ?? 0;
  const total = data?.length ?? 0;

  return (
    <>
      <PageHeader
        title="Learning centre"
        description="Short lessons on using these workflows well. Enablement is part of the platform, not a separate PDF nobody opens."
      />

      {loading && <Loading />}
      {error && <ErrorBox message={error} />}

      {data && (
        <>
          <Card className="mb-6">
            <p className="text-sm">
              Completed <span className="font-semibold">{completed} / {total}</span>
            </p>
            <div className="mt-2 h-1.5 w-full max-w-sm overflow-hidden rounded-full bg-line">
              <div
                className="h-full rounded-full bg-brand-500"
                style={{ width: `${total ? (100 * completed) / total : 0}%` }}
              />
            </div>
          </Card>

          <div className="grid gap-4 md:grid-cols-2">
            {data.map((module) => (
              <article key={module.id} className="card flex flex-col">
                <div className="flex items-start justify-between gap-3">
                  <h3 className="text-sm font-semibold">{module.title}</h3>
                  <span className="text-xs text-muted">{module.minutes} min</span>
                </div>
                <p className="mt-2 flex-1 text-xs text-muted">{module.summary}</p>
                <div className="mt-4 flex items-center gap-2">
                  <button
                    type="button"
                    className="btn-secondary"
                    onClick={() => setOpen(open?.id === module.id ? null : module)}
                  >
                    {open?.id === module.id ? "Close" : "Read"}
                  </button>
                  {module.completed ? (
                    <span className="text-xs font-medium text-emerald-700">✓ Completed</span>
                  ) : (
                    <button
                      type="button"
                      className="btn-primary"
                      onClick={async () => {
                        await api.completeModule(module.id);
                        reload();
                      }}
                    >
                      Mark complete
                    </button>
                  )}
                </div>
                {open?.id === module.id && (
                  <div className="mt-4 space-y-3 border-t border-line pt-4 text-sm leading-relaxed">
                    {module.body.split("\n\n").map((paragraph, index) => (
                      <p key={index} className="whitespace-pre-wrap">
                        {paragraph.replace(/\*\*/g, "")}
                      </p>
                    ))}
                  </div>
                )}
              </article>
            ))}
          </div>
        </>
      )}
    </>
  );
}
