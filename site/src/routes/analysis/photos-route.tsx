import { useState } from "react";
import photoJson from "@analysis/photo_correlates_2026.json";
import { CountryFlag } from "@/components/country-flag";
import { PlayerLink } from "@/components/player-detail";
import { Expandable, MetricCard, RankedList, SectionHeader, SegmentedControl, SortableTable } from "@/components/ui";
import { formatPct } from "@/lib/format";
import { AnalysisPage, IntervalCell, listInWords, sourceNote, teamInSentence } from "@/routes/analysis/shared";

// From scripts/analysis/photo_correlates.py. The JSON's own types come from
// the file, so a renamed key fails the typecheck.
const data = photoJson;
type Trait = (typeof data.coefficients)[number];
type ShareKey = keyof typeof data.shares;

const SHARE_VIEWS: { value: ShareKey; label: string; note: string }[] = [
  { value: "caps", label: "Caps", note: "Caps before the tournament." },
  { value: "market_value", label: "Market value", note: "Transfermarkt values set in the 12 months before the tournament." },
  { value: "big_five_club", label: "Club", note: "Premier League, La Liga, Bundesliga, Serie A or Ligue 1 at call-up." },
  { value: "minutes", label: "Minutes", note: "Minutes played at the tournament." },
  { value: "confederation", label: "Confederation", note: "The national team's confederation." },
  { value: "position", label: "Position", note: "Position in the squad list." },
];

function capitalize(text: string): string {
  return text.charAt(0).toUpperCase() + text.slice(1);
}

function points(value: number): string {
  return `${value > 0 ? "+" : value < 0 ? "−" : ""}${Math.abs(value).toFixed(1)}`;
}

function pointsWithInterval(row: Trait): string {
  const [low, high] = row.average_marginal_effect_points_ci95;
  return `${points(row.average_marginal_effect_points)} (${points(low)} to ${points(high)})`;
}

const clearTraits = [...data.coefficients]
  .filter((row) => {
    const [low, high] = row.odds_ratio_ci95;
    return low > 1 || high < 1;
  })
  .sort((a, b) => Math.abs(b.average_marginal_effect_points) - Math.abs(a.average_marginal_effect_points));
const unclearTraits = data.coefficients.filter((row) => !clearTraits.includes(row));
const hundredCaps = data.curiosities;
const mostCapped = data.curiosities.most_capped_without_photo[0];
const mostValuable = data.curiosities.most_valuable_without_photo[0];
const lowest = data.curiosities.lowest_team_share[0];

function euros(value: number): string {
  return `€${Math.round(value / 1_000_000).toLocaleString()}m`;
}

