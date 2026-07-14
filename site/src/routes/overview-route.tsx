import { Link } from "react-router-dom";
import metaJson from "@data/meta.json";
import { activePlayers, clubs, matches, teams } from "@/lib/data";

const REPO_URL = "https://github.com/torqueda/world_cup_player_tracker";

// --- values derived from the current imports (never hard-coded) ---

const playedMatches = matches.filter((match) => match.status === "played").length;

const STAGE_ORDER = [
  "First Stage",
  "Round of 32",
  "Round of 16",
  "Quarter-final",
  "Semi-final",
  "Play-off for third place",
  "Final",
];
const STAGE_LABEL: Record<string, string> = {
  "First Stage": "the group stage",
  "Round of 32": "the round of 32",
  "Round of 16": "the round of 16",
  "Quarter-final": "the quarterfinals",
  "Semi-final": "the semifinals",
  "Play-off for third place": "the third-place playoff",
  "Final": "the final",
};

function currentStageLabel(): string {
  const playedStages = matches.filter((match) => match.status === "played").map((match) => match.stage);
  if (playedStages.length === 0) {
    return "the group stage";
  }
  const deepest = playedStages.reduce((best, stage) =>
    STAGE_ORDER.indexOf(stage) > STAGE_ORDER.indexOf(best) ? stage : best,
  );
  return STAGE_LABEL[deepest] ?? deepest;
}

const MONTHS = [
  "January",
  "February",
  "March",
  "April",
  "May",
  "June",
  "July",
  "August",
  "September",
  "October",
  "November",
  "December",
];

// Format the export date from its own parts so the label never shifts a day
// across time zones.
function formatExportDate(iso: string | undefined): string | null {
  if (!iso) {
    return null;
  }
  const [year, month, day] = iso.split("-").map(Number);
  if (!year || !month || !day) {
    return null;
  }
  return `${MONTHS[month - 1]} ${day}, ${year}`;
}

const exportedAt = formatExportDate((metaJson as { exported_at?: string }).exported_at);
const currentStage = currentStageLabel();

const headlineMetrics = [
  { value: teams.length, label: "Final squads" },
  { value: activePlayers.length, label: "Active final-squad players" },
  { value: clubs.length, label: "Canonical clubs" },
  { value: playedMatches, label: "Matches played" },
];

interface EntryLink {
  to: string;
  label: string;
}

interface EntryCard {
  eyebrow: string;
  heading: string;
  body: string;
  links: EntryLink[];
}

const entryCards: EntryCard[] = [
  {
    eyebrow: "Club Map",
    heading: "Follow every player back to club football.",
    body: "Zoom from countries to club cities, then open the clubs and players behind each marker. Filter by national team, club country, league, club, or player.",
    links: [{ to: "/players-clubs", label: "Open the club map" }],
  },
  {
    eyebrow: "Teams",
    heading: "See how every squad is assembled.",
    body: `Open any of the ${teams.length} teams to explore its roster, age and experience profile, birthplaces, clubs, leagues, coach, and tournament progress.`,
    links: [{ to: "/national-teams", label: "Browse all teams" }],
  },
  {
    eyebrow: "Matches & Leaderboards",
    heading: "Follow what happened on the pitch.",
    body: "Browse every result and upcoming fixture, then explore the leading scorers, creators, goalkeepers, and team statistics.",
    links: [
      { to: "/matches", label: "View matches" },
      { to: "/stats", label: "See leaderboards" },
    ],
  },
  {
    eyebrow: "Analysis",
    heading: "Beyond the headline numbers.",
    body: "Compare birthplace patterns, home-grown and diaspora squads, club and league influence, squad ages, confederation performance, coaches, officials, and expected-goals results.",
    links: [{ to: "/insights", label: "Open the analysis" }],
  },
];

