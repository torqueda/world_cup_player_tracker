import { CountryFlag } from "@/components/country-flag";
import { Expandable, MetricCard, SectionHeader, SortableTable, type Column } from "@/components/ui";
import { ANALYTICS_INPUT } from "@/lib/data/analytics-input";
import {
  buildBirthplaceSummary,
  buildClubCountrySummary,
  type BirthCountryRow,
  type ClubCountryRow,
} from "@/lib/analytics";
import { csvDataUri, formatPct } from "@/lib/format";
import { AnalysisPage, listInWords, sourceNote } from "@/routes/analysis/shared";

const birthplaces = buildBirthplaceSummary(ANALYTICS_INPUT);
const clubCountries = buildClubCountrySummary(ANALYTICS_INPUT);

const TOP_ROWS = 15;
const CITY_ROWS = 10;
const THREE_COUNTRY_ROWS = 5;
const OTHER_TEAMS_SHOWN = 3;
const HOST_NATIONS = ["United States", "Canada", "Mexico"];

function CountryCell({ country }: { country: string }) {
  return (
    <span className="team-cell">
      <CountryFlag country={country} />
      {country}
    </span>
  );
}

function teamsWithCounts(teams: { team: string; players: number }[], limit = OTHER_TEAMS_SHOWN): string {
  if (teams.length === 0) {
    return "None";
  }
  const shown = teams
    .slice(0, limit)
    .map((item) => `${item.team} ${item.players}`)
    .join(", ");
  const more = teams.length - limit;
  return more > 0 ? `${shown} and ${more} more` : shown;
}

/* ---- Birth countries ---- */

