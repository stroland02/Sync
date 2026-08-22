/**
 * Settings → Model: which model writes the patches, and whose credential pays.
 *
 * **Owner ruling, 2026-08-19: the operator's own credential is never inherited.** A deployment
 * that configures nothing spends nobody. So the honest default state is *no model connected*, and
 * this screen's job is to say that plainly and show the two ways to connect one.
 *
 * ## Why this reads rather than writes
 *
 * Every other Settings panel that writes goes through a route that stores a value in the graph.
 * This one does not, and the reason is the rule rather than the effort: **a model credential is a
 * customer secret, and `CLAUDE.md` says we never hold one, unqualified.** A form that accepted an
 * API key would have to put it somewhere — a column, a config file, a request body — and every
 * one of those is a place it can leak. The key stays in the environment the operator controls, and
 * this screen reports only *whether one is present*.
 *
 * That is a real trade and it is worth naming: this is configuration shown, not configuration
 * performed. What it buys is that Sync never becomes a place a stolen key is found.
 *
 * ## What it shows
 *
 * The three states the resolver can be in, each with the exact variables that move it forward —
 * carried on the payload rather than restated here, so a variable renamed in Python does not leave
 * a screen naming the old one.
 */

import { useQuery } from "@tanstack/react-query"

import {
  ApiStatusError,
  MalformedResponseError,
  UnreachableApiError,
} from "@/api/errors"
import { InfoHint } from "@/components/info-hint"
import { Absent } from "@/components/status"
import { ErrorState, LoadingState } from "@/components/states"
import { usePanelStatus } from "@/features/settings/panel-status"
import type { StatusSegment } from "@/layouts/status-band"

interface ModelProvider {
  kind: "unconfigured" | "frontier" | "self-hosted" | "unusable"
  model: string | null
  base_url: string | null
  has_credential: boolean
  usable: boolean
  detail: string
  blocked_because?: string
  variables: { model: string; base_url: string; api_key: string }
}

interface SetupPayload {
  operator: { forge_login: string | null }
  model: ModelProvider
}

async function fetchSetup(signal?: AbortSignal): Promise<SetupPayload> {
  const path = "/api/setup"
  let response: Response
  try {
    response = await fetch(path, { headers: { Accept: "application/json" }, signal })
  } catch (cause) {
    if (signal?.aborted) throw cause
    throw new UnreachableApiError(path, { cause })
  }
  if (!response.ok) throw new ApiStatusError(response.status, path)
  try {
    return (await response.json()) as SetupPayload
  } catch (cause) {
    throw new MalformedResponseError(path, { cause })
  }
}

function Option({
  title,
  cost,
  detail,
  lines,
  active,
}: {
  title: string
  cost: string
  detail: string
  lines: string[]
  active: boolean
}) {
  return (
    <div
      className={
        "flex min-w-0 flex-col gap-row rounded-surface border bg-surface p-section " +
        (active ? "border-line-strong" : "border-line")
      }
    >
      <div className="flex flex-wrap items-baseline justify-between gap-row">
        <h3 className="text-section">{title}</h3>
        <span className="furniture rounded-control border border-line px-field py-field text-meta text-ink-muted">
          {active ? "in use" : cost}
        </span>
      </div>
      <p className="max-w-prose text-body text-ink-muted">{detail}</p>
      {lines.length > 0 && (
        <code className="block overflow-x-auto rounded-control border border-line bg-surface-subtle px-field py-field font-mono text-meta text-ink select-all">
          {lines.map((line) => (
            <span key={line} className="block">
              {line}
            </span>
          ))}
        </code>
      )}
    </div>
  )
}

export function ModelSettingsPanel() {
  const query = useQuery({
    queryKey: ["setup", "model"],
    queryFn: ({ signal }) => fetchSetup(signal),
  })

  const model = query.data?.model ?? null
  const status: StatusSegment[] =
    model === null
      ? [
          {
            kind: "none",
            why: query.isError
              ? "the model connection did not answer"
              : "asking which model is connected",
          },
        ]
      : [
          { kind: "listing", label: "Model", text: model.detail },
          {
            kind: "listing",
            label: "Credential",
            // `unusable` is the resolver refusing to answer, so its `has_credential: false` is a
            // default rather than a probe: "none supplied" there states a measurement nothing made.
            text:
              model.kind === "unusable"
                ? "not determined — the configuration did not resolve"
                : model.has_credential
                  ? "one is present in the environment"
                  : "none supplied",
          },
        ]
  usePanelStatus(status)

  if (query.isPending) return <LoadingState what="the model connection" />
  if (query.isError) {
    return (
      <ErrorState
        error={query.error}
        what="the model connection"
        onRetry={() => void query.refetch()}
      />
    )
  }

  const provider = query.data.model
  const vars = provider.variables

  return (
    <div className="flex flex-col gap-section">
      <div className="flex items-center gap-row">
        <h2 className="text-section">Model</h2>
        <InfoHint label="About the model connection">
          The one place Sync spends on AI: writing a patch. Indexing, watching vendors, detecting
          problems and recording telemetry all run without a model and cost nothing. Sync connects
          to <em>your</em> model — it never uses the credentials of whoever installed it, so a
          deployment that configures nothing spends nobody and writes no patches. Your key is read
          from the environment at the moment of the call and is never stored, logged or sent
          anywhere by this console: what you see below is whether one is present, never its value.
        </InfoHint>
      </div>

      {/* The current state, stated before the options. A reader arriving wants to know what is
          happening now, and only then what they could change. */}
      <div className="flex min-w-0 flex-col gap-row rounded-surface border border-line bg-surface p-section">
        <span className="furniture text-meta text-ink-muted">Currently</span>
        <span className="text-emphasis text-ink">
          {provider.usable ? provider.detail : <Absent>{provider.detail}</Absent>}
        </span>
        {!provider.usable && provider.blocked_because && (
          <p className="max-w-prose text-meta text-ink-muted">{provider.blocked_because}</p>
        )}
        <p className="max-w-prose text-meta text-ink-muted">
          Credential:{" "}
          {provider.has_credential ? (
            "one is present in the environment"
          ) : (
            <Absent>none supplied</Absent>
          )}
          . Sync reads it at call time and never stores it.
        </p>
      </div>

      <div className="grid auto-rows-fr gap-section xl:grid-cols-3">
        <Option
          title="Your own frontier model"
          cost="you pay the vendor"
          detail="A hosted model on your own account and your own key. Highest quality, and the bill is yours rather than anybody else's."
          lines={[`${vars.model}=claude-opus-5`, `${vars.api_key}=<your key>`]}
          active={provider.kind === "frontier"}
        />
        <Option
          title="A model you run"
          cost="free"
          detail="Ollama, LM Studio or vLLM on your own machine. No credential, because there is nobody to bill. Sync sends the same request to a different address."
          lines={[`${vars.base_url}=http://localhost:11434`, `${vars.model}=qwen2.5-coder`]}
          active={provider.kind === "self-hosted"}
        />
        <Option
          title="No model at all"
          cost="free"
          detail="The graph, the detectors and every finding still run — they use no model. What you lose is the written patch, not the analysis."
          lines={[]}
          active={provider.kind === "unconfigured"}
        />
      </div>

      <p className="max-w-prose text-meta text-ink-muted">
        Set these where the Sync process reads its environment, then restart it. This screen
        reports the connection; it does not perform it — a form that accepted a key would have to
        put it somewhere, and every one of those places is somewhere it can leak.
      </p>
    </div>
  )
}