export function OverviewRoute() {
  return (
    <div className="landing">
      {/* 1. HERO */}
      <section className="landing-hero reveal" aria-labelledby="landing-hero-title">
        <p className="eyebrow">World Cup 2026 · Data Explorer</p>
        <h2 id="landing-hero-title" className="landing-hero-title">
          {activePlayers.length.toLocaleString()} players, traced from birthplace to club to World Cup.
        </h2>
        <p className="landing-hero-lead">
          Explore where every final-squad player at the 2026 World Cup was born, which club and
          league they represented at call-up, how all {teams.length} squads were assembled, and
          what happened across the tournament — all thanks to publicly sourced data.
        </p>
        <div className="landing-actions">
          <Link className="button-primary" to="/players-clubs">
            Explore the club map
          </Link>
          <Link className="button-secondary" to="/national-teams">
            Browse all teams
          </Link>
          <Link className="link-quiet" to="/sources">
            Read the methodology
          </Link>
        </div>
        {exportedAt ? (
          <p className="landing-status">
            Data through {currentStage} · Updated {exportedAt}
          </p>
        ) : null}
      </section>

      {/* 2. HEADLINE METRICS */}
      <section className="landing-metrics reveal" aria-label="Dataset at a glance">
        {headlineMetrics.map((metric) => (
          <div key={metric.label} className="landing-metric">
            <span className="landing-metric-value">{metric.value.toLocaleString()}</span>
            <span className="landing-metric-label">{metric.label}</span>
          </div>
        ))}
      </section>

      {/* 3. HOW IT STARTED */}
      <section className="landing-section landing-prose" aria-labelledby="landing-origin">
        <p className="eyebrow">How It Started</p>
        <h2 id="landing-origin">How two questions became a month-long data project.</h2>
        <p>
          I started with the simple idea of visualizing where World Cup players were born, and how
          many were representing a country other than the one they were born in.
        </p>
        <p>
          Then came ages, clubs, leagues, stadiums, coordinates, match results, player statistics,
          coaches, and officials. What I expected to finish in a week became a month-long effort to
          collect, connect, clean, and validate a dataset large enough to justify building this
          site.
        </p>
        <p>
          The more the project grew, the more questions the data made possible: Which clubs supplied
          the most players? Which squads were built mostly at home, and which drew heavily from a
          diaspora? How widely were teams distributed across the club-football world? Which leagues
          had the greatest presence at the tournament?
        </p>
      </section>

      {/* 4. EXPLORE THE TOURNAMENT */}
      <section className="landing-section" aria-labelledby="landing-explore">
        <div className="landing-section-head">
          <p className="eyebrow">Explore the Tournament</p>
          <h2 id="landing-explore">Start anywhere. Follow the connections.</h2>
        </div>
        <div className="landing-cards">
          {entryCards.map((card) => (
            <article key={card.eyebrow} className="landing-card">
              <p className="screen-eyebrow">{card.eyebrow}</p>
              <h3>{card.heading}</h3>
              <p>{card.body}</p>
              <div className="landing-card-links">
                {card.links.map((link) => (
                  <Link key={link.to} className="landing-card-link" to={link.to}>
                    {link.label}
                    <span aria-hidden="true"> →</span>
                  </Link>
                ))}
              </div>
            </article>
          ))}
        </div>
      </section>

      {/* 5. BEHIND THE DATA */}
      <section className="landing-section landing-prose" aria-labelledby="landing-methodology">
        <p className="eyebrow">Behind the Data</p>
        <h2 id="landing-methodology">
          The hardest part of building this dataset was deciding what to trust.
        </h2>
        <p>
          Public sources rarely aligned perfectly. Player and club names varied between sites.
          Identity records and reusable images were incomplete. Stadium information appeared in
          inconsistent formats, and automated geocoding sometimes returned a municipality or
          neighborhood instead of the city the analysis required.
        </p>
        <p>Automation handled the repetitive work. Manual research handled the ambiguity.</p>
        <p>
          Roughly 500 player records had to be researched and entered directly. About 300 more were
          spot-checked and corrected as testing and early visualizations exposed inconsistencies.
          Club and location data required another substantial review, including the manual
          verification of names and/or coordinates for about 300 club cities.
        </p>
        <blockquote className="landing-quote">
          Every public-facing number has a source trail. Every correction is logged.
        </blockquote>
        <p>
          The project combines data from official tournament pages and public sources including
          ESPN, Wikipedia, Wikidata, Wikimedia Commons, and GeoNames. The canonical workbook is
          versioned, exports pass through integrity checks, and the site publishes its source
          registry, methods, and change history.
        </p>
        <div className="landing-actions">
          <Link className="button-secondary" to="/sources">
            See the methodology
          </Link>
          <a className="link-quiet" href={REPO_URL} target="_blank" rel="noreferrer noopener">
            View the repository
          </a>
        </div>
      </section>

      {/* 6. FROM DATASET TO WEBSITE */}
      <section className="landing-section landing-prose" aria-labelledby="landing-build">
        <p className="eyebrow">From Dataset to Website</p>
        <h2 id="landing-build">Built for people who do not want to open a spreadsheet.</h2>
        <p>
          Once the dataset was stable enough, the next challenge was turning it into something that
          anyone could explore.
        </p>
        <p>
          I had never built anything larger than a Streamlit page. For this project, I used Codex
          and Claude Code more heavily than I had before to accelerate implementation of the React
          and TypeScript interface. That shifted my attention toward the data model, information
          architecture, page layout, visual consistency, testing, and the way each finding is
          explained to the user.
        </p>
        <p>
          Discovering Netlify helped me clear the final deployment hurdle and turn the project into
          a public site rather than something that existed only in a local environment or GitHub
          repository.
        </p>
        <p className="landing-techline">Python · React · TypeScript · Vite · Leaflet · Netlify</p>
      </section>

      {/* 7. FINAL CTA */}
      <section className="landing-section landing-final" aria-labelledby="landing-final-cta">
        <h2 id="landing-final-cta">Start with the map. Stay for the rabbit holes.</h2>
        <p>Choose a team, club, city, match, or player and see where the data leads.</p>
        <div className="landing-actions">
          <Link className="button-primary" to="/players-clubs">
            Explore the club map
          </Link>
          <Link className="button-secondary" to="/insights">
            Open the analysis
          </Link>
        </div>
      </section>

      {/* 8. FOOTER DISCLAIMER */}
      <footer className="landing-disclaimer">
        <p>
          World Cup 2026 Player Tracker is an independent data project built from publicly available
          sources. It is not affiliated with FIFA. Data definitions, source links, image
          attributions, and corrections are available in <Link to="/sources">Methodology</Link>.
        </p>
      </footer>
    </div>
  );
}
