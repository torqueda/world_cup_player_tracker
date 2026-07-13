import { useMemo, useState } from "react";
import {
  getPlayerById,
  getTeamByCode,
  playerStats,
  teamStats,
  type PlayerStat,
  type TeamStat,
} from "@/lib/data";

const AS_OF = playerStats[0]?.as_of_stage ?? "through quarterfinals";

function displayName(stat: PlayerStat): string {
  return getPlayerById(stat.player_id)?.display_name ?? stat.fifa_listed_name;
}

function teamName(stat: PlayerStat): string {
  return getTeamByCode(stat.team_code)?.team ?? stat.team_code;
}

function topWithTies(metric: (stat: PlayerStat) => number, count: number): PlayerStat[] {
  const sorted = [...playerStats].filter((stat) => metric(stat) > 0).sort((a, b) => metric(b) - metric(a));
  if (sorted.length === 0) {
    return [];
  }
  const cutoff = metric(sorted[Math.min(count, sorted.length) - 1]);
  return sorted.filter((stat, index) => index < count || metric(stat) === cutoff);
}

interface PictoRow {
  key: string;
  label: string;
  picto: string;
  value: string;
  title?: string;
}

function PictoList({ rows }: { rows: PictoRow[] }) {
  return (
    <div className="picto-list">
      {rows.map((row) => (
        <div key={row.key} className="picto-row" title={row.title ?? `${row.label}: ${row.value}`}>
          <span className="picto-label">{row.label}</span>
          <span className="picto-icons">{row.picto}</span>
          <span className="picto-value">{row.value}</span>
        </div>
      ))}
    </div>
  );
}

const goalRows: PictoRow[] = topWithTies((s) => s.goals, 10).map((s) => ({
  key: `${s.team_code}-${s.fifa_listed_name}`,
  label: `${displayName(s)} (${teamName(s)})`,
  picto: "⚽".repeat(s.goals),
  value: String(s.goals),
  title: `${displayName(s)}: ${s.goals} goals, ${s.assists} assists`,
}));

const assistRows: PictoRow[] = topWithTies((s) => s.assists, 10).map((s) => ({
  key: `${s.team_code}-${s.fifa_listed_name}`,
  label: `${displayName(s)} (${teamName(s)})`,
  picto: "🤝".repeat(s.assists),
  value: String(s.assists),
}));

const minuteRows: PictoRow[] = topWithTies((s) => s.minutes_played, 10).map((s) => ({
  key: `${s.team_code}-${s.fifa_listed_name}`,
  label: `${displayName(s)} (${teamName(s)})`,
  picto: "🏃",
  value: `${s.minutes_played.toLocaleString()} min`,
}));

const saveRows: PictoRow[] = topWithTies((s) => s.gk_saves ?? 0, 10).map((s) => ({
  key: `${s.team_code}-${s.fifa_listed_name}`,
  label: `${displayName(s)} (${teamName(s)})`,
  picto: "🧤",
  value: `${s.gk_saves} saves`,
}));

const cardRows: PictoRow[] = topWithTies(
  (s) => s.yellow_cards + 3 * (s.red_cards + s.indirect_red_cards),
  10,
).map((s) => {
  const reds = s.red_cards + s.indirect_red_cards;
  return {
    key: `${s.team_code}-${s.fifa_listed_name}`,
    label: `${displayName(s)} (${teamName(s)})`,
    picto: "🟨".repeat(s.yellow_cards) + "🟥".repeat(reds),
    value: `${s.yellow_cards + 3 * reds} pts`,
    title: `${displayName(s)}: ${s.yellow_cards} yellow, ${reds} red`,
  };
});

type TeamSortKey =
  | "team"
  | "stage"
  | "played"
  | "wins"
  | "draws"
  | "losses"
  | "gf"
  | "ga"
  | "xg"
  | "possession";

const STAGE_RANK: Record<string, number> = {
  "Group stage": 0,
  "Round of 32": 1,
  "Round of 16": 2,
  "Quarter-finals": 3,
  "Semi-finals (in progress)": 4,
};

const TEAM_SORT: Record<TeamSortKey, (stat: TeamStat) => string | number> = {
  team: (s) => s.team,
  stage: (s) => STAGE_RANK[s.stage_reached] ?? -1,
  played: (s) => s.matches_played,
  wins: (s) => s.wins,
  draws: (s) => s.draws,
  losses: (s) => s.losses,
  gf: (s) => s.goals_for,
  ga: (s) => s.goals_against,
  xg: (s) => s.xg,
  possession: (s) => s.possession_pct,
};

