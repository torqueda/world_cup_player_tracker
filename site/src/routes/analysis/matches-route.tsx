import { useMemo, useState } from "react";
import { Expandable, FilterGroup, MetricCard, RankedList, SectionHeader, SortableTable } from "@/components/ui";
import { matches } from "@/lib/data";
import { ANALYTICS_INPUT } from "@/lib/data/analytics-input";
import { stageLabel, stageRank } from "@/lib/data/stages";
import { buildMatchAnalysis } from "@/lib/analytics";
import { AnalysisPage, sourceNote } from "@/routes/analysis/shared";

const matchAnalysis = buildMatchAnalysis(ANALYTICS_INPUT);

export function AnalysisMatchesRoute() {
  const [venueMinMatches, setVenueMinMatches] = useState(2);
  const filteredVenueRows = useMemo(
    () => matchAnalysis.goalsByVenue.filter((row) => row.matches >= venueMinMatches),
    [venueMinMatches],
  );

  return (
    <AnalysisPage
      slug="matches"
      intro="Goals by stage and by venue, how often matches were won by one goal or more, and how the confederations did against each other."
    >
        <section id="matches" className="content-panel reveal">
          <SectionHeader
            title="Match and venue analysis"
            note="All match summaries use played matches with a recorded score. Penalty shootouts are counted separately from draws after 90 or 120 minutes."
            aside={sourceNote("Stage, margin, venue, team-stage, and confederation matchup summaries from played match rows.", "Played matches with non-null scores.", `${venueMinMatches} matches for the venue ranking`)}
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
                  name: stageLabel(row.stage),
                  value: row.goalsPerMatch,
                  valueLabel: row.goalsPerMatch.toFixed(2),
                  meta: `${row.goals} goal${row.goals === 1 ? "" : "s"} in ${row.matches} match${row.matches === 1 ? "" : "es"}`,
                }))}
                showRank={false}
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
                  meta: `${row.goals} goal${row.goals === 1 ? "" : "s"} in ${row.matches} match${row.matches === 1 ? "" : "es"}`,
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
                render: (row) => `${row.confedA} ${row.confedAWins}-${row.confedBWins} ${row.confedB}, ${row.draws} draw${row.draws === 1 ? "" : "s"}`,
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
                { key: "stage", label: "Stage", sortValue: (row) => stageRank(row.stage), render: (row) => stageLabel(row.stage) },
                { key: "played", label: "P", align: "right", sortValue: (row) => row.played, render: (row) => row.played },
                { key: "wins", label: "W", align: "right", initialAsc: false, sortValue: (row) => row.wins, render: (row) => row.wins },
                { key: "draws", label: "D", align: "right", initialAsc: false, sortValue: (row) => row.draws, render: (row) => row.draws },
                { key: "losses", label: "L", align: "right", initialAsc: false, sortValue: (row) => row.losses, render: (row) => row.losses },
                { key: "gf", label: "GF", align: "right", initialAsc: false, sortValue: (row) => row.goalsFor, render: (row) => row.goalsFor },
                { key: "ga", label: "GA", align: "right", initialAsc: false, sortValue: (row) => row.goalsAgainst, render: (row) => row.goalsAgainst },
              ]}
            />
          </Expandable>
        </section>
    </AnalysisPage>
  );
}
