import { Link } from "react-router-dom";
import { PageHeader } from "@/components/ui";

export function NotFoundRoute() {
  return (
    <div className="page-stack">
      <PageHeader
        title="Page not found"
        intro="There is no page at this address. The link may be out of date or the address mistyped."
        actions={
          <Link className="button-primary" to="/">
            Go to the home page
          </Link>
        }
      />
    </div>
  );
}
