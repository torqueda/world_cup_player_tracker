import { useEffect, useMemo, useRef, useState } from "react";
import Fuse from "fuse.js";
import {
  PlayersClubsMap,
  boundsForCities,
  MAP_COUNTRY_COLOR,
  MAP_CITY_COLOR,
  MAP_ACTIVE_COLOR,
  type MapFocus,
} from "@/components/players-clubs-map";
import { PlayerLink } from "@/components/player-detail";
import { CountryFlag } from "@/components/country-flag";
import {
  ChartLegend,
  EmptyState,
  Expandable,
  FilterGroup,
  PageHeader,
  SummaryRow,
} from "@/components/ui";
import {
  activePlayers,
  cities,
  clubAliases,
  clubs,
  getClubById,
  getClubsForCity,
  getPlayersForClub,
  getTeamForPlayer,
  getTeamsForClub,
  teams,
  type Club,
} from "@/lib/data";

const ALL = "all";
const MAX_SUGGESTIONS = 8;

// Fuzzy indices for typo tolerance, built once. These only ever *add* matches
// after the exact substring matches below, so existing search behaviour is
// unchanged — fuzzy results are a fallback, never a replacement.
const clubFuse = new Fuse(clubs, {
  keys: ["club_name", "club_name_ascii"],
  threshold: 0.3,
  ignoreLocation: true,
  minMatchCharLength: 2,
});
const playerFuse = new Fuse(activePlayers, {
  keys: ["display_name", "name_ascii"],
  threshold: 0.3,
  ignoreLocation: true,
  minMatchCharLength: 2,
});

interface SearchSelection {
  type: "club" | "player";
  id: string;
  label: string;
}

interface Suggestion extends SearchSelection {
  hint: string;
}

// Precomputed once: which teams each club supplies, and each player's club.
const clubTeams = new Map<string, string[]>(clubs.map((club) => [club.club_id, getTeamsForClub(club.club_id)]));
const playerClubId = new Map<string, string>();
for (const club of clubs) {
  for (const player of getPlayersForClub(club.club_id)) {
    playerClubId.set(player.player_id, club.club_id);
  }
}

