import { KnockoutBracket } from "@/components/knockout-bracket";
import { matches, type Match } from "@/lib/data";

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

// Knockout placeholders FIFA uses before the semifinals resolve.
const TEAM_PLACEHOLDERS: Record<string, string> = {
  W101: "Winner SF1",
  W102: "Winner SF2",
  RU101: "Loser SF1",
  RU102: "Loser SF2",
};

function teamLabel(name: string): string {
  return TEAM_PLACEHOLDERS[name] ?? name;
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
  const base = `${match.home_score} – ${match.away_score}`;
  if (match.home_pens !== null && match.away_pens !== null) {
    return `${base} (${match.home_pens}–${match.away_pens} pens)`;
  }
  return base;
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

const matchesByStage = new Map<string, Match[]>();
for (const match of matches) {
  const bucket = matchesByStage.get(match.stage);
  if (bucket) {
    bucket.push(match);
  } else {
    matchesByStage.set(match.stage, [match]);
  }
}

const playedCount = matches.filter((m) => m.status === "played").length;
const upcoming = matches.filter((m) => m.status === "scheduled");

export function MatchesRoute() {
  return (
    <div className="page-stack">
      <section className="content-panel reveal">
        <div className="panel-heading">
          <p className="eyebrow">Matches</p>
          <h2>Results &amp; schedule</h2>
        </div>
        <p className="panel-intro">
          Every World Cup 2026 match from the group stage through the knockout rounds —{" "}
          {playedCount} played so far, {upcoming.length} still to come.
        </p>
      </section>

      <section className="content-panel reveal">
        <h3 className="section-heading stage-heading">Knockout bracket</h3>
        <KnockoutBracket matches={matches} />
      </section>

      {upcoming.length > 0 ? (
        <section className="content-panel reveal">
          <h3 className="section-heading stage-heading">Coming up</h3>
          <div className="match-list">
            {upcoming.map((match) => (
              <article key={match.match_id} className="match-row match-row-upcoming">
                <span className="match-teams">
                  <span>{teamLabel(match.home_team)}</span>
                  <span className="match-score">{scoreText(match)}</span>
                  <span>{teamLabel(match.away_team)}</span>
                </span>
                <span className="match-meta">
                  {STAGE_LABELS[match.stage] ?? match.stage} · {formatDate(match.match_date)} ·{" "}
                  {match.stadium} ({match.city})
                </span>
              </article>
            ))}
          </div>
        </section>
      ) : null}

      {STAGE_ORDER.filter((stage) => matchesByStage.has(stage)).map((stage) => {
        const stageMatches = matchesByStage.get(stage) ?? [];
        const played = stageMatches.filter((m) => m.status === "played");
        if (played.length === 0) {
          return null;
        }
        // Group-stage matches read best grouped by their group, each group's
        // matches sorted most recent first; knockout stages stay as one list.
        const sections =
          stage === "First Stage"
            ? Array.from(
                played.reduce((acc, match) => {
                  const key = match.group ?? "Group ?";
                  const bucket = acc.get(key);
                  if (bucket) {
                    bucket.push(match);
                  } else {
                    acc.set(key, [match]);
                  }
                  return acc;
                }, new Map<string, Match[]>()),
              )
                .sort(([a], [b]) => a.localeCompare(b))
                .map(([group, groupMatches]) => ({
                  title: group,
                  matches: [...groupMatches].sort(
                    (a, b) => new Date(b.match_date).getTime() - new Date(a.match_date).getTime(),
                  ),
                }))
            : [
                {
                  title: null as string | null,
                  matches: [...played].sort(
                    (a, b) => new Date(b.match_date).getTime() - new Date(a.match_date).getTime(),
                  ),
                },
              ];
        return (
          <section key={stage} className="content-panel reveal">
            <h3 className="section-heading stage-heading">{STAGE_LABELS[stage] ?? stage}</h3>
            {sections.map((section) => (
              <div key={section.title ?? stage}>
                {section.title ? <h4 className="match-group-heading">{section.title}</h4> : null}
                <div className="match-list">
                  {section.matches.map((match) => {
                    const winner = winnerSide(match);
                    return (
                      <article key={match.match_id} className="match-row">
                        <span className="match-teams">
                          <span className={winner === "home" ? "match-winner" : undefined}>
                            {match.home_team}
                          </span>
                          <span className="match-score">{scoreText(match)}</span>
                          <span className={winner === "away" ? "match-winner" : undefined}>
                            {match.away_team}
                          </span>
                        </span>
                        <span className="match-meta">
                          {formatDate(match.match_date)} · {match.stadium} ({match.city})
                        </span>
                      </article>
                    );
                  })}
                </div>
              </div>
            ))}
          </section>
        );
      })}
    </div>
  );
}
