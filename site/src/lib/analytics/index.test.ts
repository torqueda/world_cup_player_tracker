import assert from "node:assert/strict";
import test from "node:test";
import {
  ageInYears,
  buildDataQualitySummary,
  buildImpactRows,
  buildMatchAnalysis,
  buildPlayerEfficiencyRows,
  buildSquadConcentration,
  buildSquadScorecards,
  median,
  type AnalyticsInput,
} from "./index.js";
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

const teams: Team[] = [
  { team: "Alpha", team_code: "ALP", tournament: "FIFA World Cup 2026", squad_size: 3, replacement_count: 0, players: [] },
  { team: "Beta", team_code: "BET", tournament: "FIFA World Cup 2026", squad_size: 2, replacement_count: 0, players: [] },
];

const players: Player[] = [
  player("p1", "A One", "2004-06-11", "Alpha", "forward", "img"),
  player("p2", "A Two", "1990-01-01", "Gamma", "midfielder", null),
  player("p3", "A Three", "1998-01-01", null, "goalkeeper", null),
  player("p4", "B One", "2000-01-01", "Beta", "forward", "img"),
  player("p5", "B Two", "1988-01-01", "Beta", "defender", null),
];

const squadEntries: SquadEntry[] = [
  entry("s1", "ALP", "Alpha", "p1", 10),
  entry("s2", "ALP", "Alpha", "p2", 20),
  entry("s3", "ALP", "Alpha", "p3", null),
  entry("s4", "BET", "Beta", "p4", 5),
  entry("s5", "BET", "Beta", "p5", 15),
  { ...entry("s6", "BET", "Beta", "removed", 99), squad_status: "removed" },
];

const clubs: Club[] = [
  club("c1", "Alpha FC", "Alpha League", "Alpha", 1, 1),
  club("c2", "Gamma FC", "Gamma League", "Gamma", 2, 2),
  club("c3", "Beta FC", "Beta League", "Beta", null, null),
];

const callups: PlayerClubAtCallup[] = [
  callup("p1", "c1", "Alpha"),
  callup("p2", "c1", "Alpha"),
  callup("p3", "c2", "Alpha"),
  callup("p4", "c3", "Beta"),
  callup("p5", "c3", "Beta"),
];

const playerStats: PlayerStat[] = [
  stat("p1", "ALP", 2, 1, 270, 1, 0, 0),
  stat("p2", "ALP", 1, 0, 90, 0, 0, 0),
  stat("p3", "ALP", 0, 0, 270, 0, 0, 0, 4),
  stat("p4", "BET", 1, 2, 180, 2, 0, 0),
  stat("p5", "BET", 0, 0, 45, 1, 1, 0),
];

const teamStats: TeamStat[] = [
  {
    team: "Alpha",
    team_code: "ALP",
    tournament: "FIFA World Cup 2026",
    matches_played: 2,
    wins: 1,
    draws: 1,
    losses: 0,
    goals_for: 3,
    goals_against: 2,
    stage_reached: "Round of 16",
    assists: 1,
    xg: 2.4,
    possession_pct: 52,
    as_of_stage: "test",
  },
  {
    team: "Beta",
    team_code: "BET",
    tournament: "FIFA World Cup 2026",
    matches_played: 2,
    wins: 0,
    draws: 1,
    losses: 1,
    goals_for: 2,
    goals_against: 3,
    stage_reached: "Group stage",
    assists: 2,
    xg: 1.8,
    possession_pct: 48,
    as_of_stage: "test",
  },
];

const matches: Match[] = [
  match("m1", "First Stage", "Alpha", "Beta", 2, 1, null, null, "North Stadium", "North City"),
  match("m2", "Round of 32", "Alpha", "Beta", 1, 1, 4, 3, "North Stadium", "North City"),
];