const birthColumns: Column<BirthCountryRow>[] = [
  {
    key: "country",
    label: "Birth country",
    width: "20%",
    sortValue: (row) => row.country,
    render: (row) => <CountryCell country={row.country} />,
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
    render: (row) => teamsWithCounts(row.otherTeams),
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

/* ---- Host nations ---- */

const hostRows = HOST_NATIONS.map((country) => birthplaces.rows.find((row) => row.country === country)).filter(
  (row): row is BirthCountryRow => row !== undefined,
);

/* ---- Club countries ---- */

const clubCountryColumns: Column<ClubCountryRow>[] = [
  {
    key: "country",
    label: "Club country",
    width: "24%",
    sortValue: (row) => row.country,
    render: (row) => <CountryCell country={row.country} />,
  },
  {
    key: "players",
    label: "Players at its clubs",
    align: "right",
    initialAsc: false,
    sortValue: (row) => row.players,
    render: (row) => row.players,
  },
  {
    key: "clubs",
    label: "Clubs",
    align: "right",
    initialAsc: false,
    sortValue: (row) => row.clubs,
    render: (row) => row.clubs,
  },
  {
    key: "home",
    label: "Play for its team",
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
];

const clubCountryCsv = csvDataUri(clubCountries.rows, [
  { label: "club_country", value: (row) => row.country },
  { label: "players", value: (row) => row.players },
  { label: "clubs", value: (row) => row.clubs },
  { label: "play_for_its_team", value: (row) => row.playForIt },
  { label: "play_for_other_teams", value: (row) => row.playForOthers },
]);

const THREE_COUNTRY_LISTS: { key: "born" | "team" | "club"; title: string }[] = [
  { key: "born", title: "Most often born in" },
  { key: "team", title: "Most often playing for" },
  { key: "club", title: "Most often at a club in" },
];

const topWithoutTeam = clubCountries.rows.find((row) => row.playForIt === null);

export function OriginsRoute() {
  return (
    <AnalysisPage
      slug="origins"
      intro="Every squad together: the countries and cities the players were born in, and the countries where they play their club football."
    >
      <section id="born" className="content-panel reveal">
        <SectionHeader
          title="Where the players were born"
          note="How many players were born in the country they play for, and which countries the players were born in."
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
          rows={birthplaces.rows.slice(0, TOP_ROWS)}
          columns={birthColumns}
          getRowKey={(row) => row.country}
          initialSortKey="born"
          initialSortAsc={false}
          caption={`The ${TOP_ROWS} countries where the most players were born`}
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

      <section id="confederations" className="content-panel reveal">
        <SectionHeader
          title="Home-born players by confederation"
          note="The share of each confederation's players who were born in the country they play for."
          aside={sourceNote(
            "Born in the country they play for, grouped by the team's confederation.",
            "Active final-squad players.",
          )}
        />
        <SortableTable
          rows={birthplaces.byConfederation}
          getRowKey={(row) => row.confederation}
          initialSortKey="share"
          initialSortAsc={false}
          caption="Players born in the country they play for, by confederation"
          columns={[
            {
              key: "confederation",
              label: "Confederation",
              sortValue: (row) => row.confederation,
              render: (row) => row.confederation,
            },
            {
              key: "teams",
              label: "Teams",
              align: "right",
              initialAsc: false,
              sortValue: (row) => row.teams,
              render: (row) => row.teams,
            },
            {
              key: "players",
              label: "Players",
              align: "right",
              initialAsc: false,
              sortValue: (row) => row.players,
              render: (row) => row.players,
            },
            {
              key: "share",
              label: "Born in the country they play for",
              align: "right",
              initialAsc: false,
              sortValue: (row) => row.bornInRepresentedCountry / row.players,
              render: (row) =>
                `${formatPct(row.bornInRepresentedCountry / row.players)} (${row.bornInRepresentedCountry})`,
            },
          ]}
        />
      </section>

      <section id="hosts" className="content-panel reveal">
        <SectionHeader
          title="Players born in the host nations"
          note="Players born in the United States, Canada and Mexico, and the teams they play for."
          aside={sourceNote("Birth country as recorded for each player.", "Active final-squad players.")}
        />
        <SortableTable
          rows={hostRows}
          getRowKey={(row) => row.country}
          caption="Players born in the three host nations"
          className="wide-table"
          focusable
          columns={[
            { key: "country", label: "Born in", render: (row) => <CountryCell country={row.country} /> },
            { key: "born", label: "Players", align: "right", render: (row) => row.bornThere },
            { key: "home", label: "Play for it", align: "right", render: (row) => row.playForIt ?? "No team" },
            { key: "others", label: "Play for other teams", align: "right", render: (row) => row.playForOthers },
            {
              key: "otherTeams",
              label: "Other teams (players)",
              width: "40%",
              render: (row) => teamsWithCounts(row.otherTeams, Number.POSITIVE_INFINITY),
            },
          ]}
        />
      </section>

      <section id="cities" className="content-panel reveal">
        <SectionHeader
          title="Birth cities"
          note="The places where the most players were born. A city and its suburbs count separately, as recorded."
          aside={sourceNote(
            "Place of birth as recorded for each player, with its country.",
            "Active final-squad players.",
          )}
        />
        <SortableTable
          rows={birthplaces.birthCities.slice(0, CITY_ROWS)}
          getRowKey={(row) => `${row.city}|${row.country}`}
          initialSortKey="players"
          initialSortAsc={false}
          caption={`The ${CITY_ROWS} places where the most players were born`}
          className="wide-table"
          focusable
          columns={[
            { key: "city", label: "Birthplace", sortValue: (row) => row.city, render: (row) => row.city },
            {
              key: "country",
              label: "Country",
              sortValue: (row) => row.country,
              render: (row) => <CountryCell country={row.country} />,
            },
            {
              key: "players",
              label: "Players",
              align: "right",
              initialAsc: false,
              sortValue: (row) => row.players,
              render: (row) => row.players,
            },
            { key: "teams", label: "Play for", render: (row) => listInWords(row.teams) },
          ]}
        />
      </section>

      <section id="clubs" className="content-panel reveal">
        <SectionHeader
          title="Where they play their club football"
          note="The country of each player's club when the squads were named."
          actions={
            <a className="button-secondary" href={clubCountryCsv} download="world-cup-2026-club-countries.csv">
              Download CSV
            </a>
          }
          aside={sourceNote(
            "Club-at-call-up country, matched to the team's country or a documented alias.",
            "Active final-squad players with a club country.",
          )}
        />
        <div className="metrics-grid">
          <MetricCard
            label="Play in their own country"
            value={formatPct(clubCountries.playAtHome / clubCountries.clubCountryKnown)}
            note={`${clubCountries.playAtHome.toLocaleString()} of ${clubCountries.clubCountryKnown.toLocaleString()} players`}
          />
          <MetricCard
            label="Club countries"
            value={clubCountries.clubCountries}
            note={`${clubCountries.countriesWithoutTeam} with no team at the tournament`}
          />
          <MetricCard
            label="At clubs in countries with no team"
            value={clubCountries.playersInCountriesWithoutTeam}
            note={topWithoutTeam ? `${topWithoutTeam.players} of them in ${topWithoutTeam.country}` : undefined}
          />
        </div>
        <h3 className="subsection-heading">Countries whose clubs have the most players</h3>
        <SortableTable
          rows={clubCountries.rows.slice(0, TOP_ROWS)}
          columns={clubCountryColumns}
          getRowKey={(row) => row.country}
          initialSortKey="players"
          initialSortAsc={false}
          caption={`The ${TOP_ROWS} countries whose clubs have the most players`}
          className="wide-table"
          focusable
        />
        <Expandable summary={`All ${clubCountries.clubCountries} club countries`}>
          <SortableTable
            rows={clubCountries.rows}
            columns={clubCountryColumns}
            getRowKey={(row) => row.country}
            initialSortKey="players"
            initialSortAsc={false}
            caption="Every club country"
            className="wide-table"
            focusable
          />
        </Expandable>
      </section>

      <section id="three-countries" className="content-panel reveal">
        <SectionHeader
          title="Three countries"
          note="Players born in one country who play for a second and are at a club in a third."
          aside={sourceNote(
            "Birth country, team and club-at-call-up country all different.",
            "Active final-squad players with a birth country and a club country.",
          )}
        />
        <div className="metrics-grid">
          <MetricCard
            label="Born, play for and club in three countries"
            value={clubCountries.threeCountries}
            note={`of ${clubCountries.clubCountryKnown.toLocaleString()} players`}
          />
        </div>
        <div className="analysis-cols analysis-cols-3">
          {THREE_COUNTRY_LISTS.map((list) => (
            <div key={list.key}>
              <h3 className="subsection-heading">{list.title}</h3>
              <ol className="detail-list">
                {clubCountries.threeCountriesBy[list.key].slice(0, THREE_COUNTRY_ROWS).map((row) => (
                  <li key={row.country}>
                    <span className="team-cell">
                      <CountryFlag country={row.country} />
                      {row.country}, {row.players}
                    </span>
                  </li>
                ))}
              </ol>
            </div>
          ))}
        </div>
      </section>
    </AnalysisPage>
  );
}
