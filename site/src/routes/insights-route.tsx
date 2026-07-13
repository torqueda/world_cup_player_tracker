import { useMemo, useState } from "react";
import { BarList, type BarListItem } from "@/components/bar-list";
import { DonutGauge } from "@/components/donut-gauge";
import { Treemap, type TreemapItem } from "@/components/treemap";
import {
  activePlayers,
  coaches,
  confederations,
  getClubById,
  getClubForPlayer,
  getCoachForTeam,
  getConfederationForCountry,
  getSquadRosterForTeam,
  getTeamForPlayer,
  getTeamStat,
  matches,
  playerClubAtCallup,
  referees,
  teams,
  teamStats,
  TEAM_COUNTRY_ALIASES,
} from "@/lib/data";

function isOwnCountry(team: string, country: string | null): boolean {
  if (!country) {
    return false;
  }
  const aliases = TEAM_COUNTRY_ALIASES[team] ?? [team];
  return aliases.includes(country);
}

function rankWithTies<T>(rows: T[], value: (row: T) => number, count: number): T[] {
  const sorted = [...rows].sort((a, b) => value(b) - value(a));
  if (sorted.length <= count) {
    return sorted;
  }
  const cutoff = value(sorted[count - 1]);
  let end = count;
  while (end < sorted.length && value(sorted[end]) === cutoff) {
    end += 1;
  }
  return sorted.slice(0, end);
}

// --- Country-of-birth aggregates (active final squads only) ---

const playersWithBirthData = activePlayers.filter((player) => player.birth_country);
const playersMissingBirthData = activePlayers.length - playersWithBirthData.length;

const birthCountryCounts = new Map<string, number>();
const playersByBirthCountry = new Map<string, string[]>();
for (const player of playersWithBirthData) {
  const country = player.birth_country as string;
  birthCountryCounts.set(country, (birthCountryCounts.get(country) ?? 0) + 1);
  const label = player.place_of_birth
    ? `${player.display_name} (${player.place_of_birth})`
    : player.display_name;
  const bucket = playersByBirthCountry.get(country);
  if (bucket) {
    bucket.push(label);
  } else {
    playersByBirthCountry.set(country, [label]);
  }
}

function countryTooltip(country: string): string {
  const names = playersByBirthCountry.get(country) ?? [];
  return names.length <= 12 ? names.join(", ") : `${names.slice(0, 12).join(", ")} … +${names.length - 12} more`;
}

const birthCountryItems: BarListItem[] = Array.from(birthCountryCounts.entries())
  .map(([country, count]) => ({ key: country, label: country, value: count }))
  .sort((a, b) => b.value - a.value);

const mostBirthCountry = birthCountryItems[0];
const minBirthCount = Math.min(...birthCountryItems.map((item) => item.value));
const leastBirthCountries = birthCountryItems
  .filter((item) => item.value === minBirthCount)
  .sort((a, b) => a.label.localeCompare(b.label));

interface BirthCityGroup {
  city: string;
  country: string;
  playerNames: string[];
}

const birthCityGroups = new Map<string, BirthCityGroup>();
for (const player of playersWithBirthData) {
  if (!player.place_of_birth) {
    continue;
  }
  const key = `${player.place_of_birth}__${player.birth_country}`;
  const group = birthCityGroups.get(key);
  if (group) {
    group.playerNames.push(player.display_name);
  } else {
    birthCityGroups.set(key, {
      city: player.place_of_birth,
      country: player.birth_country as string,
      playerNames: [player.display_name],
    });
  }
}
const maxBirthCityCount = Math.max(...Array.from(birthCityGroups.values()).map((g) => g.playerNames.length));
const topBirthCities = Array.from(birthCityGroups.values()).filter(
  (group) => group.playerNames.length === maxBirthCityCount,
);

const playerContextByName = new Map<string, string>();
for (const player of activePlayers) {
  const team = getTeamForPlayer(player.player_id);
  const club = getClubForPlayer(player.player_id);
  playerContextByName.set(
    player.display_name,
    `${team?.team ?? "Unknown team"} · ${club?.club_name ?? "Unknown club"}`,
  );
}

// --- Home-grown vs diaspora, all 48 teams, sortable ---

interface TeamCountryStat {
  team: string;
  teamCode: string;
  bornIn: number;
  bornOut: number;
  squadSize: number;
}

