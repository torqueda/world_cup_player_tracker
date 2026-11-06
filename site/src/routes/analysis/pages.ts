// The Analysis pages, in menu order. root-layout.tsx reads the labels for the
// browser-tab titles, and the index page lists them.

export interface AnalysisPageInfo {
  slug: string;
  label: string;
  question: string;
}

export const ANALYSIS_PAGES: AnalysisPageInfo[] = [
  {
    slug: "squads",
    label: "Squad make-up",
    question: "How old is each squad, where do its players play, and how many clubs does it draw on?",
  },
  {
    slug: "origins",
    label: "Where players come from",
    question: "Where were the players born, and where do they play their club football?",
  },
  {
    slug: "clubs",
    label: "Clubs & leagues",
    question: "Which clubs and leagues sent the most players, minutes and goals?",
  },
  {
    slug: "players",
    label: "Player efficiency",
    question: "Who scored and assisted most per 90 minutes?",
  },
  {
    slug: "matches",
    label: "Matches & venues",
    question: "How did goals vary by stage and venue, and how did the confederations fare against each other?",
  },
  {
    slug: "compare",
    label: "Compare two teams",
    question: "How do two squads and their tournaments compare side by side?",
  },
  {
    slug: "what-wins",
    label: "What goes with winning",
    question: "Did rating, squad value, top-league players, age or caps go with winning matches?",
  },
  {
    slug: "photos",
    label: "Who has a photo",
    question: "Which players have a free photo on Wikimedia Commons, and what do they have in common?",
  },
];

export const ANALYSIS_BASE = "/insights";

export function analysisPath(slug: string): string {
  return `${ANALYSIS_BASE}/${slug}`;
}

// Sections of the old single Analysis page, so its links keep working.
export const OLD_SECTION_TARGETS: Record<string, string> = {
  scorecard: analysisPath("squads"),
  concentration: `${analysisPath("squads")}#concentration`,
  impact: analysisPath("clubs"),
  compare: analysisPath("compare"),
  efficiency: analysisPath("players"),
  matches: analysisPath("matches"),
  quality: "/sources#quality",
};
