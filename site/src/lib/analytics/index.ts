import type {
  Club,
  Match,
  Player,
  PlayerClubAtCallup,
  PlayerStat,
  SquadEntry,
  Team,
  TeamStat,
} from "../data/types.js";

export const TOURNAMENT_START_DATE = "2026-06-11";
export const DEFAULT_MEANINGFUL_MINUTES = 180;

export interface AnalyticsInput {
  teams: Team[];
  players: Player[];
  squadEntries: SquadEntry[];
  playerClubAtCallup: PlayerClubAtCallup[];
  clubs: Club[];
  playerStats: PlayerStat[];
  teamStats: TeamStat[];
  matches: Match[];
  teamCountryAliases: Record<string, string[]>;
  confederationForCountry: (country: string) => string | undefined;
}

export interface Denominator {
  count: number;
  total: number;
}

export interface SquadScorecard {
  team: string;
  teamCode: string;
  squadSize: number;
  averageAge: number | null;
  medianAge: number | null;
  under23Count: number;
  age30PlusCount: number;
  ageKnown: Denominator;
  totalCaps: number | null;
  medianCaps: number | null;
  capsKnown: Denominator;
  domesticLeaguePlayers: number;
  domesticLeaguePct: number | null;
  domesticLeagueKnown: Denominator;
  clubsRepresented: number;
  clubCountriesRepresented: number;
  leaguesRepresented: number;
  homegrownBirthPlayers: number;
  homegrownBirthShare: number | null;
  birthCountryKnown: Denominator;
  stageReached: string;
}

export interface ConcentrationRow {
  team: string;
  teamCode: string;
  squadSize: number;
  largestClubShare: number | null;
  largestClubName: string | null;
  clubDenominator: number;
  largestClubCountryShare: number | null;
  largestClubCountry: string | null;
  clubCountryDenominator: number;
  clubHhi: number | null;
  clubCountryHhi: number | null;
  effectiveClubCount: number | null;
  normalizedEffectiveClubCount: number | null;
}

export interface ImpactRow {
  key: string;
  label: string;
  kind: "club" | "league";
  playersSent: number;
  teamsRepresented: number;
  totalMinutes: number;
  goals: number;
  assists: number;
  goalContributions: number;
  meaningfulMinutesPlayers: number;
  impactIndex: number;
  impactComponents: {
    players: number;
    teams: number;
    minutes: number;
    goalContributions: number;
  };
}

export type ImpactMetric =
  | "playersSent"
  | "teamsRepresented"
  | "totalMinutes"
  | "goals"
  | "assists"
  | "goalContributions"
  | "impactIndex";

export interface PlayerEfficiencyRow {
  playerId: string;
  playerName: string;
  team: string;
  teamCode: string;
  position: string;
  bucket: "goalkeeper" | "outfield";
  minutes: number;
  goals: number;
  assists: number;
  goalContributions: number;
  cards: number;
  goalsPer90: number;
  assistsPer90: number;
  goalContributionsPer90: number;
  cardsPer90: number;
}

export interface StageGoalRow {
  stage: string;
  matches: number;
  goals: number;
  goalsPerMatch: number;
}

export interface MarginRow {
  margin: string;
  matches: number;
}

export interface VenueGoalRow {
  venue: string;
  city: string;
  matches: number;
  goals: number;
  goalsPerMatch: number;
}

export interface TeamStageRecordRow {
  team: string;
  stage: string;
  played: number;
  wins: number;
  draws: number;
  losses: number;
  goalsFor: number;
  goalsAgainst: number;
}

export interface ConfederationMatchupRow {
  key: string;
  matchup: string;
  matches: number;
  confedA: string;
  confedB: string;
  confedAWins: number;
  confedBWins: number;
  draws: number;
  shootouts: number;
  goals: number;
}

