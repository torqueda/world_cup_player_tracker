import winFactorsJson from "@analysis/win_factors_2026.json";
import { CountryFlag } from "@/components/country-flag";
import { Expandable, MetricCard, SectionHeader, SortableTable } from "@/components/ui";
import { formatNumber, formatPct } from "@/lib/format";
import { AnalysisPage, IntervalCell, listInWords, sourceNote, teamInSentence } from "@/routes/analysis/shared";

// From scripts/analysis/win_factors.py. The JSON's own types come from the
// file, so a renamed key fails the typecheck.
const data = winFactorsJson;
type MatchModel = (typeof data.match_models)[number];
type Coefficient = MatchModel["coefficients"][number];
type TeamRow = (typeof data.teams)[number];
type Interval = number[];

interface Factor {
  key: string;
  label: string;
  unit: string;
  feature: string;
  alone: string;
  withElo: string | null;
  teamFactor: string;
}

// Elo first, as the baseline every other factor is tested against. Each
// factor is the difference between the two teams, per the unit given.
const FACTORS: Factor[] = [
  {
    key: "elo",
    label: "Elo rating",
    unit: "100 points",
    feature: "elo_gap_per_100",
    alone: "elo_only",
    withElo: null,
    teamFactor: "elo_before",
  },
  {
    key: "value",
    label: "Top-11 market value",
    unit: "doubling",
    feature: "value_gap_per_doubling",
    alone: "value_gap_per_doubling_alone",
    withElo: "elo_plus_value_gap_per_doubling",
    teamFactor: "top11_value_eur",
  },
  {
    key: "bigFive",
    label: "Big-five share",
    unit: "10 points of the squad",
    feature: "big_five_gap_per_10pts",
    alone: "big_five_gap_per_10pts_alone",
    withElo: "elo_plus_big_five_gap_per_10pts",
    teamFactor: "big_five_share",
  },
  {
    key: "age",
    label: "Average age",
    unit: "1 year",
    feature: "age_gap",
    alone: "age_gap_alone",
    withElo: "elo_plus_age_gap",
    teamFactor: "mean_age",
  },
  {
    key: "caps",
    label: "Average caps",
    unit: "10 caps",
    feature: "caps_gap_per_10",
    alone: "caps_gap_per_10_alone",
    withElo: "elo_plus_caps_gap_per_10",
    teamFactor: "mean_caps",
  },
];

function model(name: string): MatchModel {
  const found = data.match_models.find((row) => row.model === name);
  if (!found) {
    throw new Error(`win_factors_2026.json has no model ${name}`);
  }
  return found;
}

function coefficient(modelName: string, feature: string): Coefficient {
  const found = model(modelName).coefficients.find((row) => row.feature === feature);
  if (!found) {
    throw new Error(`model ${modelName} has no coefficient ${feature}`);
  }
  return found;
}

const includesNoEffect = ([low, high]: Interval, none: number) => low <= none && high >= none;

function ratio(value: number): string {
  return `×${value.toFixed(2)}`;
}

function ratioWithInterval(row: Coefficient): string {
  const [low, high] = row.odds_ratio_ci95;
  return `${ratio(row.odds_ratio)} (${low.toFixed(2)} to ${high.toFixed(2)})`;
}

// The models report the change in forecast error against Elo alone, where
// below zero is better. The page shows it as a gain, so above zero is better.
function forecastGain(modelName: string): string {
  const row = model(modelName);
  const change = row.leave_one_out_rps_minus_elo_only;
  const interval = row.leave_one_out_rps_minus_elo_only_ci95;
  if (change === undefined || interval === undefined) {
    return "N/A";
  }
  const signed = (value: number) => (value === 0 ? "0.000" : `${value > 0 ? "+" : "−"}${Math.abs(value).toFixed(3)}`);
  return `${signed(-change)} (${signed(-interval[1])} to ${signed(-interval[0])})`;
}

interface FactorRow {
  factor: Factor;
  per: string;
  alone: Coefficient;
  withElo: Coefficient | null;
  verdict: string;
}

const factorRows: FactorRow[] = FACTORS.map((factor) => {
  const alone = coefficient(factor.alone, factor.feature);
  const withElo = factor.withElo ? coefficient(factor.withElo, factor.feature) : null;
  let verdict = "The baseline";
  if (withElo) {
    const forecast = factor.withElo ? model(factor.withElo).leave_one_out_rps_minus_elo_only_ci95 : undefined;
    if (!includesNoEffect(withElo.odds_ratio_ci95, 1)) {
      verdict = forecast && includesNoEffect(forecast, 0) ? "Adds to Elo; forecasts not clearly better" : "Adds to Elo";
    } else if (!includesNoEffect(alone.odds_ratio_ci95, 1)) {
      verdict = "Linked, but not beyond Elo";
    } else {
      verdict = "No clear link";
    }
  }
  return { factor, per: alone.per, alone, withElo, verdict };
});

