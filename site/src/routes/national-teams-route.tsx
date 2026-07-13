import { useMemo, useState } from "react";
import {
  getCoachForTeam,
  getConfederationForCountry,
  getSquadRosterForTeam,
  getTeamStat,
  teams,
} from "@/lib/data";

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

type SortKey = "player" | "position" | "shirt" | "caps" | "club" | "league" | "country";

const SORT_ACCESSORS: Record<SortKey, (row: RosterRow) => string | number> = {
  player: (row) => row.player?.display_name ?? row.entry.display_name_at_source,
  position: (row) => POSITION_ORDER[row.entry.position_group ?? ""] ?? 99,
  shirt: (row) => row.entry.shirt_number ?? 999,
  caps: (row) => row.entry.caps_pre_tournament ?? -1,
  club: (row) => row.club?.club_name ?? "",
  league: (row) => row.club?.league ?? "",
  country: (row) => row.club?.country ?? "",
};

const COLUMNS: { key: SortKey; label: string }[] = [
  { key: "player", label: "Player" },
  { key: "position", label: "Position" },
  { key: "shirt", label: "#" },
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

      <div className="national-teams-grid reveal">
        <article className="content-panel compact-panel">
          <div className="panel-heading">
            <p className="eyebrow">{teams.length} squads</p>
            <h3>Choose a team</h3>
          </div>
          <input
            type="text"
            className="team-search"
            value={teamQuery}
            onChange={(event) => setTeamQuery(event.target.value)}
            placeholder="Search teams…"
          />
          <label className="filter-field confed-filter">
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
          <div className="team-list team-list-full">
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
        </article>

        <article className="content-panel">
          {selectedTeam ? (
            <>
              <div className="panel-heading">
                <p className="eyebrow">Squad</p>
                <h3>
                  {selectedTeam.team} <span className="team-button-code">{selectedTeam.team_code}</span>
                </h3>
                {selectedCoach ? (
                  <p className="insight-note">
                    Coach: <strong>{selectedCoach.coach_name}</strong>
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

              <div className="metrics-grid metrics-grid-centered">
                <article className="metric-card">
                  <p className="metric-label">Squad size</p>
                  <p className="metric-value">{roster.length}</p>
                </article>
                <article className="metric-card">
                  <p className="metric-label">Clubs represented</p>
                  <p className="metric-value">{clubCount}</p>
                </article>
                <article className="metric-card">
                  <p className="metric-label">Club countries</p>
                  <p className="metric-value">{countryCount}</p>
                </article>
              </div>

              <div className="data-table-wrap">
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
                    {roster.map(({ entry, player, club }) => (
                      <tr key={entry.squad_entry_id}>
                        <td>
                          {player?.display_name ?? entry.display_name_at_source}
                          {entry.is_captain ? <span className="captain-badge"> C</span> : null}
                        </td>
                        <td>{formatPosition(entry.position_group)}</td>
                        <td>{entry.shirt_number ?? "—"}</td>
                        <td>{entry.caps_pre_tournament ?? "—"}</td>
                        <td>{club?.club_name ?? "Unknown"}</td>
                        <td>{club?.league ?? "—"}</td>
                        <td>{club?.country ?? "—"}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </>
          ) : (
            <p className="city-detail-empty">Choose a team to see its squad.</p>
          )}
        </article>
      </div>
    </div>
  );
}
