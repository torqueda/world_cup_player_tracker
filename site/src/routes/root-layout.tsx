import { NavLink, Outlet } from "react-router-dom";

const navItems = [
  { to: "/", label: "Overview", end: true },
  { to: "/players-clubs", label: "Players & Clubs" },
  { to: "/national-teams", label: "National Teams" },
  { to: "/matches", label: "Matches" },
  { to: "/stats", label: "Stats" },
  { to: "/insights", label: "Insights" },
  { to: "/sources", label: "Data & Sources" },
];

export function RootLayout() {
  return (
    <div className="app-shell">
      <div className="ambient ambient-left" />
      <div className="ambient ambient-right" />
      <header className="site-header">
        <div className="header-kicker">World Cup 2026 Player Tracker</div>
        <div className="header-row">
          <div>
            <h1 className="site-title">Every player at the 2026 World Cup</h1>
            <p className="site-subtitle">
              All 48 final squads, their clubs on the map, official tournament stats, and
              every match result — with the sources behind each number one tab away.
            </p>
          </div>
          <div className="status-pill">Data through the quarterfinals · updated 2026-07-12</div>
        </div>
        <nav className="site-nav" aria-label="Primary">
          {navItems.map((item) => (
            <NavLink
              key={item.to}
              to={item.to}
              end={item.end}
              className={({ isActive }) =>
                isActive ? "nav-link nav-link-active" : "nav-link"
              }
            >
              {item.label}
            </NavLink>
          ))}
        </nav>
      </header>
      <main className="page-wrap">
        <Outlet />
      </main>
    </div>
  );
}
