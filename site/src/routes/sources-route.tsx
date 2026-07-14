import changeLogJson from "@data/change_log.json";
import metaJson from "@data/meta.json";
import { coaches, referees } from "@/lib/data";
import { PageHeader, MetricCard, Expandable } from "@/components/ui";

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
const DATA_URL = "https://github.com/torqueda/world_cup_player_tracker/tree/main/data/processed/app_exports";

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

const DEFINITIONS: { term: string; definition: string }[] = [
  {
    term: "Active",
    definition:
      "A player on a current final squad. Only active players are counted in the site's totals and visualizations.",
  },
  {
    term: "Removed",
    definition:
      "A player cut from an announced squad. Removed records stay in the dataset for history but are excluded from live counts.",
  },
  {
    term: "Registered",
    definition:
      "An entity (player, club, coach, official) that has a canonical record with a stable ID in the master workbook.",
  },
  {
    term: "Geocoded",
    definition:
      "A club city whose latitude/longitude were resolved from GeoNames/Wikimedia and manually confirmed where needed.",
  },
  {
    term: "Mapped",
    definition: "A club placed on the club map via its geocoded city, so its players appear at that location.",
  },
];

const LINEAGE = [
  { key: "sources", label: "Public sources", note: "ESPN · Wikipedia · Wikidata · FIFA · GeoNames" },
  { key: "workbook", label: "Master workbook", note: "versioned canonical .xlsx" },
  { key: "audit", label: "Integrity audit", note: "referential + identity checks" },
  { key: "exports", label: "App exports", note: "typed JSON per table" },
  { key: "site", label: "Website", note: "this app" },
];

const refereeCounts = referees.reduce(
  (acc, official) => {
    acc[official.role] = (acc[official.role] ?? 0) + 1;
    return acc;
  },
  {} as Record<string, number>,
);

const coverageCards = [
  { key: "players", label: "Players", value: meta.counts.players, note: "final-squad + removed records" },
  { key: "teams", label: "Final squads", value: meta.counts.teams },
  { key: "clubs", label: "Clubs", value: meta.counts.clubs, note: "registered & mapped" },
  { key: "cities", label: "Club cities", value: meta.counts.cities, note: "geocoded" },
  { key: "matches", label: "Matches", value: meta.counts.world_cup_history },
  { key: "coaches", label: "Coaches", value: coaches.length },
  { key: "officials", label: "Match officials", value: referees.length },
  { key: "sources", label: "Cited sources", value: meta.counts.sources },
];

// Recent corrections shown by default; older ones collapse behind a disclosure.
const RECENT_CHANGES = 6;
const changeLogDesc = [...changeLog].reverse();
const recentChanges = changeLogDesc.slice(0, RECENT_CHANGES);
const olderChanges = changeLogDesc.slice(RECENT_CHANGES);

function ChangeRow({ change }: { change: ChangeLogRow }) {
  return (
    <article className="change-row">
      <span className="change-date">{String(change.changed_at ?? "—").slice(0, 10)}</span>
      <span>
        <strong>{change.change_type ?? "change"}</strong>
        {change.team && change.team !== "ALL" ? ` · ${change.team}` : ""}
        {change.field_changed ? ` · ${change.field_changed}` : ""}
        {change.notes ? <span className="change-notes"> — {change.notes}</span> : null}
      </span>
    </article>
  );
}

