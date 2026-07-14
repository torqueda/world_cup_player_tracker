import { useMemo, useState } from "react";
import type { Match } from "@/lib/data";

// Knockout rounds, leaves → root. The data carries no explicit bracket
// linkage, so the tree is reconstructed by matching each round's participants
// to the previous round's winners (and the Final/third-place to the two
// semi-finals, since those still hold placeholder teams).
const ROUNDS = ["Round of 32", "Round of 16", "Quarter-final", "Semi-final", "Final"] as const;

const ROUND_LABELS: Record<string, string> = {
  "Round of 32": "Round of 32",
  "Round of 16": "Round of 16",
  "Quarter-final": "Quarter-finals",
  "Semi-final": "Semi-finals",
  "Final": "Final",
};

// Placeholders FIFA uses before the semifinals resolve.
const PLACEHOLDERS: Record<string, string> = {
  W101: "Winner SF1",
  W102: "Winner SF2",
  RU101: "Loser SF1",
  RU102: "Loser SF2",
};

function teamLabel(name: string): string {
  return PLACEHOLDERS[name] ?? name;
}

function isPlaceholder(name: string): boolean {
  return name in PLACEHOLDERS;
}

function winnerOf(match: Match): string | null {
  if (match.status !== "played" || match.home_score === null || match.away_score === null) {
    return null;
  }
  if (match.home_score !== match.away_score) {
    return match.home_score > match.away_score ? match.home_team : match.away_team;
  }
  if (match.home_pens !== null && match.away_pens !== null && match.home_pens !== match.away_pens) {
    return match.home_pens > match.away_pens ? match.home_team : match.away_team;
  }
  return null;
}

// --- layout constants (SVG units) ---
const COL_W = 210;
const BOX_W = 180;
const BOX_H = 48;
const ROW_H = 60;
const PAD_TOP = 10;

interface BracketNode {
  match: Match;
  round: number;
  children: BracketNode[];
  x: number;
  y: number;
}

interface BuiltBracket {
  nodes: BracketNode[];
  connectors: { from: BracketNode; to: BracketNode }[];
  thirdPlace: Match | null;
  width: number;
  height: number;
}

function buildBracket(all: Match[]): BuiltBracket {
  const byStage = new Map<string, Match[]>();
  for (const stage of ROUNDS) {
    byStage.set(
      stage,
      all
        .filter((m) => m.stage === stage)
        .sort((a, b) => a.match_date.localeCompare(b.match_date) || a.match_id.localeCompare(b.match_id)),
    );
  }
  const finalMatch = byStage.get("Final")?.[0];
  if (!finalMatch) {
    return { nodes: [], connectors: [], thirdPlace: null, width: 0, height: 0 };
  }

  // Feeder matches for each match one round down.
  const feeders = new Map<string, (Match | null)[]>();
  for (let ri = 1; ri < ROUNDS.length; ri++) {
    const round = ROUNDS[ri];
    const prevMatches = byStage.get(ROUNDS[ri - 1]) ?? [];
    if (round === "Final") {
      const semis = byStage.get("Semi-final") ?? [];
      feeders.set(finalMatch.match_id, [semis[0] ?? null, semis[1] ?? null]);
      continue;
    }
    const winnerToMatch = new Map<string, Match>();
    for (const pm of prevMatches) {
      const w = winnerOf(pm);
      if (w) {
        winnerToMatch.set(w, pm);
      }
    }
    for (const m of byStage.get(round) ?? []) {
      feeders.set(m.match_id, [winnerToMatch.get(m.home_team) ?? null, winnerToMatch.get(m.away_team) ?? null]);
    }
  }

  const nodes: BracketNode[] = [];
  let leafIndex = 0;
  function build(match: Match, round: number): BracketNode {
    const children =
      round === 0
        ? []
        : (feeders.get(match.match_id) ?? [])
            .filter((m): m is Match => Boolean(m))
            .map((feeder) => build(feeder, round - 1));
    const node: BracketNode = { match, round, children, x: round * COL_W, y: 0 };
    if (children.length === 0) {
      node.y = PAD_TOP + leafIndex * ROW_H + ROW_H / 2;
      leafIndex += 1;
    } else {
      node.y = children.reduce((sum, c) => sum + c.y, 0) / children.length;
    }
    nodes.push(node);
    return node;
  }
  build(finalMatch, ROUNDS.length - 1);

  const connectors: { from: BracketNode; to: BracketNode }[] = [];
  for (const node of nodes) {
    for (const child of node.children) {
      connectors.push({ from: child, to: node });
    }
  }

  const thirdPlace = all.find((m) => m.stage === "Play-off for third place") ?? null;
  const height = PAD_TOP * 2 + Math.max(leafIndex, 1) * ROW_H;
  const width = ROUNDS.length * COL_W;
  return { nodes, connectors, thirdPlace, width, height };
}

