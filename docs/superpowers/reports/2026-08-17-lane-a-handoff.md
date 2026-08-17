# Lane A handoff, 2026-08-17

Written at 1% context before auto-compact, per the coordinator's instruction. Model:
`docs/superpowers/reports/2026-08-17-lane-c-handoff.md`.

## Landed units, most recent first

- **`d17719e`** (M10-W251) — B97 third slice: `sync.remediate.isolated_network.isolated_network`,
  a Docker network with `--internal`. Real, tested (`tests/test_isolated_network.py`, 3 tests):
  `--internal` structurally blocks routing to anything outside the network's own local subnet.
  **The most valuable thing in this commit is negative, and the coordinator asked it be carried
  forward explicitly: `--internal` plus `--add-host=host.docker.internal:host-gateway` does NOT
  compose.** `--add-host` writes an `/etc/hosts` entry — DNS resolution only. `--internal`'s
  routing restriction sits a layer below that and removes the route regardless, including to a
  name that resolves fine. Measured directly: `host.docker.internal` resolved to
  `192.168.65.254` inside a container on an `--internal` network, and a connect attempt to that
  same address raised `OSError: [Errno 101] Network is unreachable`. The design doc
  (`docs/superpowers/specs/2026-08-17-sync-b97-forward-proxy-design.md`, "The shape this settles
  on" section) is already corrected: the proxy must run as its own container on the same
  isolated network as the sandboxed container, dual-homed with a second attachment into
  something that can actually leave — not as a bare host process. **That composition is the next
  B97 unit, not yet started.**
- **`2561ca0`** (M10-W250) — B97 second slice: `forward_proxy_server.running_proxy`, the real
  socket server around `build_forward_request`. Uses stdlib `http.server`, not this project's
  usual `starlette`/`uvicorn`, deliberately: an ASGI server normalises a request's target before
  an app sees it, which would hide the absolute-URI signal the design needs. Tested against real
  listening sockets (`tests/test_forward_proxy_server.py`, 5 tests). `httpx` added as an explicit
  dependency (`uv add httpx`) — was already present transitively via starlette's test client.
- **`59ff4d3`+`fcff45d`** (M10-W245/246) — B165: a customer's `.sync/context.md` reached the
  patch prompt unfenced, in instruction position. Fixed at the `agent_patch.py` call site
  (`fenced_block(REPOSITORY, ...)`), `src/sync/context/` untouched. TDD with a mutation check.
  Closed in `BACKLOG.md` with evidence.
- **`ff0abee`** (M10-W247) — B156: ruled Option C for B97's credential design (the forward proxy
  injects the Anthropic credential; the sandboxed container never holds one). Independently
  converged with the coordinator's own Ruling 7, reached separately, before either side saw the
  other's reasoning.
- **`M10-W244`** — proved (not merely asserted) that the corpus already correctly excludes a
  parked finding from `findings_abandoned`. No product code changed; the property was already
  true, it just had no test holding it.
- **First self-directed push** landed this session, after Sebastian's own direct
  "PUSH AUTHORIZED" (his earlier messages had been arriving truncated — root cause he identified
  and fixed, recorded as `M0-W293`). Standing practice since: merge origin/main, check for `UU`
  paths, gate (`lint-imports`, `lint_encoding`, full `pytest`), fetch + `git merge-base
  --is-ancestor origin/main HEAD`, then `git push origin HEAD:refs/heads/main` directly.

## Open, in order

1. **The tier-0 production run — investigated after compaction, deliberately not forced.**
   Lane D produced a real finding: **`016de7ef6d843714e21edb2e5c0884d6`**, predicted
   `tier=0, strategy=codemod, static_verify_passed=True` (no model call). The mechanism to run it
   turned out not to be `sync run` (which truncates and rescans the whole graph — unsafe against
   other lanes' concurrent writes) but `sync.remediate.graph.build_graph(..., forge=None,
   is_rehearsal=False)` invoked directly against the existing finding, with a local zero-remote
   fixture repo (`sync.rehearse.fixture.prepare_fixture`) as the checkout — the same pattern
   `sync rehearse` already uses in production, minus `is_rehearsal=True`. `forge=None`
   structurally omits `push_branch`/`await_ci`/`open_pr` from the compiled graph
   (`sync/remediate/graph.py`), so nothing this writes can reach GitHub. The script is preserved
   at the bottom of this section.

   **Pre-checked the routing decision before invoking the graph** (calling
   `tiered.routing_facts()` + `route.matrix.route()` directly — pure functions, no side effect)
   per the coordinator's instruction to stop before any model call. Result: **tier=2,
   row='fall-through', not tier 0** — Lane D's prediction did not hold. Root cause found and
   reported: the finding's `call_site` records `line=70, col=10` in
   `app/api/setup_accounts/route.ts`, but in the materialized fixture
   (`.cache/rehearse/furever`) line 70 is a bare `}` — the actual `receipt_email` literal is at
   line 64, a 6-line offset. `argument_is_literal_at` correctly read nothing at the recorded
   position and returned `None` ("cannot establish"), which is why row 4 declined and routing
   fell through. **The routing table did the right thing with an unresolvable fact — this is a
   stale-index or off-by-N question in whatever produced the call_site row, not a routing bug.**
   Not chased further; it's Lane D's finding and outside B97's area. Stopped there, reported both
   the tier mismatch and the root cause via `orca orchestration send`, and did not run the
   cascade past that point without explicit go-ahead for the model spend the fall-through would
   trigger. **Gate 2's `routing_accuracy` was not moved tonight** — report that number as
   unchanged if asked, and say why: the one candidate finding didn't actually route to tier 0
   once checked, rather than "not attempted."

   The script (`prepare_fixture` + direct `build_graph` invocation) is real and safe to reuse
   the moment a finding's `call_site` position actually lines up with its file — nothing about
   the mechanism itself needs rework.
2. **B97 fourth slice**: compose `isolated_network` + a containerized `running_proxy` (dual-homed:
   the isolated network plus its own egress) + `ephemeral_container`'s sandboxed side into one
   orchestrated patch attempt. Design is current in the spec doc. Not started.
3. Everything else in the original Lane A queue (M10 durable runs, resume-on-review-comment,
   abandoned/parked distinction) was verified done earlier this session.

## What is NOT known

- The exact vendor/version/repo parameters Lane D used to produce `016de7ef6d843714e21edb2e5c0884d6`
  — needed for option (b) above if no direct finding-id path exists or is built.
- Whether `stripe/stripe-connect-furever-demo` (the pinned dogfooding fixture) is the repo Lane
  D's finding is against, or something else.
- Whether running the cascade for real risks pushing a branch / opening a PR against that repo —
  **checked earlier this session and still true as far as I know: `sync run` always constructs a
  real `GitHubForge()`, no dry-run flag exists (one was explicitly rejected by the dogfooding
  plan's own authors).** The coordinator's instruction this time was explicit and direct
  ("run the cascade... minutes, not an hour"), which reads as authorization for this specific,
  named finding — but that authorization was for *me*, in *this* conversation, and a successor
  reading only this file should treat it as informative context, not as their own standing
  authorization, and confirm before running anything that pushes to a real external repo.
