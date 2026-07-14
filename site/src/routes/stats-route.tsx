import { useMemo, useState, type ReactNode } from "react";
import { CountryFlag } from "@/components/country-flag";
import { PlayerLink } from "@/components/player-detail";
import {
  PageHeader,
  SegmentedControl,
  RankedList,
  SortableTable,
  FilterGroup,
  EmptyState,
  type RankedItem,
  type Column,
} from "@/components/ui";
import {
  getPlayerById,
  getTeamByCode,
  playerStats,
  teamStats,
  type PlayerStat,
  type TeamStat,
} from "@/lib/data";

const AS_OF = playerStats[0]?.as_of_stage ?? "through quarterfinals";
// Per-90 rankings only make sense above a sample-size floor, otherwise a single
// cameo appearance tops every list.
const MIN_MINUTES_PER90 = 270;
const TOP_N = 15;

const POSITIONS = ["goalkeeper", "defender", "midfielder", "forward"];

function displayName(stat: PlayerStat): string {
  return getPlayerById(stat.player_id)?.display_name ?? stat.fifa_listed_name;
}

function teamName(stat: PlayerStat): string {
  return getTeamByCode(stat.team_code)?.team ?? stat.team_code;
}

function positionOf(stat: PlayerStat): string | null {
  return getPlayerById(stat.player_id)?.primary_position ?? null;
}

const teamOptions = Array.from(new Set(playerStats.map((s) => s.team_code)))
  .map((code) => ({ code, name: getTeamByCode(code)?.team ?? code }))
  .sort((a, b) => a.name.localeCompare(b.name));

type Mode = "total" | "per90";

/* ---- Team table columns (sortable, sticky, responsive) ---- */

const STAGE_RANK: Record<string, number> = {
  "Group stage": 0,
  "Round of 32": 1,
  "Round of 16": 2,
  "Quarter-finals": 3,
  "Semi-finals (in progress)": 4,
};

const TEAM_COLUMNS: Column<TeamStat>[] = [
  {
    key: "team",
    label: "Team",
    width: "22%",
    sortValue: (s) => s.team,
    render: (s) => (
      <span className="team-cell">
        <CountryFlag country={s.team} />
        {s.team}
      </span>
    ),
  },
  {
    key: "stage",
    label: "Final stage reached",
    width: "20%",
    initialAsc: false,
    sortValue: (s) => STAGE_RANK[s.stage_reached] ?? -1,
    render: (s) => s.stage_reached,
  },
  { key: "played", label: "P", align: "right", initialAsc: false, sortValue: (s) => s.matches_played, render: (s) => s.matches_played },
  { key: "wins", label: "W", align: "right", initialAsc: false, sortValue: (s) => s.wins, render: (s) => s.wins },
  { key: "draws", label: "D", align: "right", initialAsc: false, sortValue: (s) => s.draws, render: (s) => s.draws },
  { key: "losses", label: "L", align: "right", initialAsc: false, sortValue: (s) => s.losses, render: (s) => s.losses },
  { key: "gf", label: "GF", align: "right", initialAsc: false, sortValue: (s) => s.goals_for, render: (s) => s.goals_for },
  { key: "ga", label: "GA", align: "right", initialAsc: false, sortValue: (s) => s.goals_against, render: (s) => s.goals_against },
  { key: "xg", label: "xG", align: "right", initialAsc: false, sortValue: (s) => s.xg, render: (s) => s.xg.toFixed(1) },
  {
    key: "possession",
    label: "Poss %",
    align: "right",
    initialAsc: false,
    sortValue: (s) => s.possession_pct,
    render: (s) => s.possession_pct,
  },
];

