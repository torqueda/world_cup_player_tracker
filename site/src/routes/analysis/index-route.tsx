import { Link, Navigate, useLocation } from "react-router-dom";
import { PageHeader } from "@/components/ui";
import { ANALYSIS_PAGES, OLD_SECTION_TARGETS, analysisPath } from "@/routes/analysis/pages";
import { AS_OF } from "@/routes/analysis/shared";

export function AnalysisIndexRoute() {
  const location = useLocation();

  // Analysis used to be one long page. Its old section links, such as
  // /insights#impact, and shared comparisons (/insights?teamA=ARG&teamB=FRA)
  // go to the page that now holds that section.
  const oldTarget = OLD_SECTION_TARGETS[location.hash.slice(1)];
  if (oldTarget) {
    const [path, hash] = oldTarget.split("#");
    return <Navigate replace to={{ pathname: path, search: location.search, hash: hash ? `#${hash}` : "" }} />;
  }
  const params = new URLSearchParams(location.search);
  if (params.has("teamA") || params.has("teamB")) {
    return <Navigate replace to={{ pathname: analysisPath("compare"), search: location.search }} />;
  }

  return (
    <div className="page-stack">
      <PageHeader
        title="Tournament analysis"
        intro={`Each page below answers one question about the 2026 World Cup. Data through the ${AS_OF} stage.`}
      />
      <ul className="analysis-index reveal">
        {ANALYSIS_PAGES.map((page) => (
          <li key={page.slug}>
            <Link className="analysis-index-card" to={analysisPath(page.slug)}>
              <span className="analysis-index-title">{page.label}</span>
              <span className="analysis-index-question">{page.question}</span>
            </Link>
          </li>
        ))}
      </ul>
      <p className="insight-note">
        The data-quality checks are on{" "}
        <Link className="table-link" to="/sources#quality">
          Data &amp; sources
        </Link>
        , with the rest of
        the method.
      </p>
    </div>
  );
}
