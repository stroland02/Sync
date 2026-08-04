# Configuration and secrets across three engineering references

Audited 2026-08-04 against clones under
`C:/Users/strol/AppData/Local/Temp/claude/C--Users-strol-orca-Sync-Sync/b4674d1e-f115-48c1-ab2c-dab217d86019/scratchpad/engrefs/`.
Examined for this note: `open-code-review`, `codebase-memory-mcp`, `PageIndex`. Every claim is
labelled VERIFIED (I opened the file this session), REPORTED (a document asserts it and I did not
independently confirm), or INFERENCE (my reasoning from what I read).

## 1. What this dimension covers, and why it matters here

Configuration is every value that changes behavior without changing code — a port, a DSN, a model
name, a feature flag — and secrets are the subset of those values that must never appear in a log,
a commit, or an error message. For a project shaped like Sync the two are inseparable from a third
question this note was commissioned around: what happens when two components need to agree on one
value, and nothing forces them to.

Sync answered that question the hard way. `src/sync/api/__main__.py` and `web/vite.config.ts` are
two files, two languages, one HTTP port, and until recently two different numbers — 8000 on one
side, 8787 on the other — so following the project's own documented steps produced a proxy error
instead of a console. Both files carry a comment today explaining the coupling
(`src/sync/api/__main__.py:30-31`: "8787 is what `web/vite.config.ts` proxies `/api` to. The two
have to name one port or the console's every request is a proxy error."; `web/vite.config.ts:10-12`
mirrors it), and both still hardcode the number. VERIFIED by reading both files in full — neither
reads the other's value, generates from a shared source, or is checked by a test that would fail if
they diverged again. The comment is the only thing standing guard now.

## 2. The comparison

### 2.1 How configuration is expressed

Three different shapes, none of them Sync's.

**A YAML file merged into a mutable namespace.** PageIndex's `pageindex/config.yaml` (VERIFIED, 13
lines) sets `model`, `summary_model`, `retrieve_model`, and five numeric/string tuning knobs.
`pageindex/utils.py:921-952`'s `ConfigLoader` loads it with `yaml.safe_load`, and `load()` merges a
caller's `dict` or `config` object on top with `{**self._default_dict, **user_dict}`, returning
`config(**merged)`. VERIFIED at line 17: `from types import SimpleNamespace as config`. The
configuration object is a `SimpleNamespace` — there is no field list, no type, and no bound. A
boolean-shaped setting is a string: `if_add_node_id: "yes"` (line 10), so nothing stops
`if_add_node_id: "true"` or `if_add_node_id: 1` from being silently falsy wherever the code tests
for the literal string `"yes"`.

