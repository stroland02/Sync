# Sync — B97 Sandbox Integration Design

**Date:** 2026-08-16
**Status:** Design. Nothing in this document is built. It is the planning pass the second
bounded step on B97 declined to skip — "wiring, image deployment, or the Anthropic-only
forward proxy without a planning pass first" — and it is written against the code as it
stands after that step, not against the original 2026-07-25 sketch.
**Scope:** How `AgentRemediator._drive_agent` actually starts running inside
`sync.remediate.sandbox`'s primitives, how the image it needs gets built and kept warm off
the request path, and how the sandboxed agent's own model traffic reaches Anthropic without
reopening the network hole the container exists to close. Three decisions, each with the open
questions that survive it.

## Where this picks up

`src/sync/remediate/sandbox.py` exists and three of its properties are measured against a real
Docker Desktop/WSL2 host: a container loses its route the instant `disconnect_network` returns,
a `network="none"` container never had one to lose, and destroying a container — not
disconnecting it — is what actually stops an already-open socket from delivering the rest of
its stream. `docker/patch-sandbox/Dockerfile` builds, runs as a non-root user, and carries a
pinned TypeScript. None of that is wired to anything. `AgentRemediator._drive_agent` still
constructs `ClaudeAgentOptions(cwd=repo_path, ...)` and calls the SDK's `query()` directly on
the host, exactly as it did before `sandbox.py` was written, and `prepare()` still runs
`install_dependencies` on the host too. This document is what has to be decided before either
of those calls can move.

