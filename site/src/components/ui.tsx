// Shared presentational primitives used across the redesigned routes. These are
// thin wrappers over the existing token/class system — they add no data or
// bundle behavior, they just stop the routes from re-implementing the same
// markup (metric cards, ranked rows, filter groups, headers, tables, empty
// states, expandable lists, chart legends, segmented controls).

import {
  useId,
  useMemo,
  useState,
  type ReactNode,
} from "react";

export function cx(...parts: (string | false | null | undefined)[]): string {
  return parts.filter(Boolean).join(" ");
}

/* ---------- Page header ---------- */

export function PageHeader({
  eyebrow,
  title,
  intro,
  actions,
  center = false,
  className,
}: {
  eyebrow?: ReactNode;
  title: ReactNode;
  intro?: ReactNode;
  actions?: ReactNode;
  center?: boolean;
  className?: string;
}) {
  return (
    <header className={cx("page-header", center && "page-header-center", className)}>
      {eyebrow ? <p className="eyebrow">{eyebrow}</p> : null}
      <div className="page-header-row">
        <h1 className="page-header-title">{title}</h1>
        {actions ? <div className="page-header-actions">{actions}</div> : null}
      </div>
      {intro ? <p className="page-header-intro">{intro}</p> : null}
    </header>
  );
}

/* ---------- Section header (in-panel) ---------- */

export function SectionHeader({
  title,
  note,
  actions,
  id,
}: {
  title: ReactNode;
  note?: ReactNode;
  actions?: ReactNode;
  id?: string;
}) {
  return (
    <div className="section-header">
      <div className="section-header-main">
        <h2 id={id} className="section-heading">
          {title}
        </h2>
        {note ? <p className="insight-note">{note}</p> : null}
      </div>
      {actions ? <div className="section-header-actions">{actions}</div> : null}
    </div>
  );
}

/* ---------- Metric card ---------- */

export function MetricCard({
  label,
  value,
  note,
  className,
}: {
  label: ReactNode;
  value: ReactNode;
  note?: ReactNode;
  className?: string;
}) {
  return (
    <article className={cx("metric-card", className)}>
      <p className="metric-label">{label}</p>
      <p className="metric-value">{value}</p>
      {note ? <p className="metric-note">{note}</p> : null}
    </article>
  );
}

/* ---------- Compact summary row (label · value pairs with dividers) ---------- */

export function SummaryRow({
  items,
  className,
}: {
  items: { key: string; label: ReactNode; value: ReactNode }[];
  className?: string;
}) {
  return (
    <dl className={cx("summary-row", className)}>
      {items.map((item) => (
        <div key={item.key} className="summary-item">
          <dt>{item.label}</dt>
          <dd>{item.value}</dd>
        </div>
      ))}
    </dl>
  );
}

/* ---------- Filter group (label + control) ---------- */

export function FilterGroup({
  label,
  children,
  htmlFor,
  className,
}: {
  label: ReactNode;
  children: ReactNode;
  htmlFor?: string;
  className?: string;
}) {
  // Use a <label> wrapper when the control is a native input/select (no id
  // needed); callers with custom controls can pass htmlFor to associate.
  return (
    <label className={cx("filter-field", className)} htmlFor={htmlFor}>
      <span>{label}</span>
      {children}
    </label>
  );
}

/* ---------- Empty state ---------- */

export function EmptyState({ children, className }: { children: ReactNode; className?: string }) {
  return <p className={cx("empty-state", className)}>{children}</p>;
}

/* ---------- Ranked rows with horizontal bars ---------- */

export interface RankedItem {
  key: string;
  name: ReactNode;
  value: number;
  /** Text shown at the right; defaults to the numeric value. */
  valueLabel?: ReactNode;
  meta?: ReactNode;
  title?: string;
  tone?: "accent" | "gold";
}