**A layered environment-variable resolver with named strategies.** open-code-review's
`internal/llm/resolver.go:82-118` tries, in order, an OCR config file, `OCR_LLM_*` environment
variables, Claude Code's `ANTHROPIC_*` variables, then a shell rc file, and returns the first
strategy that produces a complete `URL`/`Token`/`Model` triple (line 108's `ok && ep.URL != "" &&
ep.Token != "" && ep.Model != ""`). Each strategy is a named function, and the final error message
at line 117 lists every variable a user could have set, across all strategies, so a misconfigured
setup is diagnosable from the error alone. `internal/telemetry/config.go` layers the same pattern at
smaller scale: `DefaultConfig()` → `LoadFromJSON()` → `resolveEnv()`, precedence stated in a comment
at line 43 ("Environment takes highest priority").

**A JSON or SQLite file per concern, at OS-conventional paths.** codebase-memory-mcp's
`docs/CONFIGURATION.md` (VERIFIED, read in full) documents seven distinct configuration and log
locations, each with its own format and its own precedence rule — a global JSON file for extension
mappings, a per-project JSON file that overrides it, a SQLite database for CLI-managed runtime
settings, a separate JSON file for UI settings. There is no single configuration object anywhere in
this repository; every subsystem owns its own file.

### 2.2 Schema and validation: one real check, two absences

**PageIndex validates key names only.** `ConfigLoader._validate_keys` (`utils.py:932-935`) computes
`set(user_dict) - set(self._default_dict)` and raises `ValueError` on an unknown key. VERIFIED: that
is the entire validation surface. No type is checked, no range is checked, and no required value is
enforced — a malformed value (wrong type, out-of-range page count, a typo'd model name) is accepted
and fails, if at all, wherever it is later used, not at load time.

**open-code-review validates by trying to parse, and treats a malformed value as absence.**
`internal/telemetry/config.go:79-82`, `LoadFromJSON`: `if err := json.Unmarshal(data, &root); err !=
nil { return nil // malformed JSON — skip silently }`. VERIFIED — the comment states the choice in
the code. A syntactically broken telemetry config is indistinguishable from no telemetry config; the
process starts with defaults and never reports the parse failure. The LLM resolver is stricter in
one place only: `internal/llm/providers.go` and the extra-headers parser return real errors that
propagate into `ResolveEndpointWithOptions`'s wrapped `fmt.Errorf`, so a malformed
`OCR_LLM_EXTRA_HEADERS` does surface. The two config paths in the same codebase disagree on whether
malformed input is an error or a silent default.

**codebase-memory-mcp validates permissively and documents the fallback in prose.**
`src/discover/userconfig.c:9-11`'s header states the policy outright: "Unknown language values warn
and are skipped (fail-open). Missing files are silently ignored." That is a deliberate, named
design choice rather than an accident, which is the one thing distinguishing it from PageIndex's
version of the same permissiveness.

None of the three uses a schema library (no Pydantic, no JSON Schema, no `zod` in any of the trees
searched). Sync's own configuration is environment-variable-only at the entry point
(`src/sync/api/__main__.py:23` reads `os.environ["SYNC_GRAPH_DSN"]` with no default, which raises
`KeyError` on a missing value rather than silently defaulting) — that is closer to open-code-review's
"error on missing" posture than to PageIndex's "namespace with no validation" posture, and stricter
than codebase-memory-mcp's stated fail-open policy.

### 2.3 Secrets: the strongest reference finding is defensive, not custodial

None of the three repositories runs a service that holds a customer's or vendor's long-lived
secret the way Sync's constraint ("we never hold customer secrets") implies Sync's neighbors might.
All three instead answer a narrower question: how do you avoid a secret leaking through a surface
that was built for something else?

**codebase-memory-mcp has a purpose-built secret detector, used to protect against ingesting a
scanned repository's secrets into its own index.** `src/pipeline/pass_envscan.c:493`:
`if (cbm_is_secret_binding(key, value) || cbm_is_secret_value(value)) { continue; }` — a URL-only
environment scanner (its own header at lines 1-8 says it "filters out secrets") that walks
Dockerfiles, `.env` files, YAML, TOML, and Terraform, and refuses to store a binding it classifies as
a credential. VERIFIED via the test fixtures that exercise the classifier at
`tests/test_pipeline.c:7837-7846` (a literal `sk-` string, a PEM header, a `PORT=8080` binding
correctly classified as *not* secret) and `tests/test_pipeline.c:7940-8218` (a Dockerfile `ENV
API_KEY=sk-...` line, a Terraform `default = "sk-..."` block). This is a value-shape and key-name
classifier, not a true secret scanner (it would not catch a credential that doesn't look like one),
but it is the only mechanism in the three repositories that actively stops a secret-shaped value
from being persisted anywhere.

**open-code-review has a dedicated redaction floor on everything it writes into a session
manifest, plus a design that never lets a secret enter the hashed identity of a run.**
`internal/session/manifest.go:621-679` — VERIFIED in full. `secretAssignmentRe` is a case-insensitive
regex over `authorization|api[_-]?key|access[_-]?token|refresh[_-]?token|client[_-]?secret|secret|
password|passwd|token` keys, applied by `sanitizeReason`, described in the comment at line 647 as
"the single, best-effort redaction+truncation floor applied to every reason the builder stores, so
no caller path can write an unredacted secret." The comment is honest about its own limit at line
651: "this is only a defensive floor; callers still own context-aware redaction." Separately,
`RuntimeConfig` (`internal/agent/agent.go:144-146`) is documented as deliberately excluding every
secret — "no token, and only the endpoint host" — and `runtimeConfigSHA256`
(`internal/agent/agent.go:869-873`) hashes only that allowlisted struct, so the run's identity hash
is provably credential-free by construction rather than by discipline at each call site. That
construction — a type that cannot hold a secret, rather than a rule that says not to put one there —
is the strongest single idea in this note.

**PageIndex has no secret-handling code at all**, and its one piece of key management is a global
mutation: `pageindex/client.py:35-39`, `PageIndexClient.__init__` writes a passed `api_key` straight
into `os.environ["OPENAI_API_KEY"]` as a side effect of constructing a client, and separately aliases
`CHATGPT_API_KEY` onto `OPENAI_API_KEY` at import time (`utils.py:23-25`) and again in the client
constructor. VERIFIED. Writing a caller-supplied secret into process-global environment state means
any other code in the same process — a third-party import, a subprocess inheriting the environment,
a future logging call that dumps `os.environ` for debugging — sees it. There is no redaction
anywhere in the repository; a grep for `redact|mask` over `pageindex/*.py` returns nothing.

### 2.4 Committed secrets: none found, three near-misses explained

Grepped all three trees (excluding `.git`, `vendored/`, `node_modules/`) for OpenAI-shaped
(`sk-[A-Za-z0-9]{20,}`), AWS-shaped (`AKIA[0-9A-Z]{16}`), GitHub-shaped (`ghp_[A-Za-z0-9]{30,}`),
Slack-shaped (`xox[baprs]-...`), and PEM private-key markers. Five hits in open-code-review, one in
codebase-memory-mcp, none in PageIndex. Every hit is a false positive, checked individually:

- open-code-review's four translated `integrations/ci.md` pages and
  `examples/github_actions/README.md:279` all say `GITHUB_APP_PRIVATE_KEY | Contents of the .pem
  file (including -----BEGIN RSA PRIVATE KEY----- ...)` — documentation naming the format of a
  secret a user must supply, not a secret itself.
- codebase-memory-mcp's hit is `tests/test_pipeline.c:7838-8996` — the secret-detector's own test
  fixtures, using literal strings like `sk-1234567890abcdef12345` and a GitHub URL embedding
  `ghp_FAKEFAKEFAKEFAKEFAKEFAKEFAKEFAKEFAKE`, both plainly synthetic and there to prove the
  classifier in 2.3 fires correctly.

No actual committed credential in any of the three trees.

## 3. What Sync should adopt

**The allowlisted, secret-free config type, from `open-code-review/internal/agent/agent.go:144-146`
and `869-873`.** Sync's remediation pipeline already separates concerns that could be modeled this
way — the patch agent's `ClaudeAgentOptions` construction in `sync.remediate` carries no vendor
secret today, but as more of the pipeline's provenance gets hashed or logged (run manifests, the
`migration_outcome` ledger), the open-code-review pattern is the one to copy: define the loggable
subset as its own type, so a reviewer can see by the type signature alone that a secret cannot reach
it, rather than by auditing every call site that constructs a log line.

**A redaction floor at the write boundary of anything free-text, from
`open-code-review/internal/session/manifest.go:647-679`.** Sync's `abandon_reason` column is
explicitly meant to hold free text ("Abandoned runs are data" — `CLAUDE.md`), and free text written
by an agent that just ran inside a customer's clone is exactly the shape of value that could carry a
credential the agent encountered while patching. `sanitizeReason`'s design — apply one regex-based
floor at the single function every caller must pass through, document that it is a floor and not a
substitute for context-aware redaction — is a half-day addition wherever `abandon_reason` is written,
and open-code-review's own comment about *why* it strips a stray control byte before running the
regex (line 664-668: a byte gap would let a split secret partially survive) is worth reading in full
before implementing it.

**Neither open-code-review nor PageIndex nor codebase-memory-mcp has a mechanism that would have
caught Sync's port mismatch, and that absence is itself the most important finding in this note.**
The question asked was whether any of the three has a single source of truth for a value two
components share. None does — and codebase-memory-mcp has the closest analogous architecture (a
daemon and a separately-built web UI, exactly like Sync's API and console) and exhibits the
identical failure shape, unresolved: `src/ui/config.h:13` defines `#define CBM_UI_DEFAULT_PORT 9749`
for the C daemon, and `graph-ui/vite.config.ts:7` independently hardcodes `const uiBackendOrigin =
"http://127.0.0.1:9749"` for the Vite dev server that proxies to it. VERIFIED — grepping the whole
tree for `9749` turns up the C header, the daemon and CLI call sites, `docs/CONFIGURATION.md`, and
the one line in `vite.config.ts`; nothing generates one from the other, and no test in
`tests/test_daemon_application.c`, `tests/test_httpd.c`, or `tests/test_ui.c` asserts the two
numbers agree. It is the same defect class as Sync's, in a different language pair, currently
dormant only because nobody has had reason to change the number. This is worth stating plainly since
Sync's own fix is not structurally different: `src/sync/api/__main__.py:30-31` and
`web/vite.config.ts:10-12` are two independently-hardcoded `8787`s with a comment on each side, which
is exactly codebase-memory-mcp's pattern one incident earlier in its life. **Adopt:** a single
generated or environment-sourced value — even something as small as a `.env`-style file both `uvicorn`
and Vite's dev-server config read at startup (Vite supports `loadEnv`), or a test that starts both
configs and asserts the numbers match — would close the gap none of the three references closes
either.

## 4. Where Sync is already ahead, and where a reference is a step backward

**Sync's fail-loud default beats two of the three references' fail-open defaults.**
`os.environ["SYNC_GRAPH_DSN"]` (no default, raises on absence) is stricter than PageIndex's
`SimpleNamespace` (accepts any type for any field) and stricter than codebase-memory-mcp's
documented "missing files are silently ignored, unknown values warn and are skipped." Sync's
posture — a config value with no default is a startup crash, not a guess — is the correct one for a
system that reaches production customer repositories, and none of the three references chose it
uniformly.

**open-code-review's silent-skip-on-malformed-JSON in `telemetry/config.go:81` would be a
regression if copied.** A telemetry toggle silently failing closed is low-stakes; the same pattern
applied to, say, a malformed `SYNC_CHECKPOINTER_DSN` would mean a typo'd DSN falls back to
`SYNC_GRAPH_DSN` (which the code already does deliberately at
`src/sync/api/__main__.py:24` — `os.environ.get("SYNC_CHECKPOINTER_DSN", dsn)` — that one is an
intentional default, not a swallowed parse error, and the distinction is worth stating explicitly in
code review whenever a new environment variable gains a fallback: is this a documented default, or
is it a parse failure wearing a default's clothes).

**PageIndex's global-environment-mutation client constructor (`client.py:35-37`) is a pattern Sync
should actively avoid**, and Sync's own toolchain table already avoids it — the Claude Agent SDK
configuration in `CLAUDE.md` passes `model`, `thinking`, `effort` etc. as explicit constructor
arguments to `ClaudeAgentOptions`, never through a mutated `os.environ`, so a second concurrent call
in the same process cannot see or clobber another call's credential.

## 5. Open questions only the project's owner can settle

**Should the API/console port pairing get a structural fix now, given that codebase-memory-mcp
shows the same duplication surviving unfixed?** Section 3 names two candidate mechanisms (a shared
env-sourced value, or a test asserting the two hardcoded numbers agree). Both are cheap. Neither is
built. The fact that a comparable project has carried the identical duplication without incident is
weak evidence it's low-risk, and weak evidence is not the same as safe — Sync already has the
counter-example.

**Does `abandon_reason` need a redaction floor today, or only once an agent's free-text failure
descriptions start being written from inside a customer clone at higher volume?** The pipeline
discipline spec treats abandoned runs as data to be queried, which argues for redaction being in
place before the column fills up rather than after a credential shows up in a queryable table. This
is a scheduling question, not a design question — the mechanism in 3.2 is straightforward once
someone decides it is time.

**Is a `SimpleNamespace`-style config ever the right choice for a plugin surface Sync exposes to
third-party vendor-adapter authors?** PageIndex's zero-validation config is the softest possible
contract for a config-file author, and Sync's adapter story (`sync.signals.<vendor>`) will eventually
need to let a third party configure something. Whether that surface gets Pydantic validation (Sync's
existing dependency) or a looser namespace is a product-facing developer-experience call the owner
should make deliberately rather than by default.
