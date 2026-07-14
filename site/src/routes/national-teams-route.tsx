import { useMemo, useState } from "react";
import { BarList } from "@/components/bar-list";
import { PlayerLink } from "@/components/player-detail";
import {
  getCoachForTeam,
  getConfederationForCountry,
  getSquadRosterForTeam,
  getTeamStat,
  teams,
  TEAM_COUNTRY_ALIASES,
} from "@/lib/data";

const TOURNAMENT_START = new Date("2026-06-11T00:00:00Z");

function kickoffAge(dateOfBirth: string | null): number | null {
  if (!dateOfBirth) {
    return null;
  }
  const dob = new Date(dateOfBirth);
  if (Number.isNaN(dob.getTime())) {
    return null;
  }
  return (TOURNAMENT_START.getTime() - dob.getTime()) / (1000 * 60 * 60 * 24 * 365.25);
}

const ALL_CONFEDS = "all";
const CONFED_CODES = Array.from(
  new Set(teams.map((team) => getConfederationForCountry(team.team)).filter((code): code is string => Boolean(code))),
).sort((a, b) => a.localeCompare(b));

const POSITION_ORDER: Record<string, number> = {
  goalkeeper: 0,
  defender: 1,
  midfielder: 2,
  forward: 3,
};

function formatPosition(position: string | null): string {
  if (!position) {
    return "Unknown";
  }
  return position.charAt(0).toUpperCase() + position.slice(1);
}

type RosterRow = ReturnType<typeof getSquadRosterForTeam>[number];

type SortKey =
  | "player"
  | "position"
  | "shirt"
  | "born"
  | "age"
  | "caps"
  | "club"
  | "league"
  | "country";

const SORT_ACCESSORS: Record<SortKey, (row: RosterRow) => string | number> = {
  player: (row) => row.player?.display_name ?? row.entry.display_name_at_source,
  position: (row) => POSITION_ORDER[row.entry.position_group ?? ""] ?? 99,
  shirt: (row) => row.entry.shirt_number ?? 999,
  born: (row) => row.player?.birth_country ?? "",
  age: (row) => kickoffAge(row.player?.date_of_birth ?? null) ?? -1,
  caps: (row) => row.entry.caps_pre_tournament ?? -1,
  club: (row) => row.club?.club_name ?? "",
  league: (row) => row.club?.league ?? "",
  country: (row) => row.club?.country ?? "",
};

const COLUMNS: { key: SortKey; label: string }[] = [
  { key: "player", label: "Player" },
  { key: "position", label: "Position" },
  { key: "shirt", label: "#" },
  { key: "born", label: "Born" },
  { key: "age", label: "Age" },
  { key: "caps", label: "Caps" },
  { key: "club", label: "Club" },
  { key: "league", label: "League" },
  { key: "country", label: "Country" },
];

