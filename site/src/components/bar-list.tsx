import { useState } from "react";
import { CountryFlag } from "@/components/country-flag";

export interface BarListItem {
  key: string;
  label: string;
  value: number;
  emphasized?: boolean;
  /** Optional custom hover text; defaults to "label: value". */
  title?: string;
  /** When set, a country flag is rendered before the label. */
  flagCountry?: string;
}

interface BarListProps {
  items: BarListItem[];
  mode?: "uniform" | "emphasis";
  scrollable?: boolean;
  valueFormatter?: (value: number) => string;
  /** When set and exceeded, only this many bars show until "Show all". */
  initialVisible?: number;
  itemsLabel?: string;
}

const defaultFormatter = (value: number) => value.toLocaleString();

export function BarList({
  items,
  mode = "uniform",
  scrollable = false,
  valueFormatter,
  initialVisible,
  itemsLabel = "entries",
}: BarListProps) {
  const [expanded, setExpanded] = useState(false);
  const maxValue = items.reduce((max, item) => Math.max(max, item.value), 0) || 1;
  const format = valueFormatter ?? defaultFormatter;
  const collapsible = initialVisible != null && items.length > initialVisible;
  const visible = collapsible && !expanded ? items.slice(0, initialVisible) : items;

  return (
    <>
      <div className={scrollable ? "bar-list bar-list-scroll" : "bar-list"}>
        {visible.map((item) => {
          const widthPct = Math.max((item.value / maxValue) * 100, 2);
          const isAccent = mode === "uniform" || item.emphasized;
          // tabIndex + aria-label make the full detail (which the title shows on
          // hover) reachable by keyboard focus and screen readers too.
          const detail = item.title ?? `${item.label}: ${format(item.value)}`;
          return (
            <div key={item.key} className="bar-row" title={detail} tabIndex={0} aria-label={detail}>
              <span className="bar-label">
                {item.flagCountry ? <CountryFlag country={item.flagCountry} /> : null}
                {item.label}
              </span>
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
