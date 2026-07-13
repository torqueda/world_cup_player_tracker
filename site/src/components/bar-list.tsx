export interface BarListItem {
  key: string;
  label: string;
  value: number;
  emphasized?: boolean;
  /** Optional custom hover text; defaults to "label: value". */
  title?: string;
}

interface BarListProps {
  items: BarListItem[];
  mode?: "uniform" | "emphasis";
  scrollable?: boolean;
  valueFormatter?: (value: number) => string;
}

const defaultFormatter = (value: number) => value.toLocaleString();

export function BarList({ items, mode = "uniform", scrollable = false, valueFormatter }: BarListProps) {
  const maxValue = items.reduce((max, item) => Math.max(max, item.value), 0) || 1;
  const format = valueFormatter ?? defaultFormatter;

  return (
    <div className={scrollable ? "bar-list bar-list-scroll" : "bar-list"}>
      {items.map((item) => {
        const widthPct = Math.max((item.value / maxValue) * 100, 2);
        const isAccent = mode === "uniform" || item.emphasized;
        return (
          <div key={item.key} className="bar-row" title={item.title ?? `${item.label}: ${format(item.value)}`}>
            <span className="bar-label">{item.label}</span>
            <span className="bar-track">
              <span
                className={isAccent ? "bar-fill bar-fill-accent" : "bar-fill bar-fill-muted"}
                style={{ width: `${widthPct}%` }}
              />
            </span>
            <span className="bar-value">{format(item.value)}</span>
          </div>
        );
      })}
    </div>
  );
}
