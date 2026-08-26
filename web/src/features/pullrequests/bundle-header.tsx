/**
 * What this bundle *is*, spanning the panes and never scrolling.
 *
 * It replaces the 360px fact rail the screen carried beside a single scrolling column. The rail's
 * six rows did not evaporate with it: two are the bundle's own name and are the title line, three
 * identify the run and are the fact row, and the generations caveat is the meta row beneath — the
 * same arrangement `features/workflows/run-identity-header.tsx` landed on for the Solution
 * Workflow, and for the same reason: under a locked viewport, height spent on a rail is height
 * taken from the panes a reader is actually working in.
 *
 * **The title is the bundle's own name — `#number · branch` — and it states which nothing it is
 * when there is no number or no branch.** `bundle-facts.ts` owns both phrases, keyed by the run's
 * outcome, because a pull request missing because routing decided against a patch, missing because
 * the run was abandoned, and missing because the run has not got there yet are three different
 * facts and one sentence for all three is the defect. A title cannot carry three sentences, which
 * is why the absence is rendered in place of the value rather than beside it.
 *
 * **Those outcome-keyed phrases are reachable only once a run has answered.** With no run in hand
 * they would say *the run has not opened one yet* over a finding the checkpointer holds no run for
 * at all — one nothing rendered as another, which is the refusal this file is most exposed to. So
 * an unanswered read says which nothing the *read* is, once, and the fact row drops to the one fact
 * the address itself answers rather than repeating that same nothing three times.
 *
 * **There is no State row.** The outcome is a tag on the title line and a panel of its own beside
 * the diff; a third rendering would be one fact at three weights.
 *
 * `dt`/`dd` semantics are deliberate: the labels are what a test can address without touching a
 * class name, and a run's identity genuinely is a set of term/definition pairs.
 */

import type { ReactNode } from "react"
import { ExternalLink } from "lucide-react"
import { Link } from "react-router"

import type { WorkflowState } from "@/api/types"
import { Absent } from "@/components/status"
import { OutcomeTag } from "@/components/tag"
import {
  type BundleFacts,
  noBranchPhrase,
  noPullRequestPhrase,
} from "@/features/pullrequests/bundle-facts"
import { findingHref, workflowHref } from "@/lib/hrefs"

/** Label beside value rather than above it: on one baseline three facts cost half the height. */
function Fact({ label, children }: { label: string; children: ReactNode }) {
  return (
    <div className="flex min-w-0 items-baseline gap-row">
      <dt className="furniture shrink-0 text-meta text-ink-muted">{label}</dt>
      <dd className="min-w-0 text-body">{children}</dd>
    </div>
  )
}

export function BundleHeader({
  repoId,
  findingId,
  data,
  facts,
  failure,
}: {
  repoId: string
  findingId: string
  /** `undefined` until the run answers. */
  data: WorkflowState | undefined
  facts: BundleFacts
  /** Which nothing the run is, when it did not answer. `null` while it is still being asked. */
  failure: ReactNode | null
}) {
  return (
    <header
      data-testid="bundle-header"
      className="flex min-w-0 shrink-0 flex-col gap-row rounded-surface border border-line bg-card px-section py-row"
    >
      <div className="flex min-w-0 flex-wrap items-baseline gap-x-section gap-y-field">
        <h2 className="flex min-w-0 flex-wrap items-baseline gap-row text-emphasis">
          {data === undefined ? (
            (failure ?? <Absent>still asking the checkpointer for this run</Absent>)
          ) : facts.prNumber === null ? (
            /* One claim, not two. Measured on the running console 2026-08-26: a `reported` run
               put both outcome-keyed sentences in the title, joined by a middot — *no patch was
               warranted, so none was opened · no patch was attempted, so nothing was pushed* —
               which is the "too much information" failure at the loudest weight on the screen.
               The branch's own nothing keeps its place, in the fact row below. */
            <Absent>{noPullRequestPhrase(data.outcome)}</Absent>
          ) : (
            <>
              <span className="font-mono">#{facts.prNumber}</span>
              <span aria-hidden="true" className="text-ink-muted">
                ·
              </span>
              {facts.branch === null ? (
                <Absent>{noBranchPhrase(data.outcome)}</Absent>
              ) : (
                <span className="min-w-0 font-mono break-all">{facts.branch}</span>
              )}
            </>
          )}
        </h2>

        {data?.outcome != null && <OutcomeTag outcome={data.outcome} />}

        {/* Omitted rather than disabled when the run opened nothing: a control that cannot go
            anywhere is chrome asserting a destination that does not exist. */}
        {facts.prUrl !== null && (
          <a
            href={facts.prUrl}
            target="_blank"
            rel="noreferrer noopener"
            title="Opens the forge in a new tab — this link leaves the console."
            className="ml-auto inline-flex shrink-0 items-center gap-field text-body underline underline-offset-2"
          >
            Open the pull request
            <ExternalLink aria-hidden="true" className="size-3.5 text-graphics" />
          </a>
        )}
      </div>

      <dl className="flex min-w-0 flex-wrap items-baseline gap-x-section gap-y-field">
        {/* Answered by the address rather than by the query, so it wears no absence in any state
            and is the one fact worth keeping when nothing else has answered. */}
        <Fact label="Finding">
          <Link to={findingHref(repoId, findingId)} className="underline underline-offset-2">
            <code className="font-mono text-meta break-all">{findingId}</code>
          </Link>
        </Fact>

        {data !== undefined && (
          <>
            <Fact label="Run">
              <code className="font-mono text-meta break-all select-all">{data.thread_id}</code>
            </Fact>

            <Fact label="Repository">
              {data.repo_id === null ? (
                <Absent>the run recorded no repository</Absent>
              ) : (
                <Link
                  to={`/repositories/${encodeURIComponent(data.repo_id)}`}
                  className="underline underline-offset-2"
                >
                  <code className="font-mono text-meta break-all">{data.repo_id}</code>
                </Link>
              )}
            </Fact>
          </>
        )}

        <p className="min-w-0 text-meta text-ink-muted">
          Five of the run&#39;s eight nodes — the ones a pull request rests on.{" "}
          <Link to={workflowHref(repoId, findingId)} className="underline underline-offset-2">
            The solution workflow
          </Link>{" "}
          shows all eight.
          {data !== undefined && data.generation_count > 1 && (
            <>
              {" "}
              This is the newest of {data.generation_count} runs the checkpointer holds for this
              finding; an earlier generation may have reached a pull request where this one has not.
            </>
          )}
        </p>
      </dl>
    </header>
  )
}