**One reframing before the three decisions, because it changes what "wiring `_drive_agent`"
has to mean.** The threat model's mitigation 1 is one sentence — "clone, install, patch, and
typecheck run in an ephemeral container" — and `_drive_agent` is only the patch half of it.
`prepare()`'s `install_dependencies` call is the phase the adversarial review's finding is
actually about: "the realistic attacker here — malicious code executed during the dependency
install — needs no special timing to exploit this." If Decision 1 moves only `_drive_agent`
into a container and leaves `prepare()` installing on the host, the sandboxed agent turn is
real containment for a channel (the live agent's own tool calls) that was already the smaller
of the two attacker-controlled surfaces, while the channel the third bounded step was written
to close — the install — stays exactly where it was on 2026-08-06. Decision 1 below covers
both, because covering only one is not a smaller version of the mitigation, it is a different
mitigation that happens to share a name with this one.

---

## Decision 1 — Wiring `prepare` and `_drive_agent` through `sandbox.py`

### Container topology

Two containers, matching the risky/safe split `copy_between_containers` was built for, and
matching the granularity the existing code already uses:

- **Container R (risky, networked).** Created once per clone — the same granularity
  `TypeScriptAdapter.prepare` already memoizes install against (`self._installed_at`,
  `self._baselines`, keyed by resolved path), not once per finding. `ephemeral_container(image,
  network="bridge")`. Its only job is running whichever install command
  `sync.index.deps.install_dependencies` selects from the lockfile, then it is destroyed. The
  destruction is unconditional today (`ephemeral_container`'s `finally: _docker("rm", "-f",
  ...)`) and this design does not touch that; a container that installed something malicious
  during a networked window is gone before anything safe-phase touches its output.
- **Container S (safe, model-traffic-only).** Created fresh per patch attempt — per call to
  `make_patch`, i.e. per `static_attempts` increment — on the internal network Decision 3
  defines rather than on `"none"` or `"bridge"`. It runs the agent's live turn and then, because
  nothing in this tree distinguishes "verify" as a separately networked phase and `tsc` needs no
  network at all once the compiler is pinned into the image, also runs `static_verify`'s `tsc`
  invocation before it is destroyed. One container per attempt rather than one per run keeps the
  wall-clock kill (below) and the "destroy, don't disconnect" property scoped to the thing that
  can go wrong, which is one agent turn, not the whole finding's retry history.

`copy_between_containers` moves whatever R produced — `node_modules`, updated lockfiles — into S
before R is destroyed. This is the primitive as already built; nothing about the copy changes.

### The clone: bind-mounted, not copied

`copy_between_containers` is the right tool for a boundary crossing that happens once
(R's output into S). It is the wrong tool for a repository the live agent turn edits
incrementally across many `Write`/`Edit`/`Bash` calls and then has to be re-read from, because
there is no round-trip primitive for that today and building one would mean re-implementing
file synchronization as a side channel to a live multi-turn conversation.

The design instead bind-mounts `repo.local_path` into container S at a fixed container path
(`/workspace/repo`, matching the Dockerfile's `WORKDIR`), for the whole lifetime of that
attempt's container. This is a change to `ephemeral_container`'s contract — it takes no mount
argument today — and is the one addition Decision 1 makes to `sandbox.py`'s public surface.
Everything downstream of the agent's turn stays unmodified as a result: `propose()`'s
`_unstaged_additions(repo_path)` and `_git_diff(repo_path, identity)` already run `git` against
the host path, and a bind mount means the host path *is* the same inode set the container
edited — those two calls need no change, because the boundary the agent turn crosses is process
and network, not filesystem. A copy-based design would have had to invent a way to pull the
edited tree back out before those calls could run at all; the bind mount makes that a
non-question.

Bind-mounting the clone does not weaken the property mitigation 1 is protecting. The clone's own
contents — a customer's `.env`, if one is checked in — were already the thing `Read`/`Bash`
could reach unsandboxed; nothing about where those bytes live changes. What the boundary has to
hold is `SYNC_GRAPH_DSN` and friends staying out of the container's environment (`build_container_env`,
unchanged) and the container having no route anywhere but the proxy (Decision 3) — a bind mount
touches neither.

### The harder seam: getting the CLI process itself inside the container

This is the part of Decision 1 that is genuinely unresolved, and it is worth being precise about
why, because the obvious-looking shortcuts do not work.

**Shallow alternative considered and rejected.** Keep the `claude` CLI process running on the
host, as today, and have `sync.remediate.tool_gate`'s `PreToolUse` hook rewrite `Bash` commands
in flight — `command` becomes `docker exec <container> sh -c '<command>'` — so at least the
shell escapes into the sandbox. This is cheap and it is not the mitigation: `Read`, `Grep`,
`Write`, and `Edit` are the SDK's own built-in tool implementations, and they execute inside the
CLI process wherever that process runs. The threat model is explicit that the read channel —
"what the agent fetches for itself" — is "the larger channel by volume," and a design that
containerizes `Bash` while leaving `Read`/`Grep` running on the host containerizes the smaller
half. Rejected for the same reason the tool gate's own docstring already concedes about itself:
"a call the agent makes is now weighed, but what the agent reads is still unweighed."

**What actually has to happen instead.** The CLI process — not merely its environment — has to
run inside container S. `ClaudeAgentOptions.cli_path` is the SDK's only seam for this, and it is
a narrower seam than it looks: `claude_agent_sdk/_internal/transport/subprocess_cli.py` builds
`cmd = [self._cli_path, "--output-format", "stream-json", "--verbose"]` and spawns it directly
via `anyio` process creation — no shell, no argument reordering, and on Windows a `.bat`/`.cmd`
`cli_path` is refused outright (`_reject_windows_batch_cli`). There is no field that inserts
`docker exec -i <container> claude` as a prefix in front of the SDK's own arguments. The only way
to route the actual subprocess into the container is for `cli_path` to name a program that
behaves like `claude` from the SDK's point of view — accepts the same argv, speaks the same
line-framed stream-json protocol on stdin/stdout — and internally re-execs `docker exec -i
<container> claude "$@"`, transparently forwarding stdio. That program does not exist in this
tree.

On the container's own side this is nothing: Docker containers here already run Linux (WSL2
backend), and a two-line POSIX shell script with a shebang is a completely ordinary `cli_path`
on Linux. **The open problem is specific to developing and probably deploying from this Windows
host**: `cli_path` must be something `CreateProcess` can launch directly, which rules out a
batch script by the SDK's own check and rules out a bare shebang script by how Windows resolves
executables at all. That leaves a real, compiled native executable — a small Go or Rust binary
whose entire job is argv-forwarding and stdio-proxying into `docker exec -i` — as new
infrastructure this design calls for and does not build. It is a small program, but it is a
program that has to be built, tested for stream-json framing fidelity (a buffering bug here
would look like a hung or truncated agent turn, not a clean error), and kept in the deploy
artifact alongside the sandbox image. Sizing this honestly: it is probably the single largest
unbuilt piece of Decision 1, larger than the container orchestration around it.

`cwd` interacts with this in a way worth flagging rather than working around silently: the SDK
validates `options.cwd` against the *host* filesystem before spawning (`if self._cwd and not
Path(self._cwd).exists(): raise CLIConnectionError`), so `cwd` has to stay a real host path —
the bind-mounted `repo.local_path` — even though the path the wrapper needs to `docker exec -w`
into is the fixed container path. The wrapper has to know that fixed path independently (it can,
since `/workspace/repo` is a constant this design fixes, not something derived per-run), rather
than translating `options.cwd` itself. Setting `cwd` to a container-only path that does not exist
on the host would simply fail the SDK's own precondition before anything reaches Docker.

### `prepare()`'s install moves the same way, with its own new seam

`install_dependencies` runs `subprocess.run` directly against the host `repo_path` today.
Moving it into container R means the equivalent commands run via `docker exec` against R
instead — this half has no `cli_path`-shaped problem, because nothing here is the Agent SDK;
it is Sync's own subprocess call, and `sandbox.py`'s `_docker("exec", ...)` pattern already
does exactly this kind of call for `probe_connect`. `shutil.which(manager)` (deciding whether
`npm`/`pnpm`/`yarn` is available) has to become a check made inside the container rather than
on the host, since the answer is "whatever the image has," not "whatever this host's `PATH`
resolves" — and per CLAUDE.md's toolchain table, that answer is currently different (`yarn`
needs the unelevated-corepack shim workaround on this host; the image installs it directly via
`corepack enable`, so the container's answer is arguably *more* correct, not merely different).

### Error handling and timeouts across the boundary

**This is where wiring `_drive_agent` through the container changes behavior that today's tests
do not exercise, and `make_patch` (`src/sync/remediate/nodes.py`) has to change to keep it
honest.** Today, `remediator.propose(...)` raising anything at all is caught by one bare `except
Exception` in `make_patch`, and the exception's message is written into *both* `diagnostics`
(the operator-facing line) and `feedback` (what the *next* patch attempt is told, verbatim, as
retry guidance) — and it consumes one of the finding's three `static_attempts`. That is a
reasonable way to treat "the agent tried and failed to produce a working edit." It is the wrong
way to treat "the Docker daemon was mid-restart when `docker create` ran" or "`docker exec`
returned `OCI runtime exec failed: container not running` because something outside this attempt
killed the container." Feeding an infrastructure fault to the model as if it were feedback about
its own patch burns a retry attempt on nothing the next attempt can act on, and it pollutes
exactly the signal `docs/superpowers/specs/2026-07-27-sync-pipeline-discipline.md` says
`abandon_reason` exists to protect: "abandoned attempts are where routing learns which change
kinds are not mechanically safe," and a Docker Desktop hiccup is not a fact about the change
kind.

The fix reuses a mechanism this graph already has rather than inventing a new `RunState` key.
`prepare_ok` already exists to mean "an environment fault, not something a different patch could
fix, routes straight to `abandon` bypassing the static-attempt retry budget." Provisioning
container S — `docker create`, `docker start`, the bind mount, joining the internal network —
happens once per attempt but is entirely infrastructure, none of it agent behavior, so it
belongs on the `prepare_ok`-shaped side of the boundary: if container S cannot be *started*,
that is a `prepare`-style fatal fault. Once S is running and `docker exec` successfully launches
the wrapper, whatever the wrapper reports back through the stream-json protocol — including the
CLI never producing a `ResultMessage`, or `result.is_error` — is unchanged from today's meaning
and stays inside `make_patch`'s existing retry path. The one new case to route deliberately is
the container dying *mid-attempt* (as opposed to failing to start): rare, but not the same fact
as "the agent's edit did not typecheck," and worth its own distinguishable exception type so a
future operator reading `abandon_reason` or `diagnostics` sees "the sandbox container was lost
mid-run" rather than a `docker` stderr string indistinguishable from a model failure.

Net answer to "what changes in the `RunState`/graph contract": **no new checkpointed field.**
The shape of `patch`, `diagnostics`, `feedback`, `static_attempts` is unchanged. What changes is
which existing fatal-vs-retryable path a given failure is routed into, and that routing decision
has to be made by whoever writes the container-provisioning and `docker exec` code, not left to
fall into the generic `except Exception` by default.

Timeouts split across the same host/container line. `_DOCKER_TIMEOUT_SECONDS = 30` in
`sandbox.py` today governs the Docker Engine *control-plane* calls (create/start/rm) and must
not be reused for the `docker exec` that runs an actual agent turn — the latency spec's own tier
table puts a `xhigh`-effort turn at 30 seconds to 5 minutes, so the exec call needs a timeout
sized to that budget (with margin) passed explicitly, not inherited from the 30-second default
built for a fast control-plane round trip. Where that timeout is enforced is a real design
choice this document surfaces without settling: enforced host-side (the Python code awaiting
`docker exec` gives up and kills the container) or container-side (the wrapper or an entrypoint
wraps the CLI invocation in `timeout(1)`, and the container self-terminates). Host-side is
simpler and matches how every other timeout in this codebase already works (`_TSC_TIMEOUT_SECONDS`,
`_PROBE_TIMEOUT_SECONDS`); this design recommends it and does not have a measured reason yet to
prefer the alternative.

---

## Decision 2 — Image build, tag, and pre-warming

The Dockerfile exists and was built and probed by hand once. Nothing builds it as part of a run,
nothing tags it reproducibly, and nothing keeps it warm. The latency spec's Lever 2 is explicit
that this has to be precomputation off the request path — "the fastest work is work already
finished when the request arrives" — so the design constraint is that the first real patch
attempt after a deploy must never pay a `docker build`.

**Tag by content, not by `latest`.** A tag computed from a hash of the Dockerfile plus its build
args (`TYPESCRIPT_VERSION`, `NODE_MAJOR`) — `sync-patch-sandbox:<hash>` — makes "is the image I'm
about to run current" a cheap, deterministic `docker image inspect` rather than a trust exercise
in whatever happens to be cached under `latest` on a given host. This also gives the pipeline-
discipline culture in this repository something it already asks for elsewhere: a build is
reproducible by construction rather than by convention.

**Pin the base image by digest, not by tag.** `FROM python:3.12-slim-bookworm` is a mutable tag —
the same Dockerfile can produce a different image next month with nothing in this tree changed,
because upstream rebuilds `python:3.12-slim-bookworm` on its own schedule. That is in direct
tension with the content-hash tagging above: a tag computed from the Dockerfile's bytes implies
"the same tag means the same image," and it does not hold if the base image underneath it moved.
Pinning `FROM python:3.12-slim-bookworm@sha256:...` closes that, and a base-image bump becomes a
deliberate, reviewed change to the pinned digest rather than a silent drift the content hash
would misreport as unchanged.

**Pre-warming, concretely.** A small idempotent check — `docker image inspect
sync-patch-sandbox:<hash>`, build only on a miss — run at two points: once when the remediation
worker process starts (so a fresh deploy pays the build once, before any finding is waiting on
it), and once on a schedule (daily is enough; nothing about this image changes faster than the
Dockerfile or the pinned base digest does) to catch the case where the local image cache was
evicted between runs. Neither point is on the critical path of an actual patch attempt.

**What this design deliberately does not build, and why.** A registry (push/pull across
multiple workers) is not part of this design. Nothing in this repository's CI
(`.github/workflows/ci.yml`) builds or references a container image today, and nothing in the
codebase implies more than one worker host exists yet. Building a registry story ahead of a
second worker is exactly the debt CLAUDE.md's own rule warns against — "an abstraction, a flag,
or a hook added for an anticipated second caller is debt with no asset behind it; wait for the
caller." The local build-and-tag mechanism above is what a single-host deployment needs; a
registry is a follow-up sized to whatever worker topology actually gets built, not to a topology
imagined now.

**The open risk this decision does not fully close.** The Dockerfile's own comment already
concedes it: `corepack enable` installs the *shim*, not the package manager, so pnpm and yarn are
fetched over the network on first invocation rather than baked into the image — measured as
pnpm 11.22.0 and yarn 1.22.22 resolving on first use on this host. `corepack prepare
pnpm@<version> yarn@<version> --activate` at build time would force that fetch into the image
build rather than the first install, and reduces how often a real run pays it. It cannot
eliminate the cost, and this matters more than it looks: `corepack`'s whole design is
per-project version pinning through a customer's own `package.json` `packageManager` field, and
a customer repository can name a version this image never pre-fetched. Baking in the versions
observed on this host raises the hit rate; it cannot guarantee one, because the set of versions
a customer might pin is not something Sync controls or can enumerate ahead of time. The honest
framing is the same shape CLAUDE.md already uses for the oasdiff idempotency exemption: a named,
scoped exception to "no network cost on the critical path" — first-use-of-an-unanticipated-
package-manager-version stays a network fetch inside the install phase (which is already
networked, so this is not a new hole, only an unremoved latency cost) — rather than a gap
papered over as solved.

---

## Decision 3 — The Anthropic-only forward proxy

`network="none"` gives container S no route to anything, including the SDK's own traffic, and
"no route at all" cannot host a live agent turn — the CLI has to keep talking to Anthropic for
the whole run. The proxy is the mechanism that lets exactly that traffic through while nothing
else gets a path out.

### Shape: an SNI-filtering forward proxy, no TLS termination

A small long-lived proxy — its own container, not part of the sandbox image — sits on two
networks: the ordinary internet-facing bridge, and a purpose-built internal network container S
joins. It does not terminate TLS. It reads the SNI hostname off the TLS ClientHello of each
connection it is asked to forward (a `CONNECT`-style or raw-TCP-with-SNI-sniffing proxy; this
does not require decrypting anything) and either forwards the raw bytes if the hostname matches
an allowlist, or resets the connection if it does not. This is a deliberate choice against a
TLS-terminating proxy that would decrypt and re-encrypt traffic to inject something: it means the
proxy never needs a certificate the container has to trust, never sees plaintext prompt or
response content, and its correctness is checkable by the same kind of positive-control test
`sandbox.py`'s own network tests already use — attempt a connection to an allowed host and to an
arbitrary one from inside container S, and watch which one a real listener receives bytes from.

### Network topology, and why it does not reuse `disconnect_network`

The prompt for this document asks Decision 1 to reuse "the existing network-cutoff sequence" —
worth being explicit about why Decision 3 does not, rather than silently diverging.
`disconnect_network` is *narrow to a different problem*: it revokes a route a container already
had, and the third bounded step already measured that revocation is not instantaneous — a
socket open before the call keeps delivering for the better part of a second. Attaching container
S broadly and then narrowing it down to the proxy after the fact would reintroduce exactly that
window, for exactly the reason the adversarial review already closed it once. The fix that
worked there generalizes here: never grant the broader access in the first place. Container S is
created directly on the internal network — passed as `ephemeral_container(image,
network="sync-patch-proxy-net")`, which needs no change to `ephemeral_container`'s signature,
since `network` is already a free-form Docker network name and "attach to a purpose-built network
at creation" is exactly what the parameter already does. That internal network is created with
Docker's own `--internal` flag, which makes Docker itself refuse to route it to the internet —
an enforcement point independent of whatever the proxy's own filtering logic does or does not get
right. If the proxy container crashes, container S has no route to anywhere, including the proxy;
it fails closed by construction, not by the proxy's code being correct under failure.

Routing container S's outbound calls to the proxy is a standard `HTTPS_PROXY`/`ALL_PROXY`
environment variable, supplied through `build_container_env`'s `auth_env` parameter — which
already exists for exactly this purpose ("the caller's problem to populate"). **This rests on an
assumption this design has not verified**: that the Claude Agent SDK's CLI subprocess honors a
standard proxy environment variable at all. `build_container_env`'s own docstring already flags
the adjacent unknown — "what credential the Claude Agent SDK's own CLI needs to reach Anthropic's
API is unverified in this tree" — and proxy-honoring is the same shape of gap: nothing in this
tree currently proves it, and the honest way to close it is to build a throwaway container,
point it at a proxy that logs what reaches it, and watch — not to assume standard env vars are
respected because most HTTP clients respect them.

### The allowlist: what host, named how

`api.anthropic.com` is the obvious candidate and almost certainly incomplete. The CLI's traffic
for one run plausibly includes the actual API calls, an auth/session refresh, telemetry, and an
update check — CLAUDE.md's own environment snapshot for this project found no `ANTHROPIC_*`
variable and only `CLAUDE_CODE_EXECPATH`, meaning auth flows through an already-authenticated CLI
installation rather than a documented API key, and nothing in this tree enumerates what hosts
that authentication path itself touches. Determining the real list requires watching a live run —
and that is precisely the kind of observation `docs/superpowers/specs/2026-07-25-sync-threat-
model.md` already says the test discipline here forbids doing casually ("observing it needs a
model API call, which the test discipline here forbids"). This document does not resolve that
tension; it names the same compromise CLAUDE.md already models elsewhere for a fact that cannot
be derived and can only be measured: a deliberate, human-supervised, one-time traced session
(not a routine test, not something CI reruns) that captures the actual SNI list a real run
produces, hardcoded as a small, named, commented constant — and treated exactly like the corepack
version pins in Decision 2, a scoped exception with a stated condition that retires it: revisit
when Anthropic publishes a stable, documented egress list for the CLI, or when the SDK exposes
its configured base URL programmatically rather than leaving it implicit in the binary.

### The credential tension this design does not resolve

Mitigation 1's original text is specific: the ephemeral container should have "no model API key
... in its environment or on its filesystem." Everything built so far assumes the model
credential is an env var-shaped secret that `build_container_env`'s allowlist can simply omit.
The evidence gathered while building `sandbox.py` says otherwise: authentication runs through an
already-logged-in `claude` binary, which almost certainly means a session or token file on disk,
not an environment variable — and `build_container_env` filters environment variables. It says
nothing about a credential baked into the image or copied in as a file, which is a leak surface
this design has not addressed at all. Two shapes to choose between, and this document does not
pick one because the choice depends on facts about Sync's own auth flow that are not yet known
here:

- **The container holds its own credential**, scoped as narrowly and as short-lived as the auth
  mechanism allows, destroyed with the container at the end of the attempt. This keeps the proxy
  simple (SNI-only, no decryption) but requires a way to mint a run-scoped credential in the
  first place, which nothing in this tree currently does or shows how to do for an
  already-authenticated CLI installation rather than an API key.
- **The proxy holds the one long-lived credential and injects it**, meaning container S runs
  with no Anthropic credential of its own and the proxy authenticates on its behalf. This
  requires the proxy to terminate TLS to inject an `Authorization` header, which is the design
  this section chose against above for a different reason (simplicity, auditability, no
  certificate to trust into the container) — so choosing this path to solve the credential
  problem un-chooses the simpler proxy shape, and the two decisions have to be made together,
  not independently.

Naming this rather than picking one is the honest state of the design: it is a real fork, it
depends on facts about the SDK's auth mechanism that are unverified in this tree exactly the way
`build_container_env`'s docstring already says, and picking wrong here is expensive to unwind
once a proxy and a container-provisioning path are both built around the choice.

---

## What would make each decision testable

Following the pattern `sandbox.py`'s own tests already set — a positive control, so a pass
cannot be mistaken for a harness that never had a route to begin with:

- **Decision 1**: a real patch attempt against a fixture repository, asserting the diff lands
  correctly with the CLI process's PID (or an equivalent liveness signal) never appearing in the
  host's own process list — proving the process ran in the container, not merely that its
  environment was filtered.
- **Decision 2**: a build-cache test that asserts a second pre-warm call against an unchanged
  Dockerfile performs zero `docker build` work, and one that asserts a changed Dockerfile (or
  bumped base digest) does trigger a rebuild — proving the content-hash tag actually invalidates
  when it should and stays cheap when it should not.
- **Decision 3**: the same shape as `test_container_network_cutoff_blocks_arbitrary_egress` —
  attempt a connection from inside container S to an attacker-controlled listener and to the
  allowlisted host, and prove the first is refused and the second is not, from inside the
  container's own network namespace rather than inferred from which flags created it.

None of these exist yet. This document is what they would be written against.
