/**
 * Settings → Setup: what the full loop needs, each item probed and stated.
 *
 * The loop is index → detect → remediate → verify → pull request, and this panel is the one
 * place a person setting Sync up beside a codebase can see which prerequisites stand: the
 * indexed codebase, the staged vendor specification, forge access (`gh`), the agent runtime
 * (`claude`), the git remote the loop addresses, and the merge policy in force.
 *
 * **The states are three, and nothing sums them.** `ready` and `missing` are probed answers;
 * `unanswered` is a probe that itself failed, which is a different fact from either and gets
 * its own word. A progress figure over the six would average "could not check" onto "checked
 * and missing", which is the collapse this console refuses everywhere else.
 *
 * The one editable field lives beside the item that needs it: the git remote is recorded here
 * because `sync run` clones the remote and addresses the same repository through the forge —
 * a local checkout carries no owner and name for that call.
 */

import { useState } from "react"
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query"

import { InfoHint } from "@/components/info-hint"
import { ErrorState, LoadingState } from "@/components/states"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { usePanelStatus } from "@/features/settings/panel-status"
import type { StatusSegment } from "@/layouts/status-band"
import { describeRecordWindow } from "@/lib/record-window"
import {
  fetchRepoSettings,
  fetchSetup,
  updateRepoSettings,
  type SetupItem,
} from "@/features/settings/api"

/** The state as a word in a hairline chip — a closed vocabulary, legible without colour. */
function StateChip({ state }: { state: SetupItem["state"] }) {
  const wording: Record<SetupItem["state"], string> = {
    ready: "Ready",
    missing: "Missing",
    unanswered: "Not answered",
  }
  return (
    <span className="furniture shrink-0 rounded-control border border-line px-field py-field text-meta text-ink-muted">
      {wording[state]}
    </span>
  )
}

function RemoteUrlEditor({ repoId }: { repoId: string }) {
  const queryClient = useQueryClient()
  const settingsQuery = useQuery({
    queryKey: ["repo-settings", repoId],
    queryFn: ({ signal }) => fetchRepoSettings(repoId, signal),
  })
  const current = settingsQuery.data?.remote_url ?? null
  const [value, setValue] = useState("")
  const [touched, setTouched] = useState(false)
  const shown = touched ? value : (current ?? "")
  const mutation = useMutation({
    mutationFn: (remote_url: string) => updateRepoSettings(repoId, { remote_url }),
    onSuccess: () => {
      setTouched(false)
      void queryClient.invalidateQueries({ queryKey: ["setup"] })
      void queryClient.invalidateQueries({ queryKey: ["repo-settings", repoId] })
    },
  })
  const changed = touched && shown.trim() !== (current ?? "")

  return (
    <div className="flex w-full max-w-xl flex-col gap-field">
      <div className="flex flex-wrap items-center gap-row">
        <Input
          value={shown}
          onChange={(event) => {
            setTouched(true)
            setValue(event.target.value)
          }}
          placeholder="https://github.com/owner/repo or git@github.com:owner/repo"
          className="flex-1 bg-surface font-mono text-meta border-line"
        />
        <Button
          size="sm"
          disabled={!changed || mutation.isPending}
          onClick={() => mutation.mutate(shown.trim())}
        >
          {mutation.isPending ? "Saving…" : "Save remote"}
        </Button>
      </div>
      {mutation.isError && (
        <p className="text-meta text-ink-muted">
          {mutation.error instanceof Error ? mutation.error.message : "The save did not go through."}
        </p>
      )}
    </div>
  )
}

function SetupRow({ item, repoId }: { item: SetupItem; repoId: string | null }) {
  return (
    <div className="flex flex-col gap-field border-b border-line py-section last:border-b-0 last:pb-0 first:pt-0">
      <div className="flex flex-wrap items-center gap-row">
        <span className="text-body font-medium text-ink">{item.label}</span>
        <StateChip state={item.state} />
      </div>
      <p className="max-w-prose text-body text-ink-muted">{item.detail}</p>
      {item.fix !== null && item.state !== "ready" && (
        <p className="text-meta text-ink-muted">
          Fix: <code className="font-mono text-ink">{item.fix}</code>
        </p>
      )}
      {item.id === "remote" && repoId !== null && <RemoteUrlEditor repoId={repoId} />}
    </div>
  )
}

export function SetupPanel({ repoId }: { repoId: string }) {
  const query = useQuery({
    queryKey: ["setup", repoId],
    queryFn: ({ signal }) => fetchSetup(repoId, signal),
  })

  // The prerequisites themselves are counted; their three states are not. `setup.py` refuses a
  // figure over them, because a count of ready items over six averages "could not check" onto
  // "checked and missing" — the collapse the whole checklist exists to keep apart.
  const status: StatusSegment[] = query.isSuccess
    ? [
        {
          kind: "records",
          label: "Prerequisites",
          text: describeRecordWindow(
            0,
            query.data.items.length,
            { count: query.data.items.length, boundReached: false },
            "prerequisite",
            "prerequisites",
          ),
        },
        {
          kind: "note",
          text: "Each item states its own answer and nothing sums them: probed and ready, probed and missing, and a probe that itself did not answer are three different facts.",
        },
      ]
    : [
        {
          kind: "none",
          why: query.isError
            ? "the setup checklist did not answer"
            : "probing what the full loop needs",
        },
      ]
  usePanelStatus(status)

  if (query.isPending) return <LoadingState what="the setup checklist" />
  if (query.isError) {
    return (
      <ErrorState
        error={query.error}
        what="the setup checklist"
        onRetry={() => void query.refetch()}
      />
    )
  }

  return (
    <div className="flex flex-col gap-section">
      <div className="flex flex-col gap-field border-b border-line pb-field">
        <div className="flex items-center gap-row">
          <h2 className="text-emphasis font-medium text-ink">Setup</h2>
          <InfoHint label="About setup">
            Everything the full loop needs, probed when this screen loads: index → detect →
            remediate → verify → pull request. Each item states its own answer; there is no
            score over them, because &ldquo;could not check&rdquo; and &ldquo;checked and
            missing&rdquo; are different facts.
          </InfoHint>
        </div>
        <p className="max-w-prose text-body text-ink-muted">
          Probed just now, on this machine — a credential fixed in another terminal shows up on
          the next load.
        </p>
      </div>
      <div className="flex flex-col rounded-surface border border-line bg-surface p-section">
        {query.data.items.map((item) => (
          <SetupRow key={item.id} item={item} repoId={query.data.repo_id} />
        ))}
      </div>
    </div>
  )
}
