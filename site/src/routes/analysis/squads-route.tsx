import { CountryFlag } from "@/components/country-flag";
import { Expandable, MetricCard, SectionHeader, SortableTable, type Column } from "@/components/ui";
import { ANALYTICS_INPUT } from "@/lib/data/analytics-input";
import {
  TOURNAMENT_START_DATE,
  buildBirthplaceSummary,
  buildSquadConcentration,
  buildSquadScorecards,
  type BirthCountryRow,
  type SquadScorecard,
} from "@/lib/analytics";
import { csvDataUri, formatNumber, formatPct } from "@/lib/format";
import { AnalysisPage, listInWords, sourceNote, topBy } from "@/routes/analysis/shared";

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

const birthplaces = buildBirthplaceSummary(ANALYTICS_INPUT);
const BIRTH_TOP = 15;
const OTHER_TEAMS_SHOWN = 3;

function otherTeamsText(row: BirthCountryRow): string {
  if (row.otherTeams.length === 0) {
    return "None";
  }
  const shown = row.otherTeams
    .slice(0, OTHER_TEAMS_SHOWN)
    .map((item) => `${item.team} ${item.players}`)
    .join(", ");
  const more = row.otherTeams.length - OTHER_TEAMS_SHOWN;
  return more > 0 ? `${shown} and ${more} more` : shown;
}

const birthColumns: Column<BirthCountryRow>[] = [
  {
    key: "country",
    label: "Birth country",
    width: "20%",
    sortValue: (row) => row.country,
    render: (row) => (
      <span className="team-cell">
        <CountryFlag country={row.country} />
        {row.country}
      </span>
    ),
  },
  {
    key: "born",
    label: "Players born there",
    align: "right",
    initialAsc: false,
    sortValue: (row) => row.bornThere,
    render: (row) => row.bornThere,
  },
  {
    key: "home",
    label: "Play for it",
    align: "right",
    initialAsc: false,
    sortValue: (row) => row.playForIt ?? -1,
    render: (row) => (row.playForIt === null ? "No team" : row.playForIt),
  },
  {
    key: "others",
    label: "Play for other teams",
    align: "right",
    initialAsc: false,
    sortValue: (row) => row.playForOthers,
    render: (row) => row.playForOthers,
  },
  {
    key: "otherTeams",
    label: "Other teams (players)",
    width: "34%",
    sortValue: (row) => row.otherTeams.length,
    render: (row) => otherTeamsText(row),
  },
];

const birthCsv = csvDataUri(birthplaces.rows, [
  { label: "birth_country", value: (row) => row.country },
  { label: "players_born_there", value: (row) => row.bornThere },
  { label: "play_for_it", value: (row) => row.playForIt },
  { label: "play_for_other_teams", value: (row) => row.playForOthers },
  { label: "other_teams", value: (row) => row.otherTeams.map((item) => `${item.team} (${item.players})`).join("; ") },
]);

const topExporter = [...birthplaces.rows].sort((a, b) => b.playForOthers - a.playForOthers)[0];

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

        <section id="birthplaces" className="content-panel reveal">
          <SectionHeader
            title="Where the players were born"
            note="Every squad together: how many players were born in the country they play for, and which countries the players were born in."
            actions={
              <a className="button-secondary" href={birthCsv} download="world-cup-2026-birth-countries.csv">
                Download CSV
              </a>
            }
            aside={sourceNote(
              "Birth country as recorded for each player, matched to the team's country or a documented alias.",
              "Active final-squad players.",
            )}
          />
          <div className="metrics-grid">
            <MetricCard
              label="Born in the country they play for"
              value={formatPct(birthplaces.bornInRepresentedCountry / birthplaces.birthCountryKnown)}
              note={`${birthplaces.bornInRepresentedCountry.toLocaleString()} of ${birthplaces.birthCountryKnown.toLocaleString()} players`}
            />
            <MetricCard
              label="Squads mostly home-born"
              value={`${birthplaces.mostlyHomeBornSquads} of ${birthplaces.squads}`}
              note={`${birthplaces.allHomeBornSquads.length} entirely`}
            />
            <MetricCard
              label="Birth countries"
              value={birthplaces.birthCountries}
              note={`${birthplaces.birthCountriesWithoutTeam} with no team at the tournament`}
            />
            {topExporter ? (
              <MetricCard
                label="Most players for other teams"
                value={topExporter.playForOthers}
                note={`born in ${topExporter.country}, playing for ${topExporter.otherTeams.length} teams`}
              />
            ) : null}
          </div>
          <p className="insight-note">
            The squads made up entirely of players born in the country are {listInWords(birthplaces.allHomeBornSquads)}.
            &quot;Mostly&quot; means more than half the squad.
          </p>
          <h3 className="subsection-heading">Countries where the most players were born</h3>
          <SortableTable
            rows={birthplaces.rows.slice(0, BIRTH_TOP)}
            columns={birthColumns}
            getRowKey={(row) => row.country}
            initialSortKey="born"
            initialSortAsc={false}
            caption={`The ${BIRTH_TOP} countries where the most players were born`}
            className="wide-table"
            focusable
          />
          <Expandable summary={`All ${birthplaces.birthCountries} birth countries`}>
            <SortableTable
              rows={birthplaces.rows}
              columns={birthColumns}
              getRowKey={(row) => row.country}
              initialSortKey="born"
              initialSortAsc={false}
              caption="Every birth country"
              className="wide-table"
              focusable
            />
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
