import { Link, isRouteErrorResponse, useRouteError } from "react-router-dom";
import { PageHeader } from "@/components/ui";
import { isStaleFileError } from "@/lib/routing/lazy-route";

// Shown in place of a page that fails to load or render, inside the normal
// layout, instead of the router's developer error screen.
export function RouteError() {
  const error = useRouteError();
  const stale = isStaleFileError(error);
  const notFound = isRouteErrorResponse(error) && error.status === 404;

  const title = notFound ? "Page not found" : "This page could not load";
  const intro = notFound
    ? "There is no page at this address. The link may be out of date or the address mistyped."
    : stale
      ? "Its files could not be downloaded. This happens just after the site is updated or when the connection drops, and reloading usually fixes it."
      : "Something went wrong while showing this page. Reloading usually fixes it.";

  return (
    <div className="page-stack">
      <PageHeader
        title={title}
        intro={intro}
        actions={
          <>
            {notFound ? null : (
              <button
                type="button"
                className="button-primary"
                onClick={() => window.location.reload()}
              >
                Reload the page
              </button>
            )}
            <Link className={notFound ? "button-primary" : "button-secondary"} to="/">
              Go to the home page
            </Link>
          </>
        }
      />
    </div>
  );
}