const elo = factorRows[0].alone;
const strongestAddition = factorRows
  .filter((row) => row.verdict.startsWith("Adds to Elo") && row.withElo)
  .sort((a, b) => (a.withElo!.p_value ?? 1) - (b.withElo!.p_value ?? 1))[0];
const noLink = factorRows.filter((row) => row.verdict === "No clear link");
const home = coefficient("elo_only", "home");
const hosts = data.teams.filter((team) => team.host).map((team) => teamInSentence(team.team));

const FACTOR_NAMES: Record<string, string> = {
  mean_age: "Average age",
  mean_caps: "Average caps",
  big_five_share: "Big-five share",
  elo_before: "Elo rating before",
  top11_value_eur: "Top-11 market value",
};

interface CorrelationRow {
  key: string;
  label: string;
  points: (typeof data.team_level)[number] | undefined;
  eloChange: (typeof data.team_level)[number] | undefined;
}

const correlationRows: CorrelationRow[] = FACTORS.map((factor) => ({
  key: factor.teamFactor,
  label: factor.key === "elo" ? "Elo rating before" : factor.label,
  points: data.team_level.find((row) => row.factor === factor.teamFactor && row.outcome === "points_per_match"),
  eloChange: data.team_level.find((row) => row.factor === factor.teamFactor && row.outcome === "elo_change"),
}));

function spearman(row: (typeof data.team_level)[number] | undefined): string {
  if (!row) {
    return "Not measured";
  }
  const [low, high] = row.spearman_ci95;
  const signed = (value: number) => `${value < 0 ? "−" : ""}${Math.abs(value).toFixed(2)}`;
  return `${signed(row.spearman)} (${signed(low)} to ${signed(high)})`;
}

function millions(value: number): string {
  return `€${Math.round(value / 1_000_000).toLocaleString()}m`;
}