export interface MatchAnalysis {
  goalsByStage: StageGoalRow[];
  marginDistribution: MarginRow[];
  draws: number;
  penaltyShootouts: number;
  goalsByVenue: VenueGoalRow[];
  teamRecordsByStage: TeamStageRecordRow[];
  confederationMatchups: ConfederationMatchupRow[];
}

export interface DataQualityRow {
  key: string;
  label: string;
  status: "available" | "missing" | "not_applicable" | "not_yet_collected" | "failed_validation";
  count: number | null;
  total: number | null;
  pct: number | null;
  note: string;
}

export interface DataQualitySummary {
  rowCounts: { entity: string; rows: number }[];
  latestExportDate: string | null;
  sourceCoverage: DataQualityRow[];
  fieldStatus: DataQualityRow[];
}

export function median(values: number[]): number | null {
  if (values.length === 0) {
    return null;
  }
  const sorted = [...values].sort((a, b) => a - b);
  const middle = Math.floor(sorted.length / 2);
  return sorted.length % 2 === 0 ? (sorted[middle - 1] + sorted[middle]) / 2 : sorted[middle];
}

export function ageInYears(dateOfBirth: string | null | undefined, asOf = TOURNAMENT_START_DATE): number | null {
  if (!dateOfBirth) {
    return null;
  }
  const dob = new Date(`${dateOfBirth.slice(0, 10)}T00:00:00Z`);
  const asOfDate = new Date(`${asOf}T00:00:00Z`);
  if (Number.isNaN(dob.getTime()) || Number.isNaN(asOfDate.getTime())) {
    return null;
  }
  return (asOfDate.getTime() - dob.getTime()) / (1000 * 60 * 60 * 24 * 365.25);
}

export function pct(count: number, total: number): number | null {
  return total > 0 ? count / total : null;
}

export function isCountryMatch(team: string, country: string | null | undefined, aliases: Record<string, string[]>): boolean {
  if (!country) {
    return false;
  }
  return new Set([team, ...(aliases[team] ?? [])]).has(country);
}

function activeEntries(entries: SquadEntry[]): SquadEntry[] {
  return entries.filter((entry) => entry.squad_status === "active");
}

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

function hhi(values: Iterable<number>, denominator: number): number | null {
  if (denominator <= 0) {
    return null;
  }
  let total = 0;
  for (const value of values) {
    const share = value / denominator;
    total += share * share;
  }
  return total;
}

function countMap<T>(rows: T[], value: (row: T) => string | null | undefined): Map<string, number> {
  const map = new Map<string, number>();
  for (const row of rows) {
    const key = value(row);
    if (!key) {
      continue;
    }
    map.set(key, (map.get(key) ?? 0) + 1);
  }
  return map;
}

function sortedEntries(map: Map<string, number>): [string, number][] {
  return Array.from(map.entries()).sort((a, b) => b[1] - a[1] || a[0].localeCompare(b[0]));
}