const input: AnalyticsInput = {
  teams,
  players,
  squadEntries,
  playerClubAtCallup: callups,
  clubs,
  playerStats,
  teamStats,
  matches,
  teamCountryAliases: {},
  confederationForCountry: (country) => (country === "Alpha" ? "AFC" : "UEFA"),
};

test("median and age helpers handle even lists and invalid dates", () => {
  assert.equal(median([4, 1, 9, 3]), 3.5);
  assert.equal(median([]), null);
  assert.equal(ageInYears(null), null);
  assert.equal(ageInYears("not-a-date"), null);
});

test("squad scorecards use explicit denominators and active entries only", () => {
  const alpha = buildSquadScorecards(input).find((row) => row.team === "Alpha");
  assert.ok(alpha);
  assert.equal(alpha.squadSize, 3);
  assert.equal(alpha.under23Count, 1);
  assert.equal(alpha.age30PlusCount, 1);
  assert.deepEqual(alpha.capsKnown, { count: 2, total: 3 });
  assert.equal(alpha.totalCaps, 30);
  assert.equal(alpha.medianCaps, 15);
  assert.equal(alpha.domesticLeaguePlayers, 2);
  assert.equal(alpha.domesticLeaguePct, 2 / 3);
  assert.equal(alpha.homegrownBirthShare, 1 / 2);
  assert.equal(alpha.stageReached, "Round of 16");
});

test("concentration reports HHI and effective club counts", () => {
  const alpha = buildSquadConcentration(input).find((row) => row.team === "Alpha");
  assert.ok(alpha);
  assert.equal(alpha.largestClubName, "Alpha FC");
  assert.equal(alpha.largestClubShare, 2 / 3);
  assert.equal(alpha.clubHhi, 5 / 9);
  assert.equal(alpha.effectiveClubCount, 1 / (5 / 9));
});

test("club and league impact aggregate player stats without starts", () => {
  const clubRows = buildImpactRows(input, "club", 180);
  const alphaFc = clubRows.find((row) => row.key === "c1");
  assert.ok(alphaFc);
  assert.equal(alphaFc.playersSent, 2);
  assert.equal(alphaFc.teamsRepresented, 1);
  assert.equal(alphaFc.totalMinutes, 360);
  assert.equal(alphaFc.goalContributions, 4);
  assert.equal(alphaFc.meaningfulMinutesPlayers, 1);

  const leagueRows = buildImpactRows(input, "league", 180);
  assert.equal(leagueRows.find((row) => row.key === "Beta League")?.playersSent, 2);
});

test("player efficiency filters low-minute players and separates goalkeepers", () => {
  const rows = buildPlayerEfficiencyRows(input, 180);
  assert.equal(rows.some((row) => row.playerId === "p2"), false);
  assert.equal(rows.find((row) => row.playerId === "p3")?.bucket, "goalkeeper");
  assert.equal(rows.find((row) => row.playerId === "p4")?.goalContributionsPer90, 1.5);
});

test("match analysis summarizes goals, margins, venues, records, and confederations", () => {
  const analysis = buildMatchAnalysis(input);
  assert.equal(analysis.goalsByStage.find((row) => row.stage === "First Stage")?.goalsPerMatch, 3);
  assert.equal(analysis.draws, 1);
  assert.equal(analysis.penaltyShootouts, 1);
  assert.equal(analysis.goalsByVenue[0].goals, 5);
  assert.equal(analysis.teamRecordsByStage.find((row) => row.team === "Alpha" && row.stage === "Round of 32")?.wins, 1);
  assert.equal(analysis.confederationMatchups[0].shootouts, 1);
});

test("data quality distinguishes missing, not applicable, deferred, and validation statuses", () => {
  const quality = buildDataQualitySummary(input, { counts: { players: players.length }, exported_at: "2026-07-14" });
  assert.equal(quality.latestExportDate, "2026-07-14");
  assert.equal(quality.rowCounts.find((row) => row.entity === "players")?.rows, players.length);
  assert.equal(quality.fieldStatus.find((row) => row.key === "active_player_images")?.count, 2);
  assert.equal(quality.fieldStatus.find((row) => row.key === "xga_unavailable")?.status, "not_yet_collected");
  assert.equal(quality.fieldStatus.find((row) => row.key === "goalkeeper_stats")?.status, "not_applicable");
  assert.equal(quality.fieldStatus.find((row) => row.key === "validation_failures")?.status, "failed_validation");
});