const teamCountryStats: TeamCountryStat[] = teams.map((team) => {
  const roster = getSquadRosterForTeam(team.team_code);
  const bornIn = roster.filter((row) => row.player && isOwnCountry(team.team, row.player.birth_country)).length;
  return {
    team: team.team,
    teamCode: team.team_code,
    bornIn,
    bornOut: roster.length - bornIn,
    squadSize: roster.length,
  };
});

type HomegrownSort = "alphabetical" | "most-homegrown" | "most-diaspora" | "confederation";

const HOMEGROWN_SORTS: Record<HomegrownSort, (a: TeamCountryStat, b: TeamCountryStat) => number> = {
  alphabetical: (a, b) => a.team.localeCompare(b.team),
  "most-homegrown": (a, b) => b.bornIn - a.bornIn || a.team.localeCompare(b.team),
  "most-diaspora": (a, b) => b.bornOut - a.bornOut || a.team.localeCompare(b.team),
  confederation: (a, b) =>
    (getConfederationForCountry(a.team) ?? "").localeCompare(getConfederationForCountry(b.team) ?? "") ||
    a.team.localeCompare(b.team),
};

// Countries whose players appear in the dataset but aren't one of the 48
// competing nations (accounting for the alias differences above).
const competingCountryNames = new Set<string>();
for (const team of teams) {
  competingCountryNames.add(team.team);
  for (const alias of TEAM_COUNTRY_ALIASES[team.team] ?? []) {
    competingCountryNames.add(alias);
  }
}
const diasporaCountries = birthCountryItems
  .filter((item) => !competingCountryNames.has(item.label))
  .sort((a, b) => a.label.localeCompare(b.label));

// --- Squad age (as of the 2026-06-11 kickoff) ---

const TOURNAMENT_START = new Date("2026-06-11T00:00:00Z");

function ageInYears(dateOfBirth: string | null): number | null {
  if (!dateOfBirth) {
    return null;
  }
  const dob = new Date(dateOfBirth);
  if (Number.isNaN(dob.getTime())) {
    return null;
  }
  return (TOURNAMENT_START.getTime() - dob.getTime()) / (1000 * 60 * 60 * 24 * 365.25);
}

function averageAgeForRoster(roster: ReturnType<typeof getSquadRosterForTeam>): number | null {
  const ages = roster
    .map((row) => (row.player ? ageInYears(row.player.date_of_birth) : null))
    .filter((age): age is number => age !== null);
  if (ages.length === 0) {
    return null;
  }
  return ages.reduce((sum, age) => sum + age, 0) / ages.length;
}

interface TeamAgeStat {
  team: string;
  averageAge: number;
}

const teamAgeStats: TeamAgeStat[] = teams
  .map((team) => {
    const averageAge = averageAgeForRoster(getSquadRosterForTeam(team.team_code));
    return averageAge === null ? null : { team: team.team, averageAge };
  })
  .filter((stat): stat is TeamAgeStat => stat !== null)
  .sort((a, b) => b.averageAge - a.averageAge);

const youngestSquad = teamAgeStats[teamAgeStats.length - 1];
const oldestSquad = teamAgeStats[0];
const overallAverageAge =
  teamAgeStats.reduce((sum, stat) => sum + stat.averageAge, 0) / (teamAgeStats.length || 1);

// --- Club-at-call-up aggregates (active squads only) ---

const activePlayerIdSet = new Set(activePlayers.map((player) => player.player_id));
const activeCallups = playerClubAtCallup.filter((link) => activePlayerIdSet.has(link.player_id));

const clubCallupCounts = new Map<string, number>();
for (const link of activeCallups) {
  clubCallupCounts.set(link.club_id, (clubCallupCounts.get(link.club_id) ?? 0) + 1);
}

const clubItems: BarListItem[] = Array.from(clubCallupCounts.entries())
  .map(([clubId, count]) => ({ key: clubId, label: getClubById(clubId)?.club_name ?? clubId, value: count }))
  .sort((a, b) => b.value - a.value);

const leagueCallupCounts = new Map<string, number>();
for (const link of activeCallups) {
  const league = getClubById(link.club_id)?.league ?? "League pending review";
  leagueCallupCounts.set(league, (leagueCallupCounts.get(league) ?? 0) + 1);
}