export function buildSquadScorecards(input: AnalyticsInput): SquadScorecard[] {
  const playersById = indexBy(input.players, (player) => player.player_id);
  const clubsById = indexBy(input.clubs, (club) => club.club_id);
  const callupByPlayerId = indexBy(input.playerClubAtCallup, (link) => link.player_id);
  const teamStatsByCode = indexBy(input.teamStats, (stat) => stat.team_code);
  const entriesByTeam = groupBy(activeEntries(input.squadEntries), (entry) => entry.team_code);

  return input.teams
    .map((team) => {
      const entries = entriesByTeam.get(team.team_code) ?? [];
      const roster = entries.map((entry) => {
        const player = playersById.get(entry.player_id);
        const club = clubsById.get(callupByPlayerId.get(entry.player_id)?.club_id ?? "");
        return { entry, player, club };
      });
      const ages = roster
        .map((row) => ageInYears(row.player?.date_of_birth))
        .filter((age): age is number => age !== null);
      const caps = roster
        .map((row) => row.entry.caps_pre_tournament)
        .filter((value): value is number => typeof value === "number" && Number.isFinite(value));
      const clubCountries = roster.map((row) => row.club?.country).filter((value): value is string => Boolean(value));
      const domestic = clubCountries.filter((country) => isCountryMatch(team.team, country, input.teamCountryAliases)).length;
      const birthCountries = roster
        .map((row) => row.player?.birth_country)
        .filter((value): value is string => Boolean(value));
      const homeBirth = birthCountries.filter((country) => isCountryMatch(team.team, country, input.teamCountryAliases)).length;
      const clubs = new Set(roster.map((row) => row.club?.club_id).filter(Boolean));
      const leagueSet = new Set(roster.map((row) => row.club?.league).filter(Boolean));
      const clubCountrySet = new Set(clubCountries);

      return {
        team: team.team,
        teamCode: team.team_code,
        squadSize: entries.length,
        averageAge: ages.length ? ages.reduce((sum, age) => sum + age, 0) / ages.length : null,
        medianAge: median(ages),
        under23Count: ages.filter((age) => age < 23).length,
        age30PlusCount: ages.filter((age) => age >= 30).length,
        ageKnown: { count: ages.length, total: entries.length },
        totalCaps: caps.length ? caps.reduce((sum, value) => sum + value, 0) : null,
        medianCaps: median(caps),
        capsKnown: { count: caps.length, total: entries.length },
        domesticLeaguePlayers: domestic,
        domesticLeaguePct: pct(domestic, clubCountries.length),
        domesticLeagueKnown: { count: clubCountries.length, total: entries.length },
        clubsRepresented: clubs.size,
        clubCountriesRepresented: clubCountrySet.size,
        leaguesRepresented: leagueSet.size,
        homegrownBirthPlayers: homeBirth,
        homegrownBirthShare: pct(homeBirth, birthCountries.length),
        birthCountryKnown: { count: birthCountries.length, total: entries.length },
        stageReached: teamStatsByCode.get(team.team_code)?.stage_reached ?? "Not available",
      };
    })
    .sort((a, b) => a.team.localeCompare(b.team));
}

export function buildSquadConcentration(input: AnalyticsInput): ConcentrationRow[] {
  const clubsById = indexBy(input.clubs, (club) => club.club_id);
  const callupByPlayerId = indexBy(input.playerClubAtCallup, (link) => link.player_id);
  const entriesByTeam = groupBy(activeEntries(input.squadEntries), (entry) => entry.team_code);

  return input.teams
    .map((team) => {
      const entries = entriesByTeam.get(team.team_code) ?? [];
      const callups = entries
        .map((entry) => clubsById.get(callupByPlayerId.get(entry.player_id)?.club_id ?? ""))
        .filter((club): club is Club => Boolean(club));
      const clubCounts = countMap(callups, (club) => club.club_id);
      const clubCountryCounts = countMap(callups, (club) => club.country);
      const topClub = sortedEntries(clubCounts)[0] ?? null;
      const topCountry = sortedEntries(clubCountryCounts)[0] ?? null;
      const clubHhi = hhi(clubCounts.values(), callups.length);
      const countryDenominator = Array.from(clubCountryCounts.values()).reduce((sum, count) => sum + count, 0);
      const countryHhi = hhi(clubCountryCounts.values(), countryDenominator);
      const effectiveClubCount = clubHhi ? 1 / clubHhi : null;

      return {
        team: team.team,
        teamCode: team.team_code,
        squadSize: entries.length,
        largestClubShare: topClub ? topClub[1] / callups.length : null,
        largestClubName: topClub ? (clubsById.get(topClub[0])?.club_name ?? topClub[0]) : null,
        clubDenominator: callups.length,
        largestClubCountryShare: topCountry ? topCountry[1] / countryDenominator : null,
        largestClubCountry: topCountry?.[0] ?? null,
        clubCountryDenominator: countryDenominator,
        clubHhi,
        clubCountryHhi: countryHhi,
        effectiveClubCount,
        normalizedEffectiveClubCount:
          effectiveClubCount && clubCounts.size > 0 ? effectiveClubCount / clubCounts.size : null,
      };
    })
    .sort((a, b) => (b.clubHhi ?? -1) - (a.clubHhi ?? -1) || a.team.localeCompare(b.team));
}

