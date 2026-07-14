import { useMemo, useState } from "react";
import { BarList } from "@/components/bar-list";
import { CountryFlag } from "@/components/country-flag";
import { PlayerLink } from "@/components/player-detail";
import {
  PageHeader,
  SummaryRow,
  SortableTable,
  EmptyState,
  FilterGroup,
  type Column,
} from "@/components/ui";
import {
  confederations,
  getCoachForTeam,
  getConfederationForCountry,
  getPlayerStat,
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
const CONFED_NAME = new Map(confederations.map((confed) => [confed.code, confed.name]));
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

function rosterMinutes(row: RosterRow): number | null {
  const stat = row.player ? getPlayerStat(row.player.player_id) : undefined;
  return stat ? stat.minutes_played : null;
}

export function NationalTeamsRoute() {
  const [teamQuery, setTeamQuery] = useState("");
  const [confedFilter, setConfedFilter] = useState(ALL_CONFEDS);
  const [selectedTeamCode, setSelectedTeamCode] = useState(teams[0]?.team_code ?? null);

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

  // Group by confederation only when the user isn't actively searching/filtering.
  const grouped = teamQuery.trim() === "" && confedFilter === ALL_CONFEDS;
  const teamGroups = useMemo(() => {
    if (!grouped) {
      return [{ code: null as string | null, teams: filteredTeams }];
    }
    const byCode = new Map<string, typeof filteredTeams>();
    for (const team of filteredTeams) {
      const code = getConfederationForCountry(team.team) ?? "Other";
      const bucket = byCode.get(code);
      if (bucket) {
        bucket.push(team);
      } else {
        byCode.set(code, [team]);
      }
    }
    return Array.from(byCode.entries())
      .sort((a, b) => a[0].localeCompare(b[0]))
      .map(([code, list]) => ({ code, teams: list }));
  }, [filteredTeams, grouped]);

  const selectedTeam = teams.find((team) => team.team_code === selectedTeamCode) ?? null;
  const selectedCoach = selectedTeam ? getCoachForTeam(selectedTeam.team_code) : null;
  const selectedTeamStat = selectedTeam ? getTeamStat(selectedTeam.team_code) : null;

  const roster = useMemo(
    () => (selectedTeam ? getSquadRosterForTeam(selectedTeam.team_code) : []),
    [selectedTeam],
  );

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
        flagCountry: country === "Unknown club location" ? undefined : country,
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
  const totalCaps = useMemo(
    () => roster.reduce((sum, row) => sum + (row.entry.caps_pre_tournament ?? 0), 0),
    [roster],
  );
  const totalMinutes = useMemo(
    () => roster.reduce((sum, row) => sum + (rosterMinutes(row) ?? 0), 0),
    [roster],
  );
  const averageAge = useMemo(() => {
    const ages = roster
      .map((row) => kickoffAge(row.player?.date_of_birth ?? null))
      .filter((age): age is number => age !== null);
    return ages.length ? ages.reduce((sum, age) => sum + age, 0) / ages.length : null;
  }, [roster]);

  const selectedConfed = selectedTeam ? getConfederationForCountry(selectedTeam.team) : undefined;

  const columns: Column<RosterRow>[] = [
    {
      key: "player",
      label: "Player",
      width: "20%",
      sortValue: (row) => row.player?.display_name ?? row.entry.display_name_at_source,
      render: (row) => (
        <>
          {row.player ? (
            <PlayerLink playerId={row.player.player_id}>{row.player.display_name}</PlayerLink>
          ) : (
            row.entry.display_name_at_source
          )}
          {row.entry.is_captain ? <span className="captain-badge"> C</span> : null}
        </>
      ),
    },
    {
      key: "position",
      label: "Pos",
      width: "11%",
      sortValue: (row) => POSITION_ORDER[row.entry.position_group ?? ""] ?? 99,
      render: (row) => formatPosition(row.entry.position_group),
    },
    {
      key: "shirt",
      label: "#",
      width: "5%",
      align: "right",
      sortValue: (row) => row.entry.shirt_number ?? 999,
      render: (row) => row.entry.shirt_number ?? "—",
    },
    {
      key: "born",
      label: "Born",
      width: "12%",
      sortValue: (row) => row.player?.birth_country ?? "",
      render: (row) =>
        row.player?.birth_country ? <CountryFlag country={row.player.birth_country} showName /> : "—",
    },
    {
      key: "age",
      label: "Age",
      width: "6%",
      align: "right",
      initialAsc: false,
      sortValue: (row) => kickoffAge(row.player?.date_of_birth ?? null) ?? -1,
      render: (row) => {
        const age = kickoffAge(row.player?.date_of_birth ?? null);
        return age !== null ? Math.floor(age) : "—";
      },
    },
    {
      key: "caps",
      label: "Caps",
      width: "6%",
      align: "right",
      initialAsc: false,
      sortValue: (row) => row.entry.caps_pre_tournament ?? -1,
      render: (row) => row.entry.caps_pre_tournament ?? "—",
    },
    {
      key: "minutes",
      label: "Min",
      width: "7%",
      align: "right",
      initialAsc: false,
      sortValue: (row) => rosterMinutes(row) ?? -1,
      render: (row) => {
        const min = rosterMinutes(row);
        return min !== null ? min.toLocaleString() : "—";
      },
    },
    {
      key: "club",
      label: "Club",
      width: "16%",
      sortValue: (row) => row.club?.club_name ?? "",
      render: (row) => row.club?.club_name ?? "Unknown",
    },
    {
      key: "league",
      label: "League",
      width: "11%",
      sortValue: (row) => row.club?.league ?? "",
      render: (row) => row.club?.league ?? "—",
    },
    {
      key: "country",
      label: "Country",
      width: "12%",
      sortValue: (row) => row.club?.country ?? "",
      render: (row) => (row.club?.country ? <CountryFlag country={row.club.country} showName /> : "—"),
    },
  ];

  return (
    <div className="page-stack">
      <PageHeader
        eyebrow="National teams"
        title="All 48 squads"
        intro="Pick any World Cup 2026 squad to see its full roster, coach, each player's club, and how far the team went in the tournament."
      />

      <section className="content-panel reveal">
        <div className="team-picker-header">
          <div className="panel-heading">
            <p className="eyebrow">{teams.length} squads</p>
            <h2 className="section-heading">Choose a team</h2>
          </div>
          <div className="team-picker-controls">
            <FilterGroup label="Search">
              <input
                type="text"
                value={teamQuery}
                onChange={(event) => setTeamQuery(event.target.value)}
                placeholder="Search teams…"
              />
            </FilterGroup>
            <FilterGroup label="Confederation">
              <select value={confedFilter} onChange={(event) => setConfedFilter(event.target.value)}>
                <option value={ALL_CONFEDS}>All confederations</option>
                {CONFED_CODES.map((code) => (
                  <option key={code} value={code}>
                    {code}
                  </option>
                ))}
              </select>
            </FilterGroup>
          </div>
        </div>

        {filteredTeams.length === 0 ? (
          <EmptyState>No teams match your search.</EmptyState>
        ) : (
          teamGroups.map((group) => (
            <div key={group.code ?? "all"} className="team-group">
              {group.code ? (
                <h3 className="team-group-heading">
                  {group.code}
                  <span className="team-group-sub">
                    {CONFED_NAME.get(group.code) ?? "Other"} · {group.teams.length} team
                    {group.teams.length === 1 ? "" : "s"}
                  </span>
                </h3>
              ) : null}
              <ul className="team-grid">
                {group.teams.map((team) => (
                  <li key={team.team_code}>
                    <button
                      type="button"
                      className={
                        team.team_code === selectedTeamCode ? "team-card team-card-active" : "team-card"
                      }
                      onClick={() => setSelectedTeamCode(team.team_code)}
                      aria-pressed={team.team_code === selectedTeamCode}
                    >
                      <CountryFlag country={team.team} />
                      <span className="team-card-name">{team.team}</span>
                      <span className="team-card-code">{team.team_code}</span>
                    </button>
                  </li>
                ))}
              </ul>
            </div>
          ))
        )}
      </section>

      {selectedTeam ? (
        <>
          <section className="content-panel reveal">
            <div className="squad-header">
              <h2 className="squad-title">
                <CountryFlag country={selectedTeam.team} />
                {selectedTeam.team}
                <span className="team-card-code">{selectedTeam.team_code}</span>
                {selectedConfed ? <span className="confed-badge">{selectedConfed}</span> : null}
              </h2>
              <SummaryRow
                items={[
                  {
                    key: "coach",
                    label: "Coach",
                    value: selectedCoach ? (
                      <>
                        {selectedCoach.coach_name}
                        {selectedCoach.coach_nationality &&
                        selectedCoach.coach_nationality !== selectedTeam.team
                          ? ` (${selectedCoach.coach_nationality})`
                          : ""}
                      </>
                    ) : (
                      "—"
                    ),
                  },
                  {
                    key: "stage",
                    label: "Reached",
                    value: selectedTeamStat?.stage_reached ?? "—",
                  },
                  {
                    key: "age",
                    label: "Avg age",
                    value: averageAge !== null ? averageAge.toFixed(1) : "—",
                  },
                  { key: "caps", label: "Total caps", value: totalCaps.toLocaleString() },
                  {
                    key: "minutes",
                    label: "Squad minutes",
                    value: totalMinutes > 0 ? totalMinutes.toLocaleString() : "—",
                  },
                  { key: "clubs", label: "Clubs", value: clubCount },
                  { key: "countries", label: "Club countries", value: countryCount },
                ]}
              />
            </div>
          </section>

          <section className="content-panel reveal">
            <h2 className="section-heading">Full roster</h2>

            {/* Desktop: compact sortable table with a sticky header. */}
            <div className="squad-roster-desktop">
              <SortableTable
                columns={columns}
                rows={roster}
                getRowKey={(row) => row.entry.squad_entry_id}
                initialSortKey="position"
                caption={`${selectedTeam.team} roster`}
                className="squad-roster"
              />
            </div>

            {/* Mobile: player cards instead of a squeezed table. */}
            <ul className="squad-roster-cards">
              {roster.map((row) => {
                const age = kickoffAge(row.player?.date_of_birth ?? null);
                const minutes = rosterMinutes(row);
                return (
                  <li key={row.entry.squad_entry_id} className="squad-player-card">
                    <div className="squad-player-top">
                      <span className="squad-player-name">
                        {row.player ? (
                          <PlayerLink playerId={row.player.player_id}>
                            {row.player.display_name}
                          </PlayerLink>
                        ) : (
                          row.entry.display_name_at_source
                        )}
                        {row.entry.is_captain ? <span className="captain-badge"> C</span> : null}
                      </span>
                      <span className="squad-player-shirt">
                        {row.entry.shirt_number != null ? `#${row.entry.shirt_number}` : ""}
                      </span>
                    </div>
                    <p className="squad-player-meta">
                      {formatPosition(row.entry.position_group)}
                      {age !== null ? ` · ${Math.floor(age)} yrs` : ""}
                      {row.entry.caps_pre_tournament != null
                        ? ` · ${row.entry.caps_pre_tournament} caps`
                        : ""}
                      {minutes !== null ? ` · ${minutes.toLocaleString()} min` : ""}
                    </p>
                    <p className="squad-player-meta">
                      {row.player?.birth_country ? (
                        <>
                          Born <CountryFlag country={row.player.birth_country} showName />
                          {" · "}
                        </>
                      ) : null}
                      {row.club?.club_name ?? "Unknown club"}
                      {row.club?.country ? (
                        <>
                          {" "}
                          <CountryFlag country={row.club.country} />
                        </>
                      ) : null}
                    </p>
                  </li>
                );
              })}
            </ul>

            <h3 className="subsection-heading">Where this squad plays club football</h3>
            <p className="insight-note">
              {selectedTeam.team} in the accent color, every other club country in gray.
            </p>
            <BarList items={clubCountryBreakdown} mode="emphasis" />
          </section>
        </>
      ) : (
        <section className="content-panel reveal">
          <EmptyState>Choose a team to see its squad.</EmptyState>
        </section>
      )}
    </div>
  );
}