export function NationalTeamsRoute() {
  const [teamQuery, setTeamQuery] = useState("");
  const [confedFilter, setConfedFilter] = useState(ALL_CONFEDS);
  const [selectedTeamCode, setSelectedTeamCode] = useState(teams[0]?.team_code ?? null);
  const [sortKey, setSortKey] = useState<SortKey>("position");
  const [sortAsc, setSortAsc] = useState(true);

  const filteredTeams = useMemo(() => {
    const query = teamQuery.trim().toLowerCase();
    return teams.filter((team) => {
      if (confedFilter !== ALL_CONFEDS && getConfederationForCountry(team.team) !== confedFilter) {
        return false;
      }
      if (!query) {
        return true;
      }
      return team.team.toLowerCase().includes(query) || team.team_code.toLowerCase().includes(query);
    });
  }, [teamQuery, confedFilter]);

  const selectedTeam = teams.find((team) => team.team_code === selectedTeamCode) ?? null;
  const selectedCoach = selectedTeam ? getCoachForTeam(selectedTeam.team_code) : null;
  const selectedTeamStat = selectedTeam ? getTeamStat(selectedTeam.team_code) : null;

  const roster = useMemo(() => {
    if (!selectedTeam) {
      return [];
    }
    const accessor = SORT_ACCESSORS[sortKey];
    return [...getSquadRosterForTeam(selectedTeam.team_code)].sort((a, b) => {
      const valueA = accessor(a);
      const valueB = accessor(b);
      const compared =
        typeof valueA === "number" && typeof valueB === "number"
          ? valueA - valueB
          : String(valueA).localeCompare(String(valueB));
      if (compared !== 0) {
        return sortAsc ? compared : -compared;
      }
      const nameA = a.player?.display_name ?? a.entry.display_name_at_source;
      const nameB = b.player?.display_name ?? b.entry.display_name_at_source;
      return nameA.localeCompare(nameB);
    });
  }, [selectedTeam, sortKey, sortAsc]);

  function toggleSort(key: SortKey) {
    if (key === sortKey) {
      setSortAsc((asc) => !asc);
    } else {
      setSortKey(key);
      setSortAsc(true);
    }
  }

  const clubCountryBreakdown = useMemo(() => {
    if (!selectedTeam) {
      return [];
    }
    const counts = new Map<string, number>();
    for (const row of roster) {
      const country = row.club?.country ?? "Unknown club location";
      counts.set(country, (counts.get(country) ?? 0) + 1);
    }
    const aliases = new Set([selectedTeam.team, ...(TEAM_COUNTRY_ALIASES[selectedTeam.team] ?? [])]);
    return Array.from(counts.entries())
      .map(([country, count]) => ({
        key: country,
        label: country,
        value: count,
        emphasized: aliases.has(country),
      }))
      .sort((a, b) => b.value - a.value);
  }, [roster, selectedTeam]);

  const clubCount = useMemo(
    () => new Set(roster.map((row) => row.club?.club_id).filter(Boolean)).size,
    [roster],
  );
  const countryCount = useMemo(
    () => new Set(roster.map((row) => row.club?.country).filter(Boolean)).size,
    [roster],
  );

  return (
    <div className="page-stack">
      <section className="content-panel centered-panel reveal">
        <div className="panel-heading">
          <p className="eyebrow">National teams</p>
          <h2>All 48 squads</h2>
        </div>
        <p className="panel-intro">
          Pick any World Cup 2026 squad to see its full roster, coach, each player's club,
          and how far the team made it in the tournament.
        </p>
      </section>

      <section className="content-panel reveal">
        <div className="team-picker-header">
          <div className="panel-heading">
            <p className="eyebrow">{teams.length} squads</p>
            <h3>Choose a team</h3>
          </div>
          <div className="team-picker-controls">
            <label className="filter-field">
              <span>Search</span>
              <input
                type="text"
                value={teamQuery}
                onChange={(event) => setTeamQuery(event.target.value)}
                placeholder="Search teams…"
              />
            </label>
            <label className="filter-field">
              <span>Confederation</span>
              <select value={confedFilter} onChange={(event) => setConfedFilter(event.target.value)}>
                <option value={ALL_CONFEDS}>All confederations</option>
                {CONFED_CODES.map((code) => (
                  <option key={code} value={code}>
                    {code}
                  </option>
                ))}
              </select>
            </label>
          </div>
        </div>
        <div className="team-list team-list-horizontal">
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
      </section>

      {selectedTeam ? (
        <>
          <section className="content-panel reveal">
            <div className="panel-heading">
              <p className="eyebrow">Selected squad</p>
              <h3>
                {selectedTeam.team} <span className="team-button-code">{selectedTeam.team_code}</span>
              </h3>
            </div>
            <div className="team-info-row">
              <div className="team-info-facts">
                {selectedCoach ? (
                  <p className="insight-note">
                    Coach:{" "}
                    <strong>{selectedCoach.coach_name}</strong>
                    {selectedCoach.coach_nationality &&
                    selectedCoach.coach_nationality !== selectedTeam.team
                      ? ` (${selectedCoach.coach_nationality})`
                      : ""}
                  </p>
                ) : null}
                {selectedTeamStat ? (
                  <p className="insight-note">
                    How far this team made it in the World Cup:{" "}
                    <strong>{selectedTeamStat.stage_reached}</strong>
                  </p>
                ) : null}
              </div>
              <div className="team-info-metrics">
                <article className="metric-card">
                  <p className="metric-label">Clubs represented</p>
                  <p className="metric-value">{clubCount}</p>
                </article>
                <article className="metric-card">
                  <p className="metric-label">Club countries</p>
                  <p className="metric-value">{countryCount}</p>
                </article>
              </div>
            </div>
          </section>

          <section className="content-panel reveal">
            <h3 className="section-heading">Full roster</h3>
            <div className="data-table-wrap squad-table">
              <table className="data-table">
                <thead>
                  <tr>
                    {COLUMNS.map((column) => (
                      <th key={column.key}>
                        <button
                          type="button"
                          className={
                            column.key === sortKey ? "table-sort table-sort-active" : "table-sort"
                          }
                          onClick={() => toggleSort(column.key)}
                        >
                          {column.label}
                          {column.key === sortKey ? (sortAsc ? " ↑" : " ↓") : ""}
                        </button>
                      </th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {roster.map(({ entry, player, club }) => {
                    const age = kickoffAge(player?.date_of_birth ?? null);
                    return (
                      <tr key={entry.squad_entry_id}>
                        <td>
                          {player ? (
                            <PlayerLink playerId={player.player_id}>{player.display_name}</PlayerLink>
                          ) : (
                            entry.display_name_at_source
                          )}
                          {entry.is_captain ? <span className="captain-badge"> C</span> : null}
                        </td>
                        <td>{formatPosition(entry.position_group)}</td>
                        <td>{entry.shirt_number ?? "—"}</td>
                        <td>{player?.birth_country ?? "—"}</td>
                        <td title={player?.date_of_birth ? `Born ${String(player.date_of_birth).slice(0, 10)}` : undefined}>
                          {age !== null ? Math.floor(age) : "—"}
                        </td>
                        <td>{entry.caps_pre_tournament ?? "—"}</td>
                        <td>{club?.club_name ?? "Unknown"}</td>
                        <td>{club?.league ?? "—"}</td>
                        <td>{club?.country ?? "—"}</td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>

            <h4 className="subsection-heading">Where this squad plays club football</h4>
            <p className="insight-note">
              {selectedTeam.team} in the accent color, every other club country in gray.
            </p>
            <BarList items={clubCountryBreakdown} mode="emphasis" />
          </section>
        </>
      ) : (
        <section className="content-panel reveal">
          <p className="city-detail-empty">Choose a team to see its squad.</p>
        </section>
      )}
    </div>
  );
}