const TEAM_COLUMNS: { key: TeamSortKey; label: string }[] = [
  { key: "team", label: "Team" },
  { key: "stage", label: "Final stage reached" },
  { key: "played", label: "Played" },
  { key: "wins", label: "W" },
  { key: "draws", label: "D" },
  { key: "losses", label: "L" },
  { key: "gf", label: "GF" },
  { key: "ga", label: "GA" },
  { key: "xg", label: "xG" },
  { key: "possession", label: "Poss. %" },
];

export function StatsRoute() {
  const [teamSortKey, setTeamSortKey] = useState<TeamSortKey>("wins");
  const [teamSortAsc, setTeamSortAsc] = useState(false);

  const sortedTeamStats = useMemo(() => {
    const accessor = TEAM_SORT[teamSortKey];
    return [...teamStats].sort((a, b) => {
      const valueA = accessor(a);
      const valueB = accessor(b);
      const compared =
        typeof valueA === "number" && typeof valueB === "number"
          ? valueA - valueB
          : String(valueA).localeCompare(String(valueB));
      if (compared !== 0) {
        return teamSortAsc ? compared : -compared;
      }
      return a.team.localeCompare(b.team);
    });
  }, [teamSortKey, teamSortAsc]);

  function toggleTeamSort(key: TeamSortKey) {
    if (key === teamSortKey) {
      setTeamSortAsc((asc) => !asc);
    } else {
      setTeamSortKey(key);
      setTeamSortAsc(key === "team");
    }
  }

  return (
    <div className="page-stack">
      <section className="content-panel centered-panel reveal">
        <div className="panel-heading">
          <p className="eyebrow">Stats</p>
          <h2>Tournament leaders</h2>
        </div>
        <p className="panel-intro">
          Official FIFA statistics, {AS_OF}. Player leaderboards on top, the full team table
          underneath — both refresh with each dataset update.
        </p>
      </section>

      <div className="content-grid reveal">
        <section className="content-panel">
          <h3 className="section-heading">Golden Boot race</h3>
          <p className="insight-note">One ball per goal.</p>
          <PictoList rows={goalRows} />
          <h4 className="subsection-heading">Most assists</h4>
          <p className="insight-note">One handshake per assist.</p>
          <PictoList rows={assistRows} />
        </section>
        <section className="content-panel">
          <h3 className="section-heading">Workhorses &amp; walls</h3>
          <h4 className="subsection-heading">Most minutes played</h4>
          <PictoList rows={minuteRows} />
          <h4 className="subsection-heading">Most goalkeeper saves</h4>
          {saveRows.length > 0 ? (
            <PictoList rows={saveRows} />
          ) : (
            <p className="insight-note">Goalkeeping columns land with the next dataset refresh.</p>
          )}
          <h4 className="subsection-heading">Fair Play</h4>
          <p className="insight-note">
            Cards collected so far — each yellow card counts 1 point and each red card counts
            3, so a higher total means a worse disciplinary record.
          </p>
          <PictoList rows={cardRows} />
        </section>
      </div>

      <section className="content-panel reveal">
        <h3 className="section-heading">Team table</h3>
        <p className="insight-note">
          "Played" counts every recorded match (group stage plus knockouts, through the
          quarterfinals). Click any column to sort.
        </p>
        <div className="data-table-wrap">
          <table className="data-table">
            <thead>
              <tr>
                {TEAM_COLUMNS.map((column) => (
                  <th key={column.key}>
                    <button
                      type="button"
                      className={
                        column.key === teamSortKey ? "table-sort table-sort-active" : "table-sort"
                      }
                      onClick={() => toggleTeamSort(column.key)}
                    >
                      {column.label}
                      {column.key === teamSortKey ? (teamSortAsc ? " ↑" : " ↓") : ""}
                    </button>
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {sortedTeamStats.map((stat) => (
                <tr key={stat.team_code}>
                  <td>{stat.team}</td>
                  <td>{stat.stage_reached}</td>
                  <td>{stat.matches_played}</td>
                  <td>{stat.wins}</td>
                  <td>{stat.draws}</td>
                  <td>{stat.losses}</td>
                  <td>{stat.goals_for}</td>
                  <td>{stat.goals_against}</td>
                  <td>{stat.xg}</td>
                  <td>{stat.possession_pct}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </section>
    </div>
  );
}