const leagueItems: BarListItem[] = Array.from(leagueCallupCounts.entries())
  .map(([league, count]) => ({ key: league, label: league, value: count }))
  .sort((a, b) => b.value - a.value);

// Podium (top clubs, ties included) + long-tail frequency: how many clubs
// sent exactly N players. The tail IS the story — most clubs sent one player.
const clubPodium = rankWithTies(clubItems, (item) => item.value, 5);
const clubTailFrequency = (() => {
  const freq = new Map<number, number>();
  for (const item of clubItems) {
    freq.set(item.value, (freq.get(item.value) ?? 0) + 1);
  }
  return Array.from(freq.entries()).sort((a, b) => b[0] - a[0]);
})();

// League treemap: biggest leagues as tiles, the rest folded into one block.
const LEAGUE_TILE_COUNT = 14;
const leagueTreemapItems: TreemapItem[] = (() => {
  const top = leagueItems.slice(0, LEAGUE_TILE_COUNT).map((item) => ({
    key: item.key,
    label: item.label,
    value: item.value,
    title: `${item.label}: ${item.value} players`,
  }));
  const rest = leagueItems.slice(LEAGUE_TILE_COUNT);
  if (rest.length > 0) {
    const restTotal = rest.reduce((sum, item) => sum + item.value, 0);
    top.push({
      key: "__others__",
      label: `${rest.length} other leagues`,
      value: restTotal,
      title: `${rest.length} other leagues: ${restTotal} players combined`,
    });
  }
  return top;
})();

// --- Confederation aggregates ---

const STAGE_RANKS: [string, number][] = [
  ["Group stage", 0],
  ["Round of 32", 1],
  ["Round of 16", 2],
  ["Quarter-finals", 3],
  ["Semi-finals (in progress)", 4],
];
const stageRankByName = new Map(STAGE_RANKS);
const STAGE_COLUMNS = ["Round of 32", "Round of 16", "Quarter-finals", "Semi-finals (in progress)"];
const STAGE_COLUMN_LABELS: Record<string, string> = {
  "Round of 32": "R32",
  "Round of 16": "R16",
  "Quarter-finals": "QF",
  "Semi-finals (in progress)": "SF",
};

interface ConfedFunnelRow {
  code: string;
  starters: number;
  survivors: Record<string, number>; // stage column -> teams that reached it
  teams: { team: string; stage: string }[];
}

const confedFunnel: ConfedFunnelRow[] = (() => {
  const byCode = new Map<string, ConfedFunnelRow>();
  for (const stat of teamStats) {
    const code = getConfederationForCountry(stat.team) ?? "?";
    let row = byCode.get(code);
    if (!row) {
      row = { code, starters: 0, survivors: Object.fromEntries(STAGE_COLUMNS.map((s) => [s, 0])), teams: [] };
      byCode.set(code, row);
    }
    row.starters += 1;
    row.teams.push({ team: stat.team, stage: stat.stage_reached });
    const rank = stageRankByName.get(stat.stage_reached) ?? 0;
    for (const column of STAGE_COLUMNS) {
      if (rank >= (stageRankByName.get(column) ?? 99)) {
        row.survivors[column] += 1;
      }
    }
  }
  return Array.from(byCode.values()).sort((a, b) => b.starters - a.starters || a.code.localeCompare(b.code));
})();

// Inter-confederation head-to-head: wins in decided matches (including
// penalty shootouts) where the two teams belong to different confederations.
const interConfedRecords = (() => {
  const wins = new Map<string, Map<string, number>>();
  for (const match of matches) {
    if (match.status !== "played" || match.home_score === null || match.away_score === null) {
      continue;
    }
    const homeConf = getConfederationForCountry(match.home_team);
    const awayConf = getConfederationForCountry(match.away_team);
    if (!homeConf || !awayConf || homeConf === awayConf) {
      continue;
    }
    let winner: string | null = null;
    let loser: string | null = null;
    if (match.home_score !== match.away_score) {
      [winner, loser] = match.home_score > match.away_score ? [homeConf, awayConf] : [awayConf, homeConf];
    } else if (match.home_pens !== null && match.away_pens !== null && match.home_pens !== match.away_pens) {
      [winner, loser] = match.home_pens > match.away_pens ? [homeConf, awayConf] : [awayConf, homeConf];
    }
    if (winner && loser) {
      const row = wins.get(winner) ?? new Map<string, number>();
      row.set(loser, (row.get(loser) ?? 0) + 1);
      wins.set(winner, row);
    }
  }
  return wins;
})();

