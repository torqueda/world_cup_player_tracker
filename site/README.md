# Site

The React, TypeScript, React Router and Vite app for the World Cup 2026 Player Tracker, live at https://worldcupplayertracker.netlify.app/.

It reads the JSON exports in `../data/processed/app_exports/` through the `@data` alias in `vite.config.ts`, so regenerating the exports is all it takes to change the data. `src/lib/data/` loads and joins the tables, `src/lib/analytics/` computes the Analysis page's measures (with unit tests), and `src/routes/` holds one file per page.

How to install, run, test and build it is in the main [README](../README.md#running-the-site-locally).
