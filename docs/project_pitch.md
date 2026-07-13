# Project Pitch

This project is a data-driven map and dashboard for the 2026 FIFA World Cup. The goal is to let anyone explore where World Cup players come from, which clubs they represent, how national teams are connected to the global club football system, and what patterns appear across geography, roster building, player development, and migration.

At the center of the project is a carefully built dataset: players, national teams, clubs, birthplaces, current club-at-call-up information, images, sources, review decisions, and eventually roster changes over time. The data is being assembled like a relational database, with stable IDs and source notes, so the public-facing site can be transparent instead of just visually impressive.

The eventual website should feel approachable for casual fans but deep enough for analysis. A visitor might filter by national team, click a club marker to see every World Cup player connected to it, compare domestic and overseas player pools, browse player cards with licensed images, or read short findings and fun facts about the tournament's global footprint.

The project is currently in the final data-preparation phase. Player identities, images, and club normalization have already gone through substantial review. The active work is club geolocation: confirming the correct club, stadium or city, and coordinates for each canonical club before building the first map/dashboard prototype.
