import type { ReactNode } from "react";
import { Link, NavLink } from "react-router-dom";
import { SourceNote } from "@/components/source-note";
import { PageHeader } from "@/components/ui";
import { playerStats, teamStats } from "@/lib/data";
import { ANALYSIS_BASE, ANALYSIS_PAGES, analysisPath } from "@/routes/analysis/pages";

export const AS_OF = playerStats[0]?.as_of_stage ?? teamStats[0]?.as_of_stage ?? "latest";

export function topBy<T>(rows: T[], value: (row: T) => number | null, asc = false): T | null {
  const valid = rows.filter((row) => value(row) !== null);
  if (valid.length === 0) {
    return null;
  }
  return [...valid].sort((a, b) => {
    const delta = (value(a) ?? 0) - (value(b) ?? 0);
    return asc ? delta : -delta;
  })[0];
}

// Team names as they read inside a sentence: "the United States".
const TAKES_THE = new Set(["United States", "Netherlands", "Czech Republic"]);

export function teamInSentence(team: string): string {
  return TAKES_THE.has(team) ? `the ${team}` : team;
}

export function listInWords(items: string[]): string {
  return items.length <= 1 ? (items[0] ?? "") : `${items.slice(0, -1).join(", ")} and ${items[items.length - 1]}`;
}

function subNavClass({ isActive }: { isActive: boolean }): string {
  return isActive ? "section-nav-link section-nav-link-active" : "section-nav-link";
}

// One Analysis page: the heading, then links to the other Analysis pages.
export function AnalysisPage({
  slug,
  intro,
  actions,
  children,
}: {
  slug: string;
  intro: ReactNode;
  actions?: ReactNode;
  children: ReactNode;
}) {
  const page = ANALYSIS_PAGES.find((item) => item.slug === slug);
  return (
    <div className="page-stack">
      <PageHeader
        eyebrow={<Link to={ANALYSIS_BASE}>Analysis</Link>}
        title={page?.label ?? "Analysis"}
        intro={intro}
        actions={actions}
      />
      <nav className="section-nav reveal" aria-label="Analysis pages">
        {ANALYSIS_PAGES.map((item) => (
          <NavLink key={item.slug} to={analysisPath(item.slug)} className={subNavClass}>
            {item.label}
          </NavLink>
        ))}
      </nav>
      {children}
    </div>
  );
}

export function sourceNote(definition: ReactNode, population: ReactNode, threshold: ReactNode = "None") {
  return <SourceNote definition={definition} population={population} threshold={threshold} />;
}

// "×1.94 (1.54 to 2.45)" in a table cell: the estimate, with its interval on a
// smaller second line, so the column stays narrow on phones.
export function IntervalCell({ text }: { text: string }) {
  const match = /^(.*) \((.*)\)$/.exec(text);
  if (!match) {
    return <>{text}</>;
  }
  return (
    <>
      {match[1]}
      <span className="table-cell-note">{match[2]}</span>
    </>
  );
}
