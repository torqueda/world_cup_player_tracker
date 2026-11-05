import { createBrowserRouter } from "react-router-dom";
import { RootLayout } from "@/routes/root-layout";
import { OverviewRoute } from "@/routes/overview-route";
import { PlayersClubsRoute } from "@/routes/players-clubs-route";
import { NationalTeamsRoute } from "@/routes/national-teams-route";
import { MatchesRoute } from "@/routes/matches-route";
import { StatsRoute } from "@/routes/stats-route";
import { AnalysisIndexRoute } from "@/routes/analysis/index-route";
import { SquadsRoute } from "@/routes/analysis/squads-route";
import { ClubsRoute } from "@/routes/analysis/clubs-route";
import { PlayersRoute } from "@/routes/analysis/players-route";
import { AnalysisMatchesRoute } from "@/routes/analysis/matches-route";
import { CompareRoute } from "@/routes/analysis/compare-route";
import { SourcesRoute } from "@/routes/sources-route";
import { NotFoundRoute } from "@/routes/not-found-route";
import { RouteError } from "@/routes/route-error";
import { loadRoute } from "@/lib/routing/lazy-route";

// Where a navigation in progress is going. A page that loads on first visit
// is fetched before the address changes, so this is the page to open if its
// file has to be fetched afresh.
function pendingAddress(): string | undefined {
  const next = router.state.navigation.location;
  return next ? `${next.pathname}${next.search}${next.hash}` : undefined;
}

export const router = createBrowserRouter([
  {
    path: "/",
    element: <RootLayout />,
    // Fallback if the layout itself fails; page errors are caught below.
    errorElement: <RouteError />,
    children: [
      {
        // A page that fails to load or render shows a plain message inside
        // the layout, not the router's developer error screen.
        errorElement: <RouteError />,
        children: [
          {
            index: true,
            element: <OverviewRoute />,
          },
          {
            path: "players-clubs",
            element: <PlayersClubsRoute />,
          },
          {
            path: "national-teams",
            element: <NationalTeamsRoute />,
          },
          {
            path: "matches",
            element: <MatchesRoute />,
          },
          {
            path: "stats",
            element: <StatsRoute />,
          },
          {
            path: "insights",
            children: [
              { index: true, element: <AnalysisIndexRoute /> },
              { path: "squads", element: <SquadsRoute /> },
              { path: "clubs", element: <ClubsRoute /> },
              { path: "players", element: <PlayersRoute /> },
              { path: "matches", element: <AnalysisMatchesRoute /> },
              { path: "compare", element: <CompareRoute /> },
              // These two read the analysis files, so they load on first visit
              // instead of adding them to every page's download.
              {
                path: "what-wins",
                lazy: async () => ({
                  Component: (
                    await loadRoute(
                      () => import("@/routes/analysis/what-wins-route"),
                      pendingAddress,
                    )
                  ).WhatWinsRoute,
                }),
              },
              {
                path: "photos",
                lazy: async () => ({
                  Component: (
                    await loadRoute(() => import("@/routes/analysis/photos-route"), pendingAddress)
                  ).PhotosRoute,
                }),
              },
            ],
          },
          {
            path: "sources",
            element: <SourcesRoute />,
          },
          {
            // Any other address: a page-not-found message inside the normal layout,
            // not the router's developer error screen.
            path: "*",
            element: <NotFoundRoute />,
          },
        ],
      },
    ],
  },
]);