export function RankedList({
  items,
  showRank = true,
  initialVisible,
  itemsLabel = "entries",
  className,
}: {
  items: RankedItem[];
  showRank?: boolean;
  /** When set and exceeded, only this many rows show until "Show all". */
  initialVisible?: number;
  itemsLabel?: string;
  className?: string;
}) {
  const [expanded, setExpanded] = useState(false);
  // Bar scale is fixed to the full list so collapsing never rescales the bars.
  const max = items.reduce((m, item) => Math.max(m, item.value), 0) || 1;
  const collapsible = initialVisible != null && items.length > initialVisible;
  const visible = collapsible && !expanded ? items.slice(0, initialVisible) : items;
  return (
    <>
      <ol className={cx("ranked-list", className)}>
        {visible.map((item, index) => {
          const pct = Math.max((item.value / max) * 100, 1.5);
          return (
            <li key={item.key} className="ranked-row" title={item.title}>
              {showRank ? <span className="ranked-rank">{index + 1}</span> : null}
              <div className="ranked-body">
                <div className="ranked-line">
                  <span className="ranked-name">{item.name}</span>
                  <span className="ranked-value">{item.valueLabel ?? item.value.toLocaleString()}</span>
                </div>
                <span className="ranked-track">
                  <span
                    className={cx("ranked-fill", item.tone === "gold" && "ranked-fill-gold")}
                    style={{ width: `${pct}%` }}
                  />
                </span>
                {item.meta ? <span className="ranked-meta">{item.meta}</span> : null}
              </div>
            </li>
          );
        })}
      </ol>
      {collapsible ? (
        <button
          type="button"
          className="show-more-button"
          onClick={() => setExpanded((value) => !value)}
          aria-expanded={expanded}
        >
          {expanded ? "Show fewer" : `Show all ${items.length} ${itemsLabel}`}
        </button>
      ) : null}
    </>
  );
}

/* ---------- Show-more list (top-N then reveal) ---------- */

export function ShowMoreList<T>({
  items,
  initial = 10,
  renderItem,
  as: As = "div",
  className,
  itemsLabel = "records",
}: {
  items: T[];
  initial?: number;
  renderItem: (item: T, index: number) => ReactNode;
  as?: "div" | "ol" | "ul";
  className?: string;
  itemsLabel?: string;
}) {
  const [expanded, setExpanded] = useState(false);
  const shown = expanded ? items : items.slice(0, initial);
  const hidden = items.length - initial;
  return (
    <>
      <As className={className}>{shown.map((item, index) => renderItem(item, index))}</As>
      {hidden > 0 ? (
        <button
          type="button"
          className="show-more-button"
          onClick={() => setExpanded((value) => !value)}
          aria-expanded={expanded}
        >
          {expanded ? "Show fewer" : `Show all ${items.length} ${itemsLabel}`}
        </button>
      ) : null}
    </>
  );
}

/* ---------- Expandable disclosure ---------- */

export function Expandable({
  summary,
  children,
  defaultOpen = false,
  className,
}: {
  summary: ReactNode;
  children: ReactNode;
  defaultOpen?: boolean;
  className?: string;
}) {
  return (
    <details className={cx("expandable", className)} open={defaultOpen}>
      <summary className="expandable-summary">{summary}</summary>
      <div className="expandable-body">{children}</div>
    </details>
  );
}

/* ---------- Chart legend ---------- */

export function ChartLegend({
  items,
  className,
}: {
  items: { key: string; color: string; label: ReactNode; shape?: "dot" | "line" | "box" }[];
  className?: string;
}) {
  return (
    <ul className={cx("chart-legend", className)}>
      {items.map((item) => (
        <li key={item.key} className="chart-legend-item">
          <span
            className={cx("chart-legend-swatch", `chart-legend-${item.shape ?? "box"}`)}
            style={{ background: item.shape === "line" ? "transparent" : item.color, borderColor: item.color }}
            aria-hidden="true"
          />
          <span>{item.label}</span>
        </li>
      ))}
    </ul>
  );
}

