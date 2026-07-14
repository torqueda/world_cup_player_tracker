export interface Club {
  club_id: string;
  wikidata_id: string | null;
  club_name: string;
  club_name_ascii: string;
  // league/country/city are null for clubs added with late roster
  // replacements until their manual review fills them in.
  league: string | null;
  country: string | null;
  city: string | null;
  stadium: string | null;
  city_lat: number | null;
  city_lon: number | null;
  city_source_url: string | null;
  city_geo_source: string | null;
  city_match_confidence: string | null;
  manual_review_flag: boolean;
  notes: string | null;
  city_key: string | null;
  city_review_notes: string | null;
}

export interface ClubAlias {
  // An alternate (as-scraped) club name that differs from the canonical one,
  // surfaced as an extra searchable label pointing at the canonical club.
  alias: string;
  alias_ascii: string;
  canonical_club_id: string;
}

export interface City {
  city_key: string;
  country: string;
  city: string;
  city_ascii: string;
  city_lat: number;
  city_lon: number;
  city_source_url: string | null;
  city_geo_source: string | null;
  city_match_confidence: string | null;
  city_review_notes: string | null;
  club_count: number;
  club_ids: string[];
}

export interface Player {
  player_id: string;
  wikidata_id: string | null;
  fifa_id: string | null;
  espn_id: string | null;
  display_name: string;
  name_ascii: string;
  date_of_birth: string | null;
  place_of_birth: string | null;
  birth_country: string | null;
  birth_lat: number | null;
  birth_lon: number | null;
  height_cm: number | null;
  primary_position: string | null;
  image_commons_title: string | null;
  image_url: string | null;
  image_author: string | null;
  image_license: string | null;
  image_source_url: string | null;
  bio_source_url: string | null;
  data_confidence: string | null;
  manual_review_flag: boolean;
  notes: string | null;
}

export interface Team {
  team: string;
  team_code: string;
  tournament: string;
  squad_size: number;
  replacement_count: number;
  players: string[];
}

export interface SquadEntry {
  squad_entry_id: string;
  tournament: string;
  team: string;
  team_code: string;
  player_id: string;
  display_name_at_source: string;
  position_group: string | null;
  shirt_number: number | null;
  squad_status: string;
  is_captain?: boolean | null;
  caps_pre_tournament?: number | null;
  goals_pre_tournament?: number | null;
  is_replacement: boolean;
  replaced_player_id: string | null;
  replacement_reason: string | null;
  official_roster_source_url: string | null;
  verified_at: string | null;
}

export interface Match {
  match_id: string;
  tournament: string;
  match_date: string;
  stage: string;
  group: string | null;
  home_team: string;
  away_team: string;
  home_score: number | null;
  away_score: number | null;
  home_pens: number | null;
  away_pens: number | null;
  stadium: string;
  city: string;
  status: string;
}

export interface PlayerStat {
  player_id: string;
  tournament: string;
  team_code: string;
  fifa_listed_name: string;
  goals: number;
  assists: number;
  minutes_played: number;
  yellow_cards: number;
  red_cards: number;
  indirect_red_cards: number;
  as_of_stage: string;
  gk_saves?: number | null;
  gk_actions_inside_box?: number | null;
  gk_actions_outside_box?: number | null;
}

export interface TeamStat {
  team: string;
  team_code: string;
  tournament: string;
  matches_played: number;
  wins: number;
  draws: number;
  losses: number;
  goals_for: number;
  goals_against: number;
  stage_reached: string;
  assists: number;
  xg: number;
  possession_pct: number;
  as_of_stage: string;
}

export interface Coach {
  coach_id: string;
  team: string;
  team_code: string;
  coach_name: string;
  coach_nationality: string | null;
}

export interface Referee {
  official_id: string;
  name: string;
  country: string;
  role: string;
  confederation: string | null;
}

export interface Confederation {
  code: string;
  name: string;
  source_url: string | null;
  members: string[];
}

export interface PlayerClubAtCallup {
  player_club_callup_id: string;
  player_id: string;
  club_id: string;
  team: string;
  club_name_at_source: string | null;
  club_rule: string | null;
  is_on_loan: string;
  parent_club_id: string | null;
  loan_club_id: string | null;
  club_source_url: string | null;
  confidence: string | null;
  notes: string | null;
}
