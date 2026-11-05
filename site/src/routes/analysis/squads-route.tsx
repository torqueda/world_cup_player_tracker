import { CountryFlag } from "@/components/country-flag";
import { Expandable, MetricCard, SectionHeader, SortableTable, type Column } from "@/components/ui";
import { ANALYTICS_INPUT } from "@/lib/data/analytics-input";
import { TOURNAMENT_START_DATE, buildSquadConcentration, buildSquadScorecards, type SquadScorecard } from "@/lib/analytics";
import { csvDataUri, formatNumber, formatPct } from "@/lib/format";
import { AnalysisPage, sourceNote, topBy } from "@/routes/analysis/shared";

const squadScorecards = buildSquadScorecards(ANALYTICS_INPUT);
const concentrationRows = buildSquadConcentration(ANALYTICS_INPUT);

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
    key: "domestic",
    label: "Domestic",
    align: "right",
    initialAsc: false,
    sortValue: (row) => row.domesticLeaguePct ?? -1,
    render: (row) => `${formatPct(row.domesticLeaguePct)} (${row.domesticLeaguePlayers}/${row.domesticLeagueKnown.count})`,
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
    label: "Born in represented country",
    align: "right",
    initialAsc: false,
    sortValue: (row) => row.homegrownBirthShare ?? -1,
    render: (row) => `${formatPct(row.homegrownBirthShare)} (${row.homegrownBirthPlayers}/${row.birthCountryKnown.count})`,
  },
  {
    key: "stage",
    label: "Stage",
    sortValue: (row) => row.stageReached,
    render: (row) => row.stageReached,
  },
];

const scorecardCsv = csvDataUri(squadScorecards, [
  { label: "team", value: (row) => row.team },
  { label: "average_age", value: (row) => row.averageAge },
  { label: "median_age", value: (row) => row.medianAge },
  { label: "under_23_count", value: (row) => row.under23Count },
  { label: "age_30_plus_count", value: (row) => row.age30PlusCount },
  { label: "domestic_league_pct", value: (row) => row.domesticLeaguePct },
  { label: "clubs_represented", value: (row) => row.clubsRepresented },
  { label: "club_countries_represented", value: (row) => row.clubCountriesRepresented },
  { label: "leagues_represented", value: (row) => row.leaguesRepresented },
  { label: "birthplace_homegrown_share", value: (row) => row.homegrownBirthShare },
  { label: "stage_reached", value: (row) => row.stageReached },
]);

const oldest = topBy(squadScorecards, (row) => row.averageAge);
const youngest = topBy(squadScorecards, (row) => row.averageAge, true);
const mostDomestic = topBy(squadScorecards, (row) => row.domesticLeaguePct);
const mostConcentrated = topBy(concentrationRows, (row) => row.clubHhi);

export function SquadsRoute() {
  return (
    <AnalysisPage
      slug="squads"
      intro="Every squad's age profile, how many of its players play at home, where they were born, and how many clubs it draws on."
    >
        <section id="scorecard" className="content-panel reveal">
          <SectionHeader
            title="Squad composition scorecard"
            note="Compare every national-team squad. Each metric uses players with available data; missing values are excluded."
            actions={
              <a className="button-secondary" href={scorecardCsv} download="world-cup-2026-squad-scorecard.csv">
                Download CSV
              </a>
            }
            aside={sourceNote("Team-level roster and composition metrics.", "Active final-squad entries.", "Per-field non-null denominators")}
          />
          <div className="metrics-grid">
            <MetricCard label="Oldest average age" value={formatNumber(oldest?.averageAge, 1)} note={oldest?.team} />
            <MetricCard label="Youngest average age" value={formatNumber(youngest?.averageAge, 1)} note={youngest?.team} />
            <MetricCard
              label="Highest domestic share"
              value={formatPct(mostDomestic?.domesticLeaguePct)}
              note={
                mostDomestic
                  ? `${mostDomestic.team}, ${mostDomestic.domesticLeaguePlayers} of ${mostDomestic.domesticLeagueKnown.count} players`
                  : undefined
              }
            />
            <MetricCard
              label="Most club-concentrated"
              value={formatNumber(mostConcentrated?.clubHhi, 3)}
              note={mostConcentrated?.team}
            />
          </div>
          <div className="method-note-grid">
            <p className="insight-note">
              <strong>Domestic</strong> means the player&apos;s club-at-call-up country matches the national team country
              or a documented country-name alias. It is not a nationality, birthplace, or eligibility measure.
            </p>
            <p className="insight-note">
              <strong>Born in represented country</strong> means the player&apos;s recorded birth country matches the national team
              country or alias. It is not a statement about development pathway, citizenship, or eligibility history.
            </p>
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
        </section>

        <section id="concentration" className="content-panel reveal">
          <SectionHeader
            title="Concentration and diversity"
            note="HHI sums squared shares across clubs or club countries. Higher means the squad is concentrated in fewer clubs; lower means it is spread more broadly."
            aside={sourceNote("Transparent concentration measures across club-at-call-up assignments.", "Active squads with club records.", "Rows with missing club country excluded from country HHI")}
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
        </section>
    </AnalysisPage>
  );
}
