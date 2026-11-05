import changeLogJson from "@data/change_log.json";
import metaJson from "@data/meta.json";
import { SourceNote } from "@/components/source-note";
import { activePlayers, coaches, referees } from "@/lib/data";
import { PageHeader, MetricCard, Expandable, SortableTable } from "@/components/ui";
import { ANALYTICS_INPUT } from "@/lib/data/analytics-input";
import type { ChangeLogRow } from "@/lib/data/types";
import { buildDataQualitySummary, type DataQualityRow } from "@/lib/analytics";
import { formatPct } from "@/lib/format";

const changeLog = changeLogJson as ChangeLogRow[];
const meta = metaJson as { counts: Record<string, number>; exported_at?: string };

const dataQuality = buildDataQualitySummary(ANALYTICS_INPUT, meta);

function qualityStatusLabel(status: DataQualityRow["status"]): string {
  return status.replace(/_/g, " ");
}

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
      "Player identity data (dates of birth, birthplaces, and cross-references) is sourced from Wikidata, with manual review.",
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
    statement:
      "The Elo ratings on the Analysis page about winning are built from every international result since 1872, from martj42's international results dataset (CC0).",
    links: [{ label: "International results", url: "https://github.com/martj42/international_results" }],
  },
  {
    statement:
      "Squad market values on the Analysis pages come from the transfermarkt-datasets project (CC0), using values set in the 12 months before the tournament.",
    links: [{ label: "transfermarkt-datasets", url: "https://github.com/dcaribou/transfermarkt-datasets" }],
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
  { key: "matches", label: "Matches", value: meta.counts.matches },
  { key: "coaches", label: "Coaches", value: coaches.length },
  { key: "officials", label: "Match officials", value: referees.length },
  { key: "sources", label: "Cited sources", value: meta.counts.sources },
];

// Recent corrections shown by default; older ones collapse behind a disclosure.
const RECENT_CHANGES = 6;
const changeLogDesc = [...changeLog].reverse();
const recentChanges = changeLogDesc.slice(0, RECENT_CHANGES);
const olderChanges = changeLogDesc.slice(RECENT_CHANGES);

// The kind of change in words. The note says what changed, so the column
// names in field_changed stay in the data and off the page.
function changeLabel(changeType: string | null | undefined): string {
  const words = (changeType ?? "change").replace(/_/g, " ");
  return words.charAt(0).toUpperCase() + words.slice(1);
}

function ChangeRow({ change }: { change: ChangeLogRow }) {
  return (
    <article className="change-row">
      <span className="change-date">{String(change.changed_at ?? "—").slice(0, 10)}</span>
      <span>
        <strong>{changeLabel(change.change_type)}</strong>
        {change.team && change.team !== "ALL" ? ` · ${change.team}` : ""}
      </span>
      {change.notes ? <span className="change-notes">{change.notes}</span> : null}
    </article>
  );
}

export function SourcesRoute() {
  return (
    <div className="page-stack">
      <PageHeader
        title="Data & sources"
        intro="Every number on this site traces back to a public source. Here is what the dataset covers, how it is built and checked, where it comes from, and the main corrections and updates."
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
            Manually verified values outrank automated matches. Most player identities were
            matched to Wikidata automatically, accepting a candidate only when it scored high on
            name, sport, nationality, national-team and position evidence and clearly beat the next
            one. Late replacements were matched only when Wikidata&apos;s date of birth equalled the
            squad list&apos;s, and players the rules could not settle were matched by hand. Birth
            dates were then compared with Wikipedia&apos;s final squad lists, and mismatches are
            flagged for review.
          </li>
          <li>
            Tournament statistics were collected at stage checkpoints, and the last refresh covers
            every match through the final.
          </li>
          <li>
            Exports pass referential-integrity and identity checks before they reach the site, and
            club cities are geocoded then manually confirmed where automated matches were ambiguous.
          </li>
        </ul>
      </section>

      {/* 3. DATA QUALITY */}
      <section id="quality" className="content-panel reveal">
        <h2 className="section-heading">Data quality</h2>
        <p className="insight-note">
          How complete each table is, and which fields are missing, not applicable or not yet collected.
        </p>
        <div className="metrics-grid">
          {dataQuality.latestExportDate ? <MetricCard label="Data updated" value={dataQuality.latestExportDate} /> : null}
          <MetricCard label="Active players" value={activePlayers.length.toLocaleString()} />
          <MetricCard label="Data tables" value={dataQuality.rowCounts.length} />
        </div>
        <div className="analysis-cols">
          <div>
            <h3 className="subsection-heading">Rows per table</h3>
            <SortableTable
              rows={dataQuality.rowCounts}
              getRowKey={(row) => row.entity}
              initialSortKey="rows"
              initialSortAsc={false}
              caption="Rows per table"
              columns={[
                { key: "entity", label: "Table", sortValue: (row) => row.label, render: (row) => row.label },
                { key: "rows", label: "Rows", align: "right", initialAsc: false, sortValue: (row) => row.rows, render: (row) => row.rows.toLocaleString() },
              ]}
            />
          </div>
          <div>
            <h3 className="subsection-heading">Coverage and field status</h3>
            <SortableTable
              rows={[...dataQuality.sourceCoverage, ...dataQuality.fieldStatus]}
              getRowKey={(row) => row.key}
              initialSortKey="status"
              caption="Data quality status"
              columns={[
                { key: "label", label: "Check", sortValue: (row) => row.label, render: (row) => row.label },
                { key: "status", label: "Status", sortValue: (row) => row.status, render: (row) => <span className={`quality-pill quality-${row.status}`}>{qualityStatusLabel(row.status)}</span> },
                { key: "coverage", label: "Coverage", align: "right", initialAsc: false, sortValue: (row) => row.pct ?? -1, render: (row) => row.pct === null ? null : `${formatPct(row.pct)} (${row.count}/${row.total})` },
                { key: "note", label: "Interpretation", render: (row) => row.note },
              ]}
            />
          </div>
        </div>
        <Expandable summary="How to read this dashboard">
          <dl className="definition-list">
            <div className="definition-item">
              <dt>Missing</dt>
              <dd>A field is expected for the population but absent in one or more rows, so analyses use explicit denominators.</dd>
            </div>
            <div className="definition-item">
              <dt>Not applicable</dt>
              <dd>The field is intentionally irrelevant for that population, such as goalkeeper stat fields for outfield players.</dd>
            </div>
            <div className="definition-item">
              <dt>Not yet collected</dt>
              <dd>The measure would be useful, but the data does not have it yet, such as xGA or player starts.</dd>
            </div>
            <div className="definition-item">
              <dt>Failed validation</dt>
              <dd>The site&apos;s data is rebuilt only when every audit rule passes, so a failing row never reaches the site and the count is always 0.</dd>
            </div>
          </dl>
        </Expandable>
        <SourceNote
          definition="Coverage checks and the fields not yet collected, counted from the site's data tables."
          population="Every table on the site."
          threshold="No imputation"
        />
      </section>

      {/* 4. SOURCES AND ATTRIBUTION */}
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

      {/* 5. CORRECTIONS AND CHANGE HISTORY */}
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
