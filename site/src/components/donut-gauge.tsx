interface DonutGaugeProps {
  label: string;
  value: number;
  total: number;
  /** Text drawn in the donut's center; defaults to `${value}`. */
  centerText?: string;
  /** Small line under the label, e.g. "24 of 26". */
  sublabel?: string;
  /** Alternating color tone so adjacent donuts read as distinct. */
  tone?: "a" | "b";
  /** Native tooltip text. */
  title?: string;
}

const SIZE = 84;
const STROKE = 10;
const RADIUS = (SIZE - STROKE) / 2;
const CIRCUMFERENCE = 2 * Math.PI * RADIUS;

/**
 * A small donut that fills clockwise with `value / total`. Used where a bar
 * chart would overstate small differences and the "how full is it" reading
 * matters more than cross-row comparison.
 */
export function DonutGauge({ label, value, total, centerText, sublabel, tone = "a", title }: DonutGaugeProps) {
  const fraction = total > 0 ? Math.min(Math.max(value / total, 0), 1) : 0;
  const dash = fraction * CIRCUMFERENCE;

  return (
    <figure className="donut-gauge" title={title ?? `${label}: ${value} of ${total}`}>
      <svg viewBox={`0 0 ${SIZE} ${SIZE}`} role="img" aria-label={`${label}: ${value} of ${total}`}>
        <circle
          cx={SIZE / 2}
          cy={SIZE / 2}
          r={RADIUS}
          fill="none"
          className="donut-track"
          strokeWidth={STROKE}
        />
        <circle
          cx={SIZE / 2}
          cy={SIZE / 2}
          r={RADIUS}
          fill="none"
          className={tone === "b" ? "donut-fill donut-fill-b" : "donut-fill"}
          strokeWidth={STROKE}
          strokeLinecap="round"
          strokeDasharray={`${dash} ${CIRCUMFERENCE - dash}`}
          transform={`rotate(-90 ${SIZE / 2} ${SIZE / 2})`}
        />
        <text x="50%" y="50%" dominantBaseline="central" textAnchor="middle" className="donut-center">
          {centerText ?? String(value)}
        </text>
      </svg>
      <figcaption>
        <span className="donut-label">{label}</span>
        {sublabel ? <span className="donut-sublabel">{sublabel}</span> : null}
      </figcaption>
    </figure>
  );
}
