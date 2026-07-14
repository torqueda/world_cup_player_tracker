import changeLogJson from "@data/change_log.json";
import metaJson from "@data/meta.json";
import { coaches, referees } from "@/lib/data";

interface ChangeLogRow {
  change_id: string;
  changed_at: string | null;
  team: string | null;
  change_type: string | null;
  field_changed: string | null;
  notes: string | null;
}

const changeLog = changeLogJson as unknown as ChangeLogRow[];
const meta = metaJson as { counts: Record<string, number>; exported_at?: string };

const REPO_URL = "https://github.com/torqueda/world_cup_player_tracker";

// Statement-style attributions: one line per kind of data, linking to the
// general site or the specific pages that hold the bulk of it.
const ATTRIBUTIONS: { statement: string; links: { label: string; url: string }[] }[] = [
  {
    statement:
      "Rosters were bootstrapped from ESPN's all-teams squad announcement article, then verified against FIFA's final squad lists.",
    links: [{ label: "ESPN", url: "https://www.espn.com/soccer/" }],
  },
  {
    statement:
      "Final squads, shirt numbers, pre-tournament caps, coaches, and match officials are sourced from Wikipedia.",
    links: [
      { label: "2026 World Cup squads", url: "https://en.wikipedia.org/wiki/2026_FIFA_World_Cup_squads" },
      { label: "2026 World Cup officials", url: "https://en.wikipedia.org/wiki/2026_FIFA_World_Cup_officials" },
    ],
  },
  {
    statement:
      "Player identity data — dates of birth, birthplaces, and cross-references — is sourced from Wikidata, with manual review.",
    links: [{ label: "Wikidata", url: "https://www.wikidata.org/" }],
  },
  {
    statement:
      "Match results, player statistics, and team statistics are sourced from FIFA's official tournament pages.",
    links: [
      {
        label: "Player statistics",
        url: "https://www.fifa.com/en/tournaments/mens/worldcup/canadamexicousa2026/statistics/player-statistics",
      },
      {
        label: "Team statistics",
        url: "https://www.fifa.com/en/tournaments/mens/worldcup/canadamexicousa2026/statistics/team-statistics",
      },
      {
        label: "Scores & fixtures",
        url: "https://www.fifa.com/en/tournaments/mens/worldcup/canadamexicousa2026/scores-fixtures",
      },
    ],
  },
  {
    statement: "City coordinates for club locations are sourced from GeoNames and Wikimedia.",
    links: [
      { label: "GeoNames", url: "https://www.geonames.org/" },
      { label: "Wikimedia", url: "https://www.wikimedia.org/" },
    ],
  },
  {
    statement: "Club identities and league assignments were normalized against Wikipedia and official club sites.",
    links: [{ label: "Wikipedia", url: "https://en.wikipedia.org/" }],
  },
];

const refereeCounts = referees.reduce(
  (acc, official) => {
    acc[official.role] = (acc[official.role] ?? 0) + 1;
    return acc;
  },
  {} as Record<string, number>,
);

export function SourcesRoute() {
  return (
    <div className="page-stack">
      <section className="content-panel reveal">
        <div className="panel-heading">
          <p className="eyebrow">Data &amp; sources</p>
          <h2>Where this data comes from</h2>
        </div>
        <p className="panel-intro">
          Every number on this site traces back to a public source, and every correction is
          logged. The dataset currently holds {meta.counts.players?.toLocaleString()} players,{" "}
          {meta.counts.clubs} clubs, {meta.counts.world_cup_history} matches, {coaches.length} coaches,
          and {referees.length} match officials
          {Object.entries(refereeCounts).length > 0
            ? ` (${Object.entries(refereeCounts)
                .map(([role, count]) => `${count} ${role.replace(/_/g, " ")}s`)
                .join(", ")})`
            : ""}
          .
        </p>
        <p className="insight-note note-spaced">
          {meta.exported_at ? <>Data last regenerated on {meta.exported_at}. </> : null}
          The canonical dataset is a versioned workbook; the full pipeline, collection
          scripts, and change history are public at{" "}
          <a className="table-link" href={REPO_URL} target="_blank" rel="noreferrer">
            github.com/torqueda/world_cup_player_tracker
          </a>
          .
        </p>
      </section>

      <section className="content-panel reveal">
        <h3 className="section-heading">Attributions</h3>
        <ul className="attribution-list">
          {ATTRIBUTIONS.map((item) => (
            <li key={item.statement}>
              {item.statement}{" "}
              <span className="attribution-links">
                {item.links.map((link, index) => (
                  <span key={link.url}>
                    {index > 0 ? " · " : ""}
                    <a className="table-link" href={link.url} target="_blank" rel="noreferrer">
                      {link.label}
                    </a>
                  </span>
                ))}
              </span>
            </li>
          ))}
        </ul>
      </section>

      <section className="content-panel reveal">
        <h3 className="section-heading">Change log</h3>
        <p className="insight-note">
          Corrections and bulk updates applied to the dataset, most recent first.
        </p>
        <div className="change-list">
          {[...changeLog].reverse().map((change) => (
            <article key={change.change_id} className="change-row">
              <span className="change-date">{String(change.changed_at ?? "—").slice(0, 10)}</span>
              <span>
                <strong>{change.change_type ?? "change"}</strong>
                {change.team && change.team !== "ALL" ? ` · ${change.team}` : ""}
                {change.field_changed ? ` · ${change.field_changed}` : ""}
                {change.notes ? <span className="change-notes"> — {change.notes}</span> : null}
              </span>
            </article>
          ))}
        </div>
      </section>

      <section className="content-panel reveal">
        <h3 className="section-heading">Method notes</h3>
        <ul className="detail-list">
          <li>
            Players cut from the announced squads stay in the dataset with a removed status
            for history; only final-squad players are counted on this site.
          </li>
          <li>
            Manually verified values outrank automated matches; identity matches are only
            auto-accepted when the date of birth confirms them.
          </li>
          <li>
            Tournament statistics are collected at stage checkpoints (currently: through the
            quarterfinals) and refreshed with each dataset update.
          </li>
        </ul>
      </section>
    </div>
  );
}