function MatchBox({
  match,
  selectedTeam,
  onSelectTeam,
}: {
  match: Match;
  selectedTeam: string | null;
  onSelectTeam: (team: string) => void;
}) {
  const winner = winnerOf(match);
  const played = match.status === "played";
  const rows = [
    {
      team: match.home_team,
      own: !isPlaceholder(match.home_team),
      isWinner: winner === match.home_team,
      score: match.home_score,
      pens: match.home_pens,
    },
    {
      team: match.away_team,
      own: !isPlaceholder(match.away_team),
      isWinner: winner === match.away_team,
      score: match.away_score,
      pens: match.away_pens,
    },
  ];
  return (
    <div className="bracket-match">
      {rows.map((row, index) => {
        const highlighted = selectedTeam !== null && row.team === selectedTeam;
        const className = [
          "bracket-team",
          row.isWinner ? "bracket-team-winner" : "",
          highlighted ? "bracket-team-active" : "",
        ]
          .join(" ")
          .trim();
        // Each team's own goals, with their shootout count in parentheses when
        // the tie went to penalties — so "1 (4)" beats "1 (3)" reads cleanly.
        const scoreLabel = played
          ? row.pens !== null
            ? `${row.score} (${row.pens})`
            : String(row.score)
          : "";
        return row.own ? (
          <button key={row.team} type="button" className={className} onClick={() => onSelectTeam(row.team)}>
            <span className="bracket-team-name">{row.team}</span>
            {scoreLabel ? <span className="bracket-team-score">{scoreLabel}</span> : null}
          </button>
        ) : (
          <span key={`${row.team}-${index}`} className={`${className} bracket-team-placeholder`}>
            <span className="bracket-team-name">{teamLabel(row.team)}</span>
          </span>
        );
      })}
    </div>
  );
}

export function KnockoutBracket({ matches }: { matches: Match[] }) {
  const [selectedTeam, setSelectedTeam] = useState<string | null>(null);
  const { nodes, connectors, thirdPlace, width, height } = useMemo(() => buildBracket(matches), [matches]);

  if (nodes.length === 0) {
    return <p className="insight-note">The bracket appears once knockout fixtures are scheduled.</p>;
  }

  function onSelectTeam(team: string) {
    setSelectedTeam((current) => (current === team ? null : team));
  }

  // Column headers positioned over each round.
  const headers = ROUNDS.map((round, index) => ({ round, x: index * COL_W + BOX_W / 2 }));

  return (
    <div className="bracket-wrap">
      <div className="bracket-toolbar">
        <p className="insight-note">
          The full knockout tree, Round of 32 to the Final. Click any team to trace its path; the
          semifinals, third-place playoff, and Final fill in as those matches are played.
        </p>
        {selectedTeam ? (
          <button type="button" className="link-button" onClick={() => setSelectedTeam(null)}>
            Clear “{selectedTeam}” highlight
          </button>
        ) : null}
      </div>
      <div className="bracket-scroll">
        <svg
          viewBox={`0 0 ${width} ${height + 34}`}
          style={{ width: Math.max(width, 320), height: height + 34 }}
          role="img"
          aria-label="World Cup 2026 knockout bracket"
        >
          {headers.map((header) => (
            <text key={header.round} x={header.x} y={16} className="bracket-round-label" textAnchor="middle">
              {ROUND_LABELS[header.round]}
            </text>
          ))}
          <g transform="translate(0, 28)">
            {connectors.map(({ from, to }, index) => {
              const startX = from.x + BOX_W;
              const endX = to.x;
              const midX = (startX + endX) / 2;
              const onPath =
                selectedTeam !== null &&
                (from.match.home_team === selectedTeam ||
                  from.match.away_team === selectedTeam ||
                  to.match.home_team === selectedTeam ||
                  to.match.away_team === selectedTeam);
              return (
                <path
                  key={index}
                  d={`M ${startX} ${from.y} H ${midX} V ${to.y} H ${endX}`}
                  className={onPath ? "bracket-link bracket-link-active" : "bracket-link"}
                  fill="none"
                />
              );
            })}
            {nodes.map((node) => (
              <foreignObject
                key={node.match.match_id}
                x={node.x}
                y={node.y - BOX_H / 2}
                width={BOX_W}
                height={BOX_H}
              >
                <MatchBox match={node.match} selectedTeam={selectedTeam} onSelectTeam={onSelectTeam} />
              </foreignObject>
            ))}
          </g>
        </svg>
      </div>
      {thirdPlace ? (
        <div className="bracket-thirdplace">
          <span className="bracket-thirdplace-label">Third-place playoff</span>
          <MatchBox match={thirdPlace} selectedTeam={selectedTeam} onSelectTeam={onSelectTeam} />
        </div>
      ) : null}
    </div>
  );
}