export function SourcesRoute() {
  return (
    <div className="page-stack">
      <PageHeader
        eyebrow="Methodology"
        title="Data & sources"
        intro="Every number on this site traces back to a public source, and every correction is logged. Here is what the dataset covers, how it is built and checked, where it comes from, and how it has changed."
        actions={
          <>
            <a className="button-primary" href={REPO_URL} target="_blank" rel="noreferrer noopener">
              View the repository
            </a>
            <a className="button-secondary" href={DATA_URL} target="_blank" rel="noreferrer noopener">
              Browse the data exports
            </a>
          </>
        }
      />

      {/* 1. DATASET COVERAGE */}
      <section id="coverage" className="content-panel reveal">
        <h2 className="section-heading">Dataset coverage</h2>
        <p className="insight-note">
          {meta.exported_at ? <>Regenerated {meta.exported_at}. </> : null}
          Counts come straight from the current app exports.
          {Object.entries(refereeCounts).length > 0
            ? ` Officials break down as ${Object.entries(refereeCounts)
                .map(([role, count]) => `${count} ${role.replace(/_/g, " ")}s`)
                .join(", ")}.`
            : ""}
        </p>
        <div className="metrics-grid">
          {coverageCards.map((card) => (
            <MetricCard
              key={card.key}
              label={card.label}
              value={(card.value ?? 0).toLocaleString()}
              note={card.note}
            />
          ))}
        </div>

        <h3 className="subsection-heading">Definitions</h3>
        <dl className="definition-list">
          {DEFINITIONS.map((item) => (
            <div key={item.term} className="definition-item">
              <dt>{item.term}</dt>
              <dd>{item.definition}</dd>
            </div>
          ))}
        </dl>
      </section>

      {/* 2. PIPELINE AND QUALITY CHECKS */}
      <section id="pipeline" className="content-panel reveal">
        <h2 className="section-heading">Pipeline &amp; quality checks</h2>
        <p className="insight-note">
          Data flows one way, from public sources into a versioned workbook, through an integrity
          audit, out to typed exports, and finally into this site.
        </p>
        <ol className="lineage" aria-label="Data lineage from public sources to website">
          {LINEAGE.map((step, index) => (
            <li key={step.key} className="lineage-step">
              <div className="lineage-box">
                <span className="lineage-label">{step.label}</span>
                <span className="lineage-note">{step.note}</span>
              </div>
              {index < LINEAGE.length - 1 ? (
                <span className="lineage-arrow" aria-hidden="true">
                  →
                </span>
              ) : null}
            </li>
          ))}
        </ol>

        <h3 className="subsection-heading">Method notes</h3>
        <ul className="detail-list">
          <li>
            Players cut from the announced squads stay in the dataset with a removed status for
            history; only active final-squad players are counted on this site.
          </li>
          <li>
            Manually verified values outrank automated matches; identity matches are only
            auto-accepted when the date of birth confirms them.
          </li>
          <li>
            Tournament statistics are collected at stage checkpoints (currently through the
            quarterfinals) and refreshed with each dataset update.
          </li>
          <li>
            Exports pass referential-integrity and identity checks before they reach the site, and
            club cities are geocoded then manually confirmed where automated matches were ambiguous.
          </li>
        </ul>
      </section>

      {/* 3. SOURCES AND ATTRIBUTION */}
      <section id="attribution" className="content-panel reveal">
        <h2 className="section-heading">Sources &amp; attribution</h2>
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
        <p className="source-note">
          Player photos are used under their individual Wikimedia Commons licenses; each photo's
          author and license are shown in that player's detail panel. Where no license-free photo
          exists, the player's national-team flag is shown instead.
        </p>
      </section>

      {/* 4. CORRECTIONS AND CHANGE HISTORY */}
      <section id="changes" className="content-panel reveal">
        <h2 className="section-heading">Corrections &amp; change history</h2>
        <p className="insight-note">
          Corrections and bulk updates applied to the dataset, most recent first. Older entries are
          collapsed.
        </p>
        <div className="change-list">
          {recentChanges.map((change) => (
            <ChangeRow key={change.change_id} change={change} />
          ))}
        </div>
        {olderChanges.length > 0 ? (
          <Expandable summary={`${olderChanges.length} older correction${olderChanges.length === 1 ? "" : "s"}`}>
            <div className="change-list">
              {olderChanges.map((change) => (
                <ChangeRow key={change.change_id} change={change} />
              ))}
            </div>
          </Expandable>
        ) : null}
      </section>
    </div>
  );
}
