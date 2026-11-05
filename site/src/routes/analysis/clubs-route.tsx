import { useState } from "react";
import { Expandable, RankedList, SectionHeader, SegmentedControl, SortableTable, type Column, type RankedItem } from "@/components/ui";
import { ANALYTICS_INPUT } from "@/lib/data/analytics-input";
import { DEFAULT_MEANINGFUL_MINUTES, buildImpactRows, type ImpactMetric, type ImpactRow } from "@/lib/analytics";
import { csvDataUri } from "@/lib/format";
import { AnalysisPage, sourceNote } from "@/routes/analysis/shared";

const clubImpactRows = buildImpactRows(ANALYTICS_INPUT, "club", DEFAULT_MEANINGFUL_MINUTES);
const leagueImpactRows = buildImpactRows(ANALYTICS_INPUT, "league", DEFAULT_MEANINGFUL_MINUTES);

const IMPACT_METRIC_LABELS: Record<ImpactMetric, string> = {
  playersSent: "Players",
  teamsRepresented: "Teams represented",
  totalMinutes: "Minutes",
  goals: "Goals",
  assists: "Assists",
  goalContributions: "Goal contributions",
  impactIndex: "Impact index",
};

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

const impactColumns: Column<ImpactRow>[] = [
  { key: "label", label: "Entity", width: "24%", sortValue: (row) => row.label, render: (row) => row.label },
  { key: "players", label: "Players", align: "center", initialAsc: false, sortValue: (row) => row.playersSent, render: (row) => row.playersSent },
  { key: "teams", label: "Teams", align: "center", initialAsc: false, sortValue: (row) => row.teamsRepresented, render: (row) => row.teamsRepresented },
  { key: "minutes", label: "Minutes", align: "center", initialAsc: false, sortValue: (row) => row.totalMinutes, render: (row) => row.totalMinutes.toLocaleString() },
  { key: "goals", label: "G", align: "center", initialAsc: false, sortValue: (row) => row.goals, render: (row) => row.goals },
  { key: "assists", label: "A", align: "center", initialAsc: false, sortValue: (row) => row.assists, render: (row) => row.assists },
  { key: "gc", label: "G+A", align: "center", initialAsc: false, sortValue: (row) => row.goalContributions, render: (row) => row.goalContributions },
  {
    key: "meaningful",
    label: "Meaningful min",
    align: "center",
    initialAsc: false,
    sortValue: (row) => row.meaningfulMinutesPlayers,
    render: (row) => row.meaningfulMinutesPlayers,
  },
  {
    key: "impact",
    label: "Index",
    align: "center",
    initialAsc: false,
    sortValue: (row) => row.impactIndex,
    render: (row) => row.impactIndex.toFixed(1),
  },
];

export function ClubsRoute() {
  const [impactKind, setImpactKind] = useState<"club" | "league">("club");
  const [impactMetric, setImpactMetric] = useState<ImpactMetric>("playersSent");
  const impactRows = impactKind === "club" ? clubImpactRows : leagueImpactRows;
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
    <AnalysisPage
      slug="clubs"
      intro="The clubs and leagues behind the 48 squads: how many players each sent, to how many teams, and what those players did at the tournament."
    >
        <section id="impact" className="content-panel reveal">
          <SectionHeader
            title="Club and league impact"
            note="Players, national-team reach, minutes, goals, assists, and goal contributions are separate components. The optional index is analytical, not an official ranking."
            actions={
              <a className="button-secondary" href={impactCsv} download={`world-cup-2026-${impactKind}-impact.csv`}>
                Download CSV
              </a>
            }
            aside={sourceNote(
              "Club or league totals aggregate active players' official goals, assists, and minutes.",
              "Active final-squad players with club-at-call-up records.",
              `${DEFAULT_MEANINGFUL_MINUTES} minutes for meaningful-minutes counts; the data has no starts`,
            )}
          />
          <div className="leaders-toolbar impact-toolbar">
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
                { value: "playersSent", label: "Players" },
                { value: "totalMinutes", label: "Minutes" },
                { value: "goals", label: "Goals" },
                { value: "assists", label: "Assists" },
                { value: "goalContributions", label: "G+A" },
                { value: "teamsRepresented", label: "Teams" },
                { value: "impactIndex", label: "Index" },
              ]}
            />
          </div>
          <div className="analysis-cols analysis-impact-cols">
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
        </section>
    </AnalysisPage>
  );
}
