/**
 * Where you are in the API Dependency Graph.
 *
 * The trail is passed in rather than derived from the URL because only the page knows the
 * labels — `/vendors/stripe` is "stripe" but `/findings/f-91ac` is a finding whose vendor
 * is not in the path.
 */

import { Link } from "react-router"

export interface Crumb {
  label: string
  /** Absent on the current level, which is a destination rather than a link. */
  to?: string
}

export function Breadcrumbs({ trail }: { trail: Crumb[] }) {
  return (
    <nav aria-label="Breadcrumb" className="text-sm text-muted-foreground">
      <ol className="flex flex-wrap items-center gap-2">
        {trail.map((crumb, index) => (
          <li key={`${crumb.label}-${index}`} className="flex items-center gap-2">
            {index > 0 && <span aria-hidden="true">→</span>}
            {crumb.to === undefined ? (
              <span aria-current="page" className="text-foreground">
                {crumb.label}
              </span>
            ) : (
              <Link to={crumb.to} className="underline underline-offset-2">
                {crumb.label}
              </Link>
            )}
          </li>
        ))}
      </ol>
    </nav>
  )
}