export function PhotosRoute() {
  const [view, setView] = useState<ShareKey>("caps");
  const viewInfo = SHARE_VIEWS.find((item) => item.value === view) ?? SHARE_VIEWS[0];

  return (
    <AnalysisPage
      slug="photos"
      intro={`The site shows a player's photo when Wikimedia Commons has a free one. ${data.about.with_photo.toLocaleString()} of the ${data.about.players.toLocaleString()} players in the final squads have one. So who gets photographed? A light-hearted look, and associations only.`}
    >
      <section id="who" className="content-panel reveal">
        <SectionHeader
          title="Who has a photo"
          note="The share of players with a photo in each group. Fame helps: caps, a big club and a high price all go with being photographed."
        />
        <div className="metrics-grid">
          <MetricCard
            label="Players with a photo"
            value={formatPct(data.about.with_photo / data.about.players)}
            note={`${data.about.with_photo.toLocaleString()} of ${data.about.players.toLocaleString()}`}
          />
          <MetricCard
            label="100 caps or more"
            value={`${hundredCaps.players_with_100_caps_with_photo} of ${hundredCaps.players_with_100_caps}`}
            note="have a photo"
          />
          {mostCapped ? (
            <MetricCard
              label="Most caps without a photo"
              value={mostCapped.caps}
              note={`${mostCapped.display_name}, ${mostCapped.team}`}
            />
          ) : null}
          {mostValuable ? (
            <MetricCard
              label="Most valuable without a photo"
              value={euros(mostValuable.market_value_eur)}
              note={`${mostValuable.display_name}, ${mostValuable.team}`}
            />
          ) : null}
        </div>
        <div className="leaders-toolbar">
          <SegmentedControl<ShareKey>
            ariaLabel="Group players by"
            value={view}
            onChange={setView}
            options={SHARE_VIEWS.map((item) => ({ value: item.value, label: item.label }))}
          />
        </div>
        <p className="insight-note">{viewInfo.note}</p>
        <RankedList
          showRank={false}
          items={data.shares[view].map((row) => ({
            key: row.group,
            name: capitalize(row.group),
            value: row.share,
            valueLabel: formatPct(row.share),
            meta: `${row.with_photo.toLocaleString()} of ${row.players.toLocaleString()} players`,
          }))}
        />
      </section>

      <section id="traits" className="content-panel reveal">
        <SectionHeader
          title="Holding the other traits fixed"
          note="Famous players are often older, more capped and at big clubs all at once. A model that takes the traits together says how much each one adds on its own, in percentage points of the chance of having a photo."
        />
        <SortableTable<Trait>
          focusable
          rows={clearTraits}
          getRowKey={(row) => row.feature}
          caption="Traits that go with having a photo, holding the others fixed"
          columns={[
            { key: "label", label: "Trait", width: "40%", render: (row) => row.label },
            { key: "points", label: "Change in photo chance, points", align: "right", render: (row) => <IntervalCell text={pointsWithInterval(row)} /> },
            { key: "odds", label: "Odds ratio", align: "right", render: (row) => `×${row.odds_ratio.toFixed(2)}` },
          ]}
        />
        <p className="insight-note note-spaced">
          No clear difference, with intervals that include none:{" "}
          {unclearTraits.map((row) => row.label).join("; ")}.
        </p>
        <Expandable summary="With market value in the model">
          <p className="insight-note">
            On the {data.with_market_value.fit.players.toLocaleString()} players with a recent Transfermarkt value, value
            takes over from the club: once it is in the model, playing in a big-five league adds no clear difference.
            Players without a recent value are mostly at clubs outside the leagues Transfermarkt&apos;s data covers.
          </p>
          <SortableTable<Trait>
            focusable
            rows={data.with_market_value.coefficients.filter((row) => {
              const [low, high] = row.odds_ratio_ci95;
              return low > 1 || high < 1 || row.feature === "big_five_club";
            })}
            getRowKey={(row) => row.feature}
            caption="Traits that go with having a photo, with market value in the model"
            columns={[
              { key: "label", label: "Trait", width: "40%", render: (row) => row.label },
              { key: "points", label: "Change in photo chance, points", align: "right", render: (row) => <IntervalCell text={pointsWithInterval(row)} /> },
              { key: "odds", label: "Odds ratio", align: "right", render: (row) => `×${row.odds_ratio.toFixed(2)}` },
            ]}
          />
        </Expandable>
      </section>

      <section id="missing" className="content-panel reveal">
        <SectionHeader
          title="Still waiting for a photographer"
          note={`Every player has a photo for ${listInWords(data.curiosities.highest_team_share.map((row) => teamInSentence(row.team)))}.${lowest ? ` ${lowest.team} has the lowest share, ${formatPct(lowest.share)}.` : ""}`}
        />
        <div className="analysis-cols">
          <div>
            <h3 className="subsection-heading">Most caps, no photo</h3>
            <ol className="detail-list">
              {data.curiosities.most_capped_without_photo.map((row) => (
                <li key={row.player_id}>
                  <PlayerLink playerId={row.player_id}>{row.display_name}</PlayerLink>{" "}
                  <span className="team-cell">
                    <CountryFlag country={row.team} />
                    {row.team}, {row.caps} caps
                  </span>
                </li>
              ))}
            </ol>
          </div>
          <div>
            <h3 className="subsection-heading">Highest value, no photo</h3>
            <ol className="detail-list">
              {data.curiosities.most_valuable_without_photo.map((row) => (
                <li key={row.player_id}>
                  <PlayerLink playerId={row.player_id}>{row.display_name}</PlayerLink>{" "}
                  <span className="team-cell">
                    <CountryFlag country={row.team} />
                    {row.team}, {euros(row.market_value_eur)}
                  </span>
                </li>
              ))}
            </ol>
          </div>
        </div>
        <p className="insight-note note-spaced">
          A photo on Commons needs someone to take it and release it under a free licence. If you have photographed
          one of these players, Wikimedia Commons takes uploads.
        </p>
      </section>

      <section id="method" className="content-panel reveal">
        <SectionHeader title="How this was calculated" />
        <dl className="definition-list">
          <div className="definition-item">
            <dt>Photo</dt>
            <dd>The player&apos;s Wikidata entry links a photo on Wikimedia Commons, as collected for the site in July 2026.</dd>
          </div>
          <div className="definition-item">
            <dt>Model</dt>
            <dd>
              A logistic regression on position, age, caps (on a doubling scale), a big-five league club, playing
              abroad, confederation and tournament minutes. Midfielders and UEFA teams are the reference groups. The
              change in photo chance is the average marginal effect, in percentage points.
            </dd>
          </div>
          <div className="definition-item">
            <dt>How well it sorts players</dt>
            <dd>
              Given a player with a photo and one without, the model ranks the photographed one higher{" "}
              {formatPct(data.fit.auc_cross_validated)} of the time, checked on players it was not fitted to.
            </dd>
          </div>
        </dl>
        {sourceNote(
          "Associations between player traits and having a Commons photo.",
          `The ${data.about.players.toLocaleString()} players in the final squads.`,
          "95% intervals",
        )}
      </section>
    </AnalysisPage>
  );
}
