import type { ReactNode } from "react";
import metaJson from "@data/meta.json";

const UPDATE_LABEL = (metaJson as { exported_at?: string }).exported_at ?? "Not recorded";

// Four short facts side by side, not one line that runs the full panel width.
export function SourceNote({
  definition,
  population,
  threshold = "None",
  updated = UPDATE_LABEL,
}: {
  definition: ReactNode;
  population: ReactNode;
  threshold?: ReactNode;
  updated?: ReactNode;
}) {
  return (
    <dl className="source-note source-note-facts">
      <div>
        <dt>Definition</dt>
        <dd>{definition}</dd>
      </div>
      <div>
        <dt>Population</dt>
        <dd>{population}</dd>
      </div>
      <div>
        <dt>Minimum threshold</dt>
        <dd>{threshold}</dd>
      </div>
      <div>
        <dt>Updated</dt>
        <dd>{updated}</dd>
      </div>
    </dl>
  );
}