function impactIndex(rows: Omit<ImpactRow, "impactIndex" | "impactComponents">[]): ImpactRow[] {
  const max = {
    players: Math.max(...rows.map((row) => row.playersSent), 1),
    teams: Math.max(...rows.map((row) => row.teamsRepresented), 1),
    minutes: Math.max(...rows.map((row) => row.totalMinutes), 1),
    goalContributions: Math.max(...rows.map((row) => row.goalContributions), 1),
  };

  return rows.map((row) => {
    const components = {
      players: row.playersSent / max.players,
      teams: row.teamsRepresented / max.teams,
      minutes: row.totalMinutes / max.minutes,
      goalContributions: row.goalContributions / max.goalContributions,
    };
    return {
      ...row,
      impactComponents: components,
      impactIndex:
        100 *
        (0.2 * components.players +
          0.2 * components.teams +
          0.35 * components.minutes +
          0.25 * components.goalContributions),
    };
  });
}

export function buildImpactRows(
  input: AnalyticsInput,
  kind: "club" | "league",
  meaningfulMinutes = DEFAULT_MEANINGFUL_MINUTES,
): ImpactRow[] {
  const activePlayerIds = new Set(activeEntries(input.squadEntries).map((entry) => entry.player_id));
  const statsByPlayerId = indexBy(input.playerStats, (stat) => stat.player_id);
  const clubsById = indexBy(input.clubs, (club) => club.club_id);
  const rowsByKey = new Map<string, Omit<ImpactRow, "impactIndex" | "impactComponents">>();

  for (const callup of input.playerClubAtCallup) {
    if (!activePlayerIds.has(callup.player_id)) {
      continue;
    }
    const club = clubsById.get(callup.club_id);
    const key = kind === "club" ? callup.club_id : (club?.league ?? "League pending review");
    const label = kind === "club" ? (club?.club_name ?? callup.club_name_at_source ?? callup.club_id) : key;
    const stat = statsByPlayerId.get(callup.player_id);
    const current =
      rowsByKey.get(key) ??
      {
        key,
        label,
        kind,
        playersSent: 0,
        teamsRepresented: 0,
        totalMinutes: 0,
        goals: 0,
        assists: 0,
        goalContributions: 0,
        meaningfulMinutesPlayers: 0,
      };
    current.playersSent += 1;
    current.totalMinutes += stat?.minutes_played ?? 0;
    current.goals += stat?.goals ?? 0;
    current.assists += stat?.assists ?? 0;
    current.goalContributions += (stat?.goals ?? 0) + (stat?.assists ?? 0);
    if ((stat?.minutes_played ?? 0) >= meaningfulMinutes) {
      current.meaningfulMinutesPlayers += 1;
    }
    rowsByKey.set(key, current);
  }

  const teamsByKey = new Map<string, Set<string>>();
  for (const callup of input.playerClubAtCallup) {
    if (!activePlayerIds.has(callup.player_id)) {
      continue;
    }
    const club = clubsById.get(callup.club_id);
    const key = kind === "club" ? callup.club_id : (club?.league ?? "League pending review");
    const set = teamsByKey.get(key) ?? new Set<string>();
    set.add(callup.team);
    teamsByKey.set(key, set);
  }
  for (const [key, row] of rowsByKey) {
    row.teamsRepresented = teamsByKey.get(key)?.size ?? 0;
  }

  return impactIndex(Array.from(rowsByKey.values())).sort(
    (a, b) => b.playersSent - a.playersSent || a.label.localeCompare(b.label),
  );
}

