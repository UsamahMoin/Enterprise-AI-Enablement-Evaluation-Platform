"use client";

import type { ReactNode } from "react";

import { percent, scoreTone } from "@/lib/format";
import type { DataClassification, RiskLevel } from "@/types";

export function Card({
  title,
  subtitle,
  action,
  children,
  className = "",
}: {
  title?: string;
  subtitle?: string;
  action?: ReactNode;
  children: ReactNode;
  className?: string;
}) {
  return (
    <section className={`card ${className}`}>
      {(title || action) && (
        <header className="mb-4 flex items-start justify-between gap-4">
          <div>
            {title && <h2 className="text-sm font-semibold">{title}</h2>}
            {subtitle && <p className="mt-1 text-xs text-muted">{subtitle}</p>}
          </div>
          {action}
        </header>
      )}
      {children}
    </section>
  );
}

export function StatTile({
  label,
  value,
  hint,
  tone = "",
}: {
  label: string;
  value: ReactNode;
  hint?: string;
  tone?: string;
}) {
  return (
    <div className="card">
      <p className="label">{label}</p>
      <p className={`mt-2 text-2xl font-semibold tabular-nums ${tone}`}>{value}</p>
      {hint && <p className="mt-1 text-xs text-muted">{hint}</p>}
    </div>
  );
}

const RISK_STYLES: Record<RiskLevel, string> = {
  LOW: "bg-emerald-50 text-emerald-800 border-emerald-200",
  MEDIUM: "bg-amber-50 text-amber-900 border-amber-200",
  HIGH: "bg-orange-50 text-orange-900 border-orange-200",
  PROHIBITED: "bg-red-50 text-red-800 border-red-200",
};

export function RiskBadge({ level }: { level: RiskLevel }) {
  return (
    <span
      className={`inline-flex items-center rounded-md border px-2 py-0.5 text-xs font-medium ${RISK_STYLES[level]}`}
    >
      {level === "PROHIBITED" ? "Prohibited" : `${level[0]}${level.slice(1).toLowerCase()} risk`}
    </span>
  );
}

export function Badge({ children, tone = "" }: { children: ReactNode; tone?: string }) {
  return (
    <span
      className={`inline-flex items-center rounded-md border border-line bg-canvas px-2 py-0.5 text-xs font-medium text-muted ${tone}`}
    >
      {children}
    </span>
  );
}

export function ClassificationBadge({ level }: { level: DataClassification }) {
  return <Badge>{level[0]}{level.slice(1).toLowerCase()} data</Badge>;
}

/** Horizontal bar for a 0-100 value. Also renders the number, because a bar
 *  alone is not readable for anyone comparing two rows precisely. */
export function ScoreBar({
  label,
  value,
  suffix = "",
}: {
  label: string;
  value: number | null;
  suffix?: string;
}) {
  const width = value === null ? 0 : Math.max(0, Math.min(100, value));
  return (
    <div>
      <div className="flex items-baseline justify-between gap-3 text-sm">
        <span className="text-muted">{label}</span>
        <span className={`font-semibold tabular-nums ${scoreTone(value)}`}>
          {value === null ? "N/A" : `${value.toFixed(0)}${suffix}`}
        </span>
      </div>
      <div className="mt-1 h-1.5 w-full overflow-hidden rounded-full bg-line">
        <div
          className={`h-full rounded-full ${
            value === null
              ? "bg-line"
              : value >= 90
                ? "bg-emerald-500"
                : value >= 80
                  ? "bg-brand-500"
                  : value >= 70
                    ? "bg-amber-500"
                    : "bg-red-500"
          }`}
          style={{ width: `${width}%` }}
        />
      </div>
    </div>
  );
}

export function AdoptionBar({ value }: { value: number }) {
  return (
    <div className="flex items-center gap-3">
      <div className="h-1.5 w-28 overflow-hidden rounded-full bg-line">
        <div
          className="h-full rounded-full bg-brand-500"
          style={{ width: `${Math.min(100, value)}%` }}
        />
      </div>
      <span className="tabular-nums text-sm font-medium">{percent(value, 1)}</span>
    </div>
  );
}

export function Loading({ label = "Loading..." }: { label?: string }) {
  return <p className="py-10 text-center text-sm text-muted">{label}</p>;
}

export function ErrorBox({ message }: { message: string }) {
  return (
    <div className="rounded-lg border border-red-200 bg-red-50 p-4 text-sm text-red-800">
      {message}
    </div>
  );
}

export function EmptyState({ children }: { children: ReactNode }) {
  return (
    <div className="rounded-lg border border-dashed border-line p-8 text-center text-sm text-muted">
      {children}
    </div>
  );
}

export function Table({
  headers,
  children,
}: {
  headers: string[];
  children: ReactNode;
}) {
  return (
    <div className="overflow-x-auto">
      <table className="w-full min-w-[640px] text-sm">
        <thead>
          <tr className="border-b border-line text-left">
            {headers.map((header) => (
              <th key={header} className="pb-2 pr-4 text-xs font-medium uppercase tracking-wide text-muted">
                {header}
              </th>
            ))}
          </tr>
        </thead>
        <tbody className="divide-y divide-line">{children}</tbody>
      </table>
    </div>
  );
}
