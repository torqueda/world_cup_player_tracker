import { useMemo, useState } from "react";
import { KnockoutBracket } from "@/components/knockout-bracket";
import { CountryFlag } from "@/components/country-flag";
import {
  PageHeader,
  SegmentedControl,
  Expandable,
  EmptyState,
  FilterGroup,
  cx,
} from "@/components/ui";
import { matches, type Match } from "@/lib/data";

const KNOCKOUT_STAGES = [
  "Round of 32",
  "Round of 16",
  "Quarter-final",
  "Semi-final",
  "Play-off for third place",
  "Final",
];

// Deepest → shallowest, for grouping the "All" and "Knockout" views.
const STAGE_ORDER = [
  "Final",
  "Play-off for third place",
  "Semi-final",
  "Quarter-final",
  "Round of 16",
  "Round of 32",
  "First Stage",
];

const STAGE_LABELS: Record<string, string> = {
  "First Stage": "Group stage",
};

const TEAM_PLACEHOLDERS: Record<string, string> = {
  W101: "Winner SF1",
  W102: "Winner SF2",
  RU101: "Loser SF1",
  RU102: "Loser SF2",
};

function teamLabel(name: string): string {
  return TEAM_PLACEHOLDERS[name] ?? name;
}

function isPlaceholder(name: string): boolean {
  return name in TEAM_PLACEHOLDERS;
}

function stageLabel(stage: string): string {
  return STAGE_LABELS[stage] ?? stage;
}

function formatDate(value: string): string {
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) {
    return value;
  }
  return date.toLocaleDateString("en-US", {
    weekday: "short",
    month: "short",
    day: "numeric",
    year: "numeric",
  });
}

function scoreText(match: Match): string {
  if (match.status !== "played") {
    return "vs";
  }
  return `${match.home_score} – ${match.away_score}`;
}

function pensText(match: Match): string | null {
  if (match.status === "played" && match.home_pens !== null && match.away_pens !== null) {
    return `${match.home_pens}–${match.away_pens} pens`;
  }
  return null;
}

function winnerSide(match: Match): "home" | "away" | null {
  if (match.status !== "played" || match.home_score === null || match.away_score === null) {
    return null;
  }
  if (match.home_score !== match.away_score) {
    return match.home_score > match.away_score ? "home" : "away";
  }
  if (match.home_pens !== null && match.away_pens !== null && match.home_pens !== match.away_pens) {
    return match.home_pens > match.away_pens ? "home" : "away";
  }
  return null;
}

function TeamSide({ name, side }: { name: string; side: "home" | "away" }) {
  const flag = isPlaceholder(name) ? null : <CountryFlag country={name} />;
  return (
    <>
      {side === "away" && flag}
      <span className="score-team-name">{teamLabel(name)}</span>
      {side === "home" && flag}
    </>
  );
}

function MatchRow({ match }: { match: Match }) {
  const winner = winnerSide(match);
  const pens = pensText(match);
  const upcoming = match.status !== "played";
  return (
    <article className={cx("score-row", upcoming && "score-row-upcoming")}>
      <div className="score-line">
        <span className={cx("score-team score-team-home", winner === "home" && "score-team-win")}>
          <TeamSide name={match.home_team} side="home" />
        </span>
        <span className="score-mid">
          <span className="score-value">{scoreText(match)}</span>
          {pens ? <span className="score-pens">{pens}</span> : null}
        </span>
        <span className={cx("score-team score-team-away", winner === "away" && "score-team-win")}>
          <TeamSide name={match.away_team} side="away" />
        </span>
      </div>
      <p className="score-meta">
        {stageLabel(match.stage)}
        {match.group ? ` · ${match.group}` : ""} · {formatDate(match.match_date)} · {match.stadium} (
        {match.city})
      </p>
    </article>
  );
}

function byDateDesc(a: Match, b: Match): number {
  return new Date(b.match_date).getTime() - new Date(a.match_date).getTime();
}