function player(
  playerId: string,
  displayName: string,
  dob: string | null,
  birthCountry: string | null,
  position: string,
  imageUrl: string | null,
): Player {
  return {
    player_id: playerId,
    wikidata_id: null,
    fifa_id: null,
    espn_id: null,
    display_name: displayName,
    name_ascii: displayName,
    date_of_birth: dob,
    place_of_birth: null,
    birth_country: birthCountry,
    birth_lat: null,
    birth_lon: null,
    height_cm: null,
    primary_position: position,
    image_commons_title: null,
    image_url: imageUrl,
    image_author: null,
    image_license: null,
    image_source_url: null,
    bio_source_url: null,
    data_confidence: null,
    manual_review_flag: false,
    notes: null,
  };
}

function entry(id: string, teamCode: string, team: string, playerId: string, caps: number | null): SquadEntry {
  return {
    squad_entry_id: id,
    tournament: "FIFA World Cup 2026",
    team,
    team_code: teamCode,
    player_id: playerId,
    display_name_at_source: playerId,
    position_group: null,
    shirt_number: null,
    squad_status: "active",
    caps_pre_tournament: caps,
    goals_pre_tournament: null,
    is_replacement: false,
    replaced_player_id: null,
    replacement_reason: null,
    official_roster_source_url: "https://example.com",
    verified_at: null,
  };
}

function club(id: string, name: string, league: string, country: string, lat: number | null, lon: number | null): Club {
  return {
    club_id: id,
    wikidata_id: null,
    club_name: name,
    club_name_ascii: name,
    league,
    country,
    city: null,
    stadium: null,
    city_lat: lat,
    city_lon: lon,
    city_source_url: lat === null ? null : "https://example.com",
    city_geo_source: lat === null ? null : "manual",
    city_match_confidence: null,
    manual_review_flag: false,
    notes: null,
    city_key: null,
    city_review_notes: null,
  };
}

function callup(playerId: string, clubId: string, team: string): PlayerClubAtCallup {
  return {
    player_club_callup_id: `${playerId}-${clubId}`,
    player_id: playerId,
    club_id: clubId,
    team,
    club_name_at_source: null,
    club_rule: null,
    is_on_loan: "false",
    parent_club_id: null,
    loan_club_id: null,
    club_source_url: "https://example.com",
    confidence: null,
    notes: null,
  };
}

function stat(
  playerId: string,
  teamCode: string,
  goals: number,
  assists: number,
  minutes: number,
  yellow: number,
  red: number,
  indirectRed: number,
  saves?: number,
): PlayerStat {
  return {
    player_id: playerId,
    tournament: "FIFA World Cup 2026",
    team_code: teamCode,
    fifa_listed_name: playerId,
    goals,
    assists,
    minutes_played: minutes,
    yellow_cards: yellow,
    red_cards: red,
    indirect_red_cards: indirectRed,
    as_of_stage: "test",
    gk_saves: saves,
  };
}

function match(
  id: string,
  stage: string,
  home: string,
  away: string,
  homeScore: number,
  awayScore: number,
  homePens: number | null,
  awayPens: number | null,
  stadium: string,
  city: string,
): Match {
  return {
    match_id: id,
    tournament: "FIFA World Cup 2026",
    match_date: "2026-06-11T00:00:00",
    stage,
    group: null,
    home_team: home,
    away_team: away,
    home_score: homeScore,
    away_score: awayScore,
    home_pens: homePens,
    away_pens: awayPens,
    stadium,
    city,
    status: "played",
  };
}
