import { useSearchParams } from "react-router-dom";
import { CountryFlag } from "@/components/country-flag";
import { PlayerLink } from "@/components/player-detail";
import { EmptyState, FilterGroup, SectionHeader, SummaryRow } from "@/components/ui";
import { teams, teamStats } from "@/lib/data";
import { ANALYTICS_INPUT } from "@/lib/data/analytics-input";
import {
  buildPlayerEfficiencyRows,
  buildSquadConcentration,
  buildSquadScorecards,
  type PlayerEfficiencyRow,
} from "@/lib/analytics";
import { formatNumber, formatPct, formatPoints } from "@/lib/format";
import { AnalysisPage, sourceNote } from "@/routes/analysis/shared";

const squadScorecards = buildSquadScorecards(ANALYTICS_INPUT);
const concentrationRows = buildSquadConcentration(ANALYTICS_INPUT);
const teamStatsByCode = new Map(teamStats.map((row) => [row.team_code, row]));
const scorecardByCode = new Map(squadScorecards.map((row) => [row.teamCode, row]));
const efficiencyRows = buildPlayerEfficiencyRows(ANALYTICS_INPUT, 1);

const TEAM_OPTIONS = teams
  .map((team) => ({ code: team.team_code, name: team.team }))
  .sort((a, b) => a.name.localeCompare(b.name));

function teamTopPerformers(teamCode: string): PlayerEfficiencyRow[] {
  return efficiencyRows
    .filter((row) => row.teamCode === teamCode)
    .sort((a, b) => b.goalContributions - a.goalContributions || b.minutes - a.minutes)
    .slice(0, 3);
}

function ComparisonBar({ value, max, tone = "a" }: { value: number | null; max: number; tone?: "a" | "b" }) {
  const width = value === null || max <= 0 ? 0 : Math.max((value / max) * 100, 2);
  return (
    <span className="comparison-bar" aria-hidden="true">
      <span className={`comparison-bar-fill comparison-bar-${tone}`} style={{ width: `${width}%` }} />
    </span>
  );
}

function ComparisonValue({
  label,
  a,
  b,
  formatter = (value) => formatNumber(value, 1),
  diffFormatter = formatter,
}: {
  label: string;
  a: number | null;
  b: number | null;
  formatter?: (value: number | null) => string;
  diffFormatter?: (value: number | null) => string;
}) {
  if (a === null && b === null) return null;
  const max = Math.max(a ?? 0, b ?? 0, 1);
  const diff = a !== null && b !== null ? a - b : null;
  return (
    <tr>
      <td>{label}</td>
      <td>
        <strong>{formatter(a)}</strong>
        <ComparisonBar value={a} max={max} tone="a" />
      </td>
      <td>
        <strong>{formatter(b)}</strong>
        <ComparisonBar value={b} max={max} tone="b" />
      </td>
      <td>{diff === null ? "N/A" : diff === 0 ? "Even" : `${diff > 0 ? "+" : ""}${diffFormatter(diff)}`}</td>
    </tr>
  );
}

function teamLabel(code: string): string {
  return TEAM_OPTIONS.find((team) => team.code === code)?.name ?? code;
}

