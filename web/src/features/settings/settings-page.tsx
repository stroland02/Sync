/**
 * Settings: what this deployment watches, and what it will not yet let you change.
 *
 * **A destination, not a level.** `.claude/rules/console-hierarchy.md` binds `GRAPH_LEVELS` to the
 * design document, and nothing there declares a Settings level. This screen configures the system
 * the graph describes rather than sitting on the graph, so it is declared in `DESTINATIONS` and
 * `routes.test.tsx` holds the level count at nine.
 *
 * **It ships read-only, and says so rather than disabling controls.** M4's write path does not
 * exist: the API serves one POST, for a repository's context. A page of greyed inputs would be a
 * promise the deployment cannot keep, and a reader cannot tell a control disabled by permission
 * from one disabled because the endpoint behind it was never written.
 *
 * **The merge policy panel the mock draws is not built, and its absence is stated rather than
 * mocked.** There is no merge policy in Sync — no setting, no column, no default named anywhere in
 * `sync.forge`. Rendering a panel reading "Squash and merge" would be the console asserting a fact
 * about the system that the system does not hold, which is the exact failure the honesty rules
 * exist to prevent. What is on screen instead is what would have to exist first.
 *
 * **M14-W278 put the two blocks in `DetailGrid` rather than a single flex-col stack.** Measured
 * against `docs/superpowers/reports/2026-08-17-console-mock-gaps.md`'s own snippet, this was the
 * one route among the ten measured that still read `sideBySideRegions: 0` — a destination, not a
 * level, but still a screen with no region beside another. Merge policy is the shorter of the two
 * blocks and sits in the rail; Adapters keeps the wide column, because its table is the one thing
 * on this screen that needs the room. No sentence moved changed a word.
 */

import { useAdapters } from "@/api/queries"
import { ErrorState, LoadingState } from "@/components/states"
import { AdapterTable } from "@/features/settings/adapter-table"
import { Breadcrumbs } from "@/layouts/breadcrumbs"
import { DetailGrid } from "@/layouts/detail-grid"
import { PageHeader } from "@/layouts/page-header"

const DEFAULT_QUESTION =
  "What does this deployment watch, what has each adapter actually delivered, and what " +
  "policy is in force when a patch is ready?"

export interface SettingsPageProps {
  readonly question?: string
}

export function SettingsPage({ question = DEFAULT_QUESTION }: SettingsPageProps) {
  const query = useAdapters()

  return (
    <DetailGrid
      header={
        <PageHeader
          title="Settings"
          question={question}
          trail={<Breadcrumbs trail={[{ label: "Settings" }]} />}
        />
      }
      rail={
        <div className="flex flex-col gap-field">
          <h2 className="text-emphasis">Merge policy</h2>
          <p className="text-body text-muted-foreground">
            Sync has no merge policy to show. Nothing in the pull-request path reads a configured
            merge strategy, a required-reviewer rule or an auto-merge switch; every pull request is
            opened the same way and left for a human. A panel naming a policy here would describe a
            setting that does not exist.
          </p>
          <p className="text-body text-muted-foreground">
            What has to land first is the write path this whole screen is read-only for. Until then
            the honest state of the deployment's policy is that it is your forge's, not Sync's.
          </p>
        </div>
      }
    >
      <div className="flex min-w-0 flex-col gap-section">
        <div className="flex flex-col gap-field">
          <h2 className="text-emphasis">Adapters</h2>
          <p className="text-body text-muted-foreground">
            Every adapter this deployment registers, beside what the graph has received from it.
            An adapter with nothing received has never delivered, which is not the same as having
            delivered nothing — a vendor Sync watched and found unchanged reports a count.
          </p>
        </div>
        {query.isPending && <LoadingState what="the adapter inventory" />}
        {query.isError && <ErrorState error={query.error} what="the adapter inventory" onRetry={() => void query.refetch()} />}
        {query.isSuccess && <AdapterTable adapters={query.data.adapters} />}
      </div>
    </DetailGrid>
  )
}