export function WhatWinsRoute() {
  return (
    <AnalysisPage
      slug="what-wins"
      intro={`Which squad traits went with winning matches at the 2026 World Cup? Each of the ${data.about.matches} matches is a contest between two squads, so every factor is the difference between them. These are associations from one tournament, not causes.`}
    >
      <section id="factors" className="content-panel reveal">
        <SectionHeader
          title="Each factor alone, then next to Elo"
          note="Elo is a rating built from every international result since 1872. A factor that only repeats what Elo already knows does not add to it."
        />
        <div className="metrics-grid">
          <MetricCard label="Elo rating" value={ratio(elo.odds_ratio)} note={`odds of the better result, per ${elo.per}`} />
          {strongestAddition?.withElo ? (
            <MetricCard
              label={`${strongestAddition.factor.label}, next to Elo`}
              value={ratio(strongestAddition.withElo.odds_ratio)}
              note={`per ${strongestAddition.per}`}
            />
          ) : null}
          {noLink.length > 0 ? (
            <MetricCard
              label={listInWords(noLink.map((row, index) => (index === 0 ? row.factor.label : row.factor.label.toLowerCase())))}
              value="No clear link"
              note="the intervals include no effect"
            />
          ) : null}
        </div>
        <SortableTable
          focusable
          className="wide-table"
          rows={factorRows}
          getRowKey={(row) => row.factor.key}
          caption="Odds ratios for each factor, alone and next to Elo"
          columns={[
            {
              key: "factor",
              label: "Factor",
              width: "24%",
              render: (row) => (
                <>
                  {row.factor.label}
                  <span className="table-cell-note">per {row.factor.unit}</span>
                </>
              ),
            },
            { key: "alone", label: "Alone", align: "right", render: (row) => <IntervalCell text={ratioWithInterval(row.alone)} /> },
            {
              key: "withElo",
              label: "Next to Elo",
              align: "right",
              render: (row) => (row.withElo ? <IntervalCell text={ratioWithInterval(row.withElo)} /> : "N/A"),
            },
            {
              key: "forecast",
              label: "Forecast gain over Elo alone",
              align: "right",
              render: (row) => (row.factor.withElo ? <IntervalCell text={forecastGain(row.factor.withElo)} /> : "N/A"),
            },
            { key: "verdict", label: "Reading", render: (row) => row.verdict },
          ]}
        />
        <p className="insight-note note-spaced">
          An odds ratio of ×2 doubles the odds of the better result (a win rather than a draw, or a draw rather than a
          loss); ×1 means no link. The smaller figures under each estimate are its 95% interval. The forecast gain is how much each match&apos;s
          forecast improves, forecasting it from the other {data.about.matches - 1}; above zero is better.
          {hosts.length > 0
            ? ` Only the hosts, ${listInWords(hosts)}, played at home, so home advantage is in every model but too rare to measure: ${ratioWithInterval(home)}.`
            : ""}
        </p>
      </section>

      <section id="teams" className="content-panel reveal">
        <SectionHeader
          title="Team by team"
          note={`The same factors over the ${data.about.teams} teams: how closely each one ranks the teams in the same order as their points per match, and as the Elo they gained during the tournament. 1 is the same order, 0 no relation.`}
        />
        <SortableTable
          focusable
          rows={correlationRows}
          getRowKey={(row) => row.key}
          caption="Rank correlations between team factors and results"
          columns={[
            { key: "label", label: "Factor", render: (row) => row.label },
            { key: "points", label: "With points per match", align: "right", render: (row) => <IntervalCell text={spearman(row.points)} /> },
            {
              key: "eloChange",
              label: "With Elo gained",
              align: "right",
              render: (row) => (row.key === "elo_before" ? "Not measured" : <IntervalCell text={spearman(row.eloChange)} />),
            },
          ]}
        />
        <Expandable summary={`All ${data.teams.length} teams`}>
          <SortableTable<TeamRow>
            focusable
            className="wide-table"
            rows={data.teams}
            getRowKey={(row) => row.team}
            initialSortKey="ppm"
            initialSortAsc={false}
            caption="Team factors and results"
            columns={[
              {
                key: "team",
                label: "Team",
                sortValue: (row) => row.team,
                render: (row) => (
                  <span className="team-cell">
                    <CountryFlag country={row.team} />
                    {row.team}
                  </span>
                ),
              },
              { key: "elo", label: "Elo before", align: "right", initialAsc: false, sortValue: (row) => row.elo_before, render: (row) => formatNumber(row.elo_before) },
              { key: "value", label: "Top-11 value", align: "right", initialAsc: false, sortValue: (row) => row.top11_value_eur, render: (row) => millions(row.top11_value_eur) },
              { key: "bigFive", label: "Big-five share", align: "right", initialAsc: false, sortValue: (row) => row.big_five_share, render: (row) => formatPct(row.big_five_share) },
              { key: "age", label: "Avg age", align: "right", initialAsc: false, sortValue: (row) => row.mean_age, render: (row) => formatNumber(row.mean_age, 1) },
              { key: "caps", label: "Avg caps", align: "right", initialAsc: false, sortValue: (row) => row.mean_caps, render: (row) => formatNumber(row.mean_caps, 1) },
              { key: "ppm", label: "Points per match", align: "right", initialAsc: false, sortValue: (row) => row.points_per_match, render: (row) => formatNumber(row.points_per_match, 2) },
              { key: "eloChange", label: "Elo gained", align: "right", initialAsc: false, sortValue: (row) => row.elo_change, render: (row) => `${row.elo_change > 0 ? "+" : ""}${formatNumber(row.elo_change)}` },
            ]}
          />
        </Expandable>
        <Expandable summary="The factors overlap">
          <p className="insight-note">
            Strong teams tend to be strong on several factors at once, which is why a factor can matter alone and add
            little next to Elo. Rank correlations between the factors over the {data.about.teams} teams:
          </p>
          <ul className="detail-list">
            {[...data.factor_overlap]
              .sort((a, b) => Math.abs(b.spearman) - Math.abs(a.spearman))
              .map((row) => (
                <li key={row.factors.join("-")}>
                  {row.factors.map((name) => FACTOR_NAMES[name] ?? name).join(" and ")}: {row.spearman < 0 ? "−" : ""}
                  {Math.abs(row.spearman).toFixed(2)}
                </li>
              ))}
          </ul>
        </Expandable>
      </section>

      <section id="method" className="content-panel reveal">
        <SectionHeader
          title="How this was calculated"
          aside={sourceNote(
            "Associations between squad differences and match results.",
            `The ${data.about.matches} matches of the 2026 World Cup and the ${data.about.teams} final squads.`,
            "95% intervals",
          )}
        />
        <dl className="definition-list">
          <div className="definition-item">
            <dt>Results</dt>
            <dd>{data.about.results}</dd>
          </div>
          <div className="definition-item">
            <dt>Squads</dt>
            <dd>{data.about.squads}</dd>
          </div>
          <div className="definition-item">
            <dt>Market value</dt>
            <dd>
              Transfermarkt values set in the 12 months before the tournament. Some squads have few recent values, so
              the measure is the combined value of each team&apos;s 11 most valuable players, and its odds ratio is per
              doubling.
            </dd>
          </div>
          <div className="definition-item">
            <dt>Model</dt>
            <dd>
              An ordered logistic regression on the difference between the two teams, which gives the chances of a win,
              a draw and a loss. The factor list was fixed before any model was fitted.
            </dd>
          </div>
          <div className="definition-item">
            <dt>Limits</dt>
            <dd>
              One World Cup is {data.about.matches} matches, so only strong effects can show, and the factors overlap.
              In a model with every factor at once, age and caps move together, so their separate effects there are not
              reliable.
            </dd>
          </div>
        </dl>
      </section>
    </AnalysisPage>
  );
}