const confedCodes = confedFunnel.map((row) => row.code);

function interConfedTotal(code: string, direction: "won" | "lost"): number {
  let total = 0;
  for (const [winner, row] of interConfedRecords) {
    for (const [loser, count] of row) {
      if (direction === "won" && winner === code) total += count;
      if (direction === "lost" && loser === code) total += count;
    }
  }
  return total;
}

// --- Coach & referee aggregates ---

const coachCountryCounts = new Map<string, number>();
const foreignCoached: { team: string; coach: string; nationality: string }[] = [];
for (const coach of coaches) {
  const nationality = coach.coach_nationality ?? coach.team;
  coachCountryCounts.set(nationality, (coachCountryCounts.get(nationality) ?? 0) + 1);
  const aliases = new Set([coach.team, ...(TEAM_COUNTRY_ALIASES[coach.team] ?? [])]);
  if (!aliases.has(nationality)) {
    foreignCoached.push({ team: coach.team, coach: coach.coach_name, nationality });
  }
}
const topCoachCountries = rankWithTies(
  Array.from(coachCountryCounts.entries()).map(([label, value]) => ({ key: label, label, value })),
  (item) => item.value,
  5,
);

const refereeOnly = referees.filter((official) => official.role === "referee");
const refCountryCounts = new Map<string, number>();
for (const official of refereeOnly) {
  refCountryCounts.set(official.country, (refCountryCounts.get(official.country) ?? 0) + 1);
}
const topRefCountries = rankWithTies(
  Array.from(refCountryCounts.entries()).map(([label, value]) => ({ key: label, label, value })),
  (item) => item.value,
  5,
);

// Countries represented by officials or coaches but with no team at the Cup.
const officialOrCoachCountries = new Set<string>([
  ...referees.map((official) => official.country),
  ...coaches.map((coach) => coach.coach_nationality ?? coach.team),
]);
const nonCompetingContributors = Array.from(officialOrCoachCountries)
  .filter((country) => {
    if (competingCountryNames.has(country)) {
      return false;
    }
    // also treat alias spellings as competing (e.g. "Turkey" for Türkiye)
    return !teams.some((team) => (TEAM_COUNTRY_ALIASES[team.team] ?? []).includes(country));
  })
  .sort((a, b) => a.localeCompare(b))
  .map((country) => {
    const refCount = referees.filter((official) => official.country === country).length;
    const coachCount = coaches.filter((coach) => (coach.coach_nationality ?? coach.team) === country).length;
    const parts = [];
    if (refCount) parts.push(`${refCount} official${refCount === 1 ? "" : "s"}`);
    if (coachCount) parts.push(`${coachCount} coach${coachCount === 1 ? "" : "es"}`);
    return { country, detail: parts.join(", ") };
  });

