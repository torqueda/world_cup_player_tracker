import { useMemo, useState, type ReactNode } from "react";
import { useSearchParams } from "react-router-dom";
import metaJson from "@data/meta.json";
import { CountryFlag } from "@/components/country-flag";
import { PlayerLink } from "@/components/player-detail";
import {
  EmptyState,
  Expandable,
  FilterGroup,
  MetricCard,
  PageHeader,
  RankedList,
  SectionHeader,
  SegmentedControl,
  SortableTable,
  SummaryRow,
  type Column,
  type RankedItem,
} from "@/components/ui";
import {
  activePlayers,
  clubs,
  getConfederationForCountry,
  matches,
  playerClubAtCallup,
  players,
  playerStats,
  squadEntries,
  teams,
  teamStats,
  TEAM_COUNTRY_ALIASES,
} from "@/lib/data";
import {
  DEFAULT_MEANINGFUL_MINUTES,
  TOURNAMENT_START_DATE,
  buildDataQualitySummary,
  buildImpactRows,
  buildMatchAnalysis,
  buildPlayerEfficiencyRows,
  buildSquadConcentration,
  buildSquadScorecards,
  type DataQualityRow,
  type ImpactMetric,
  type ImpactRow,
  type PlayerEfficiencyRow,
  type SquadScorecard,
} from "@/lib/analytics";

const meta = metaJson as { counts?: Record<string, number>; exported_at?: string };
const AS_OF = playerStats[0]?.as_of_stage ?? teamStats[0]?.as_of_stage ?? "current export";
const UPDATE_LABEL = meta.exported_at ?? "current export";
const ANALYTICS_INPUT = {
  teams,
  players,
  squadEntries,
  playerClubAtCallup,
  clubs,
  playerStats,
  teamStats,
  matches,
  teamCountryAliases: TEAM_COUNTRY_ALIASES,
  confederationForCountry: getConfederationForCountry,
};

const squadScorecards = buildSquadScorecards(ANALYTICS_INPUT);
const concentrationRows = buildSquadConcentration(ANALYTICS_INPUT);
const clubImpactRows = buildImpactRows(ANALYTICS_INPUT, "club", DEFAULT_MEANINGFUL_MINUTES);
const leagueImpactRows = buildImpactRows(ANALYTICS_INPUT, "league", DEFAULT_MEANINGFUL_MINUTES);
const matchAnalysis = buildMatchAnalysis(ANALYTICS_INPUT);
const dataQuality = buildDataQualitySummary(ANALYTICS_INPUT, meta);
const teamStatsByCode = new Map(teamStats.map((row) => [row.team_code, row]));
const scorecardByCode = new Map(squadScorecards.map((row) => [row.teamCode, row]));

const SECTIONS = [
  { id: "scorecard", label: "Scorecard" },
  { id: "impact", label: "Club & league impact" },
  { id: "concentration", label: "Concentration" },
  { id: "compare", label: "Compare teams" },
  { id: "efficiency", label: "Player efficiency" },
  { id: "matches", label: "Matches & venues" },
  { id: "quality", label: "Data quality" },
];

const IMPACT_METRIC_LABELS: Record<ImpactMetric, string> = {
  playersSent: "Headcount",
  teamsRepresented: "Teams represented",
  totalMinutes: "Minutes",
  goals: "Goals",
  assists: "Assists",
  goalContributions: "Goal contributions",
  impactIndex: "Impact index",
};

const TEAM_OPTIONS = teams
  .map((team) => ({ code: team.team_code, name: team.team }))
  .sort((a, b) => a.name.localeCompare(b.name));

function formatNumber(value: number | null | undefined, digits = 0): string {
  if (value === null || value === undefined || Number.isNaN(value)) {
    return "N/A";
  }
  return value.toLocaleString(undefined, {
    maximumFractionDigits: digits,
    minimumFractionDigits: digits,
  });
}

function formatPct(value: number | null | undefined, digits = 0): string {
  return value === null || value === undefined ? "N/A" : `${(value * 100).toFixed(digits)}%`;
}

function denominator(row: { count: number; total: number }): string {
  return `${row.count}/${row.total}`;
}