export function buildPlayerEfficiencyRows(input: AnalyticsInput, minMinutes: number): PlayerEfficiencyRow[] {
  const playersById = indexBy(input.players, (player) => player.player_id);
  const entriesByPlayerId = indexBy(activeEntries(input.squadEntries), (entry) => entry.player_id);
  const teamsByCode = indexBy(input.teams, (team) => team.team_code);

  return input.playerStats
    .filter((stat) => stat.minutes_played >= minMinutes && stat.minutes_played > 0)
    .map((stat) => {
      const player = playersById.get(stat.player_id);
      const entry = entriesByPlayerId.get(stat.player_id);
      const position = player?.primary_position ?? entry?.position_group ?? "unknown";
      const bucket: PlayerEfficiencyRow["bucket"] = position === "goalkeeper" ? "goalkeeper" : "outfield";
      const cards = stat.yellow_cards + stat.red_cards + stat.indirect_red_cards;
      const per90 = (value: number) => (value / stat.minutes_played) * 90;
      return {
        playerId: stat.player_id,
        playerName: player?.display_name ?? stat.fifa_listed_name,
        team: teamsByCode.get(stat.team_code)?.team ?? entry?.team ?? stat.team_code,
        teamCode: stat.team_code,
        position,
        bucket,
        minutes: stat.minutes_played,
        goals: stat.goals,
        assists: stat.assists,
        goalContributions: stat.goals + stat.assists,
        cards,
        goalsPer90: per90(stat.goals),
        assistsPer90: per90(stat.assists),
        goalContributionsPer90: per90(stat.goals + stat.assists),
        cardsPer90: per90(cards),
      };
    })
    .sort((a, b) => b.goalContributionsPer90 - a.goalContributionsPer90 || b.minutes - a.minutes);
}

function matchGoals(match: Match): number | null {
  if (match.home_score === null || match.away_score === null) {
    return null;
  }
  return match.home_score + match.away_score;
}

function matchWinner(match: Match): "home" | "away" | "draw" | null {
  if (match.home_score === null || match.away_score === null) {
    return null;
  }
  if (match.home_score > match.away_score) return "home";
  if (match.away_score > match.home_score) return "away";
  if (match.home_pens !== null && match.away_pens !== null && match.home_pens !== match.away_pens) {
    return match.home_pens > match.away_pens ? "home" : "away";
  }
  return "draw";
}

