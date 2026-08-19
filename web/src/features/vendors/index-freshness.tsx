/**
 * Dashboard N3: when the index last read each service's call sites, oldest first.
 *
 * **Staleness, which is not liveness, and the distinction is one of the four this console is
 * built to render.** A date here says when Sync last looked; it says nothing about whether the
 * service is up, whether the integration is working, or whether anything has changed since. The
 * ordering is oldest-first because the useful question is *what has Sync not looked at lately*,
 * and a table sorted by name buries that answer.
 *
 * **Not a chart, and deliberately.** A duration is chartable, but every bar length here would be
 * "time since Sync ran", which is one number repeated per row with a common cause — the last
 * index pass. Bars would draw a spread that is an artefact of when each service's first call site
 * was written rather than a difference worth reading. The dates themselves are the answer.
 *
 * **No colour, no threshold, no badge.** There is no age at which an index becomes wrong, so a
 * threshold would be invented and a coloured one would be the traffic light `CLAUDE.md` refuses.
 * A reader who knows their own release cadence knows what old means here; this console does not.
 *
 * **A service missing a date was never indexed, which is not the same as indexed long ago**, and
 * the two are rendered apart rather than sorted together with the null at one end.
 */

import { InfoHint } from "@/components/info-hint"
import { MetricPanel } from "@/components/metric-panel"
import { RelativeTime } from "@/components/relative-time"
import { Absent } from "@/components/status"

export function IndexFreshness({
  lastIndexed,
}: {
  /** Service id to ISO timestamp, or null where the index recorded none. */
  lastIndexed: Record<string, string | null>
}) {
  const entries = Object.entries(lastIndexed)
  const dated = entries
    .filter((entry): entry is [string, string] => entry[1] !== null)
    .sort((a, b) => a[1].localeCompare(b[1]))
  const undated = entries.filter(([, iso]) => iso === null).map(([service]) => service)

  const hint = (
    <InfoHint label="About index freshness">
      When the index last read a call site binding this codebase to each service, oldest first.
      This is staleness and never liveness: it says when Sync last looked, not whether the service
      is reachable, working, or unchanged since. There is no age at which this becomes wrong, so
      nothing here is coloured or flagged — an interval that matters for a weekly release is
      unremarkable for a quarterly one, and this console does not know which you run.
    </InfoHint>
  )

  if (entries.length === 0) {
    return (
      <MetricPanel label="Index freshness" hint={hint} caption="No service to date.">
        <p className="max-w-prose text-body text-ink-muted">
          The index holds no call site for any service in this codebase, so there is no date to
          report. That is the absence of an index pass rather than a codebase nothing was found in.
        </p>
      </MetricPanel>
    )
  }

  return (
    <MetricPanel
      label="Index freshness"
      hint={hint}
      caption="When the index last read each service's call sites, oldest first. A date here is when Sync looked, not when anything changed."
    >
      <div className="flex flex-col gap-row">
        {dated.length > 0 && (
          <ul className="flex flex-col gap-field">
            {dated.map(([service, iso]) => (
              <li key={service} className="flex items-baseline justify-between gap-section">
                <span className="min-w-0 truncate font-mono text-meta text-ink">{service}</span>
                <span className="shrink-0 text-meta text-ink-muted">
                  <RelativeTime iso={iso} />
                </span>
              </li>
            ))}
          </ul>
        )}

        {undated.length > 0 && (
          <div className="flex flex-col gap-field border-t border-line pt-row">
            <h3 className="furniture text-meta text-ink-muted">Never recorded</h3>
            <ul className="flex flex-col gap-field">
              {undated.map((service) => (
                <li key={service} className="flex items-baseline justify-between gap-section">
                  <span className="min-w-0 truncate font-mono text-meta text-ink">{service}</span>
                  <span className="shrink-0 text-meta">
                    <Absent>no index date</Absent>
                  </span>
                </li>
              ))}
            </ul>
            <p className="max-w-prose text-meta text-ink-muted">
              These are apart from the dated rows rather than sorted with them at one end. A
              service the index has never recorded a date for is not a service indexed a long time
              ago — it is one this list cannot date at all, and putting the two in one order would
              read the second as the first.
            </p>
          </div>
        )}
      </div>
    </MetricPanel>
  )
}
