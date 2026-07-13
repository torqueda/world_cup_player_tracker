import { Link } from "react-router-dom";
import { deferredWorkItems, projectMetrics, screenCards } from "@/lib/project-metrics";

export function OverviewRoute() {
  return (
    <div className="page-stack">
      <section className="hero-panel reveal">
        <div className="hero-copy">
          <p className="eyebrow">Current direction</p>
          <h2>Build the prototype around the real football questions first.</h2>
          <p className="hero-text">
            The current dataset is stable enough to stop polishing in circles and start
            testing the actual interface: where clubs are, which players connect to them,
            and how national squads spread across the club football map.
          </p>
        </div>
        <div className="hero-actions">
          <Link className="button-primary" to="/players-clubs">
            Open Players & Clubs
          </Link>
          <Link className="button-secondary" to="/national-teams">
            Preview National Teams
          </Link>
        </div>
      </section>

      <section className="metrics-grid reveal">
        {projectMetrics.map((metric, index) => (
          <article
            key={metric.label}
            className="metric-card"
            style={{ animationDelay: `${index * 100}ms` }}
          >
            <p className="metric-label">{metric.label}</p>
            <p className="metric-value">{metric.value}</p>
            <p className="metric-note">{metric.note}</p>
          </article>
        ))}
      </section>

      <section className="content-grid">
        <article className="content-panel reveal">
          <div className="panel-heading">
            <p className="eyebrow">Prototype surfaces</p>
            <h3>Routes already scaffolded</h3>
          </div>
          <div className="screen-list">
            {screenCards.map((card) => (
              <Link key={card.slug} to={`/${card.slug}`} className="screen-card">
                <p className="screen-eyebrow">{card.eyebrow}</p>
                <h4>{card.title}</h4>
                <p>{card.body}</p>
              </Link>
            ))}
          </div>
        </article>

        <article className="content-panel reveal">
          <div className="panel-heading">
            <p className="eyebrow">Why this scaffold matters</p>
            <h3>It keeps the app replaceable, not brittle</h3>
          </div>
          <ul className="detail-list">
            <li>The dataset stays outside the frontend source tree as a generated project output.</li>
            <li>The app can be rebuilt against refreshed exports when the final roster is ready.</li>
            <li>Route structure exists before the data layer, so later data work lands into known screens.</li>
            <li>The visual system already points toward a real dashboard instead of a starter-template shell.</li>
          </ul>
        </article>
      </section>

      <section className="content-panel reveal">
        <div className="panel-heading">
          <p className="eyebrow">Deferred items</p>
          <h3>Known follow-ups we are intentionally not blocking on</h3>
        </div>
        <ul className="detail-list">
          {deferredWorkItems.map((item) => (
            <li key={item}>{item}</li>
          ))}
        </ul>
      </section>
    </div>
  );
}
