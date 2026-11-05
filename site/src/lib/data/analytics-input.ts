// Everything the analytics builders in lib/analytics read, in one object.

import {
  clubs,
  getConfederationForCountry,
  matches,
  playerClubAtCallup,
  players,
  playerStats,
  squadEntries,
  teams,
  teamStats,
  TEAM_COUNTRY_ALIASES,
} from "@/lib/data";

export const ANALYTICS_INPUT = {
  teams,
  players,
  squadEntries,
  playerClubAtCallup,
  clubs,
  playerStats,
  teamStats,
  matches,
  teamCountryAliases: TEAM_COUNTRY_ALIASES,
  confederationForCountry: getConfederationForCountry,
};