export function PlayersClubsRoute() {
  const [team, setTeam] = useState(ALL);
  const [country, setCountry] = useState(ALL);
  const [league, setLeague] = useState(ALL);
  const [searchText, setSearchText] = useState("");
  const [selections, setSelections] = useState<SearchSelection[]>([]);
  const [selectedCityKey, setSelectedCityKey] = useState<string | null>(null);
  const [focus, setFocus] = useState<MapFocus>({ id: 0, bounds: null });
  const focusId = useRef(0);
  const searchWrapRef = useRef<HTMLDivElement>(null);
  const [suggestionsOpen, setSuggestionsOpen] = useState(false);
  const [filtersOpen, setFiltersOpen] = useState(false);

  // --- club predicate builders (each can exclude one dimension so dropdown
  // options cascade off the *other* active filters) ---

  function clubPasses(club: Club, opts: { skipTeam?: boolean; skipCountry?: boolean; skipLeague?: boolean }): boolean {
    if (!opts.skipCountry && country !== ALL && club.country !== country) {
      return false;
    }
    if (!opts.skipLeague && league !== ALL && club.league !== league) {
      return false;
    }
    if (!opts.skipTeam && team !== ALL && !(clubTeams.get(club.club_id) ?? []).includes(team)) {
      return false;
    }
    if (selections.length > 0) {
      const passesSelection = selections.some((selection) =>
        selection.type === "club"
          ? selection.id === club.club_id
          : playerClubId.get(selection.id) === club.club_id,
      );
      if (!passesSelection) {
        return false;
      }
    }
    return true;
  }

  const matchingClubIds = useMemo(() => {
    return new Set(clubs.filter((club) => clubPasses(club, {})).map((club) => club.club_id));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [team, country, league, selections]);

  const filteredCities = useMemo(
    () => cities.filter((city) => city.club_ids.some((clubId) => matchingClubIds.has(clubId))),
    [matchingClubIds],
  );

  // Cascading options: teams from country/league/selection-filtered clubs;
  // countries from team/selection-filtered clubs; leagues additionally
  // narrowed by the selected country.
  const teamOptions = useMemo(() => {
    const names = new Set<string>();
    for (const club of clubs) {
      if (clubPasses(club, { skipTeam: true })) {
        for (const name of clubTeams.get(club.club_id) ?? []) {
          names.add(name);
        }
      }
    }
    return Array.from(names).sort((a, b) => a.localeCompare(b));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [country, league, selections]);

  const countryOptions = useMemo(() => {
    const names = new Set<string>();
    for (const club of clubs) {
      if (club.country && clubPasses(club, { skipCountry: true, skipLeague: true })) {
        names.add(club.country);
      }
    }
    return Array.from(names).sort((a, b) => a.localeCompare(b));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [team, selections]);

  const leagueOptions = useMemo(() => {
    const names = new Set<string>();
    for (const club of clubs) {
      if (club.league && clubPasses(club, { skipLeague: true })) {
        names.add(club.league);
      }
    }
    return Array.from(names).sort((a, b) => a.localeCompare(b));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [team, country, selections]);

  // Keep selected values valid as the cascades narrow.
  useEffect(() => {
    if (team !== ALL && !teamOptions.includes(team)) {
      setTeam(ALL);
    }
  }, [team, teamOptions]);
  useEffect(() => {
    if (league !== ALL && !leagueOptions.includes(league)) {
      setLeague(ALL);
    }
  }, [league, leagueOptions]);

  // --- search suggestions ---
  // Layered so current behaviour is preserved and only extended: exact
  // substring matches first (clubs → curated aliases → players), then a
  // fuzzy fallback for typos, appended only while there is room and never
  // duplicating an already-listed result.
  const suggestions = useMemo<Suggestion[]>(() => {
    const query = searchText.trim().toLowerCase();
    if (query.length < 2) {
      return [];
    }
    const out: Suggestion[] = [];
    const seen = new Set<string>();

    function pushClub(club: Club, hint?: string): boolean {
      const key = `club:${club.club_id}`;
      if (seen.has(key)) {
        return out.length >= MAX_SUGGESTIONS;
      }
      seen.add(key);
      out.push({ type: "club", id: club.club_id, label: club.club_name, hint: hint ?? club.country ?? "club" });
      return out.length >= MAX_SUGGESTIONS;
    }

    function pushPlayer(playerId: string, label: string): boolean {
      const key = `player:${playerId}`;
      if (seen.has(key)) {
        return out.length >= MAX_SUGGESTIONS;
      }
      seen.add(key);
      const playerTeam = getTeamForPlayer(playerId);
      out.push({ type: "player", id: playerId, label, hint: playerTeam?.team ?? "player" });
      return out.length >= MAX_SUGGESTIONS;
    }

    // 1. Exact substring — clubs by canonical name (unchanged).
    for (const club of clubs) {
      if (club.club_name.toLowerCase().includes(query) || club.club_name_ascii.toLowerCase().includes(query)) {
        if (pushClub(club)) return out;
      }
    }
    // 2. Exact substring — curated aliases resolving to their canonical club
    //    (e.g. "Monaco" → AS Monaco, "Roma" → AS Roma).
    for (const alias of clubAliases) {
      if (alias.alias.toLowerCase().includes(query) || alias.alias_ascii.toLowerCase().includes(query)) {
        const club = getClubById(alias.canonical_club_id);
        if (club && pushClub(club, `also “${alias.alias}” · ${club.country ?? "club"}`)) return out;
      }
    }
    // 3. Exact substring — players (unchanged).
    for (const player of activePlayers) {
      if (
        player.display_name.toLowerCase().includes(query) ||
        player.name_ascii.toLowerCase().includes(query)
      ) {
        if (pushPlayer(player.player_id, player.display_name)) return out;
      }
    }
    // 4. Fuzzy fallback for typos, only if the exact passes left room.
    if (out.length < MAX_SUGGESTIONS) {
      for (const result of clubFuse.search(query, { limit: MAX_SUGGESTIONS })) {
        if (pushClub(result.item)) return out;
      }
    }
    if (out.length < MAX_SUGGESTIONS) {
      for (const result of playerFuse.search(query, { limit: MAX_SUGGESTIONS })) {
        if (pushPlayer(result.item.player_id, result.item.display_name)) return out;
      }
    }
    return out;
  }, [searchText]);

  function addSelection(suggestion: SearchSelection) {
    setSelections((current) =>
      current.some((s) => s.type === suggestion.type && s.id === suggestion.id)
        ? current
        : [...current, suggestion],
    );
    setSearchText("");
    setSuggestionsOpen(false);
  }

  function removeSelection(selection: SearchSelection) {
    setSelections((current) => current.filter((s) => !(s.type === selection.type && s.id === selection.id)));
  }

  useEffect(() => {
    function onClickOutside(event: MouseEvent) {
      if (searchWrapRef.current && !searchWrapRef.current.contains(event.target as Node)) {
        setSuggestionsOpen(false);
      }
    }
    document.addEventListener("mousedown", onClickOutside);
    return () => document.removeEventListener("mousedown", onClickOutside);
  }, []);

  // --- auto-zoom: refocus the map whenever the filter signature changes ---
  const hasActiveFilters = team !== ALL || country !== ALL || league !== ALL || selections.length > 0;
  const filterSignature = `${team}|${country}|${league}|${selections.map((s) => s.id).join(",")}`;
  useEffect(() => {
    focusId.current += 1;
    if (hasActiveFilters && filteredCities.length > 0) {
      setFocus({ id: focusId.current, bounds: boundsForCities(filteredCities) });
    } else {
      setFocus({ id: focusId.current, bounds: null });
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [filterSignature]);

  useEffect(() => {
    if (selectedCityKey && !filteredCities.some((city) => city.city_key === selectedCityKey)) {
      setSelectedCityKey(null);
    }
  }, [filteredCities, selectedCityKey]);

  const selectedCity = filteredCities.find((city) => city.city_key === selectedCityKey) ?? null;
  const selectedClubs = selectedCity
    ? getClubsForCity(selectedCity.city_key).filter((club) => matchingClubIds.has(club.club_id))
    : [];

  function clearFilters() {
    setTeam(ALL);
    setCountry(ALL);
    setLeague(ALL);
    setSearchText("");
    setSelections([]);
  }

  const activeChips: { key: string; label: string; onRemove: () => void }[] = [
    ...(team !== ALL ? [{ key: "team", label: `Team: ${team}`, onRemove: () => setTeam(ALL) }] : []),
    ...(country !== ALL
      ? [{ key: "country", label: `Club country: ${country}`, onRemove: () => setCountry(ALL) }]
      : []),
    ...(league !== ALL ? [{ key: "league", label: `League: ${league}`, onRemove: () => setLeague(ALL) }] : []),
    ...selections.map((selection) => ({
      key: `${selection.type}-${selection.id}`,
      label: `${selection.type === "club" ? "Club" : "Player"}: ${selection.label}`,
      onRemove: () => removeSelection(selection),
    })),
  ];

  const cityDrawer = selectedCity ? (
    <aside
      className="map-drawer"
      role="dialog"
      aria-label={`Clubs and players in ${selectedCity.city}, ${selectedCity.country}`}
    >
      <header className="map-drawer-head">
        <div>
          <p className="eyebrow">Selected city</p>
          <p className="map-drawer-title">
            <CountryFlag country={selectedCity.country} /> {selectedCity.city}
          </p>
          <p className="map-drawer-sub">
            {selectedClubs.length} club{selectedClubs.length === 1 ? "" : "s"} shown
          </p>
        </div>
        <button
          type="button"
          className="map-drawer-close"
          onClick={() => setSelectedCityKey(null)}
          aria-label="Close city details"
        >
          ×
        </button>
      </header>
      <div className="map-drawer-body">
        {selectedClubs.map((club) => {
          const clubPlayers = getPlayersForClub(club.club_id).filter(
            (player) => team === ALL || getTeamForPlayer(player.player_id)?.team === team,
          );
          return (
            <article key={club.club_id} className="club-card">
              <h4>{club.club_name}</h4>
              <p className="club-card-meta">
                {club.league ?? "League pending"} &middot; {club.country ?? "—"}
                {club.stadium ? ` · ${club.stadium}` : ""}
              </p>
              {clubPlayers.length > 0 ? (
                <div className="player-chip-list">
                  {clubPlayers.map((player) => {
                    const playerTeam = getTeamForPlayer(player.player_id);
                    return (
                      <PlayerLink key={player.player_id} playerId={player.player_id} className="player-chip">
                        {player.display_name}
                        {playerTeam ? ` · ${playerTeam.team}` : ""}
                      </PlayerLink>
                    );
                  })}
                </div>
              ) : (
                <p className="city-detail-empty">
                  No players here match the current national-team filter.
                </p>
              )}
            </article>
          );
        })}
      </div>
    </aside>
  ) : null;

  return (
    <div className="page-stack">
      <PageHeader
        eyebrow="Players & clubs"
        title="The club map"
        intro="One bubble per country in the world view — click a bubble or zoom in to reveal club cities, then pick a city to see who plays there. Filters and search narrow the map and zoom it to the matching region."
      />

      <SummaryRow
        items={[
          { key: "players", label: "Players", value: activePlayers.length.toLocaleString() },
          { key: "clubs", label: "Clubs", value: clubs.length },
          { key: "cities", label: "Cities", value: cities.length },
          { key: "teams", label: "Teams", value: teams.length },
        ]}
      />

      <div className="club-map-layout reveal">
        <aside className="club-map-sidebar">
          <div className="club-map-sidebar-head">
            <h2 className="section-heading">Filters</h2>
            <button
              type="button"
              className="filter-toggle"
              aria-expanded={filtersOpen}
              aria-controls="club-map-filters"
              onClick={() => setFiltersOpen((open) => !open)}
            >
              {filtersOpen ? "Hide" : "Show"} filters
              {activeChips.length > 0 ? <span className="filter-toggle-count">{activeChips.length}</span> : null}
            </button>
          </div>
          <div
            id="club-map-filters"
            className={filtersOpen ? "club-map-filters club-map-filters-open" : "club-map-filters"}
          >
            <FilterGroup label="National team">
              <select value={team} onChange={(event) => setTeam(event.target.value)}>
                <option value={ALL}>All teams</option>
                {teamOptions.map((name) => (
                  <option key={name} value={name}>
                    {name}
                  </option>
                ))}
              </select>
            </FilterGroup>
            <FilterGroup label="Club country">
              <select value={country} onChange={(event) => setCountry(event.target.value)}>
                <option value={ALL}>All countries</option>
                {countryOptions.map((name) => (
                  <option key={name} value={name}>
                    {name}
                  </option>
                ))}
              </select>
            </FilterGroup>
            <FilterGroup label="League">
              <select value={league} onChange={(event) => setLeague(event.target.value)}>
                <option value={ALL}>All leagues</option>
                {leagueOptions.map((name) => (
                  <option key={name} value={name}>
                    {name}
                  </option>
                ))}
              </select>
            </FilterGroup>
            <div className="filter-field search-field" ref={searchWrapRef}>
              <span>Club or player search</span>
              <input
                type="text"
                value={searchText}
                onChange={(event) => {
                  setSearchText(event.target.value);
                  setSuggestionsOpen(true);
                }}
                onFocus={() => setSuggestionsOpen(true)}
                onKeyDown={(event) => {
                  if (event.key === "Enter" && suggestions.length > 0) {
                    event.preventDefault();
                    addSelection(suggestions[0]);
                  }
                }}
                placeholder="e.g. Real Madrid or Mbappe"
              />
              {suggestionsOpen && suggestions.length > 0 ? (
                <ul className="suggestion-list">
                  {suggestions.map((suggestion, index) => (
                    <li key={`${suggestion.type}-${suggestion.id}`}>
                      <button
                        type="button"
                        className={index === 0 ? "suggestion suggestion-top" : "suggestion"}
                        onClick={() => addSelection(suggestion)}
                      >
                        <span>{suggestion.label}</span>
                        <span className="suggestion-hint">
                          {suggestion.type === "club" ? "Club" : "Player"} · {suggestion.hint}
                        </span>
                      </button>
                    </li>
                  ))}
                </ul>
              ) : null}
            </div>
          </div>
        </aside>

        <div className="club-map-main">
          <div className="club-map-bar">
            <div className="active-filter-row">
              {activeChips.length > 0 ? (
                activeChips.map((chip) => (
                  <span key={chip.key} className="filter-chip">
                    {chip.label}
                    <button
                      type="button"
                      className="filter-chip-remove"
                      onClick={chip.onRemove}
                      aria-label={`Remove ${chip.label}`}
                    >
                      ×
                    </button>
                  </span>
                ))
              ) : (
                <span className="results-summary">
                  Showing all {cities.length} city markers.
                </span>
              )}
            </div>
            {hasActiveFilters ? (
              <button type="button" className="button-secondary map-reset" onClick={clearFilters}>
                Reset filters
              </button>
            ) : null}
          </div>

          {activeChips.length > 0 ? (
            <p className="results-summary map-showing">
              Showing {filteredCities.length} of {cities.length} city markers.
            </p>
          ) : null}

          <div className="club-map-stage">
            <div className="map-frame club-map-frame">
              <PlayersClubsMap
                cities={filteredCities}
                selectedCityKey={selectedCityKey}
                onSelectCity={setSelectedCityKey}
                focus={focus}
              />
            </div>
            {cityDrawer}
          </div>

          <div className="map-legend">
            <ChartLegend
              items={[
                { key: "country", color: MAP_COUNTRY_COLOR, label: "Country bubble (zoomed out)", shape: "dot" },
                { key: "city", color: MAP_CITY_COLOR, label: "Club city (zoomed in)", shape: "dot" },
                { key: "active", color: MAP_ACTIVE_COLOR, label: "Selected city", shape: "dot" },
              ]}
            />
            <p className="map-legend-note">Marker size grows with the number of clubs in that country or city.</p>
          </div>

          {filteredCities.length === 0 ? (
            <EmptyState>
              No cities match the current filters — remove one or two chips to widen the search.
            </EmptyState>
          ) : null}

          <Expandable
            summary={`Browse the ${filteredCities.length} matching cities as a list`}
            className="map-list-alt"
          >
            <div className="data-table-wrap">
              <table className="data-table">
                <thead>
                  <tr>
                    <th>City</th>
                    <th>Country</th>
                    <th style={{ textAlign: "right" }}>Clubs</th>
                    <th>Open</th>
                  </tr>
                </thead>
                <tbody>
                  {[...filteredCities]
                    .sort((a, b) => b.club_count - a.club_count || a.city.localeCompare(b.city))
                    .map((city) => (
                      <tr key={city.city_key}>
                        <td>{city.city}</td>
                        <td>
                          <CountryFlag country={city.country} showName />
                        </td>
                        <td style={{ textAlign: "right", fontVariantNumeric: "tabular-nums" }}>
                          {city.club_count}
                        </td>
                        <td>
                          <button
                            type="button"
                            className="link-button"
                            onClick={() => setSelectedCityKey(city.city_key)}
                          >
                            View clubs
                          </button>
                        </td>
                      </tr>
                    ))}
                </tbody>
              </table>
            </div>
          </Expandable>
        </div>
      </div>
    </div>
  );
}