function csvEscape(value: unknown): string {
  const text = value === null || value === undefined ? "" : String(value);
  return /[",\n]/.test(text) ? `"${text.replace(/"/g, '""')}"` : text;
}

function csvDataUri<T>(rows: T[], columns: { label: string; value: (row: T) => unknown }[]): string {
  const header = columns.map((column) => csvEscape(column.label)).join(",");
  const body = rows.map((row) => columns.map((column) => csvEscape(column.value(row))).join(",")).join("\n");
  return `data:text/csv;charset=utf-8,${encodeURIComponent(`${header}\n${body}`)}`;
}

function sourceNote(definition: ReactNode, population: ReactNode, thresholds: ReactNode = "None") {
  return (
    <p className="source-note">
      <strong>Definition:</strong> {definition} <strong>Population:</strong> {population}{" "}
      <strong>Minimum threshold:</strong> {thresholds}. <strong>Updated:</strong> {UPDATE_LABEL}.
    </p>
  );
}

function topBy<T>(rows: T[], value: (row: T) => number | null, asc = false): T | null {
  const valid = rows.filter((row) => value(row) !== null);
  if (valid.length === 0) {
    return null;
  }
  return [...valid].sort((a, b) => {
    const delta = (value(a) ?? 0) - (value(b) ?? 0);
    return asc ? delta : -delta;
  })[0];
}

function metricValue(row: ImpactRow, metric: ImpactMetric): number {
  return row[metric];
}

function impactRankedItems(rows: ImpactRow[], metric: ImpactMetric): RankedItem[] {
  return [...rows]
    .sort((a, b) => metricValue(b, metric) - metricValue(a, metric) || a.label.localeCompare(b.label))
    .slice(0, 15)
    .map((row) => ({
      key: row.key,
      name: row.label,
      value: metricValue(row, metric),
      valueLabel:
        metric === "impactIndex"
          ? row.impactIndex.toFixed(1)
          : metric === "totalMinutes"
            ? `${row.totalMinutes.toLocaleString()} min`
            : metricValue(row, metric).toLocaleString(),
      meta: `${row.playersSent} players, ${row.teamsRepresented} teams, ${row.goalContributions} G+A`,
    }));
}

function qualityStatusLabel(status: DataQualityRow["status"]): string {
  return status.replace(/_/g, " ");
}

function teamTopPerformers(teamCode: string): PlayerEfficiencyRow[] {
  return buildPlayerEfficiencyRows(ANALYTICS_INPUT, 1)
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
}: {
  label: string;
  a: number | null;
  b: number | null;
  formatter?: (value: number | null) => string;
}) {
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
      <td>{diff === null ? "N/A" : diff === 0 ? "Even" : `${diff > 0 ? "+" : ""}${formatter(diff)}`}</td>
    </tr>
  );
}

function teamLabel(code: string): string {
  return TEAM_OPTIONS.find((team) => team.code === code)?.name ?? code;
}

const scorecardColumns: Column<SquadScorecard>[] = [
  {
    key: "team",
    label: "Team",
    width: "16%",
    sortValue: (row) => row.team,
    render: (row) => (
      <span className="team-cell">
        <CountryFlag country={row.team} />
        {row.team}
      </span>
    ),
  },
  {
    key: "age",
    label: "Avg / median age",
    align: "right",
    initialAsc: false,
    sortValue: (row) => row.averageAge ?? -1,
    render: (row) => `${formatNumber(row.averageAge, 1)} / ${formatNumber(row.medianAge, 1)}`,
  },
  {
    key: "ageBands",
    label: "U23 / 30+",
    align: "right",
    initialAsc: false,
    sortValue: (row) => row.under23Count,
    render: (row) => `${row.under23Count} / ${row.age30PlusCount}`,
  },
  {
    key: "caps",
    label: "Caps total / median",
    align: "right",
    initialAsc: false,
    sortValue: (row) => row.totalCaps ?? -1,
    render: (row) => `${formatNumber(row.totalCaps)} / ${formatNumber(row.medianCaps, 0)}`,
  },
  {
    key: "domestic",
    label: "Domestic",
    align: "right",
    initialAsc: false,
    sortValue: (row) => row.domesticLeaguePct ?? -1,
    render: (row) => `${formatPct(row.domesticLeaguePct)} (${denominator(row.domesticLeagueKnown)})`,
  },
  {
    key: "diversity",
    label: "Clubs / countries / leagues",
    align: "right",
    initialAsc: false,
    sortValue: (row) => row.clubsRepresented,
    render: (row) => `${row.clubsRepresented} / ${row.clubCountriesRepresented} / ${row.leaguesRepresented}`,
  },
  {
    key: "birth",
    label: "Birth home-grown",
    align: "right",
    initialAsc: false,
    sortValue: (row) => row.homegrownBirthShare ?? -1,
    render: (row) => `${formatPct(row.homegrownBirthShare)} (${denominator(row.birthCountryKnown)})`,
  },
  {
    key: "stage",
    label: "Stage",
    sortValue: (row) => row.stageReached,
    render: (row) => row.stageReached,
  },
];

const impactColumns: Column<ImpactRow>[] = [
  { key: "label", label: "Entity", width: "24%", sortValue: (row) => row.label, render: (row) => row.label },
  { key: "players", label: "Players", align: "right", initialAsc: false, sortValue: (row) => row.playersSent, render: (row) => row.playersSent },
  { key: "teams", label: "Teams", align: "right", initialAsc: false, sortValue: (row) => row.teamsRepresented, render: (row) => row.teamsRepresented },
  { key: "minutes", label: "Minutes", align: "right", initialAsc: false, sortValue: (row) => row.totalMinutes, render: (row) => row.totalMinutes.toLocaleString() },
  { key: "goals", label: "G", align: "right", initialAsc: false, sortValue: (row) => row.goals, render: (row) => row.goals },
  { key: "assists", label: "A", align: "right", initialAsc: false, sortValue: (row) => row.assists, render: (row) => row.assists },
  { key: "gc", label: "G+A", align: "right", initialAsc: false, sortValue: (row) => row.goalContributions, render: (row) => row.goalContributions },
  {
    key: "meaningful",
    label: "Meaningful min",
    align: "right",
    initialAsc: false,
    sortValue: (row) => row.meaningfulMinutesPlayers,
    render: (row) => row.meaningfulMinutesPlayers,
  },
  {
    key: "impact",
    label: "Index",
    align: "right",
    initialAsc: false,
    sortValue: (row) => row.impactIndex,
    render: (row) => row.impactIndex.toFixed(1),
  },
];

export function InsightsRoute() {
  const [searchParams, setSearchParams] = useSearchParams();
  const [impactKind, setImpactKind] = useState<"club" | "league">("club");
  const [impactMetric, setImpactMetric] = useState<ImpactMetric>("playersSent");
  const [efficiencyBucket, setEfficiencyBucket] = useState<"outfield" | "goalkeeper">("outfield");
  const [minMinutes, setMinMinutes] = useState(DEFAULT_MEANINGFUL_MINUTES);
  const [venueMinMatches, setVenueMinMatches] = useState(2);

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

  const impactRows = impactKind === "club" ? clubImpactRows : leagueImpactRows;
  const filteredVenueRows = useMemo(
    () => matchAnalysis.goalsByVenue.filter((row) => row.matches >= venueMinMatches),
    [venueMinMatches],
  );
  const efficiencyRows = useMemo(
    () => buildPlayerEfficiencyRows(ANALYTICS_INPUT, minMinutes).filter((row) => row.bucket === efficiencyBucket),
    [minMinutes, efficiencyBucket],
  );

  const oldest = topBy(squadScorecards, (row) => row.averageAge);
  const youngest = topBy(squadScorecards, (row) => row.averageAge, true);
  const mostDomestic = topBy(squadScorecards, (row) => row.domesticLeaguePct);
  const mostConcentrated = topBy(concentrationRows, (row) => row.clubHhi);

  const scorecardCsv = csvDataUri(squadScorecards, [
    { label: "team", value: (row) => row.team },
    { label: "average_age", value: (row) => row.averageAge },
    { label: "median_age", value: (row) => row.medianAge },
    { label: "under_23_count", value: (row) => row.under23Count },
    { label: "age_30_plus_count", value: (row) => row.age30PlusCount },
    { label: "total_caps", value: (row) => row.totalCaps },
    { label: "median_caps", value: (row) => row.medianCaps },
    { label: "domestic_league_pct", value: (row) => row.domesticLeaguePct },
    { label: "clubs_represented", value: (row) => row.clubsRepresented },
    { label: "club_countries_represented", value: (row) => row.clubCountriesRepresented },
    { label: "leagues_represented", value: (row) => row.leaguesRepresented },
    { label: "birthplace_homegrown_share", value: (row) => row.homegrownBirthShare },
    { label: "stage_reached", value: (row) => row.stageReached },
  ]);
  const impactCsv = csvDataUri(impactRows, [
    { label: "entity", value: (row) => row.label },
    { label: "players_sent", value: (row) => row.playersSent },
    { label: "teams_represented", value: (row) => row.teamsRepresented },
    { label: "minutes", value: (row) => row.totalMinutes },
    { label: "goals", value: (row) => row.goals },
    { label: "assists", value: (row) => row.assists },
    { label: "goal_contributions", value: (row) => row.goalContributions },
    { label: "meaningful_minutes_players", value: (row) => row.meaningfulMinutesPlayers },
    { label: "impact_index", value: (row) => row.impactIndex },
  ]);

  return (
    <div className="page-stack">
      <PageHeader
        eyebrow="Analysis"
        title="Analytical layer"
        intro={`Portfolio-grade cuts of the World Cup 2026 dataset: squad construction, club and league impact, concentration, comparison, player efficiency, match context, and data quality. Calculations use current app exports only, ${AS_OF}.`}
      />

      <nav className="section-nav reveal" aria-label="Analysis sections">
        {SECTIONS.map((section) => (
          <a key={section.id} href={`#${section.id}`} className="section-nav-link">
            {section.label}
          </a>
        ))}
      </nav>

      <section id="scorecard" className="content-panel reveal">
        <SectionHeader
          title="Squad composition scorecard"
          note="Every row is one active national-team squad. Null ages, caps, club countries, and birth countries stay out of their respective denominators."
          actions={
            <a className="button-secondary" href={scorecardCsv} download="world-cup-2026-squad-scorecard.csv">
              Download CSV
            </a>
          }
        />
        <div className="metrics-grid">
          <MetricCard label="Oldest average age" value={formatNumber(oldest?.averageAge, 1)} note={oldest?.team} />
          <MetricCard label="Youngest average age" value={formatNumber(youngest?.averageAge, 1)} note={youngest?.team} />
          <MetricCard
            label="Highest domestic share"
            value={formatPct(mostDomestic?.domesticLeaguePct)}
            note={mostDomestic?.team}
          />
          <MetricCard
            label="Most club-concentrated"
            value={formatNumber(mostConcentrated?.clubHhi, 3)}
            note={mostConcentrated?.team}
          />
        </div>
        <SortableTable
          rows={squadScorecards}
          columns={scorecardColumns}
          getRowKey={(row) => row.teamCode}
          initialSortKey="team"
          caption="Squad composition scorecard"
        />
        <Expandable summary="How this was calculated">
          <dl className="definition-list">
            <div className="definition-item">
              <dt>Age profile</dt>
              <dd>
                Age is measured on {TOURNAMENT_START_DATE}. Average and median use players with valid dates of birth.
                Under-23 means age below 23. Age-30-plus means age at least 30.
              </dd>
            </div>
            <div className="definition-item">
              <dt>Experience</dt>
              <dd>Total and median caps use `caps_pre_tournament` only where exported on squad-entry rows.</dd>
            </div>
            <div className="definition-item">
              <dt>Domestic league share</dt>
              <dd>
                Players whose club country matches the national team country or a documented alias, divided by players
                with a non-null club country.
              </dd>
            </div>
            <div className="definition-item">
              <dt>Birthplace home-grown share</dt>
              <dd>
                Players whose birth country matches the team country or alias, divided by players with a known birth
                country.
              </dd>
            </div>
          </dl>
        </Expandable>
        {sourceNote("Team-level roster and composition metrics.", "Active final-squad entries.", "Per-field non-null denominators")}
      </section>

      <section id="impact" className="content-panel reveal">
        <SectionHeader
          title="Club and league impact"
          note="Headcount, national-team reach, minutes, goals, assists, and goal contributions are separate components. The optional index is analytical, not an official ranking."
          actions={
            <a className="button-secondary" href={impactCsv} download={`world-cup-2026-${impactKind}-impact.csv`}>
              Download CSV
            </a>
          }
        />
        <div className="leaders-toolbar">
          <SegmentedControl
            ariaLabel="Impact entity"
            value={impactKind}
            onChange={setImpactKind}
            options={[
              { value: "club", label: "Clubs" },
              { value: "league", label: "Leagues" },
            ]}
          />
          <SegmentedControl<ImpactMetric>
            ariaLabel="Impact metric"
            value={impactMetric}
            onChange={setImpactMetric}
            options={[
              { value: "playersSent", label: "Headcount" },
              { value: "totalMinutes", label: "Minutes" },
              { value: "goals", label: "Goals" },
              { value: "assists", label: "Assists" },
              { value: "goalContributions", label: "G+A" },
              { value: "teamsRepresented", label: "Teams" },
              { value: "impactIndex", label: "Index" },
            ]}
          />
        </div>
        <div className="analysis-cols">
          <div>
            <h3 className="subsection-heading">Top {impactKind}s by {IMPACT_METRIC_LABELS[impactMetric].toLowerCase()}</h3>
            <RankedList
              items={impactRankedItems(impactRows, impactMetric)}
              initialVisible={10}
              itemsLabel={`${impactKind}s`}
            />
          </div>
          <div>
            <h3 className="subsection-heading">Component table</h3>
            <SortableTable
              rows={impactRows.slice(0, 60)}
              columns={impactColumns}
              getRowKey={(row) => row.key}
              initialSortKey={impactMetric === "impactIndex" ? "impact" : impactMetric === "goalContributions" ? "gc" : undefined}
              initialSortAsc={false}
              caption="Club and league impact components"
            />
          </div>
        </div>
        <Expandable summary="Impact index formula">
          <p className="insight-note">
            Impact index = 100 * (0.20 normalized players sent + 0.20 normalized teams represented + 0.35 normalized
            tournament minutes + 0.25 normalized goal contributions). Each component is divided by the maximum value
            in the selected entity set. This weighting is an analytical lens for comparison, not an official ranking.
          </p>
        </Expandable>
        {sourceNote(
          "Club or league totals aggregate active players' official goals, assists, and minutes.",
          "Active final-squad players with club-at-call-up records.",
          `${DEFAULT_MEANINGFUL_MINUTES} minutes for meaningful-minutes counts; starts are not exported`,
        )}
      </section>

      <section id="concentration" className="content-panel reveal">
        <SectionHeader
          title="Concentration and diversity"
          note="HHI sums squared shares across clubs or club countries. Higher means the squad is concentrated in fewer clubs; lower means it is spread more broadly."
        />
        <SortableTable
          rows={concentrationRows}
          getRowKey={(row) => row.teamCode}
          initialSortKey="clubHhi"
          initialSortAsc={false}
          caption="Squad concentration measures"
          columns={[
            {
              key: "team",
              label: "Team",
              sortValue: (row) => row.team,
              render: (row) => (
                <span className="team-cell">
                  <CountryFlag country={row.team} />
                  {row.team}
                </span>
              ),
            },
            {
              key: "largestClub",
              label: "Largest club share",
              align: "right",
              initialAsc: false,
              sortValue: (row) => row.largestClubShare ?? -1,
              render: (row) => `${formatPct(row.largestClubShare)} (${row.largestClubName ?? "N/A"})`,
            },
            {
              key: "largestCountry",
              label: "Largest club-country share",
              align: "right",
              initialAsc: false,
              sortValue: (row) => row.largestClubCountryShare ?? -1,
              render: (row) => `${formatPct(row.largestClubCountryShare)} (${row.largestClubCountry ?? "N/A"})`,
            },
            {
              key: "clubHhi",
              label: "Club HHI",
              align: "right",
              initialAsc: false,
              sortValue: (row) => row.clubHhi ?? -1,
              render: (row) => formatNumber(row.clubHhi, 3),
            },
            {
              key: "countryHhi",
              label: "Country HHI",
              align: "right",
              initialAsc: false,
              sortValue: (row) => row.clubCountryHhi ?? -1,
              render: (row) => formatNumber(row.clubCountryHhi, 3),
            },
            {
              key: "effective",
              label: "Effective clubs",
              align: "right",
              initialAsc: false,
              sortValue: (row) => row.effectiveClubCount ?? -1,
              render: (row) => formatNumber(row.effectiveClubCount, 1),
            },
            {
              key: "normalized",
              label: "Normalized effective clubs",
              align: "right",
              initialAsc: false,
              sortValue: (row) => row.normalizedEffectiveClubCount ?? -1,
              render: (row) => formatPct(row.normalizedEffectiveClubCount),
            },
          ]}
        />
        <Expandable summary="How this was calculated">
          <p className="insight-note">
            HHI is the sum of squared shares. A squad split evenly across 26 different clubs has a low HHI; a squad
            drawing many players from the same club has a higher HHI. Effective clubs equals 1 / HHI. Normalized
            effective clubs divides that by the raw number of clubs represented.
          </p>
        </Expandable>
        {sourceNote("Transparent concentration measures across club-at-call-up assignments.", "Active squads with club records.", "Rows with missing club country excluded from country HHI")}
      </section>

      <section id="compare" className="content-panel reveal">
        <SectionHeader
          title="Two-team comparison"
          note="Selections are stored in URL query parameters (`teamA` and `teamB`) so a comparison can be shared."
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
              <div className="data-table-wrap">
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
                    <ComparisonValue label="Total caps" a={scoreA.totalCaps} b={scoreB.totalCaps} formatter={(v) => formatNumber(v)} />
                    <ComparisonValue label="Median caps" a={scoreA.medianCaps} b={scoreB.medianCaps} formatter={(v) => formatNumber(v)} />
                    <ComparisonValue label="Domestic share" a={scoreA.domesticLeaguePct} b={scoreB.domesticLeaguePct} formatter={(v) => formatPct(v)} />
                    <ComparisonValue label="Clubs represented" a={scoreA.clubsRepresented} b={scoreB.clubsRepresented} formatter={(v) => formatNumber(v)} />
                    <ComparisonValue label="League count" a={scoreA.leaguesRepresented} b={scoreB.leaguesRepresented} formatter={(v) => formatNumber(v)} />
                    <ComparisonValue label="Club HHI" a={concA?.clubHhi ?? null} b={concB?.clubHhi ?? null} formatter={(v) => formatNumber(v, 3)} />
                    <ComparisonValue label="Goals for" a={statA?.goals_for ?? null} b={statB?.goals_for ?? null} formatter={(v) => formatNumber(v)} />
                    <ComparisonValue label="Goals against" a={statA?.goals_against ?? null} b={statB?.goals_against ?? null} formatter={(v) => formatNumber(v)} />
                    <ComparisonValue label="xG" a={statA?.xg ?? null} b={statB?.xg ?? null} />
                    <ComparisonValue label="xGA" a={null} b={null} />
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
                Cards are not compared because team-card totals are not exported as a team table.
              </p>
            </div>
          </div>
        ) : (
          <EmptyState>Choose two teams with available squad scorecards.</EmptyState>
        )}
        {sourceNote("Side-by-side descriptive comparison using synchronized per-row bar scales.", "Selected teams from active squads and team stats.", "xGA unavailable in current exports")}
      </section>

      <section id="efficiency" className="content-panel reveal">
        <SectionHeader
          title="Player efficiency"
          note="Rate rankings exclude zero- and very-low-minute players. Goalkeepers and outfield players are separated because their role context differs."
        />
        <div className="leaders-toolbar">
          <FilterGroup label="Minimum minutes">
            <input
              type="number"
              min={1}
              step={15}
              value={minMinutes}
              onChange={(event) => setMinMinutes(Math.max(1, Number(event.target.value) || DEFAULT_MEANINGFUL_MINUTES))}
            />
          </FilterGroup>
          <SegmentedControl
            ariaLabel="Player role"
            value={efficiencyBucket}
            onChange={setEfficiencyBucket}
            options={[
              { value: "outfield", label: "Outfield" },
              { value: "goalkeeper", label: "Goalkeepers" },
            ]}
          />
        </div>
        <SortableTable
          rows={efficiencyRows.slice(0, 40)}
          getRowKey={(row) => row.playerId}
          initialSortKey="gc90"
          initialSortAsc={false}
          caption="Player efficiency per 90"
          columns={[
            {
              key: "player",
              label: "Player",
              sortValue: (row) => row.playerName,
              render: (row) => <PlayerLink playerId={row.playerId}>{row.playerName}</PlayerLink>,
            },
            {
              key: "team",
              label: "Team",
              sortValue: (row) => row.team,
              render: (row) => (
                <span className="team-cell">
                  <CountryFlag country={row.team} />
                  {row.team}
                </span>
              ),
            },
            { key: "minutes", label: "Min", align: "right", initialAsc: false, sortValue: (row) => row.minutes, render: (row) => row.minutes },
            { key: "g90", label: "G/90", align: "right", initialAsc: false, sortValue: (row) => row.goalsPer90, render: (row) => row.goalsPer90.toFixed(2) },
            { key: "a90", label: "A/90", align: "right", initialAsc: false, sortValue: (row) => row.assistsPer90, render: (row) => row.assistsPer90.toFixed(2) },
            { key: "gc90", label: "G+A/90", align: "right", initialAsc: false, sortValue: (row) => row.goalContributionsPer90, render: (row) => row.goalContributionsPer90.toFixed(2) },
            { key: "cards90", label: "Cards/90", align: "right", initialAsc: false, sortValue: (row) => row.cardsPer90, render: (row) => row.cardsPer90.toFixed(2) },
          ]}
        />
        {sourceNote("Per-90 rate = event count / minutes played * 90.", `Players with at least ${minMinutes} minutes in the selected role bucket.`, `${minMinutes} minutes, adjustable by user`)}
      </section>

      <section id="matches" className="content-panel reveal">
        <SectionHeader
          title="Match and venue analysis"
          note="All match summaries come from played matches with exported scores. Penalty shootouts are counted separately from regulation score draws."
        />
        <div className="metrics-grid">
          <MetricCard label="Played matches" value={matches.filter((match) => match.status === "played").length} />
          <MetricCard label="Drawn scorelines" value={matchAnalysis.draws} note="before shootout resolution" />
          <MetricCard label="Penalty shootouts" value={matchAnalysis.penaltyShootouts} />
        </div>
        <div className="analysis-cols">
          <div>
            <h3 className="subsection-heading">Goals per match by stage</h3>
            <RankedList
              items={matchAnalysis.goalsByStage.map((row) => ({
                key: row.stage,
                name: row.stage,
                value: row.goalsPerMatch,
                valueLabel: row.goalsPerMatch.toFixed(2),
                meta: `${row.goals} goals in ${row.matches} matches`,
              }))}
              initialVisible={8}
            />
            <h3 className="subsection-heading">Score margin distribution</h3>
            <RankedList
              items={matchAnalysis.marginDistribution.map((row) => ({
                key: row.margin,
                name: row.margin,
                value: row.matches,
              }))}
              showRank={false}
            />
          </div>
          <div>
            <div className="section-header">
              <div className="section-header-main">
                <h3 className="subsection-heading">Goals per match by venue</h3>
                <p className="insight-note">Minimum-match filter prevents one-match venue rankings from dominating.</p>
              </div>
              <FilterGroup label="Min matches">
                <input
                  type="number"
                  min={1}
                  max={10}
                  value={venueMinMatches}
                  onChange={(event) => setVenueMinMatches(Math.max(1, Number(event.target.value) || 1))}
                />
              </FilterGroup>
            </div>
            <RankedList
              items={filteredVenueRows.map((row) => ({
                key: `${row.venue}-${row.city}`,
                name: `${row.venue}, ${row.city}`,
                value: row.goalsPerMatch,
                valueLabel: row.goalsPerMatch.toFixed(2),
                meta: `${row.goals} goals in ${row.matches} matches`,
              }))}
              initialVisible={10}
              itemsLabel="venues"
            />
          </div>
        </div>
        <h3 className="subsection-heading">Confederation-vs-confederation results</h3>
        <SortableTable
          rows={matchAnalysis.confederationMatchups}
          getRowKey={(row) => row.key}
          initialSortKey="matches"
          initialSortAsc={false}
          caption="Confederation matchups"
          columns={[
            { key: "matchup", label: "Matchup", sortValue: (row) => row.matchup, render: (row) => row.matchup },
            { key: "matches", label: "Matches", align: "right", initialAsc: false, sortValue: (row) => row.matches, render: (row) => row.matches },
            {
              key: "record",
              label: "Record",
              render: (row) => `${row.confedA} ${row.confedAWins}-${row.confedBWins} ${row.confedB}, ${row.draws} draws`,
            },
            { key: "shootouts", label: "Shootouts", align: "right", initialAsc: false, sortValue: (row) => row.shootouts, render: (row) => row.shootouts },
            { key: "goals", label: "Goals", align: "right", initialAsc: false, sortValue: (row) => row.goals, render: (row) => row.goals },
          ]}
        />
        <Expandable summary="Team records by stage">
          <SortableTable
            rows={matchAnalysis.teamRecordsByStage}
            getRowKey={(row) => `${row.team}-${row.stage}`}
            initialSortKey="stage"
            caption="Team records by stage"
            columns={[
              { key: "team", label: "Team", sortValue: (row) => row.team, render: (row) => row.team },
              { key: "stage", label: "Stage", sortValue: (row) => row.stage, render: (row) => row.stage },
              { key: "played", label: "P", align: "right", sortValue: (row) => row.played, render: (row) => row.played },
              { key: "wins", label: "W", align: "right", initialAsc: false, sortValue: (row) => row.wins, render: (row) => row.wins },
              { key: "draws", label: "D", align: "right", initialAsc: false, sortValue: (row) => row.draws, render: (row) => row.draws },
              { key: "losses", label: "L", align: "right", initialAsc: false, sortValue: (row) => row.losses, render: (row) => row.losses },
              { key: "gf", label: "GF", align: "right", initialAsc: false, sortValue: (row) => row.goalsFor, render: (row) => row.goalsFor },
              { key: "ga", label: "GA", align: "right", initialAsc: false, sortValue: (row) => row.goalsAgainst, render: (row) => row.goalsAgainst },
            ]}
          />
        </Expandable>
        {sourceNote("Stage, margin, venue, team-stage, and confederation matchup summaries from played match rows.", "Played matches with non-null scores.", `${venueMinMatches} matches for the venue ranking`)}
      </section>

      <section id="quality" className="content-panel reveal">
        <SectionHeader
          title="Data quality dashboard"
          note="Quality rows distinguish available coverage, missing values, not-applicable fields, not-yet-collected fields, and validation status."
        />
        <div className="metrics-grid">
          <MetricCard label="Latest export" value={dataQuality.latestExportDate ?? "N/A"} />
          <MetricCard label="Active players" value={activePlayers.length.toLocaleString()} />
          <MetricCard label="Exported entities" value={dataQuality.rowCounts.length} />
        </div>
        <div className="analysis-cols">
          <div>
            <h3 className="subsection-heading">Row counts by entity</h3>
            <SortableTable
              rows={dataQuality.rowCounts}
              getRowKey={(row) => row.entity}
              initialSortKey="rows"
              initialSortAsc={false}
              caption="Export row counts"
              columns={[
                { key: "entity", label: "Entity", sortValue: (row) => row.entity, render: (row) => row.entity },
                { key: "rows", label: "Rows", align: "right", initialAsc: false, sortValue: (row) => row.rows, render: (row) => row.rows.toLocaleString() },
              ]}
            />
          </div>
          <div>
            <h3 className="subsection-heading">Coverage and field status</h3>
            <SortableTable
              rows={[...dataQuality.sourceCoverage, ...dataQuality.fieldStatus]}
              getRowKey={(row) => row.key}
              initialSortKey="status"
              caption="Data quality status"
              columns={[
                { key: "label", label: "Check", sortValue: (row) => row.label, render: (row) => row.label },
                { key: "status", label: "Status", sortValue: (row) => row.status, render: (row) => <span className={`quality-pill quality-${row.status}`}>{qualityStatusLabel(row.status)}</span> },
                { key: "coverage", label: "Coverage", align: "right", initialAsc: false, sortValue: (row) => row.pct ?? -1, render: (row) => row.pct === null ? "N/A" : `${formatPct(row.pct)} (${row.count}/${row.total})` },
                { key: "note", label: "Interpretation", render: (row) => row.note },
              ]}
            />
          </div>
        </div>
        <Expandable summary="How to read this dashboard">
          <dl className="definition-list">
            <div className="definition-item">
              <dt>Missing</dt>
              <dd>A field is expected for the population but absent in one or more rows, so analyses use explicit denominators.</dd>
            </div>
            <div className="definition-item">
              <dt>Not applicable</dt>
              <dd>The field is intentionally irrelevant for that population, such as goalkeeper stat fields for outfield players.</dd>
            </div>
            <div className="definition-item">
              <dt>Not yet collected</dt>
              <dd>The metric is useful but no current app-export field supports it, such as xGA or player starts.</dd>
            </div>
            <div className="definition-item">
              <dt>Failed validation</dt>
              <dd>Strict audit failures stop app-export generation. No failed-validation row list is bundled in the current app exports.</dd>
            </div>
          </dl>
        </Expandable>
        {sourceNote("Coverage checks and unresolved-field inventory from app-export rows and meta counts.", "Current JSON exports.", "No imputation")}
      </section>
    </div>
  );
}
