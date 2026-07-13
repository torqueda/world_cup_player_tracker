# Frontend Prototype

This folder contains the React + TypeScript + React Router + Vite prototype for the World Cup 2026 Player Tracker.

## Current role

The app is intentionally scaffolded before the shared JSON data-access layer is wired in. That keeps the route structure, visual system, and build surface stable while the dataset continues to evolve.

## Planned data source

The app is expected to read from the project-generated exports in:

- `../data/processed/app_exports/`

The current `vite.config.ts` already exposes an `@data` alias pointing at that folder so the next step can add typed loaders without moving the data into the app tree.

## Expected next build step

Add the typed data-access layer that loads the exported JSON files and start with the `Players & Clubs` route as the first fully functional screen.
