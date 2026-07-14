import clubsJson from "@data/clubs.json";
import citiesJson from "@data/cities.json";
import playersJson from "@data/players.json";
import teamsJson from "@data/teams.json";
import squadEntriesJson from "@data/squad_entries.json";
import playerClubAtCallupJson from "@data/player_club_at_callup.json";
import matchesJson from "@data/matches.json";
import playerStatsJson from "@data/player_stats.json";
import teamStatsJson from "@data/team_stats.json";
import coachesJson from "@data/coaches.json";
import refereesJson from "@data/referees.json";
import confederationsJson from "@data/confederations.json";
import clubAliasesJson from "@data/club_aliases.json";

import type {
  Club,
  ClubAlias,
  City,
  Player,
  Team,
  SquadEntry,
  PlayerClubAtCallup,
  Match,
  PlayerStat,
  TeamStat,
  Coach,
  Referee,
  Confederation,
} from "./types";

export type {
  Club,
  ClubAlias,
  City,
  Player,
  Team,
  SquadEntry,
  PlayerClubAtCallup,
  Match,
  PlayerStat,
  TeamStat,
  Coach,
  Referee,
  Confederation,
} from "./types";

// Cast the generated JSON exports to the hand-maintained types above instead of
// relying on TypeScript's literal inference, so a refreshed dataset with the
// same shape drops in without the app needing to change.
export const clubs = clubsJson as Club[];
export const cities = citiesJson as City[];
export const players = playersJson as Player[];
export const teams = teamsJson as Team[];
export const squadEntries = squadEntriesJson as SquadEntry[];
export const playerClubAtCallup = playerClubAtCallupJson as PlayerClubAtCallup[];
export const matches = matchesJson as Match[];
export const playerStats = playerStatsJson as PlayerStat[];
export const teamStats = teamStatsJson as TeamStat[];
export const coaches = coachesJson as Coach[];
export const referees = refereesJson as Referee[];
export const confederations = confederationsJson as Confederation[];
export const clubAliases = clubAliasesJson as ClubAlias[];

// Team names whose dataset spelling differs from the country spelling used in
// birth_country values and the confederation member lists.
export const TEAM_COUNTRY_ALIASES: Record<string, string[]> = {
  "Bosnia-Herzegovina": ["Bosnia and Herzegovina"],
  "Congo DR": ["Democratic Republic of the Congo", "DR Congo"],
  Curacao: ["Curaçao"],
  Czechia: ["Czech Republic"],
  Türkiye: ["Turkey"],
};

const confedCodeByMember = new Map<string, string>();
for (const confederation of confederations) {
  for (const member of confederation.members) {
    confedCodeByMember.set(member, confederation.code);
  }
}

/** Confederation code (AFC/CAF/…) for a team or country name, alias-aware. */
export function getConfederationForCountry(name: string): string | undefined {
  if (confedCodeByMember.has(name)) {
    return confedCodeByMember.get(name);
  }
  for (const alias of TEAM_COUNTRY_ALIASES[name] ?? []) {
    if (confedCodeByMember.has(alias)) {
      return confedCodeByMember.get(alias);
    }
  }
  return undefined;
}

// Since the final-roster import, squad_entries also contains rows with
// squad_status="removed" (players cut from the announced squads). Rosters and
// aggregates work from the active entries; the full list stays exported for
// history views.
export const activeSquadEntries = squadEntries.filter((entry) => entry.squad_status === "active");
const activePlayerIds = new Set(activeSquadEntries.map((entry) => entry.player_id));

/** Players on a current (active) final squad. */
export const activePlayers = (playersJson as Player[]).filter((player) =>
  activePlayerIds.has(player.player_id),
);

function indexBy<T, K>(rows: T[], key: (row: T) => K): Map<K, T> {
  return new Map(rows.map((row) => [key(row), row]));
}

function groupBy<T, K>(rows: T[], key: (row: T) => K): Map<K, T[]> {
  const map = new Map<K, T[]>();
  for (const row of rows) {
    const bucketKey = key(row);
    const bucket = map.get(bucketKey);
    if (bucket) {
      bucket.push(row);
    } else {
      map.set(bucketKey, [row]);
    }
  }
  return map;
}