/* ---------- Segmented control / tabs ---------- */

export function SegmentedControl<T extends string>({
  options,
  value,
  onChange,
  ariaLabel,
  className,
}: {
  options: { value: T; label: ReactNode; count?: number }[];
  value: T;
  onChange: (value: T) => void;
  ariaLabel: string;
  className?: string;
}) {
  return (
    <div className={cx("segmented", className)} role="tablist" aria-label={ariaLabel}>
      {options.map((option) => (
        <button
          key={option.value}
          type="button"
          role="tab"
          aria-selected={option.value === value}
          className={cx("segmented-option", option.value === value && "segmented-option-active")}
          onClick={() => onChange(option.value)}
        >
          {option.label}
          {option.count != null ? <span className="segmented-count">{option.count}</span> : null}
        </button>
      ))}
    </div>
  );
}

/* ---------- Sortable, sticky-header, scrollable table ---------- */

export interface Column<T> {
  key: string;
  label: ReactNode;
  align?: "left" | "right" | "center";
  /** Provide to make the column sortable. */
  sortValue?: (row: T) => string | number;
  render: (row: T) => ReactNode;
  width?: string;
  /** Ascending on first click? Defaults to true (false is handy for stats). */
  initialAsc?: boolean;
}

export function SortableTable<T>({
  columns,
  rows,
  getRowKey,
  initialSortKey,
  initialSortAsc = true,
  caption,
  className,
}: {
  columns: Column<T>[];
  rows: T[];
  getRowKey: (row: T) => string;
  initialSortKey?: string;
  initialSortAsc?: boolean;
  caption?: string;
  className?: string;
}) {
  const [sortKey, setSortKey] = useState<string | undefined>(initialSortKey);
  const [asc, setAsc] = useState(initialSortAsc);

  const sorted = useMemo(() => {
    const column = columns.find((c) => c.key === sortKey);
    if (!column?.sortValue) {
      return rows;
    }
    const accessor = column.sortValue;
    return [...rows].sort((a, b) => {
      const va = accessor(a);
      const vb = accessor(b);
      const compared =
        typeof va === "number" && typeof vb === "number"
          ? va - vb
          : String(va).localeCompare(String(vb));
      return asc ? compared : -compared;
    });
  }, [columns, rows, sortKey, asc]);

  function toggle(column: Column<T>) {
    if (!column.sortValue) {
      return;
    }
    if (column.key === sortKey) {
      setAsc((value) => !value);
    } else {
      setSortKey(column.key);
      setAsc(column.initialAsc ?? true);
    }
  }

  return (
    <div className={cx("data-table-wrap sticky-table-wrap", className)}>
      <table className="data-table">
        {caption ? <caption className="sr-only">{caption}</caption> : null}
        <colgroup>
          {columns.map((column) => (
            <col key={column.key} style={column.width ? { width: column.width } : undefined} />
          ))}
        </colgroup>
        <thead>
          <tr>
            {columns.map((column) => (
              <th key={column.key} style={{ textAlign: column.align ?? "left" }}>
                {column.sortValue ? (
                  <button
                    type="button"
                    className={cx("table-sort", column.key === sortKey && "table-sort-active")}
                    onClick={() => toggle(column)}
                    aria-sort={
                      column.key === sortKey ? (asc ? "ascending" : "descending") : "none"
                    }
                  >
                    {column.label}
                    {column.key === sortKey ? (asc ? " ↑" : " ↓") : ""}
                  </button>
                ) : (
                  column.label
                )}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {sorted.map((row) => (
            <tr key={getRowKey(row)}>
              {columns.map((column) => (
                <td key={column.key} style={{ textAlign: column.align ?? "left" }}>
                  {column.render(row)}
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

/** Stable id helper for aria wiring in callers. */
export function useAutoId(prefix: string): string {
  const id = useId();
  return `${prefix}-${id.replace(/[:]/g, "")}`;
}