export function CompareRoute() {
  const [searchParams, setSearchParams] = useSearchParams();
  const compareA = searchParams.get("teamA") ?? TEAM_OPTIONS[0]?.code ?? "";
  const compareB = searchParams.get("teamB") ?? TEAM_OPTIONS[1]?.code ?? compareA;
  const scoreA = scorecardByCode.get(compareA) ?? squadScorecards[0];
  const scoreB = scorecardByCode.get(compareB) ?? squadScorecards[1] ?? squadScorecards[0];
  const statA = teamStatsByCode.get(compareA) ?? null;
  const statB = teamStatsByCode.get(compareB) ?? null;
  const concA = concentrationRows.find((row) => row.teamCode === compareA) ?? null;
  const concB = concentrationRows.find((row) => row.teamCode === compareB) ?? null;

  function setCompareParam(key: "teamA" | "teamB", value: string) {
    const next = new URLSearchParams(searchParams);
    next.set(key, value);
    setSearchParams(next, { replace: false });
  }

  return (
    <AnalysisPage
      slug="compare"
      intro="Pick two teams to set their squads and tournaments side by side."
    >
        <section id="compare" className="content-panel reveal">
          <SectionHeader
            title="Two-team comparison"
            note="Your choice of teams is saved in the page address, so you can share the comparison."
          />
          <div className="leaders-toolbar">
            <FilterGroup label="Team A">
              <select value={compareA} onChange={(event) => setCompareParam("teamA", event.target.value)}>
                {TEAM_OPTIONS.map((team) => (
                  <option key={team.code} value={team.code}>
                    {team.name}
                  </option>
                ))}
              </select>
            </FilterGroup>
            <FilterGroup label="Team B">
              <select value={compareB} onChange={(event) => setCompareParam("teamB", event.target.value)}>
                {TEAM_OPTIONS.map((team) => (
                  <option key={team.code} value={team.code}>
                    {team.name}
                  </option>
                ))}
              </select>
            </FilterGroup>
          </div>
          {scoreA && scoreB ? (
            <div className="analysis-cols">
              <div>
                <SummaryRow
                  items={[
                    { key: "a", label: "Team A", value: <><CountryFlag country={scoreA.team} /> {scoreA.team}</> },
                    { key: "b", label: "Team B", value: <><CountryFlag country={scoreB.team} /> {scoreB.team}</> },
                  ]}
                />
                {/* Focusable so keyboard users can scroll the table sideways on small screens. */}
                <div
                  className="data-table-wrap"
                  tabIndex={0}
                  role="region"
                  aria-label="Two-team comparison table"
                >
                  <table className="data-table comparison-table">
                    <thead>
                      <tr>
                        <th>Metric</th>
                        <th>{teamLabel(compareA)}</th>
                        <th>{teamLabel(compareB)}</th>
                        <th>Difference</th>
                      </tr>
                    </thead>
                    <tbody>
                      <ComparisonValue label="Average age" a={scoreA.averageAge} b={scoreB.averageAge} />
                      <ComparisonValue label="Median age" a={scoreA.medianAge} b={scoreB.medianAge} />
                      <ComparisonValue
                        label="Domestic share"
                        a={scoreA.domesticLeaguePct}
                        b={scoreB.domesticLeaguePct}
                        formatter={(v) => formatPct(v)}
                        diffFormatter={(v) => formatPoints(v)}
                      />
                      <ComparisonValue label="Clubs represented" a={scoreA.clubsRepresented} b={scoreB.clubsRepresented} formatter={(v) => formatNumber(v)} />
                      <ComparisonValue label="League count" a={scoreA.leaguesRepresented} b={scoreB.leaguesRepresented} formatter={(v) => formatNumber(v)} />
                      <ComparisonValue label="Club HHI" a={concA?.clubHhi ?? null} b={concB?.clubHhi ?? null} formatter={(v) => formatNumber(v, 3)} />
                      <ComparisonValue label="Goals for" a={statA?.goals_for ?? null} b={statB?.goals_for ?? null} formatter={(v) => formatNumber(v)} />
                      <ComparisonValue label="Goals against" a={statA?.goals_against ?? null} b={statB?.goals_against ?? null} formatter={(v) => formatNumber(v)} />
                      <ComparisonValue label="xG" a={statA?.xg ?? null} b={statB?.xg ?? null} />
                    </tbody>
                  </table>
                </div>
              </div>
              <div>
                <h3 className="subsection-heading">Tournament record and top performers</h3>
                <div className="comparison-card-grid">
                  {[compareA, compareB].map((code) => {
                    const stat = teamStatsByCode.get(code);
                    const performers = teamTopPerformers(code);
                    return (
                      <article key={code} className="comparison-card">
                        <h4>
                          <CountryFlag country={teamLabel(code)} /> {teamLabel(code)}
                        </h4>
                        <p className="insight-note">
                          {stat ? `${stat.wins}W ${stat.draws}D ${stat.losses}L, ${stat.goals_for}-${stat.goals_against}, ${stat.stage_reached}` : "Team-stat row unavailable"}
                        </p>
                        <div className="chip-list">
                          {performers.map((row) => (
                            <PlayerLink key={row.playerId} playerId={row.playerId} className="player-chip">
                              {row.playerName} · {row.goalContributions} G+A
                            </PlayerLink>
                          ))}
                        </div>
                      </article>
                    );
                  })}
                </div>
                <p className="insight-note note-spaced">
                  Differences are descriptive only. They highlight scale and roster profile gaps without declaring causation.
                  Cards are not compared because the data has no team card totals.
                </p>
              </div>
            </div>
          ) : (
            <EmptyState>Choose two teams with available squad scorecards.</EmptyState>
          )}
          {sourceNote("Side-by-side descriptive comparison using synchronized per-row bar scales.", "Selected teams from active squads and team stats.", "xG where available; the data has no xGA or team card totals")}
        </section>
    </AnalysisPage>
  );
}