export function buildMatchAnalysis(input: AnalyticsInput): MatchAnalysis {
  const played = input.matches.filter(
    (match) => match.status === "played" && match.home_score !== null && match.away_score !== null,
  );
  const byStage = groupBy(played, (match) => match.stage);
  const goalsByStage = Array.from(byStage.entries())
    .map(([stage, rows]) => {
      const goals = rows.reduce((sum, match) => sum + (matchGoals(match) ?? 0), 0);
      return { stage, matches: rows.length, goals, goalsPerMatch: goals / rows.length };
    })
    .sort((a, b) => b.goalsPerMatch - a.goalsPerMatch || a.stage.localeCompare(b.stage));

  const margins = new Map<string, number>();
  for (const match of played) {
    const margin = Math.abs((match.home_score ?? 0) - (match.away_score ?? 0));
    const key = margin === 0 ? "Draw after 90/120" : `${margin} goal${margin === 1 ? "" : "s"}`;
    margins.set(key, (margins.get(key) ?? 0) + 1);
  }

  const venueRows = Array.from(groupBy(played, (match) => `${match.stadium}__${match.city}`).entries())
    .map(([key, rows]) => {
      const [venue, city] = key.split("__");
      const goals = rows.reduce((sum, match) => sum + (matchGoals(match) ?? 0), 0);
      return { venue, city, matches: rows.length, goals, goalsPerMatch: goals / rows.length };
    })
    .sort((a, b) => b.goalsPerMatch - a.goalsPerMatch || b.matches - a.matches || a.venue.localeCompare(b.venue));

  const teamStageRecords = new Map<string, TeamStageRecordRow>();
  for (const match of played) {
    for (const side of ["home", "away"] as const) {
      const team = side === "home" ? match.home_team : match.away_team;
      const goalsFor = side === "home" ? match.home_score ?? 0 : match.away_score ?? 0;
      const goalsAgainst = side === "home" ? match.away_score ?? 0 : match.home_score ?? 0;
      const winner = matchWinner(match);
      const key = `${team}__${match.stage}`;
      const row =
        teamStageRecords.get(key) ??
        {
          team,
          stage: match.stage,
          played: 0,
          wins: 0,
          draws: 0,
          losses: 0,
          goalsFor: 0,
          goalsAgainst: 0,
        };
      row.played += 1;
      row.goalsFor += goalsFor;
      row.goalsAgainst += goalsAgainst;
      if (winner === "draw") row.draws += 1;
      else if ((winner === "home" && side === "home") || (winner === "away" && side === "away")) row.wins += 1;
      else row.losses += 1;
      teamStageRecords.set(key, row);
    }
  }

  const matchupRows = new Map<string, ConfederationMatchupRow>();
  for (const match of played) {
    const homeConfed = input.confederationForCountry(match.home_team);
    const awayConfed = input.confederationForCountry(match.away_team);
    if (!homeConfed || !awayConfed || homeConfed === awayConfed) {
      continue;
    }
    const [confedA, confedB] = [homeConfed, awayConfed].sort((a, b) => a.localeCompare(b));
    const key = `${confedA}__${confedB}`;
    const row =
      matchupRows.get(key) ??
      {
        key,
        matchup: `${confedA} vs ${confedB}`,
        matches: 0,
        confedA,
        confedB,
        confedAWins: 0,
        confedBWins: 0,
        draws: 0,
        shootouts: 0,
        goals: 0,
      };
    const winner = matchWinner(match);
    row.matches += 1;
    row.goals += matchGoals(match) ?? 0;
    if (match.home_pens !== null && match.away_pens !== null) row.shootouts += 1;
    if (winner === "draw") {
      row.draws += 1;
    } else {
      const winnerConfed = winner === "home" ? homeConfed : awayConfed;
      if (winnerConfed === confedA) row.confedAWins += 1;
      if (winnerConfed === confedB) row.confedBWins += 1;
    }
    matchupRows.set(key, row);
  }

  return {
    goalsByStage,
    marginDistribution: Array.from(margins.entries()).map(([margin, matches]) => ({ margin, matches })),
    draws: played.filter((match) => match.home_score === match.away_score).length,
    penaltyShootouts: played.filter((match) => match.home_pens !== null && match.away_pens !== null).length,
    goalsByVenue: venueRows,
    teamRecordsByStage: Array.from(teamStageRecords.values()).sort(
      (a, b) => a.stage.localeCompare(b.stage) || a.team.localeCompare(b.team),
    ),
    confederationMatchups: Array.from(matchupRows.values()).sort((a, b) => b.matches - a.matches || a.key.localeCompare(b.key)),
  };
}

function hasSource(row: unknown, keys: string[]): boolean {
  if (!row || typeof row !== "object") {
    return false;
  }
  const record = row as Record<string, unknown>;
  return keys.some((key) => {
    const value = record[key];
    return value !== null && value !== undefined && value !== "";
  });
}

function qualityPct(count: number, total: number): number {
  return total > 0 ? count / total : 0;
}

