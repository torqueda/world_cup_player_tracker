import { activePlayers, cities, clubs, matches, playerStats, teams } from "@/lib/data";

export type ProjectMetric = {
  label: string;
  value: string;
  note: string;
};

const playedMatches = matches.filter((match) => match.status === "played").length;

export const projectMetrics: ProjectMetric[] = [
  {
    label: "Players",
    value: activePlayers.length.toLocaleString(),
    note: "Verified final-squad players across all 48 teams, including late replacements.",
  },
  {
    label: "Canonical clubs",
    value: clubs.length.toLocaleString(),
    note: "Deduplicated club universe used for player-club joins.",
  },
  {
    label: "Matches recorded",
    value: playedMatches.toLocaleString(),
    note: "Official results through the quarterfinals, penalty shootouts included.",
  },
  {
    label: "Stat lines",
    value: playerStats.length.toLocaleString(),
    note: "Per-player goals, assists, minutes, and cards from FIFA's official statistics.",
  },
];

export const screenCards = [
  {
    slug: "players-clubs",
    eyebrow: "The map",
    title: "Players & Clubs",
    body:
      "Start from countries, zoom into club cities, and connect every player back to their club at call-up.",
  },
  {
    slug: "national-teams",
    eyebrow: "The squads",
    title: "National Teams",
    body: "Full 26-player rosters with shirt numbers, coaches, clubs, and leagues for all 48 teams.",
  },
  {
    slug: "matches",
    eyebrow: "The tournament",
    title: "Matches",
    body: `All ${playedMatches} results so far, stage by stage, plus the remaining schedule.`,
  },
  {
    slug: "stats",
    eyebrow: "The numbers",
    title: "Stats",
    body: "Golden Boot race, assists, minutes, discipline, and the full team table.",
  },
  {
    slug: "insights",
    eyebrow: "The angles",
    title: "Insights",
    body: "Birthplaces, diaspora squads, squad ages, and which clubs and leagues power the Cup.",
  },
  {
    slug: "sources",
    eyebrow: "The receipts",
    title: "Data & Sources",
    body: "Source registry, change log, and method notes behind every number on the site.",
  },
];

export const deferredWorkItems = [
  `${teams.length} squads verified against FIFA's final lists; five late-replacement clubs still need geocoding before they appear among the ${cities.length} mapped cities.`,
  "Semifinal and final results plus updated stats land with the next dataset refresh.",
  "Player pages with per-country imagery are reserved for after the license-free image collection.",
  "Birthplace mapping (player-origin view) is a planned second map surface.",
];
