# Launch Guide: Making the Tracker Usable by Non-Technical People

Written 2026-07-13. This answers three questions: which delivery form to use (website vs
downloadable program), whether the project is technically ready for it, and what it costs.

## The short answer

**Publish it as a website on a free static host. Do not build a downloadable program.**

The site is already the right shape for this: it's a *static* web app — after `pnpm build`
it is just HTML, CSS, JavaScript, and the baked-in JSON data in `site/dist/`. There is no
server, no database, and no login, so hosting it means "put these files on a CDN," which
every major static host does for free. A visitor just opens a URL; nothing to install.

### Why not a downloadable executable

A desktop app (Electron/Tauri wrapper around the same site) is technically possible but
strictly worse here:

- **Distribution friction**: unsigned apps trigger macOS/Windows security warnings, and
  code-signing certificates cost ~$100–400/year — the exact opposite of "easy for
  non-technical people."
- **Size and updates**: an Electron bundle is ~100+ MB per platform, and every dataset
  refresh means users re-download an installer, versus a website where a refresh is
  invisible to them.
- **No offline need**: the map tiles and fonts load from the internet anyway, so the app
  wouldn't even work fully offline.

If a desktop artifact is ever truly wanted, Tauri (~10 MB bundles) is the path — but it
should come after the website, not instead of it.

## Is the project set up correctly for a website?

Yes, with one thing already handled and two one-time steps left:

- ✅ **Static build works**: `cd site && pnpm build` produces a self-contained `site/dist/`.
- ✅ **SPA routing fallback**: `site/public/_redirects` (added 2026-07-13) tells
  Netlify/Cloudflare Pages to serve `index.html` for deep links like `/stats`, so shared
  URLs and refreshes work. Without it, direct links would 404.
- ⬜ **First git commit + GitHub push** (one-time): the repo is initialized but has no
  commits yet. Git-connected hosting (the good kind — auto-deploy on push) needs this:

  ```bash
  cd /path/to/world_cup_player_tracker
  git add -A
  git commit -m "Initial commit: World Cup 2026 player tracker (dataset + dashboard)"
  # create an empty repo on github.com first, then:
  git remote add origin https://github.com/<your-username>/world_cup_player_tracker.git
  git push -u origin main
  ```

- ⬜ **Connect a host** (one-time, ~15 minutes, see below).

## Recommended host and exact steps

**Recommendation: Netlify or Cloudflare Pages** (equivalent for this project; both free).
They handle the SPA fallback via the `_redirects` file already in place, build on every
push, and give you a URL like `world-cup-tracker.netlify.app` immediately.

1. Sign up (free) with your GitHub account at netlify.com or pages.cloudflare.com.
2. "Add new site → Import an existing project" → pick the `world_cup_player_tracker` repo.
3. Settings when asked:
   - **Base directory**: `site`
   - **Build command**: `pnpm build`
   - **Publish directory**: `site/dist`
4. Deploy. Every future `git push` re-deploys automatically.

No-git fallback (works today, before any commit): run `pnpm build` locally and drag the
`site/dist` folder onto Netlify's "Deploy manually" drop zone. Fine for a first look;
switch to the git flow for real use.

**GitHub Pages** also works and is fine if you prefer everything on GitHub, but it needs
two extra tweaks (a `base` path in `vite.config.ts` and a 404-redirect workaround for SPA
routing), so it's the second choice, not the first.

## Costs

| Item | Cost |
|---|---|
| Netlify / Cloudflare Pages / GitHub Pages hosting | **$0** (free tiers far exceed this site's needs: ~100 GB bandwidth/month on Netlify free; Cloudflare Pages is unlimited bandwidth) |
| OpenStreetMap tiles, Google Fonts, Wikimedia/GeoNames data | $0 (attribution already in place; traffic is well within OSM's fair-use tile policy at hobby scale) |
| Custom domain (optional), e.g. `worldcuptracker.com` | ~$10–15/year at a registrar; both hosts attach it with free automatic HTTPS |
| Total to launch | **$0** ($10–15/yr only if you want a custom domain) |

The only realistic future cost trigger is viral-level traffic on Netlify's free bandwidth
cap — Cloudflare Pages has no such cap, which is a reason to pick it if you expect a spike
around the final.

## How updates work after launch

1. Edit the master workbook (Google Sheets), download to `data/master/`.
2. `python scripts/export/refresh_all_exports.py` (strict audit gate).
3. `git commit` + `git push` → the host rebuilds and the public site updates in ~1 minute.

Visitors always see the newest data; the "Data through the …" pill in the header tells
them how fresh it is.

## Pre-launch checklist (technical)

- [ ] First commit + push to GitHub (commands above).
- [ ] Connect Netlify or Cloudflare Pages with the settings above.
- [ ] Click through all seven routes on the live URL (especially deep links like
      `/stats` and `/insights`, which exercise the SPA fallback).
- [ ] Optional: custom domain + check the OpenStreetMap attribution is visible on the map.
