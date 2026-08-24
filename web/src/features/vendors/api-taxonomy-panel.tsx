/**
 * The integration-surface catalogue: what kinds of API services the platform watches and
 * intends to watch, rendered on the Services page above the workspace's own indexed services.
 *
 * A capability catalogue, not graph data — `api-service-taxonomy.ts` carries the ruling. The
 * status tag is the honest split: "watched today" is a class the pipeline genuinely binds in
 * this deployment, "planned" is declared scope. Examples are recognisable services of the
 * class, never claims this workspace calls them.
 */

import { API_SERVICE_CLASSES } from "@/features/vendors/api-service-taxonomy"
import { InfoHint } from "@/components/info-hint"
import { MetricPanel } from "@/components/metric-panel"
import { Tag } from "@/components/tag"

export function ApiTaxonomyPanel() {
  return (
    <MetricPanel
      label="Integration surfaces"
      hint={
        <InfoHint label="About integration surfaces">
          Every kind of API service the platform watches or intends to watch. A class marked
          watched-today is genuinely bound by this deployment&rsquo;s pipeline; planned is
          declared scope. The examples name services of the class — they are not claims that
          this workspace calls them, which is what the table below this panel answers.
        </InfoHint>
      }
      caption="The taxonomy of API kinds — watched today, or declared scope. The services this workspace actually calls are in the table beneath."
    >
      <div className="grid gap-section md:grid-cols-2 xl:grid-cols-3">
        {API_SERVICE_CLASSES.map((cls) => (
          <div
            key={cls.id}
            className="flex min-w-0 flex-col gap-field rounded-surface border border-line bg-card p-section"
          >
            <div className="flex flex-wrap items-center gap-row">
              <h3 className="text-emphasis">{cls.name}</h3>
              <Tag tone={cls.status === "watched today" ? "good" : "neutral"}>{cls.status}</Tag>
            </div>
            <p className="text-meta text-ink-muted">{cls.transport}</p>
            <p className="text-body text-ink-muted">{cls.watches}</p>
            <ul className="mt-auto flex flex-wrap gap-field">
              {cls.examples.map((example) => (
                <li
                  key={example}
                  className="rounded-control border border-line px-field py-field font-mono text-meta text-ink-muted"
                >
                  {example}
                </li>
              ))}
            </ul>
          </div>
        ))}
      </div>
    </MetricPanel>
  )
}