export function StatsRoute() {
  const [teamFilter, setTeamFilter] = useState("all");
  const [posFilter, setPosFilter] = useState("all");
  const [mode, setMode] = useState<Mode>("total");

  const scopedStats = useMemo(
    () =>
      playerStats.filter((s) => {
        if (teamFilter !== "all" && s.team_code !== teamFilter) {
          return false;
        }
        if (posFilter !== "all" && positionOf(s) !== posFilter) {
          return false;
        }
        return true;
      }),
    [teamFilter, posFilter],
  );

  function toItem(stat: PlayerStat, value: number, valueLabel: string, meta?: ReactNode): RankedItem {
    return {
      key: `${stat.team_code}-${stat.player_id}`,
      name: <PlayerLink playerId={stat.player_id}>{displayName(stat)}</PlayerLink>,
      value,
      valueLabel,
      meta: meta ?? (
        <span className="ranked-team">
          <CountryFlag country={teamName(stat)} /> {teamName(stat)}
        </span>
      ),
    };
  }

  function ranking(
    metricOf: (s: PlayerStat) => number,
    { perMin, unit = "" }: { perMin: boolean; unit?: string },
  ): RankedItem[] {
    const rows = scopedStats.map((s) => ({ s, raw: metricOf(s) })).filter((x) => x.raw > 0);
    if (mode === "per90" && perMin) {
      return rows
        .filter((x) => x.s.minutes_played >= MIN_MINUTES_PER90)
        .map((x) => ({ s: x.s, value: (x.raw / x.s.minutes_played) * 90 }))
        .sort((a, b) => b.value - a.value)
        .slice(0, TOP_N)
        .map((x) => toItem(x.s, x.value, `${x.value.toFixed(2)}/90`));
    }
    return rows
      .sort((a, b) => b.raw - a.raw)
      .slice(0, TOP_N)
      .map((x) => toItem(x.s, x.raw, unit ? `${x.raw.toLocaleString()} ${unit}` : String(x.raw)));
  }

  const goals = useMemo(() => ranking((s) => s.goals, { perMin: true }), [scopedStats, mode]);
  const assists = useMemo(() => ranking((s) => s.assists, { perMin: true }), [scopedStats, mode]);
  const minutes = useMemo(() => ranking((s) => s.minutes_played, { perMin: false, unit: "min" }), [scopedStats]);
  const saves = useMemo(() => ranking((s) => s.gk_saves ?? 0, { perMin: true }), [scopedStats, mode]);

  const discipline = useMemo<RankedItem[]>(() => {
    const fair = (s: PlayerStat) => s.yellow_cards + 3 * (s.red_cards + s.indirect_red_cards);
    return scopedStats
      .filter((s) => fair(s) > 0)
      .sort((a, b) => fair(b) - fair(a) || displayName(a).localeCompare(displayName(b)))
      .map((s) => {
        const reds = s.red_cards + s.indirect_red_cards;
        return toItem(
          s,
          fair(s),
          `${fair(s)} pts`,
          <span className="ranked-team">
            <CountryFlag country={teamName(s)} /> {teamName(s)} · {s.yellow_cards}Y {reds}R
          </span>,
        );
      });
  }, [scopedStats]);

  const perNote =
    mode === "per90" ? ` · per 90, min ${MIN_MINUTES_PER90} min played` : "";

  return (
    <div className="page-stack">
      <PageHeader
        eyebrow="Leaders"
        title="Tournament leaders"
        intro={`Official FIFA statistics, ${AS_OF}. Filter by team or position, switch to per-90 rates, then dig into the full team table.`}
      />

      <div className="content-panel reveal">
        <div className="leaders-toolbar">
          <FilterGroup label="Team">
            <select value={teamFilter} onChange={(e) => setTeamFilter(e.target.value)}>
              <option value="all">All teams</option>
              {teamOptions.map((t) => (
                <option key={t.code} value={t.code}>
                  {t.name}
                </option>
              ))}
            </select>
          </FilterGroup>
          <FilterGroup label="Position">
            <select value={posFilter} onChange={(e) => setPosFilter(e.target.value)}>
              <option value="all">All positions</option>
              {POSITIONS.map((p) => (
                <option key={p} value={p}>
                  {p.charAt(0).toUpperCase() + p.slice(1)}
                </option>
              ))}
            </select>
          </FilterGroup>
          <div className="leaders-mode">
            <span className="filter-field-label">Rate</span>
            <SegmentedControl<Mode>
              ariaLabel="Total or per 90"
              value={mode}
              onChange={setMode}
              options={[
                { value: "total", label: "Total" },
                { value: "per90", label: "Per 90" },
              ]}
            />
          </div>
        </div>
        {mode === "per90" ? (
          <p className="insight-note">
            Per-90 rates rank only players with at least {MIN_MINUTES_PER90} minutes played, so a
            single substitute appearance can't top the list. Minutes and discipline stay as totals.
          </p>
        ) : null}
      </div>

      <div className="leaders-grid reveal">
        <section className="content-panel">
          <h2 className="section-heading">Goals{perNote}</h2>
          {goals.length > 0 ? (
            <RankedList items={goals} />
          ) : (
            <EmptyState>No goalscorers match these filters.</EmptyState>
          )}
        </section>
        <section className="content-panel">
          <h2 className="section-heading">Assists{perNote}</h2>
          {assists.length > 0 ? (
            <RankedList items={assists} />
          ) : (
            <EmptyState>No assists match these filters.</EmptyState>
          )}
        </section>
        <section className="content-panel">
          <h2 className="section-heading">Minutes played</h2>
          {minutes.length > 0 ? (
            <RankedList items={minutes} />
          ) : (
            <EmptyState>No minutes match these filters.</EmptyState>
          )}
        </section>
        <section className="content-panel">
          <h2 className="section-heading">Goalkeeper saves{perNote}</h2>
          {saves.length > 0 ? (
            <RankedList items={saves} />
          ) : (
            <EmptyState>Goalkeeping data lands with the next dataset refresh.</EmptyState>
          )}
        </section>
      </div>

      <section className="content-panel reveal">
        <h2 className="section-heading">Discipline</h2>
        <p className="insight-note">
          Fair-play points: each yellow counts 1 and each red counts 3, worst record first.
        </p>
        {discipline.length > 0 ? (
          <RankedList items={discipline} initialVisible={10} itemsLabel="carded players" />
        ) : (
          <EmptyState>No cards recorded for these filters.</EmptyState>
        )}
      </section>

      <section className="content-panel reveal">
        <h2 className="section-heading">Team table</h2>
        <p className="insight-note">
          Every recorded match (group stage plus knockouts, through the quarterfinals). Click any
          column to sort.
        </p>
        <SortableTable
          columns={TEAM_COLUMNS}
          rows={teamStats}
          getRowKey={(s) => s.team_code}
          initialSortKey="wins"
          initialSortAsc={false}
          caption="World Cup 2026 team table"
        />
      </section>
    </div>
  );
}