function byDateAsc(a: Match, b: Match): number {
  return new Date(a.match_date).getTime() - new Date(b.match_date).getTime();
}

type View = "upcoming" | "knockout" | "groups" | "all";

const ALL = "all";

// Option lists derived once from the data.
const realTeamNames = Array.from(
  new Set(
    matches
      .flatMap((m) => [m.home_team, m.away_team])
      .filter((name) => !isPlaceholder(name)),
  ),
).sort((a, b) => a.localeCompare(b));

const cityNames = Array.from(new Set(matches.map((m) => m.city))).sort((a, b) => a.localeCompare(b));

const playedCount = matches.filter((m) => m.status === "played").length;
const scheduledCount = matches.filter((m) => m.status === "scheduled").length;
const knockoutCount = matches.filter((m) => KNOCKOUT_STAGES.includes(m.stage)).length;
const groupCount = matches.filter((m) => m.stage === "First Stage").length;

export function MatchesRoute() {
  const [view, setView] = useState<View>(scheduledCount > 0 ? "upcoming" : "all");
  const [teamFilter, setTeamFilter] = useState(ALL);
  const [venueFilter, setVenueFilter] = useState(ALL);
  const [dateFilter, setDateFilter] = useState(ALL);
  const [statusFilter, setStatusFilter] = useState(ALL);

  // Dates available in the currently-viewed slice, so the picker never offers a
  // date with nothing behind it.
  const baseForView = useMemo(() => {
    switch (view) {
      case "upcoming":
        return matches.filter((m) => m.status === "scheduled");
      case "knockout":
        return matches.filter((m) => KNOCKOUT_STAGES.includes(m.stage));
      case "groups":
        return matches.filter((m) => m.stage === "First Stage");
      default:
        return matches;
    }
  }, [view]);

  const dateOptions = useMemo(
    () => Array.from(new Set(baseForView.map((m) => m.match_date))).sort(),
    [baseForView],
  );

  const filtered = useMemo(() => {
    return baseForView.filter((m) => {
      if (teamFilter !== ALL && m.home_team !== teamFilter && m.away_team !== teamFilter) {
        return false;
      }
      if (venueFilter !== ALL && m.city !== venueFilter) {
        return false;
      }
      if (dateFilter !== ALL && m.match_date !== dateFilter) {
        return false;
      }
      if (statusFilter !== ALL && m.status !== statusFilter) {
        return false;
      }
      return true;
    });
  }, [baseForView, teamFilter, venueFilter, dateFilter, statusFilter]);

  const hasFilters =
    teamFilter !== ALL || venueFilter !== ALL || dateFilter !== ALL || statusFilter !== ALL;

  function resetFilters() {
    setTeamFilter(ALL);
    setVenueFilter(ALL);
    setDateFilter(ALL);
    setStatusFilter(ALL);
  }

  // Group filtered matches for the "groups" and "all" views.
  const byGroup = useMemo(() => {
    const map = new Map<string, Match[]>();
    for (const m of filtered) {
      const key = m.group ?? "Group ?";
      (map.get(key) ?? map.set(key, []).get(key)!).push(m);
    }
    return Array.from(map.entries()).sort(([a], [b]) => a.localeCompare(b));
  }, [filtered]);

  const byStage = useMemo(() => {
    const map = new Map<string, Match[]>();
    for (const m of filtered) {
      (map.get(m.stage) ?? map.set(m.stage, []).get(m.stage)!).push(m);
    }
    return STAGE_ORDER.filter((stage) => map.has(stage)).map((stage) => ({
      stage,
      matches: (map.get(stage) ?? []).sort(byDateDesc),
    }));
  }, [filtered]);

  return (
    <div className="page-stack">
      <PageHeader
        eyebrow="Matches"
        title="Results & schedule"
        intro={`Every World Cup 2026 match from the group stage through the knockout rounds — ${playedCount} played, ${scheduledCount} still to come.`}
      />

      <div className="matches-toolbar reveal">
        <SegmentedControl<View>
          ariaLabel="Match view"
          value={view}
          onChange={(next) => {
            setView(next);
            setDateFilter(ALL);
          }}
          options={[
            { value: "upcoming", label: "Upcoming", count: scheduledCount },
            { value: "knockout", label: "Knockout", count: knockoutCount },
            { value: "groups", label: "Groups", count: groupCount },
            { value: "all", label: "All matches", count: matches.length },
          ]}
        />
      </div>

      <section className="content-panel reveal">
        <div className="matches-filters">
          <FilterGroup label="Team">
            <select value={teamFilter} onChange={(e) => setTeamFilter(e.target.value)}>
              <option value={ALL}>All teams</option>
              {realTeamNames.map((name) => (
                <option key={name} value={name}>
                  {name}
                </option>
              ))}
            </select>
          </FilterGroup>
          <FilterGroup label="Venue (city)">
            <select value={venueFilter} onChange={(e) => setVenueFilter(e.target.value)}>
              <option value={ALL}>All venues</option>
              {cityNames.map((city) => (
                <option key={city} value={city}>
                  {city}
                </option>
              ))}
            </select>
          </FilterGroup>
          <FilterGroup label="Date">
            <select value={dateFilter} onChange={(e) => setDateFilter(e.target.value)}>
              <option value={ALL}>All dates</option>
              {dateOptions.map((date) => (
                <option key={date} value={date}>
                  {formatDate(date)}
                </option>
              ))}
            </select>
          </FilterGroup>
          <FilterGroup label="Status">
            <select value={statusFilter} onChange={(e) => setStatusFilter(e.target.value)}>
              <option value={ALL}>Any status</option>
              <option value="played">Played</option>
              <option value="scheduled">Scheduled</option>
            </select>
          </FilterGroup>
          {hasFilters ? (
            <button type="button" className="link-button matches-reset" onClick={resetFilters}>
              Clear filters
            </button>
          ) : null}
        </div>
        <p className="results-summary">
          {filtered.length} match{filtered.length === 1 ? "" : "es"} shown.
        </p>
      </section>

      {view === "knockout" ? (
        <section className="content-panel reveal">
          <h2 className="section-heading stage-heading">Knockout bracket</h2>
          <KnockoutBracket matches={matches} />
        </section>
      ) : null}

      {filtered.length === 0 ? (
        <section className="content-panel reveal">
          <EmptyState>No matches match the current filters.</EmptyState>
        </section>
      ) : view === "groups" ? (
        <section className="content-panel reveal">
          <h2 className="section-heading stage-heading">Group stage</h2>
          <p className="insight-note">Each group is collapsed — expand to see its matches.</p>
          {byGroup.map(([group, groupMatches]) => (
            <Expandable
              key={group}
              summary={`${group} · ${groupMatches.length} match${groupMatches.length === 1 ? "" : "es"}`}
            >
              <div className="score-list">
                {[...groupMatches].sort(byDateAsc).map((m) => (
                  <MatchRow key={m.match_id} match={m} />
                ))}
              </div>
            </Expandable>
          ))}
        </section>
      ) : view === "upcoming" ? (
        <section className="content-panel reveal">
          <h2 className="section-heading stage-heading">Coming up</h2>
          <div className="score-list">
            {[...filtered].sort(byDateAsc).map((m) => (
              <MatchRow key={m.match_id} match={m} />
            ))}
          </div>
        </section>
      ) : (
        // knockout + all: grouped by stage
        byStage.map(({ stage, matches: stageMatches }) => (
          <section key={stage} className="content-panel reveal">
            <h2 className="section-heading stage-heading">{stageLabel(stage)}</h2>
            <div className="score-list">
              {stageMatches.map((m) => (
                <MatchRow key={m.match_id} match={m} />
              ))}
            </div>
          </section>
        ))
      )}
    </div>
  );
}
