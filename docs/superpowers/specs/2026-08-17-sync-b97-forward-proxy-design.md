# B97's forward proxy: design before build

This is the design Ruling 7 and this session's own Option C ruling both asked for before any
code lands. Neither of those rulings built the proxy; both said it is one component with the
credential question folded in, and that the choice of *which* Anthropic credential Sync
authenticates with stays the owner's. This document is that component's shape, grounded in what
was verified against the installed `claude_agent_sdk` package and its bundled `claude` binary
rather than assumed from the SDK's own documentation, which (per `CLAUDE.md`'s own history on
this exact package) has already been wrong once.

## What has to be true when this is built

A `network="none"`-equivalent container hosting a patch attempt's agent turn must be able to
reach exactly one thing — Anthropic's API — and must never hold the credential that authenticates
it there. Everything else the sandbox already proves: `ephemeral_container`, `disconnect_network`,
`copy_between_containers` are built and tested. This is the one primitive still missing, and
composing the other three without it either breaks the agent (no route at all) or reopens the
exact hole the sandbox exists to close (a route with no restriction).

## What was verified, and how

`grep -ao` against `.venv/Lib/site-packages/claude_agent_sdk/_bundled/claude.exe` (a bundled
Node binary; its strings are the only introspection available without running it) turned up a
family of environment variables the Python SDK itself never mentions, because the SDK does not
manage authentication — `sync.remediate.sandbox`'s own docstring already established that. Read
against `claude --help` and `claude gateway --help`, both run directly, for what is actually
documented rather than merely present as a string:

- **`ANTHROPIC_BASE_URL`** — real, present in the binary, overrides where the CLI sends API
  requests. This is the mechanism that makes a plaintext-terminating proxy possible without a
  `HTTPS_PROXY`-style CONNECT tunnel: the container is told the proxy *is* Anthropic, so the
  proxy is where TLS actually terminates, not a blind relay of a tunnel it cannot see inside.
- **`CLAUDE_CODE_HTTP_PROXY` / `CLAUDE_CODE_HTTPS_PROXY`** — Claude-Code-specific proxy
  variables, distinct from the generic `HTTP_PROXY`/`HTTPS_PROXY` pair. Present; behaviour not
  documented in `--help`.
- **`CLAUDE_CODE_PROXY_AUTH_HELPER`, `CLAUDE_CODE_ENABLE_PROXY_AUTH_HELPER`,
  `CLAUDE_CODE_PROXY_AUTHENTICATE`, `CLAUDE_CODE_PROXY_AUTH_HELPER_TTL_MS`,
  `CLAUDE_CODE_PROXY_HOST`, `CLAUDE_CODE_HOST_HTTP_PROXY_PORT`,
  `CLAUDE_CODE_HOST_SOCKS_PROXY_PORT`** — a proxy-authentication subsystem exists. Present;
  none of it is in `--help`, and the `HOST_*` naming suggests it may already be aimed at exactly
  a sandboxed-agent-reaches-a-host-side-proxy topology, which would make it the intended
  mechanism rather than a repurposed one — but that is a guess this document is explicit about,
  not a verified fact.
- **`--bare`** — documented, run and read directly: *"Anthropic auth is strictly
  `ANTHROPIC_API_KEY` or `apiKeyHelper` via `--settings` (OAuth and keychain are never read)."*
  This is a real, load-bearing finding for the container side: it forces a narrow, enumerable
  auth surface and explicitly disables the two credential sources this deployment is *not*
  choosing to hand a container (an OAuth session file, an OS keychain).
- **`apiKeyHelper`** (a `--settings` key, not an env var) — a command the CLI invokes to obtain
  a key at call time, rather than reading one from the environment once. This is the seam that
  keeps the credential out of the container's own environment even under Option A's naive
  reading of it: the helper command can reach out to the proxy for a short-lived token instead
  of the container ever holding a long-lived one.
