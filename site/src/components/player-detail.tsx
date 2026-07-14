import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
  type ReactNode,
} from "react";
import {
  getClubForPlayer,
  getPlayerById,
  getPlayerStat,
  getSquadEntryForPlayer,
  getTeamForPlayer,
} from "@/lib/data";

const TOURNAMENT_START = new Date("2026-06-11T00:00:00Z");

function ageAtKickoff(dateOfBirth: string | null | undefined): number | null {
  if (!dateOfBirth) {
    return null;
  }
  const dob = new Date(dateOfBirth);
  if (Number.isNaN(dob.getTime())) {
    return null;
  }
  return Math.floor((TOURNAMENT_START.getTime() - dob.getTime()) / (1000 * 60 * 60 * 24 * 365.25));
}

function formatPosition(position: string | null | undefined): string {
  if (!position) {
    return "—";
  }
  return position.charAt(0).toUpperCase() + position.slice(1);
}

// Wikimedia Special:FilePath URLs are served over https and accept a width
// parameter, so we upgrade the (http) stored URL and ask for a right-sized
// thumbnail instead of the full-resolution original.
function thumbUrl(imageUrl: string, width = 360): string {
  const https = imageUrl.replace(/^http:\/\//, "https://");
  return https.includes("?") ? `${https}&width=${width}` : `${https}?width=${width}`;
}

interface PlayerDetailContextValue {
  openPlayer: (playerId: string) => void;
}

const PlayerDetailContext = createContext<PlayerDetailContextValue | null>(null);

export function usePlayerDetail(): PlayerDetailContextValue {
  const ctx = useContext(PlayerDetailContext);
  if (!ctx) {
    throw new Error("usePlayerDetail must be used within a PlayerDetailProvider");
  }
  return ctx;
}

export function PlayerDetailProvider({ children }: { children: ReactNode }) {
  const [openId, setOpenId] = useState<string | null>(null);
  const openPlayer = useCallback((playerId: string) => setOpenId(playerId), []);
  const closePlayer = useCallback(() => setOpenId(null), []);
  const value = useMemo(() => ({ openPlayer }), [openPlayer]);

  return (
    <PlayerDetailContext.Provider value={value}>
      {children}
      {openId ? <PlayerDetailPanel playerId={openId} onClose={closePlayer} /> : null}
    </PlayerDetailContext.Provider>
  );
}

/** Inline, button-styled trigger that opens the detail panel for a player. */
export function PlayerLink({
  playerId,
  children,
  className,
}: {
  playerId: string;
  children: ReactNode;
  className?: string;
}) {
  const { openPlayer } = usePlayerDetail();
  return (
    <button
      type="button"
      className={className ? `player-link ${className}` : "player-link"}
      onClick={() => openPlayer(playerId)}
    >
      {children}
    </button>
  );
}

interface StatCell {
  label: string;
  value: string;
}

function PlayerDetailPanel({ playerId, onClose }: { playerId: string; onClose: () => void }) {
  const player = getPlayerById(playerId);
  const entry = getSquadEntryForPlayer(playerId);
  const team = getTeamForPlayer(playerId);
  const club = getClubForPlayer(playerId);
  const stat = getPlayerStat(playerId);

  // Close on Escape and lock body scroll while the overlay is open.
  useEffect(() => {
    function onKey(event: KeyboardEvent) {
      if (event.key === "Escape") {
        onClose();
      }
    }
    document.addEventListener("keydown", onKey);
    const previousOverflow = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    return () => {
      document.removeEventListener("keydown", onKey);
      document.body.style.overflow = previousOverflow;
    };
  }, [onClose]);

  if (!player) {
    return null;
  }

  const age = ageAtKickoff(player.date_of_birth);
  const birthplace = [player.place_of_birth, player.birth_country].filter(Boolean).join(", ") || "—";
  const isGoalkeeper = player.primary_position === "goalkeeper";

  const facts: { label: string; value: ReactNode }[] = [
    {
      label: "Age at kickoff",
      value:
        age !== null
          ? `${age}${player.date_of_birth ? ` · born ${String(player.date_of_birth).slice(0, 10)}` : ""}`
          : "—",
    },
    { label: "Birthplace", value: birthplace },
    { label: "Height", value: player.height_cm ? `${player.height_cm} cm` : "—" },
    {
      label: "Club at call-up",
      value: club
        ? `${club.club_name}${club.league ? ` · ${club.league}` : ""}${club.country ? ` (${club.country})` : ""}`
        : "—",
    },
    {
      label: "Before the tournament",
      value:
        entry && (entry.caps_pre_tournament != null || entry.goals_pre_tournament != null)
          ? `${entry.caps_pre_tournament ?? "—"} caps · ${entry.goals_pre_tournament ?? "—"} goals`
          : "—",
    },
  ];

  const statCells: StatCell[] = stat
    ? [
        { label: "Minutes", value: stat.minutes_played.toLocaleString() },
        { label: "Goals", value: String(stat.goals) },
        { label: "Assists", value: String(stat.assists) },
        { label: "Yellow", value: String(stat.yellow_cards) },
        { label: "Red", value: String(stat.red_cards + stat.indirect_red_cards) },
        ...(isGoalkeeper || (stat.gk_saves ?? 0) > 0
          ? [{ label: "Saves", value: String(stat.gk_saves ?? 0) }]
          : []),
      ]
    : [];

  return (
    <div
      className="player-detail-backdrop"
      role="presentation"
      onClick={(event) => {
        if (event.target === event.currentTarget) {
          onClose();
        }
      }}
    >
      <div className="player-detail-panel" role="dialog" aria-modal="true" aria-label={player.display_name}>
        <button type="button" className="player-detail-close" onClick={onClose} aria-label="Close">
          ×
        </button>

        <div className="player-detail-head">
          <figure className="player-detail-photo">
            {player.image_url ? (
              <img
                src={thumbUrl(player.image_url)}
                alt={player.display_name}
                loading="lazy"
                width={360}
              />
            ) : (
              <div className="player-detail-photo-empty" aria-hidden="true">
                <span>No licensed photo yet</span>
              </div>
            )}
            {player.image_url ? (
              <figcaption className="player-detail-credit">
                Photo:{" "}
                {player.image_source_url ? (
                  <a href={player.image_source_url} target="_blank" rel="noreferrer noopener">
                    {player.image_author ?? "Wikimedia Commons"}
                  </a>
                ) : (
                  player.image_author ?? "Wikimedia Commons"
                )}
                {player.image_license ? ` · ${player.image_license}` : ""}
              </figcaption>
            ) : (
              <figcaption className="player-detail-credit player-detail-credit-muted">
                Framed for a license-free photo
              </figcaption>
            )}
          </figure>

          <div className="player-detail-identity">
            <p className="eyebrow">{team?.team ?? "National team pending"}</p>
            <h3>
              {player.display_name}
              {entry?.is_captain ? <span className="captain-badge"> C</span> : null}
            </h3>
            <p className="player-detail-subline">
              {formatPosition(player.primary_position ?? entry?.position_group)}
              {entry?.shirt_number != null ? ` · #${entry.shirt_number}` : ""}
              {entry?.is_replacement ? " · replacement call-up" : ""}
            </p>
          </div>
        </div>

        <dl className="player-detail-facts">
          {facts.map((fact) => (
            <div key={fact.label} className="player-detail-fact">
              <dt>{fact.label}</dt>
              <dd>{fact.value}</dd>
            </div>
          ))}
        </dl>

        <div className="player-detail-stats-head">
          <h4>This tournament</h4>
          {stat ? <span className="player-detail-asof">{stat.as_of_stage}</span> : null}
        </div>
        {statCells.length > 0 ? (
          <div className="player-detail-statline">
            {statCells.map((cell) => (
              <div key={cell.label} className="player-detail-stat">
                <span className="player-detail-stat-value">{cell.value}</span>
                <span className="player-detail-stat-label">{cell.label}</span>
              </div>
            ))}
          </div>
        ) : (
          <p className="insight-note">No tournament statistics recorded for this player.</p>
        )}
      </div>
    </div>
  );
}
