import { useEffect, useMemo, useRef, useState } from "react";
import { PlayersClubsMap, boundsForCities, type MapFocus } from "@/components/players-clubs-map";
import {
  activePlayers,
  cities,
  clubs,
  getClubsForCity,
  getPlayersForClub,
  getTeamForPlayer,
  getTeamsForClub,
  teams,
  type Club,
} from "@/lib/data";

const ALL = "all";

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
  const suggestions = useMemo<Suggestion[]>(() => {
    const query = searchText.trim().toLowerCase();
    if (query.length < 2) {
      return [];
    }
    const out: Suggestion[] = [];
    for (const club of clubs) {
      if (
        club.club_name.toLowerCase().includes(query) ||
        club.club_name_ascii.toLowerCase().includes(query)
      ) {
        out.push({ type: "club", id: club.club_id, label: club.club_name, hint: club.country ?? "club" });
        if (out.length >= 8) {
          return out;
        }
      }
    }
    for (const player of activePlayers) {
      if (
        player.display_name.toLowerCase().includes(query) ||
        player.name_ascii.toLowerCase().includes(query)
      ) {
        const playerTeam = getTeamForPlayer(player.player_id);
        out.push({
          type: "player",
          id: player.player_id,
          label: player.display_name,
          hint: playerTeam?.team ?? "player",
        });
        if (out.length >= 8) {
          return out;
        }
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

  return (
    <div className="page-stack">
      <section className="content-panel centered-panel reveal">
        <div className="panel-heading">
          <p className="eyebrow">Players &amp; clubs</p>
          <h2>The club map</h2>
        </div>
        <p className="panel-intro">
          The world view shows one bubble per country — click a bubble or zoom (buttons or
          mouse wheel) to reveal club cities, then click a city dot to see who plays there.
          Filters and search narrow the map and zoom it to the matching region.
        </p>
      </section>

      <section className="metrics-grid reveal">
        <article className="metric-card">
          <p className="metric-label">Players loaded</p>
          <p className="metric-value">{activePlayers.length}</p>
        </article>
        <article className="metric-card">
          <p className="metric-label">Clubs loaded</p>
          <p className="metric-value">{clubs.length}</p>
        </article>
        <article className="metric-card">
          <p className="metric-label">Cities loaded</p>
          <p className="metric-value">{cities.length}</p>
        </article>
        <article className="metric-card">
          <p className="metric-label">Teams loaded</p>
          <p className="metric-value">{teams.length}</p>
        </article>
      </section>

      <section className="content-panel reveal">
        <div className="panel-heading">
          <p className="eyebrow">Filters</p>
          <h3>Narrow the map</h3>
        </div>
        <div className="filter-bar">
          <label className="filter-field">
            <span>National team</span>
            <select value={team} onChange={(event) => setTeam(event.target.value)}>
              <option value={ALL}>All teams</option>
              {teamOptions.map((name) => (
                <option key={name} value={name}>
                  {name}
                </option>
              ))}
            </select>
          </label>
          <label className="filter-field">
            <span>Club country</span>
            <select value={country} onChange={(event) => setCountry(event.target.value)}>
              <option value={ALL}>All countries</option>
              {countryOptions.map((name) => (
                <option key={name} value={name}>
                  {name}
                </option>
              ))}
            </select>
          </label>
          <label className="filter-field">
            <span>League</span>
            <select value={league} onChange={(event) => setLeague(event.target.value)}>
              <option value={ALL}>All leagues</option>
              {leagueOptions.map((name) => (
                <option key={name} value={name}>
                  {name}
                </option>
              ))}
            </select>
          </label>
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

        {activeChips.length > 0 ? (
          <div className="active-filter-row">
            {activeChips.map((chip) => (
              <span key={chip.key} className="filter-chip">
                {chip.label}
                <button type="button" className="filter-chip-remove" onClick={chip.onRemove} aria-label={`Remove ${chip.label}`}>
                  ×
                </button>
              </span>
            ))}
            <button type="button" className="link-button" onClick={clearFilters}>
              Clear all
            </button>
          </div>
        ) : null}

        <p className="results-summary">
          Showing {filteredCities.length} of {cities.length} city markers.
        </p>
      </section>

      <section className="content-panel reveal">
        <div className="panel-heading">
          <p className="eyebrow">Club map</p>
          <h3>
            {filteredCities.length} cit{filteredCities.length === 1 ? "y" : "ies"} on the map
          </h3>
        </div>

        <div className="map-frame">
          <PlayersClubsMap
            cities={filteredCities}
            selectedCityKey={selectedCityKey}
            onSelectCity={setSelectedCityKey}
            focus={focus}
          />
        </div>
        {filteredCities.length === 0 ? (
          <p className="city-detail-empty">
            No cities match the current filters — remove one or two chips above to widen the search.
          </p>
        ) : null}

        {selectedCity ? (
          <div className="club-card-list">
            <p className="selected-city-label">
              {selectedCity.city}, {selectedCity.country}
            </p>
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
                          <span key={player.player_id} className="player-chip">
                            {player.display_name}
                            {playerTeam ? ` · ${playerTeam.team}` : ""}
                          </span>
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
        ) : filteredCities.length > 0 ? (
          <p className="city-detail-empty">Click a marker to see its clubs and players.</p>
        ) : null}
      </section>
    </div>
  );
}
