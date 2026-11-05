// Number and download helpers shared by the Analysis pages and Data & sources.

export function formatNumber(value: number | null | undefined, digits = 0): string {
  if (value === null || value === undefined || Number.isNaN(value)) {
    return "N/A";
  }
  return value.toLocaleString(undefined, {
    maximumFractionDigits: digits,
    minimumFractionDigits: digits,
  });
}

export function formatPct(value: number | null | undefined, digits = 0): string {
  return value === null || value === undefined ? "N/A" : `${(value * 100).toFixed(digits)}%`;
}

// A difference between two percentages is in percentage points, not percent.
export function formatPoints(value: number | null | undefined, digits = 0): string {
  return value === null || value === undefined ? "N/A" : `${(value * 100).toFixed(digits)} pts`;
}

function csvEscape(value: unknown): string {
  const text = value === null || value === undefined ? "" : String(value);
  return /[",\n]/.test(text) ? `"${text.replace(/"/g, '""')}"` : text;
}

export function csvDataUri<T>(rows: T[], columns: { label: string; value: (row: T) => unknown }[]): string {
  const header = columns.map((column) => csvEscape(column.label)).join(",");
  const body = rows.map((row) => columns.map((column) => csvEscape(column.value(row))).join(",")).join("\n");
  return `data:text/csv;charset=utf-8,${encodeURIComponent(`${header}\n${body}`)}`;
}