- **`claude gateway`** — a real, built-in subcommand, documented in `--help` as *"Run the
  enterprise auth/telemetry gateway,"* taking one `--config <path>` pointing at a YAML file.
  **Deliberately not investigated further in this pass.** Its config schema, its actual
  authentication model, and whether it is designed for this topology (one sandboxed agent
  reaching one proxy) versus a different one (centralizing auth across many organizational
  seats) are all undocumented from what `--help` shows. Reverse-engineering an undocumented
  Anthropic feature by string analysis and guessing its config format is not how this project
  builds a security boundary — `CLAUDE.md`'s own standing practice throughout this codebase has
  been to verify against the real system and say plainly what remains unverified, not to build
  on an assumption because the surface exists. If `gateway` is later confirmed (by Anthropic's
  own documentation, or by asking) to be the sanctioned mechanism for this exact case, it may be
  the better foundation. Absent that, building a small, auditable proxy Sync owns and can reason
  about in full is the safer default, and it is what the rest of this document assumes.

## The shape this settles on

A minimal HTTP(S) forward proxy, run by Sync on the host (or in its own container on the same
Docker network), that:

1. Listens on an address the sandboxed container can reach — a custom Docker bridge network
   (not the default `bridge`, so nothing else on the host's network is reachable from the
   container) with the proxy as the only other member, or `host.docker.internal` if the proxy
   runs on the host directly. Either way, the container's `network` argument to
   `ephemeral_container` stops being `"none"` — it becomes "attached to a network whose only
   other member is this proxy," which is a real narrowing from today's `"bridge"` default, not
   a step back from `"none"`'s intent. `probe_connect` (already built, already tested) is the
   tool that proves the container can reach the proxy and nothing else, the same way it already
   proves reachability today.
2. Sets `ANTHROPIC_BASE_URL` (via `build_container_env`'s existing `auth_env` parameter, which
   is already the seam this needs — no new plumbing there) to point the container's `claude`
   invocation at itself, so the proxy is the request's real destination and can read the
   plaintext request rather than blindly relaying an opaque tunnel.
3. Allowlists exactly `api.anthropic.com` (or whichever host the chosen credential's provider
   actually uses — Bedrock and Vertex have their own base URLs, per the strings above, and
   Ruling 7 already puts *which* provider outside this design's scope) as the only forward
   target. Any other destination is refused at the proxy, which is the network half of the
   containment story finally closing.
4. Attaches the real credential — whichever the owner has chosen the CLI authenticates with —
   to the forwarded request, from a value the proxy process holds and the container process
   never does. `--bare` on the container side plus a dummy or absent `ANTHROPIC_API_KEY`
   removes the container's own paths to any *other* credential it might otherwise have found.
5. Runs for the lifetime of one patch attempt and is torn down with it, the same lifecycle
   discipline `ephemeral_container` already holds the container to — a proxy that outlives its
   one attempt is a second thing that can leak the credential it was built to protect.

## What this design deliberately still leaves open, and to whom

- **Which credential.** Ruling 7's own boundary, restated rather than re-litigated: operator
  OAuth, a dedicated API key, or a third-party provider is an account-and-spend decision for the
  owner. This design's job is to make that choice a configuration value the proxy reads at
  startup, not an architecture decision baked into the container.
- **Whether `claude gateway` supersedes a hand-built proxy.** Named above; not resolved here.
- **TLS between the container and the proxy.** Plaintext HTTP on an isolated bridge network with
  no other member is a defensible starting point — the traffic never leaves a network Sync
  itself created — but it is a decision this document is stating rather than defending in full,
  and it should be revisited before anything ships past a prototype.
- **Rate limiting, retry behavior, and what the proxy does when Anthropic itself is unreachable**
  — none of this blocks a first working version and none of it is designed here.

## What this is not

Not code. Nothing in `src/` changes because of this document. The next unit is a prototype
proxy and a test proving the three properties above — reachable only through it, only
`api.anthropic.com` forwarded, credential never in the container's own environment — built the
same test-first way everything else in this module was.
