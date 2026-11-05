// Match stages in the order they are played, as the data names them. The
// pages and the analytics sort stages by this list, never alphabetically
// (alphabetically, "Final" comes before "First Stage").
export const MATCH_STAGES: readonly string[] = [
  "First Stage",
  "Round of 32",
  "Round of 16",
  "Quarter-final",
  "Semi-final",
  "Play-off for third place",
  "Final",
];

export const KNOCKOUT_STAGES: readonly string[] = MATCH_STAGES.slice(1);

const STAGE_LABELS: Record<string, string> = {
  "First Stage": "Group stage",
};

export function stageLabel(stage: string): string {
  return STAGE_LABELS[stage] ?? stage;
}

// Position in the tournament; a stage the list doesn't know sorts last.
export function stageRank(stage: string): number {
  const index = MATCH_STAGES.indexOf(stage);
  return index === -1 ? MATCH_STAGES.length : index;
}