const clubsById = indexBy(clubs, (club) => club.club_id);
const citiesByKey = indexBy(cities, (city) => city.city_key);
const playersById = indexBy(players, (player) => player.player_id);
const teamsByCode = indexBy(teams, (team) => team.team_code);
const squadEntryByPlayerId = indexBy(squadEntries, (entry) => entry.player_id);
const clubAtCallupByPlayerId = indexBy(playerClubAtCallup, (link) => link.player_id);
const playerLinksByClubId = groupBy(playerClubAtCallup, (link) => link.club_id);
const squadEntriesByTeamCode = groupBy(activeSquadEntries, (entry) => entry.team_code);
const statsByPlayerId = indexBy(playerStats, (stat) => stat.player_id);
const coachByTeamCode = indexBy(coaches, (coach) => coach.team_code);
const teamStatByCode = indexBy(teamStats, (stat) => stat.team_code);

export function getClubById(clubId: string): Club | undefined {
  return clubsById.get(clubId);
}

export function getPlayerById(playerId: string): Player | undefined {
  return playersById.get(playerId);
}

export function getTeamByCode(teamCode: string): Team | undefined {
  return teamsByCode.get(teamCode);
}

export function getSquadEntryForPlayer(playerId: string): SquadEntry | undefined {
  return squadEntryByPlayerId.get(playerId);
}

export function getTeamForPlayer(playerId: string): Team | undefined {
  const entry = squadEntryByPlayerId.get(playerId);
  return entry ? getTeamByCode(entry.team_code) : undefined;
}

export function getClubForPlayer(playerId: string): Club | undefined {
  const link = clubAtCallupByPlayerId.get(playerId);
  return link ? getClubById(link.club_id) : undefined;
}

export function getSquadForTeam(teamCode: string): SquadEntry[] {
  return squadEntriesByTeamCode.get(teamCode) ?? [];
}

export function getPlayersForClub(clubId: string): Player[] {
  const links = playerLinksByClubId.get(clubId) ?? [];
  return links
    .filter((link) => activePlayerIds.has(link.player_id))
    .map((link) => getPlayerById(link.player_id))
    .filter((player): player is Player => Boolean(player));
}

export function getPlayerStat(playerId: string): PlayerStat | undefined {
  return statsByPlayerId.get(playerId);
}

export function getCoachForTeam(teamCode: string): Coach | undefined {
  return coachByTeamCode.get(teamCode);
}

export function getTeamStat(teamCode: string): TeamStat | undefined {
  return teamStatByCode.get(teamCode);
}

export function getClubsForCity(cityKey: string): Club[] {
  const city = citiesByKey.get(cityKey);
  if (!city) {
    return [];
  }
  return city.club_ids
    .map((clubId) => getClubById(clubId))
    .filter((club): club is Club => Boolean(club));
}

export function getTeamsForClub(clubId: string): string[] {
  const teamNames = new Set((playerLinksByClubId.get(clubId) ?? []).map((link) => link.team));
  return Array.from(teamNames).sort((a, b) => a.localeCompare(b));
}

export function getLeagues(): string[] {
  // Clubs added with late roster replacements can have league/country pending
  // manual review (null); they are omitted from filter options until filled.
  return Array.from(
    new Set(clubs.map((club) => club.league).filter((league): league is string => Boolean(league))),
  ).sort((a, b) => a.localeCompare(b));
}

export function getClubCountries(): string[] {
  return Array.from(
    new Set(clubs.map((club) => club.country).filter((country): country is string => Boolean(country))),
  ).sort((a, b) => a.localeCompare(b));
}

export function getTeamNames(): string[] {
  return teams.map((team) => team.team).sort((a, b) => a.localeCompare(b));
}

export interface PlayerRosterRow {
  player: Player;
  team: Team | undefined;
  club: Club | undefined;
}

export function getPlayerRoster(): PlayerRosterRow[] {
  return players.map((player) => ({
    player,
    team: getTeamForPlayer(player.player_id),
    club: getClubForPlayer(player.player_id),
  }));
}

export interface SquadRosterRow {
  entry: SquadEntry;
  player: Player | undefined;
  club: Club | undefined;
}

export function getSquadRosterForTeam(teamCode: string): SquadRosterRow[] {
  return getSquadForTeam(teamCode).map((entry) => ({
    entry,
    player: getPlayerById(entry.player_id),
    club: getClubForPlayer(entry.player_id),
  }));
}