export function InsightsRoute() {
  const [teamQuery, setTeamQuery] = useState("");
  const [selectedTeamCode, setSelectedTeamCode] = useState(teams[0]?.team_code ?? null);
  const [homegrownSort, setHomegrownSort] = useState<HomegrownSort>("most-homegrown");

  const filteredTeams = useMemo(() => {
    const query = teamQuery.trim().toLowerCase();
    if (!query) {
      return teams;
    }
    return teams.filter(
      (team) => team.team.toLowerCase().includes(query) || team.team_code.toLowerCase().includes(query),
    );
  }, [teamQuery]);

  const selectedTeam = teams.find((team) => team.team_code === selectedTeamCode) ?? null;
  const selectedCoach = selectedTeam ? getCoachForTeam(selectedTeam.team_code) : null;
  const selectedTeamStat = selectedTeam ? getTeamStat(selectedTeam.team_code) : null;

  const roster = useMemo(() => {
    if (!selectedTeam) {
      return [];
    }
    return [...getSquadRosterForTeam(selectedTeam.team_code)].sort((a, b) => {
      const nameA = a.player?.display_name ?? a.entry.display_name_at_source;
      const nameB = b.player?.display_name ?? b.entry.display_name_at_source;
      return nameA.localeCompare(nameB);
    });
  }, [selectedTeam]);

  const clubCountryBreakdown = useMemo(() => {
    if (!selectedTeam) {
      return [];
    }
    const counts = new Map<string, number>();
    for (const row of roster) {
      const country = row.club?.country ?? "Unknown club location";
      counts.set(country, (counts.get(country) ?? 0) + 1);
    }
    return Array.from(counts.entries())
      .map(([country, count]) => ({
        key: country,
        label: country,
        value: count,
        emphasized: isOwnCountry(selectedTeam.team, country),
      }))
      .sort((a, b) => b.value - a.value);
  }, [roster, selectedTeam]);

  const selectedTeamAverageAge = useMemo(() => averageAgeForRoster(roster), [roster]);

  const sortedHomegrown = useMemo(
    () => [...teamCountryStats].sort(HOMEGROWN_SORTS[homegrownSort]),
    [homegrownSort],
  );

  const [selectedConfed, setSelectedConfed] = useState(confedFunnel[0]?.code ?? "UEFA");
  const selectedConfedRow = confedFunnel.find((row) => row.code === selectedConfed) ?? null;
  const selectedConfedInfo = confederations.find((confed) => confed.code === selectedConfed) ?? null;

  return (
    <div className="page-stack">
      <section className="content-panel centered-panel reveal">
        <div className="panel-heading">
          <p className="eyebrow">Insights</p>
          <h2>Cross-squad insights</h2>
        </div>
        <p className="panel-intro">
          Cross-squad facts drawn from where World Cup 2026 players were born and which
          clubs they play for. Pick a team in the explorer on the left to see its full
          roster alongside these same angles.
        </p>
      </section>

      <div className="insights-grid reveal">
        <aside className="insights-sidebar">
          <section className="content-panel">
            <div className="panel-heading">
              <p className="eyebrow">Team explorer</p>
              <h3>Roster, birth country &amp; club</h3>
            </div>
            <input
              type="text"
              className="team-search"
              value={teamQuery}
              onChange={(event) => setTeamQuery(event.target.value)}
              placeholder="Search teams…"
            />
            <div className="team-list team-list-compact">
              {filteredTeams.length === 0 ? (
                <p className="city-detail-empty">No teams match your search.</p>
              ) : (
                filteredTeams.map((team) => (
                  <button
                    key={team.team_code}
                    type="button"
                    className={
                      team.team_code === selectedTeamCode ? "team-button team-button-active" : "team-button"
                    }
                    onClick={() => setSelectedTeamCode(team.team_code)}
                  >
                    <span>{team.team}</span>
                    <span className="team-button-code">{team.team_code}</span>
                  </button>
                ))
              )}
            </div>

            {selectedTeam ? (
              <>
                <h4 className="subsection-heading">{selectedTeam.team}</h4>
                <p className="insight-note">
                  {selectedCoach ? <>Coach: <strong>{selectedCoach.coach_name}</strong> · </> : null}
                  {selectedTeamStat ? <>{selectedTeamStat.stage_reached} · </> : null}
                  {selectedTeamAverageAge !== null
                    ? `average age ${selectedTeamAverageAge.toFixed(1)} yrs`
                    : null}
                </p>
                <div className="data-table-wrap sidebar-table">
                  <table className="data-table">
                    <thead>
                      <tr>
                        <th>Player</th>
                        <th>Born</th>
                        <th>Club</th>
                      </tr>
                    </thead>
                    <tbody>
                      {roster.map(({ entry, player, club }) => (
                        <tr key={entry.squad_entry_id}>
                          <td>{player?.display_name ?? entry.display_name_at_source}</td>
                          <td>{player?.birth_country ?? "Pending"}</td>
                          <td>{club?.club_name ?? "Unknown"}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>

                <h4 className="subsection-heading">Where this squad plays club football</h4>
                <p className="insight-note">
                  {selectedTeam.team} in the accent color, every other club country in gray.
                </p>
                <BarList items={clubCountryBreakdown} mode="emphasis" />
              </>
            ) : (
              <p className="city-detail-empty">Choose a team to see its roster.</p>
            )}
          </section>
        </aside>

        <div className="insights-main">
          <section className="content-panel">
            <h3 className="section-heading">Country of birth</h3>

            <div className="metrics-grid">
              <article className="metric-card">
                <p className="metric-label">Most players born in one country</p>
                <p className="metric-value">{mostBirthCountry.value}</p>
                <p className="metric-note">{mostBirthCountry.label}</p>
              </article>
              <article className="metric-card">
                <p className="metric-label">Birth countries represented</p>
                <p className="metric-value">{birthCountryItems.length}</p>
                <p className="metric-note">
                  across {playersWithBirthData.length.toLocaleString()} players
                </p>
              </article>
              <article className="metric-card">
                <p className="metric-label">Most players born in one city</p>
                <p className="metric-value">{maxBirthCityCount}</p>
                <p className="metric-note">{topBirthCities.map((c) => c.city).join(", ")}</p>
              </article>
            </div>
            {playersMissingBirthData > 0 ? (
              <p className="insight-note note-spaced">
                {playersMissingBirthData} late squad addition
                {playersMissingBirthData === 1 ? "" : "s"} still awaiting birthplace data are
                excluded from these breakdowns.
              </p>
            ) : null}

            <h4 className="subsection-heading">All countries represented, by player birthplace</h4>
            <p className="insight-note">Hover a bar to see who was born there, and where.</p>
            <BarList
              items={birthCountryItems.map((item) => ({
                ...item,
                title: `${item.label} (${item.value}): ${countryTooltip(item.label)}`,
              }))}
              scrollable
            />

            <h4 className="subsection-heading">Least-represented birth countries</h4>
            <p className="insight-note">
              {minBirthCount} player{minBirthCount === 1 ? "" : "s"} each, tied across{" "}
              {leastBirthCountries.length} countries. Hover a country to see the player and
              their birth city.
            </p>
            <div className="chip-list">
              {leastBirthCountries.map((item, index) => (
                <span
                  key={item.key}
                  className={index % 2 === 0 ? "player-chip" : "player-chip player-chip-alt"}
                  title={countryTooltip(item.label)}
                >
                  {item.label}
                </span>
              ))}
            </div>

            <h4 className="subsection-heading">Player diaspora</h4>
            <p className="insight-note">
              {diasporaCountries.length} countries not competing in the 2026 World Cup still
              produced at least one World Cup 2026 player:
            </p>
            <div className="chip-list">
              {diasporaCountries.map((item, index) => (
                <span
                  key={item.key}
                  className={index % 2 === 0 ? "player-chip" : "player-chip player-chip-alt"}
                  title={countryTooltip(item.label)}
                >
                  {item.label} ({item.value})
                </span>
              ))}
            </div>

            <h4 className="subsection-heading">City spotlight</h4>
            {topBirthCities.map((group) => (
              <div key={`${group.city}-${group.country}`}>
                <p className="insight-note">
                  <strong>
                    {group.city}, {group.country}
                  </strong>{" "}
                  is the birthplace of {group.playerNames.length} World Cup 2026 players.
                  Hover a name for their team and club:
                </p>
                <div className="chip-list">
                  {group.playerNames.map((name, index) => (
                    <span
                      key={name}
                      className={index % 2 === 0 ? "player-chip" : "player-chip player-chip-alt"}
                      title={playerContextByName.get(name) ?? name}
                    >
                      {name}
                    </span>
                  ))}
                </div>
              </div>
            ))}

            <h4 className="subsection-heading">Home-grown vs diaspora, all 48 squads</h4>
            <p className="insight-note">
              Each donut fills with the share of the squad born in the country it represents;
              the rest were born abroad. Hover for the split.
            </p>
            <label className="filter-field donut-sort-field">
              <span>Sort squads</span>
              <select
                value={homegrownSort}
                onChange={(event) => setHomegrownSort(event.target.value as HomegrownSort)}
              >
                <option value="most-homegrown">Most home-grown players</option>
                <option value="most-diaspora">Most diaspora players</option>
                <option value="alphabetical">Alphabetical</option>
                <option value="confederation">By confederation</option>
              </select>
            </label>
            <div className="donut-grid">
              {sortedHomegrown.map((stat, index) => (
                <DonutGauge
                  key={stat.teamCode}
                  label={stat.team}
                  value={stat.bornIn}
                  total={stat.squadSize}
                  tone={index % 2 === 0 ? "a" : "b"}
                  sublabel={`${stat.bornIn} home · ${stat.bornOut} abroad`}
                  title={`${stat.team}: ${stat.bornIn} born in-country, ${stat.bornOut} born abroad (squad of ${stat.squadSize})`}
                />
              ))}
            </div>
          </section>
        </div>
      </div>

      <div className="content-grid insights-columns reveal">
            <section className="content-panel">
              <h3 className="section-heading">Average squad age</h3>
              <p className="insight-note">Measured as of the 2026-06-11 tournament kickoff.</p>
              <div className="metrics-grid">
                <article className="metric-card">
                  <p className="metric-label">Youngest squad</p>
                  <p className="metric-value">{youngestSquad.averageAge.toFixed(1)}</p>
                  <p className="metric-note">{youngestSquad.team}</p>
                </article>
                <article className="metric-card">
                  <p className="metric-label">Oldest squad</p>
                  <p className="metric-value">{oldestSquad.averageAge.toFixed(1)}</p>
                  <p className="metric-note">{oldestSquad.team}</p>
                </article>
                <article className="metric-card">
                  <p className="metric-label">All-squad average</p>
                  <p className="metric-value">{overallAverageAge.toFixed(1)}</p>
                  <p className="metric-note">years old</p>
                </article>
              </div>
              <h4 className="subsection-heading">Every squad, oldest to youngest</h4>
              <div className="age-pair-list">
                {teamAgeStats.map((stat) => (
                  <div key={stat.team} className="age-pair">
                    <span>{stat.team}</span>
                    <span className="age-pair-value">{stat.averageAge.toFixed(1)}</span>
                  </div>
                ))}
              </div>
            </section>

            <section className="content-panel">
              <h3 className="section-heading">Club at call-up</h3>
              <div className="metrics-grid">
                <article className="metric-card">
                  <p className="metric-label">Clubs represented</p>
                  <p className="metric-value">{clubItems.length}</p>
                  <p className="metric-note">
                    supplying all {activePlayers.length.toLocaleString()} players
                  </p>
                </article>
                <article className="metric-card">
                  <p className="metric-label">Top club by players sent</p>
                  <p className="metric-value">{clubItems[0].value}</p>
                  <p className="metric-note">{clubItems[0].label}</p>
                </article>
              </div>

              <h4 className="subsection-heading">The podium — top clubs by players sent</h4>
              <div className="podium-list">
                {clubPodium.map((item, index) => (
                  <article key={item.key} className="podium-card">
                    <span className="podium-rank">
                      {index === 0 ? "🥇" : index === 1 ? "🥈" : index === 2 ? "🥉" : `#${index + 1}`}
                    </span>
                    <span className="podium-club">{item.label}</span>
                    <span className="podium-count">{item.value} players</span>
                  </article>
                ))}
              </div>

              <h4 className="subsection-heading">…and the long tail</h4>
              <p className="insight-note">
                The real story: of {clubItems.length} clubs, most sent exactly one player.
              </p>
              <div className="tail-list">
                {clubTailFrequency.map(([playersSent, clubCount]) => (
                  <div key={playersSent} className="tail-row">
                    <span className="tail-count">{clubCount}</span>
                    <span>
                      club{clubCount === 1 ? "" : "s"} sent {playersSent} player
                      {playersSent === 1 ? "" : "s"}
                    </span>
                  </div>
                ))}
              </div>

              <h4 className="subsection-heading">Leagues, sized by players sent</h4>
              <p className="insight-note">
                {leagueItems.length} leagues in total; tiles show the biggest{" "}
                {LEAGUE_TILE_COUNT}, everything else folds into one block. Hover for exact counts.
              </p>
              <Treemap items={leagueTreemapItems} valueSuffix=" players" />
            </section>
      </div>

      <div className="content-grid insights-columns reveal">
        <section className="content-panel">
          <h3 className="section-heading">Confederations</h3>
          <p className="insight-note">
            How each confederation's teams progressed — starters, then how many were still
            alive at each knockout stage.
          </p>
          <div className="data-table-wrap">
            <table className="data-table">
              <thead>
                <tr>
                  <th>Confederation</th>
                  <th>Started</th>
                  {STAGE_COLUMNS.map((column) => (
                    <th key={column}>{STAGE_COLUMN_LABELS[column]}</th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {confedFunnel.map((row) => (
                  <tr key={row.code}>
                    <td>{row.code}</td>
                    <td>{row.starters}</td>
                    {STAGE_COLUMNS.map((column) => (
                      <td key={column}>{row.survivors[column]}</td>
                    ))}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>

          <h4 className="subsection-heading">Cross-confederation wins</h4>
          <p className="insight-note">
            Decided matches (including penalty shootouts) between teams from different
            confederations. Rows win, columns lose.
          </p>
          <div className="data-table-wrap">
            <table className="data-table confed-matrix">
              <thead>
                <tr>
                  <th>W \ L</th>
                  {confedCodes.map((code) => (
                    <th key={code}>{code}</th>
                  ))}
                  <th>Total W–L</th>
                </tr>
              </thead>
              <tbody>
                {confedCodes.map((winner) => (
                  <tr key={winner}>
                    <td>
                      <strong>{winner}</strong>
                    </td>
                    {confedCodes.map((loser) => (
                      <td key={loser}>
                        {winner === loser ? "—" : interConfedRecords.get(winner)?.get(loser) ?? 0}
                      </td>
                    ))}
                    <td>
                      {interConfedTotal(winner, "won")}–{interConfedTotal(winner, "lost")}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>

          <h4 className="subsection-heading">Explore a confederation</h4>
          <label className="filter-field donut-sort-field">
            <span>Confederation</span>
            <select value={selectedConfed} onChange={(event) => setSelectedConfed(event.target.value)}>
              {confedFunnel.map((row) => (
                <option key={row.code} value={row.code}>
                  {row.code} ({row.starters} teams)
                </option>
              ))}
            </select>
          </label>
          {selectedConfedRow ? (
            <>
              <p className="insight-note">
                {selectedConfedInfo?.name ?? selectedConfed}: {selectedConfedRow.starters} of{" "}
                {selectedConfedInfo?.members.length ?? "?"} member nations qualified for the Cup.
              </p>
              <div className="chip-list">
                {[...selectedConfedRow.teams]
                  .sort(
                    (a, b) =>
                      (stageRankByName.get(b.stage) ?? 0) - (stageRankByName.get(a.stage) ?? 0) ||
                      a.team.localeCompare(b.team),
                  )
                  .map((entry, index) => (
                    <span
                      key={entry.team}
                      className={index % 2 === 0 ? "player-chip" : "player-chip player-chip-alt"}
                      title={`${entry.team} — ${entry.stage}`}
                    >
                      {entry.team} · {STAGE_COLUMN_LABELS[entry.stage] ?? "Groups"}
                    </span>
                  ))}
              </div>
            </>
          ) : null}
        </section>

        <section className="content-panel">
          <h3 className="section-heading">Coaches &amp; referees</h3>

          <div className="metrics-grid">
            <article className="metric-card">
              <p className="metric-label">Foreign-coached teams</p>
              <p className="metric-value">{foreignCoached.length}</p>
              <p className="metric-note">of {coaches.length} squads have a coach from another nation</p>
            </article>
            <article className="metric-card">
              <p className="metric-label">Referee nations</p>
              <p className="metric-value">{refCountryCounts.size}</p>
              <p className="metric-note">countries supplied the {refereeOnly.length} on-field referees</p>
            </article>
          </div>

          <h4 className="subsection-heading">Countries supplying the most coaches</h4>
          <BarList items={topCoachCountries} />

          <h4 className="subsection-heading">Countries supplying the most referees</h4>
          <p className="insight-note">
            On-field referees only; each country also sends assistants and VARs.
          </p>
          <BarList items={topRefCountries} />

          <h4 className="subsection-heading">Teams coached by a foreign coach</h4>
          <div className="chip-list">
            {foreignCoached
              .sort((a, b) => a.team.localeCompare(b.team))
              .map((entry, index) => (
                <span
                  key={entry.team}
                  className={index % 2 === 0 ? "player-chip" : "player-chip player-chip-alt"}
                  title={`${entry.coach} (${entry.nationality}) coaches ${entry.team}`}
                >
                  {entry.team} · {entry.nationality}
                </span>
              ))}
          </div>

          <h4 className="subsection-heading">At the Cup without a team</h4>
          <p className="insight-note">
            {nonCompetingContributors.length} countries have no squad in the tournament but are
            represented by match officials or coaches. Hover for the breakdown.
          </p>
          <div className="chip-list">
            {nonCompetingContributors.map((entry, index) => (
              <span
                key={entry.country}
                className={index % 2 === 0 ? "player-chip" : "player-chip player-chip-alt"}
                title={`${entry.country}: ${entry.detail}`}
              >
                {entry.country}
              </span>
            ))}
          </div>
        </section>
      </div>
    </div>
  );
}