export function buildDataQualitySummary(
  input: AnalyticsInput,
  meta: { counts?: Record<string, number>; exported_at?: string } | null,
): DataQualitySummary {
  const activePlayerIds = new Set(activeEntries(input.squadEntries).map((entry) => entry.player_id));
  const activePlayers = input.players.filter((player) => activePlayerIds.has(player.player_id));
  const statPlayerIds = new Set(input.playerStats.map((stat) => stat.player_id));
  const validClubCoords = input.clubs.filter(
    (club) => typeof club.city_lat === "number" && typeof club.city_lon === "number",
  ).length;

  const coverage = [
    {
      key: "squad_sources",
      label: "Squad roster source URLs",
      count: input.squadEntries.filter((entry) => hasSource(entry, ["official_roster_source_url"])).length,
      total: input.squadEntries.length,
      note: "Official roster source URL present on squad-entry rows.",
    },
    {
      key: "player_bio_sources",
      label: "Player bio source URLs",
      count: input.players.filter((player) => hasSource(player, ["bio_source_url"])).length,
      total: input.players.length,
      note: "Wikidata or reviewed bio source URL present on player rows.",
    },
    {
      key: "club_sources",
      label: "Club coordinate sources",
      count: input.clubs.filter((club) => hasSource(club, ["city_source_url", "city_geo_source"])).length,
      total: input.clubs.length,
      note: "City coordinate provenance present on club rows.",
    },
    {
      key: "match_sources",
      label: "Match source IDs",
      count: input.matches.filter((match) => hasSource(match, ["source_id"])).length,
      total: input.matches.length,
      note: "FIFA fixture source ID present on match rows.",
    },
  ];

  const fieldRows: DataQualityRow[] = [
    {
      key: "active_player_images",
      label: "Active players with images",
      status: "available",
      count: activePlayers.filter((player) => Boolean(player.image_url)).length,
      total: activePlayers.length,
      pct: qualityPct(activePlayers.filter((player) => Boolean(player.image_url)).length, activePlayers.length),
      note: "Missing means no reviewed Commons image is exported for that player.",
    },
    {
      key: "active_player_stats",
      label: "Active players with player-stat records",
      status: "available",
      count: activePlayers.filter((player) => statPlayerIds.has(player.player_id)).length,
      total: activePlayers.length,
      pct: qualityPct(activePlayers.filter((player) => statPlayerIds.has(player.player_id)).length, activePlayers.length),
      note: "Player-stat coverage comes from the current FIFA stats export.",
    },
    {
      key: "club_coordinates",
      label: "Clubs with valid coordinates",
      status: "available",
      count: validClubCoords,
      total: input.clubs.length,
      pct: qualityPct(validClubCoords, input.clubs.length),
      note: "Missing means the club has no exported city latitude/longitude yet.",
    },
    {
      key: "birth_country_missing",
      label: "Active players missing birth country",
      status: "missing",
      count: activePlayers.filter((player) => !player.birth_country).length,
      total: activePlayers.length,
      pct: qualityPct(activePlayers.filter((player) => !player.birth_country).length, activePlayers.length),
      note: "Missing values are excluded from birthplace denominators rather than imputed.",
    },
    {
      key: "xga_unavailable",
      label: "Team xGA",
      status: "not_yet_collected",
      count: null,
      total: null,
      pct: null,
      note: "The current team_stats export has xG but no xGA field, so comparison views label xGA unavailable.",
    },
    {
      key: "starts_unavailable",
      label: "Player starts",
      status: "not_yet_collected",
      count: null,
      total: null,
      pct: null,
      note: "The current player_stats export has minutes but no starts. Impact views use meaningful-minutes counts instead.",
    },
    {
      key: "goalkeeper_stats",
      label: "Goalkeeper detail for outfield players",
      status: "not_applicable",
      count: null,
      total: null,
      pct: null,
      note: "Goalkeeper-specific stat fields are intentionally not applicable to outfield-player rows.",
    },
    {
      key: "validation_failures",
      label: "Failed validation rows",
      status: "failed_validation",
      count: 0,
      total: input.players.length + input.clubs.length + input.squadEntries.length,
      pct: 0,
      note: "No failed-validation rows are bundled in app exports; strict audit failures stop JSON export generation.",
    },
  ];

  return {
    rowCounts: Object.entries(meta?.counts ?? {}).map(([entity, rows]) => ({ entity, rows })),
    latestExportDate: meta?.exported_at ?? null,
    sourceCoverage: coverage.map((row) => ({
      ...row,
      status: row.count === row.total ? "available" : "missing",
      pct: qualityPct(row.count, row.total),
    })),
    fieldStatus: fieldRows,
  };
}
