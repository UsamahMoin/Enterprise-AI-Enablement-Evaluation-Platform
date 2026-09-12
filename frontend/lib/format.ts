export function percent(value: number | null | undefined, digits = 0): string {
  if (value === null || value === undefined) return "—";
  return `${value.toFixed(digits)}%`;
}

export function score(value: number | null | undefined): string {
  if (value === null || value === undefined) return "N/A";
  return value.toFixed(0);
}

export function money(value: number | null | undefined, digits = 2): string {
  if (value === null || value === undefined) return "—";
  if (value > 0 && value < 0.01 && digits === 2) return `$${value.toFixed(4)}`;
  return `$${value.toFixed(digits)}`;
}

export function hours(value: number | null | undefined): string {
  if (value === null || value === undefined) return "—";
  return `${value.toFixed(1)} hrs`;
}

export function duration(ms: number): string {
  return `${(ms / 1000).toFixed(1)} sec`;
}

export function dateTime(iso: string): string {
  const date = new Date(iso.endsWith("Z") ? iso : `${iso}Z`);
  return date.toLocaleString(undefined, {
    month: "short",
    day: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  });
}

export function titleCase(value: string): string {
  return value.replace(/_/g, " ").replace(/\b\w/g, (char) => char.toUpperCase());
}

/** Colour ramp for a 0-100 quality score. Thresholds match the backend's
 *  80-point attention threshold so the UI and the analytics agree. */
export function scoreTone(value: number | null | undefined): string {
  if (value === null || value === undefined) return "text-muted";
  if (value >= 90) return "text-emerald-700";
  if (value >= 80) return "text-ink";
  if (value >= 70) return "text-amber-700";
  return "text-red-700";
}
