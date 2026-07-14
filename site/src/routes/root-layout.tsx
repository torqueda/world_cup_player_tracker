import { useEffect, useRef, useState } from "react";
import { Link, NavLink, Outlet, useLocation } from "react-router-dom";
import metaJson from "@data/meta.json";
import { playerStats } from "@/lib/data";
import { PlayerDetailProvider } from "@/components/player-detail";

const REPO_URL = "https://github.com/torqueda/world_cup_player_tracker";

const exportedAt = (metaJson as { exported_at?: string }).exported_at;
const asOfStage = playerStats[0]?.as_of_stage ?? "through quarterfinals";
const statusText = `Data ${asOfStage}${exportedAt ? ` · updated ${exportedAt}` : ""}`;

// Visible labels changed for the redesign; URLs preserved so external links keep
// working.
const navItems = [
  { to: "/", label: "Home", end: true },
  { to: "/players-clubs", label: "Club Map" },
  { to: "/national-teams", label: "Squads" },
  { to: "/matches", label: "Matches" },
  { to: "/stats", label: "Leaders" },
  { to: "/insights", label: "Analysis" },
];

// Methodology / Data & Sources stays reachable via the secondary menu + footer.
const secondaryItems = [{ to: "/sources", label: "Methodology" }];

function navLinkClass({ isActive }: { isActive: boolean }): string {
  return isActive ? "nav-link nav-link-active" : "nav-link";
}

export function RootLayout() {
  const [mobileOpen, setMobileOpen] = useState(false);
  const location = useLocation();
  const moreRef = useRef<HTMLDetailsElement>(null);

  // Close the mobile panel and the "More" menu whenever the route changes.
  useEffect(() => {
    setMobileOpen(false);
    if (moreRef.current) {
      moreRef.current.open = false;
    }
  }, [location.pathname]);

  return (
    <div className="app-shell">
      <header className="app-header">
        <div className="app-header-inner">
          <Link className="app-brand" to="/">
            <span className="app-brand-mark">WC 2026</span>
            <span className="app-brand-sub">Player Tracker</span>
          </Link>

          <nav className="app-nav" aria-label="Primary">
            {navItems.map((item) => (
              <NavLink key={item.to} to={item.to} end={item.end} className={navLinkClass}>
                {item.label}
              </NavLink>
            ))}
          </nav>

          <div className="app-header-meta">
            <span className="data-freshness">{statusText}</span>
            <details className="app-more" ref={moreRef}>
              <summary>More</summary>
              <div className="app-more-menu">
                {secondaryItems.map((item) => (
                  <NavLink key={item.to} to={item.to} className={navLinkClass}>
                    {item.label}
                  </NavLink>
                ))}
                <a href={REPO_URL} target="_blank" rel="noreferrer noopener">
                  Repository
                </a>
              </div>
            </details>
          </div>

          <button
            type="button"
            className="nav-toggle"
            aria-expanded={mobileOpen}
            aria-controls="mobile-nav"
            onClick={() => setMobileOpen((open) => !open)}
          >
            {mobileOpen ? "Close" : "Menu"}
          </button>
        </div>

        <div
          id="mobile-nav"
          className={mobileOpen ? "mobile-nav mobile-nav-open" : "mobile-nav"}
        >
          <div className="mobile-nav-inner">
            {navItems.map((item) => (
              <NavLink key={item.to} to={item.to} end={item.end} className={navLinkClass}>
                {item.label}
              </NavLink>
            ))}
            <hr className="mobile-nav-divider" />
            {secondaryItems.map((item) => (
              <NavLink key={item.to} to={item.to} className={navLinkClass}>
                {item.label}
              </NavLink>
            ))}
            <a
              className="nav-link"
              href={REPO_URL}
              target="_blank"
              rel="noreferrer noopener"
            >
              Repository
            </a>
            <p className="mobile-nav-freshness">{statusText}</p>
          </div>
        </div>
      </header>

      <main className="page-main">
        <div className="page-wrap">
          <PlayerDetailProvider>
            <Outlet />
          </PlayerDetailProvider>
        </div>
      </main>

      <footer className="site-footer">
        <div className="site-footer-inner">
          <nav className="site-footer-nav" aria-label="Secondary">
            <Link to="/sources">Methodology</Link>
            <Link to="/sources">Data &amp; Sources</Link>
            <a href={REPO_URL} target="_blank" rel="noreferrer noopener">
              Repository
            </a>
          </nav>
          <span className="site-footer-copy">
            Independent data project · not affiliated with FIFA
          </span>
        </div>
      </footer>
    </div>
  );
}
