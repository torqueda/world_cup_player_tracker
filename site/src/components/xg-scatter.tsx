import type { TeamStat } from "@/lib/data";

interface XgScatterProps {
  stats: TeamStat[];
  /** Team names to label directly on the plot; the rest rely on hover. */
  labelled: Set<string>;
}

const WIDTH = 640;
const HEIGHT = 460;
const PAD_LEFT = 52;
const PAD_BOTTOM = 52;
const PAD_TOP = 20;
const PAD_RIGHT = 20;

const PLOT_W = WIDTH - PAD_LEFT - PAD_RIGHT;
const PLOT_H = HEIGHT - PAD_TOP - PAD_BOTTOM;

function niceMax(value: number): number {
  // Round up to the next even number so the par line lands on tick marks.
  return Math.max(2, Math.ceil(value / 2) * 2);
}

/**
 * Goals scored vs. expected goals (xG) for every team. Each dot's distance
 * above or below the diagonal par line is how much the team over- or
 * under-performed its xG.
 */
export function XgScatter({ stats, labelled }: XgScatterProps) {
  const domainMax = niceMax(Math.max(...stats.map((s) => Math.max(s.goals_for, s.xg)), 0));
  const ticks = Array.from({ length: domainMax / 2 + 1 }, (_, i) => i * 2);

  const x = (value: number) => PAD_LEFT + (value / domainMax) * PLOT_W;
  const y = (value: number) => PAD_TOP + PLOT_H - (value / domainMax) * PLOT_H;

  return (
    <div className="xg-scatter">
      <svg viewBox={`0 0 ${WIDTH} ${HEIGHT}`} role="img" aria-label="Goals scored versus expected goals per team">
        {/* gridlines + ticks */}
        {ticks.map((tick) => (
          <g key={tick}>
            <line
              x1={x(tick)}
              y1={PAD_TOP}
              x2={x(tick)}
              y2={PAD_TOP + PLOT_H}
              className="xg-grid"
            />
            <line
              x1={PAD_LEFT}
              y1={y(tick)}
              x2={PAD_LEFT + PLOT_W}
              y2={y(tick)}
              className="xg-grid"
            />
            <text x={x(tick)} y={PAD_TOP + PLOT_H + 18} className="xg-axis-tick" textAnchor="middle">
              {tick}
            </text>
            <text x={PAD_LEFT - 8} y={y(tick) + 4} className="xg-axis-tick" textAnchor="end">
              {tick}
            </text>
          </g>
        ))}

        {/* par line (goals == xG) */}
        <line x1={x(0)} y1={y(0)} x2={x(domainMax)} y2={y(domainMax)} className="xg-par-line" />
        <text x={x(domainMax) - 4} y={y(domainMax) + 16} className="xg-par-label" textAnchor="end">
          goals = xG
        </text>

        {/* axis titles */}
        <text x={PAD_LEFT + PLOT_W / 2} y={HEIGHT - 6} className="xg-axis-title" textAnchor="middle">
          Expected goals (xG)
        </text>
        <text
          x={-(PAD_TOP + PLOT_H / 2)}
          y={14}
          className="xg-axis-title"
          textAnchor="middle"
          transform="rotate(-90)"
        >
          Goals scored
        </text>

        {/* team points */}
        {stats.map((stat) => {
          const delta = stat.goals_for - stat.xg;
          const tone = delta >= 0.5 ? "over" : delta <= -0.5 ? "under" : "par";
          const cx = x(stat.xg);
          const cy = y(stat.goals_for);
          const showLabel = labelled.has(stat.team);
          return (
            <g key={stat.team_code}>
              <circle cx={cx} cy={cy} r={showLabel ? 6 : 4.5} className={`xg-dot xg-dot-${tone}`}>
                <title>
                  {stat.team}: {stat.goals_for} goals from {stat.xg.toFixed(2)} xG (
                  {delta >= 0 ? "+" : ""}
                  {delta.toFixed(2)})
                </title>
              </circle>
              {showLabel ? (
                <text x={cx + 9} y={cy + 4} className="xg-point-label">
                  {stat.team}
                </text>
              ) : null}
            </g>
          );
        })}
      </svg>
    </div>
  );
}
