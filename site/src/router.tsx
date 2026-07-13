import { createBrowserRouter } from "react-router-dom";
import { RootLayout } from "@/routes/root-layout";
import { OverviewRoute } from "@/routes/overview-route";
import { PlayersClubsRoute } from "@/routes/players-clubs-route";
import { NationalTeamsRoute } from "@/routes/national-teams-route";
import { MatchesRoute } from "@/routes/matches-route";
import { StatsRoute } from "@/routes/stats-route";
import { InsightsRoute } from "@/routes/insights-route";
import { SourcesRoute } from "@/routes/sources-route";

export const router = createBrowserRouter([
  {
    path: "/",
    element: <RootLayout />,
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
        element: <InsightsRoute />,
      },
      {
        path: "sources",
        element: <SourcesRoute />,
      },
    ],
  },
]);
