# Repository layout and module boundaries

Audit note, 2026-08-04. Dimension: how each reference repository is physically organised, and
what — if anything — stops a module importing something it should not.

## Coverage

I read the top-level tree of all nine clones under
`C:/Users/strol/AppData/Local/Temp/claude/C--Users-strol-orca-Sync-Sync/b4674d1e-f115-48c1-ab2c-dab217d86019/scratchpad/engrefs/`
and went inside the largest package of six of them: `open-code-review`, `codebase-memory-mcp`,
`codegraph`, `code-review-graph`, `Understand-Anything`, and `PageIndex`.

`superpowers`, `skills`, and `claude-cookbooks` I examined only at the top level and through their
manifests. That is deliberate rather than a gap: none of the three carries a compiled or importable
source tree — `superpowers` is 89 markdown files plus 38 shell hooks, `skills` is 112 markdown files
with no source at all, and `claude-cookbooks` is 92 notebooks organised by capability with a
`[tool.hatch.build.targets.wheel] packages = ["anthropic_cookbook"]` entry its own comment calls a
"dummy package for build system" (`claude-cookbooks/pyproject.toml:44`). There is no module boundary
in any of them to enforce. They contribute to this note only through the `skills` repository's
`setup-ts-deep-modules` skill, which is the single place across all nine where boundary tooling is
described at all.

I did not run any build, test, or linter in any reference clone. Every claim below is from reading
files.

## 1. What this dimension covers, and why Sync in particular should care

The question is narrow: given the directory tree, can a developer — or an agent — write an import
that violates the architecture and have it merge? The answer is almost always "yes, unless a tool
says no", because architecture documents do not run in CI.

For Sync this is not an aesthetic concern, it is the open-core business model expressed as a
constraint. Sync's pitch to a third party writing a Twilio adapter is that they depend on
`sync-core` and therefore install `pydantic` and nothing else. The moment `sync.core` imports a
sibling, that adapter author inherits `psycopg`, `langgraph`, `starlette`, and a Postgres 16
container on port 5433. The boundary is not "clean code"; it is the difference between a plugin
ecosystem and a monolith with a `core/` folder.

Sync already knows this and already spends real effort on it. `pyproject.toml:101-118` declares an
import-linter `forbidden` contract, `tests/test_import_boundary.py:20-44` runs `lint-imports` as a
subprocess and checks the contract report was actually produced before checking the exit code, and
`tests/test_import_boundary.py:73-92` walks core's AST and pins its third-party import set to
exactly `{"pydantic"}`. The `src/pyproject.toml` split builds `sync-core` as a separate namespace
wheel so the promise is physically true of the distribution and not only of the source tree. That
is more machinery than eight of the nine references have between them.

The useful questions, then, are whether the machinery is complete, and whether anyone does it more
cheaply.

## 2. The design space across the references

### Group A: the boundary is enforced by the compiler or the module resolver, for free

**`open-code-review`** (Go, Alibaba). Layout is by domain concern under one `internal/` root:
eighteen packages — `agent`, `config`, `delegate`, `diff`, `gitcmd`, `llm`, `llmloop`, `mcp`,
`model`, `pathutil`, `release`, `scan`, `session`, `stdout`, `suggestdiff`, `telemetry`, `tool`,
`viewer` — with a single `cmd/opencodereview` binary on top. Two top-level Go packages in total
(`cmd`, `internal`). Largest non-test file is `cmd/opencodereview/provider_tui.go` at 2,953 lines;
largest library file is `internal/agent/agent.go` at 1,574. **VERIFIED.**

The `internal/` name is the enforcement, and it is enforced by the Go compiler rather than by a
linter: nothing outside `github.com/alibaba/open-code-review` (`go.mod:1`) can import any of those
eighteen packages, ever, with no configuration to keep in sync. This is the cheapest boundary in the
entire reference set — zero lines of config, zero CI time, and it cannot drift.

It is also the *wrong shape* for Sync's problem, and that distinction matters. `internal/` protects
the module from the outside world. It says nothing about whether `internal/model` may import
`internal/llm`. I found no nested `internal/` directories (`find . -type d -name internal` returns
exactly one hit) and no test that inspects import paths — `grep -rln "go/parser\|ImportPath" --include="*_test.go"`
matches only `internal/config/rules/system_rules_test.go`, which is about review rules, not imports.
**VERIFIED.** So intra-module layering in `open-code-review` is enforced by nothing. Its `Makefile`
does `go vet`, `gofmt`, and an 80% coverage floor (`Makefile`, the `coverage` target) and no
architectural check.

**`Understand-Anything`** (TypeScript, pnpm workspace). This is the closest structural analogue to
Sync in the whole set, and the most interesting finding. `pnpm-workspace.yaml` declares three
package roots; the real one is `understand-anything-plugin/packages/`, holding `core`, `dashboard`,
`viewer`, and two wasm-grammar packages. The dashboard depends on core as `"@understand-anything/core": "workspace:*"`.
**VERIFIED.**

The boundary is `packages/core/package.json:7-32`: an `exports` map with exactly six entries —
`.`, `./search`, `./types`, `./schema`, `./languages`, `./figma`. There is no `"./*"` wildcard. That
means Node's resolver and TypeScript under `moduleResolution: "bundler"` both refuse
`@understand-anything/core/analyzer/graph-builder` outright. Everything under
`packages/core/src/analyzer/`, `src/persistence/`, and `src/plugins/` is unreachable from outside
the package unless it is re-exported through one of the six named entry points. The dashboard's
imports confirm the discipline holds in practice: eighteen import sites across
`packages/dashboard/src/` all name a declared subpath (`.../core/types` at `App.tsx:3`,
`CustomNode.tsx:4`, `store.ts:9`; `.../core/schema` at `App.tsx:2`, `store.ts:4`; `.../core/search`
at `store.ts:2`), and none reaches deeper. **VERIFIED.**

This is a boundary that costs 26 lines of JSON, is checked by the module resolver on every build,
and — crucially — has *no separate list to keep in sync*. Adding a directory to `core/src/` does not
require touching the exports map. It is private by default. Contrast that with a deny-list, which is
public by default and needs an edit every time a package is added.

The rest of `Understand-Anything` is unenforced. `eslint.config.mjs` is 60 lines and configures
`no-unused-vars`, `no-irregular-whitespace`, and a browser-globals override for the dashboard. There
is no `no-restricted-imports`, no `import/no-restricted-paths`. **VERIFIED.**

### Group B: layering is documented in prose, enforced by nothing

**`codegraph`** (TypeScript, ~79k lines). Fifteen directories under `src/`, organised by pipeline
stage — `extraction`, `resolution`, `graph`, `context`, `search`, `sync`, `db`, `mcp`, `installer`,
`bin`, `ui`, `telemetry`, `discover`-equivalents — which is very close to Sync's own INDEX → RESOLVE
→ ... shape. Largest file is `src/extraction/tree-sitter.ts` at 6,767 lines, with
`src/mcp/tools.ts` at 4,947 and `src/resolution/callback-synthesizer.ts` at 3,787. **VERIFIED.**

`codegraph/CLAUDE.md` draws the layering explicitly as an ASCII pipeline diagram and states "The
public API surface is `src/index.ts` … Library users only touch this file". **VERIFIED.** And that
is the entire enforcement. There is no eslint config in the repository at all — `ls codegraph/.eslintrc* codegraph/eslint*`
finds nothing, `package.json:19-30` has no `lint` script, and a repository-wide grep for
`dependency-cruiser|depcruise|madge|no-restricted-imports` returns zero hits in `codegraph`.
**VERIFIED.** Any file may import any other file. The 6,767-line `tree-sitter.ts` is the natural
consequence: nothing pushes back on a module accumulating responsibility, so it accumulates.

**`codebase-memory-mcp`** (C11, ~130k lines of first-party C once `vendored/` and
`internal/cbm/vendored/grammars/` are excluded — the raw file count is dominated by generated
tree-sitter parsers, one of which, `internal/cbm/vendored/grammars/lean/parser.c`, is 2.9 million
lines). Sixteen directories under `src/`, by layer with `foundation/` at the bottom, then `store`,
`cypher`, `pipeline`, `discover`, `watcher`, `mcp`, `cli`, `ui`, `daemon`, `semantic`, `traces`,
`graph_buffer`, `simhash`, `git`. `CONTRIBUTING.md:52-71` documents the tree with a one-line purpose
per directory. Largest first-party files: `src/cli/cli.c` at 11,865 lines and `src/mcp/mcp.c` at
11,753. **VERIFIED.**

`foundation/` genuinely is a dependency-free core. Every `#include "…"` in `src/foundation/*.c`
resolves to either another `foundation/` header or a vendored one (`../../vendored/tre/regex.h`,
`../../internal/cbm/vendored/verstable/verstable.h`) — nothing reaches up into `store`, `pipeline`,
or `mcp`. **VERIFIED** by extracting every quoted include in that directory. The repository also
uses a `*_internal.h` naming convention (`compat_fs_internal.h`, `lock_registry_internal.h`,
`platform_internal.h`, `private_file_lock_internal.h`, `system_info_internal.h`) to mark headers
that are private to a translation unit group.

What enforces this? Nothing. `.clang-tidy` enables every check with `WarningsAsErrors: '*'` and is
genuinely strict, but clang-tidy has no include-layering check configured here. `scripts/` contains
57 gate scripts and none of them is about includes — grepping the whole `scripts/` tree for
`layering`, `may not include`, or `forbidden include` returns nothing. **VERIFIED.** The
`_internal.h` suffix is a convention a compiler never reads; any `.c` file in `src/cli/` can
`#include "foundation/private_file_lock_internal.h"` and the build will succeed.

This is a repository with a memory-safety gate, a license gate, a DCO gate, an eight-layer security
audit, a no-test-skips policy, and a NOLINT whitelist — and *no* architectural gate. That asymmetry
is itself the finding: teams gate what has burned them, and include layering has not burned them
yet.

### Group C: no boundary, because there is no structure to bound

**`code-review-graph`** (Python, ~48k lines). This is the cautionary tale. `code_review_graph/` is a
single flat package with 47 top-level modules and no sub-packages at all except `tools/`, `eval/`,
`assets/`, and `docs/`. Files sit beside each other by feature name: `parser.py`, `graph.py`,
`embeddings.py`, `communities.py`, `daemon.py`, `wiki.py`, `refactor.py`, `hcl_resolver.py`,
`jedi_resolver.py`, `python_resolver.py`, `rescript_resolver.py`, `spring_resolver.py`,
`temporal_resolver.py`, `tsconfig_resolver.py`, `scoped_resolver.py`. **VERIFIED.**

`code_review_graph/parser.py` is **16,080 lines**. `visualization.py` is 2,355, `graph.py` 2,255,
`cli.py` 2,028. **VERIFIED.** For scale: `parser.py` alone is a third of Sync's entire 25,393-line
source tree.

Enforcement is ruff with `select = ["E", "F", "I", "N", "W"]` (`pyproject.toml`, `[tool.ruff.lint]`)
— style, imports-sorted, naming. No import contracts, no layering, and structurally nothing to
enforce, because with a flat package every module is a peer of every other by construction. The
`[project.optional-dependencies]` blocks (`embeddings`, `google-embeddings`, `communities`, `eval`,
`wiki`, `enrichment`) are a real and thoughtful attempt to keep the *installed* dependency tree
small, but the *import* tree is unpartitioned: `code_review_graph.embeddings` is importable from
anywhere and there is no test that a base install does not reach it.

**`PageIndex`** (Python, ~4k lines). Seven modules in one flat `pageindex/` package —
`client.py` (234), `page_index.py` (1,321), `page_index_md.py` (344), `retrieve.py` (137),
`tree_optimize.py` (947), `utils.py` (977), plus a `flash/` subdirectory. Three test files. No
`pyproject.toml` at all — dependencies are a flat pinned `requirements.txt`. No linter config, no
boundary of any kind. **VERIFIED.** At this size that is a defensible choice, and it is worth saying
so: the cost of a boundary is not zero and 4,000 lines does not need one.

### Group D: the boundary tooling exists, but only as advice

**`skills`** (obra). `skills/skills/in-progress/setup-ts-deep-modules/SKILL.md` is the only place in
all nine repositories where import-boundary tooling is specified. It installs dependency-cruiser and
four `error`-level rules: outside code may import only a package's *root* files; a package's own
files may import each other freely; tests may import entry points but never internals, not even
their own; no cycles. Public-versus-private is decided by **path depth** — root file is public, any
subfolder is private — so a new directory never needs a config change. **VERIFIED.**

Two things in that skill are worth more than the tool it installs. First, step 6, titled "Prove the
rules bite", requires observing a pass, then a deliberate deep import producing a *named* failure
(`tests-through-entrypoints`), then a pass again, and states "a config that doesn't fail on a
violation is worthless". That is precisely Sync's own `.claude/rules/test-discipline.md` rule about
a test that cannot fail, arriving independently at the same conclusion. Second, step 7 requires a
`README.md` *in the packages folder* plus a one-line pointer from `CLAUDE.md`, on the reasoning that
"this is what makes an agent discover the boundary rule instead of tripping over it".

The skill lives in `in-progress/`, whose README says these are "not ready to ship — expect rough
edges". It is not applied to the `skills` repository itself, which has no TypeScript.

## 3. Plugin and extension seams

Sync's vendor adapters are an extension seam, so this is worth separating out. Four distinct designs
appear.

**Out-of-process, no shared types (`open-code-review`).** Third-party capability arrives over MCP.
`internal/tool/definitions.go:15-36` hard-codes seven built-in tools as unexported struct values,
and line 50's `tool.Dynamic(name)` constructs a `Tool` for anything discovered at runtime from an
MCP server, with `IsReserved` guarding the built-in names. `internal/mcp/{client,provider}.go`
speaks the protocol. The agent-facing extensions (`plugins/open-code-review/` for Claude Code,
Codex, Cursor, opencode; `extensions/vscode/`) are pure configuration and markdown — I found no Go
import from `extensions/` into `internal/`, and the `Makefile`'s `PACKAGES` variable explicitly
excludes `/extensions/`. **VERIFIED.** The extension author shares *no* compile-time surface with
the host, which is the strongest possible version of "does not inherit the database" — and also the
weakest possible version of "typed contract".

**In-tree interface plus a registry, with a parameterized contract test (`codegraph`).** This is the
one Sync should study. `src/installer/targets/types.ts:1-14` declares `AgentTarget` and states in its
own docstring: "Adding a new agent = one new file in `targets/` + one entry in `registry.ts`".
`registry.ts:21-30` is a frozen array of eight targets. `__tests__/installer-targets.test.ts` is
1,899 lines and, per its header comment (lines 1-14), exercises *every* target against the same
contract: install writes the expected files; re-running install is byte-identical; sibling MCP
servers and unrelated config survive; uninstall reverses install; `printConfig` returns parseable
non-empty content. **VERIFIED.** `CLAUDE.md` states this is roughly 47 parameterized contract tests
and that "all installer changes need matching coverage" there. **REPORTED** (the count is from
`CLAUDE.md`; I read the header and the length, not all 47 cases).

The design property that matters: the test iterates `ALL_TARGETS` from the registry. A ninth target
is automatically subject to every contract test the moment it is added to the array — there is no
second list to remember. Idempotence-under-re-run is a first-class assertion, which is the same
property Sync's pipeline rule demands of every stage.

**In-tree interface, config-driven, no conformance test (`Understand-Anything`).**
`packages/core/src/plugins/extractors/types.ts:9-20` declares `LanguageExtractor` with
`languageIds`, `extractStructure(rootNode)`, and `extractCallGraph(rootNode)` — a small, honest
interface. `plugins/discovery.ts:14-23` holds a `DEFAULT_PLUGIN_CONFIG` and `parsePluginConfig`
parses a JSON plugin list with validation, falling back to the default on any malformed input.
`index.ts:14-15` exports `LanguageExtractor` and `builtinExtractors` through the package's public
entry point, so a third party can implement it. **VERIFIED.** But the fifteen extractors are tested
individually (`__tests__/rust-extractor.test.ts` at 755 lines, `csharp-extractor.test.ts` at 704,
`cpp-extractor.test.ts` at 696) rather than through one shared contract — there is no equivalent of
codegraph's `ALL_TARGETS` loop. Adding a sixteenth extractor means writing a sixteenth bespoke test
file and hoping it covers the same ground.

**Compile-it-in, registration in three places (`codebase-memory-mcp`).** `CONTRIBUTING.md:88-100`
spells out what adding an infrastructure language costs: a detection helper in
`src/pipeline/pass_infrascan.c`, a `CBM_LANG_<LANG>` enum value in `internal/cbm/cbm.h`, a row in
the table in `lang_specs.c`, a custom extractor returning `CBMFileResult*`, and a pass registered in
`pipeline.c`. **VERIFIED.** Five edits across four files, none of them checked by a compiler for
mutual consistency. This is what a plugin seam looks like when there is no interface type — and it
is why the project is not, in practice, third-party-extensible.

## 4. What Sync should adopt

**(a) Close the deny-list hole in the import-linter contract. This is the finding I would act on
first.**

`pyproject.toml:108-118` names nine forbidden modules: `sync.graph`, `sync.signals`, `sync.index`,
`sync.detect`, `sync.telemetry`, `sync.remediate`, `sync.forge`, `sync.route`, `sync.cli`.

`src/sync/` contains fourteen packages. The five that are **not** in the list are `sync.api`,
`sync.benchmark`, `sync.dashboard`, `sync.mcp`, and `sync.verify` — each with an `__init__.py`,
each a real package. **VERIFIED** by enumerating `src/sync/*/__init__.py` against the contract.

This is not theoretical. `sync/dashboard/` and `sync/api/` import `psycopg`, `starlette`,
`GraphStore`, `dict_row`, and `JSONResponse` (**VERIFIED** by grepping their import statements).
A single `from sync.dashboard import …` inside `sync/core/models.py` would pass `lint-imports`
cleanly, because the contract does not mention `sync.dashboard`. It would also pass
`test_core_needs_one_third_party_package`, because that test's `STDLIB_AND_SELF` set at
`tests/test_import_boundary.py:50-55` includes `"sync"`, so every first-party import is subtracted
before the assertion at line 92 runs. **VERIFIED.** Both tests would be green and the adapter author
would be installing Starlette and Postgres.

The two tests were designed to cover each other — the docstring at
`tests/test_import_boundary.py:74-79` says exactly that, noting that "a direct `import psycopg` in
core would satisfy the sibling rule while breaking it completely". The gap is the mirror image: a
sibling import that satisfies the third-party rule while breaking the sibling rule.

The fix should be a *closed set*, not a longer list, because a longer list has the same defect
one package later. Sync already owns the machinery: `_third_party_imports_of` at
`tests/test_import_boundary.py:58-70` walks core's AST and returns top-level import names. A sibling
variant is a few lines — collect the full dotted module names, keep those starting with `sync.`,
and assert every one of them starts with `sync.core.`. That closes the set by construction with no
list to maintain, which is the property that makes `Understand-Anything`'s `exports` map
(`packages/core/package.json:7-32`) work: private by default rather than public by default. Keep the
import-linter contract as well — it catches transitive chains that an AST walk of core alone does
not — but stop relying on its enumeration for completeness.

If you would rather stay declarative, the equivalent is a test that reads `forbidden_modules` from
`pyproject.toml` and asserts it equals `{d.name for d in (src/sync).iterdir() if (d/"__init__.py").exists()} - {"core"}`.
That makes the list self-checking rather than self-reporting. Either way, follow the `skills`
repository's step 6 (`setup-ts-deep-modules/SKILL.md`): add a temporary
`from sync.dashboard import create_app` to `sync/core/models.py`, watch the new test fail with the
right message, then revert. The existing test's own history — recorded in
`.claude/rules/test-discipline.md`, where the original form "exited 0 without parsing its own
argument" — is the reason not to skip that.

**(b) Make the adapter conformance kit parameterized over a registry, the way
`codegraph/__tests__/installer-targets.test.ts` is parameterized over `ALL_TARGETS`.**

`src/sync/core/conformance.py` is 1,099 lines, the second-largest file in the tree and the largest
in core. `src/sync/signals/registry.py` is 585 lines. **VERIFIED** by line count; I did not read
either in full, so what follows is **INFERENCE** about shape rather than a claim about content.

The property worth copying from `installer-targets.test.ts` is not the assertions, it is the
iteration: the test imports the registry and loops it, so a newly registered target inherits the
entire contract with no second edit. If Sync's conformance kit is invoked per-adapter rather than
driven from `sync.signals.registry`, then a tenth vendor adapter can be registered and shipped
without ever being run through the kit, and nothing fails. The check is cheap: one test that
iterates the registry and asserts each entry has been through conformance.

`codegraph`'s specific assertion list is worth stealing wholesale too, because four of the five map
directly onto Sync's stated rules — install is byte-identical on re-run (Sync's idempotence rule),
siblings are preserved, uninstall reverses install, and output is parseable and non-empty.

**(c) Steal `codebase-memory-mcp`'s content-hashed exemption format for the one exemption Sync
already has.**

`scripts/lint-mem-gate.py:1-31` describes a whitelist where each entry is pinned to the sha256 of
the specific function it argues about. Edit the function and the entry stops counting: the finding
returns and must be argued again against the code as it now is. The whitelist file
(`scripts/lint-mem-whitelist.txt:1-21`) states the rule in its own header — "A suppression that
outlives the reasoning behind it is worse than no suppression, because it reads as 'reviewed'" —
and the gate mechanically enforces a 120-character minimum on `why` and 40 on `tried`
(`lint-mem-gate.py:45-47`). **VERIFIED.**

Sync has exactly one named exemption of this kind: `CLAUDE.md` records that oasdiff-derived
`vendor_change` rows are exempt from the idempotence rule because `oasdiff breaking` returns a
different answer every run over identical bytes. That exemption is currently prose in `CLAUDE.md`
and a spec. It will outlive its reasoning the moment oasdiff is upgraded or replaced, and nothing
will notice. Pinning it to a hash of the pinned oasdiff version — or of the adapter function that
depends on the non-determinism — makes the retirement condition mechanical rather than
aspirational. The place it lands is alongside `scripts/lint_encoding.py`, which is already the
precedent for "this is a lint, not a test".

**(d) Adopt the `skills` repository's step 7: put the boundary rule next to the code it governs.**

`setup-ts-deep-modules/SKILL.md` step 7 requires a `README.md` inside the packages folder plus a
one-line pointer from `CLAUDE.md`, explicitly so that an agent discovers the rule rather than
tripping over it. Sync's boundary rule currently lives in `CLAUDE.md` under "Non-negotiables" and in
the docstring of `tests/test_import_boundary.py`. Neither is in the field of view of an agent
editing `src/sync/core/models.py`. A short `src/sync/core/README.md` — "this package ships as
`sync-core`; it may import `pydantic` and nothing else, first-party or third-party; see
`tests/test_import_boundary.py`" — costs nothing and sits where the violation would be written.

## 5. Where Sync is already ahead, and where a reference would be a step backwards

**Sync is the only repository in the set with a machine-checked first-party import boundary.** Of
nine references, one has a compiler-enforced boundary that happens to be free (`open-code-review`'s
`internal/`, which does not address intra-module layering at all), one has a resolver-enforced
package surface (`Understand-Anything`'s `exports` map), and *seven have no architectural
enforcement whatsoever*. The reader should not skim past that: unenforced is the normal case, and
several of these are serious, well-maintained projects. `codebase-memory-mcp` runs an eight-layer
security audit and a content-hashed memory-safety gate and still has no include-layering check.

**Sync is the only repository that packages its core separately to make the boundary physically
true.** `src/pyproject.toml` builds `sync-core` as a namespace-package wheel with `pydantic` as its
sole dependency, and `pyproject.toml:73-77` excludes `core/**` from the runtime wheel so the two
distributions never own the same files. `Understand-Anything` gets closest with `workspace:*` +
`exports`, but `packages/core/package.json:43-45` lists fifteen tree-sitter grammars plus `zod`,
`yaml`, `fuse.js`, and `ignore` — a plugin author there inherits the whole parsing stack. Nobody
else splits at all.

**Do not adopt `code-review-graph`'s flat-package layout, and be explicit about why.** A 16,080-line
`parser.py` is what happens when a repository has 47 peer modules and no seam that pushes back. Sync
has fourteen packages, and its largest file is `src/sync/cli.py` at 2,078 lines with the largest
non-CLI file at 1,099. **VERIFIED.** The gap is a factor of eight on the largest file and it is
structural, not disciplinary. Sync's `CLAUDE.md` already says "a file that has grown past one clear
responsibility is a signal"; `code-review-graph` is the empirical case for that sentence.

**Do not replace import-linter with `open-code-review`'s `internal/` model.** Python has no
equivalent, and the analogue people reach for — a leading underscore — is convention only. More
importantly, `internal/` solves the wrong problem: it protects the module from outsiders, whereas
Sync's constraint runs the other way, protecting an *inner* package from its own siblings.

**Do not adopt `codegraph`'s "the architecture is in CLAUDE.md" approach**, tempting as it is given
how good that document is. `codegraph/CLAUDE.md` documents its layering more thoroughly than most
projects document anything, and its largest source file is still 6,767 lines. Documentation is not
a constraint; it is a hope. **INFERENCE**, but the correlation across this set is hard to miss: the
two repositories with resolver- or compiler-enforced surfaces have the smallest largest-files
relative to their size, and the two with prose-only layering have the biggest.

**One place a reference is cheaper and Sync should notice the cost.** `Understand-Anything`'s
boundary costs 26 lines of JSON and runs on every `tsc` invocation. Sync's costs an
import-linter dev dependency, a subprocess spawn per test run, a `PYTHONIOENCODING`/`PYTHONUTF8`
workaround because import-linter renders an emoji spinner through rich and dies on cp1252
(`tests/test_import_boundary.py:24-35`), and a contract list that must be edited whenever a package
is added. That is a real maintenance surface, and the deny-list hole in section 4(a) is exactly the
failure mode it produces. The AST-based sibling check proposed there is closer to
`Understand-Anything`'s cost profile: no subprocess, no encoding workaround, no list.

## 6. Open questions only the owner can settle

1. **Is the five-package gap in `forbidden_modules` deliberate?** `sync.api`, `sync.dashboard`,
   `sync.mcp`, `sync.verify`, and `sync.benchmark` postdate the contract. If `sync.mcp` or
   `sync.verify` was consciously judged safe for core to import, that reasoning should be a comment
   in `pyproject.toml`. If it was an oversight — which the ordering of the list suggests — the
   closed-set fix in 4(a) applies. Either way the current state reads as "reviewed" when it was not,
   which is precisely the failure mode `codebase-memory-mcp`'s whitelist header warns about.

2. **Is `sync.core` allowed to grow sub-packages?** It is currently five flat modules
   (`conformance.py`, `corpus.py`, `keys.py`, `models.py`, `protocols.py`) with `conformance.py` at
   1,099 lines already the largest. `Understand-Anything`'s depth rule — root files public, any
   subfolder private — is only available if the answer is yes, and it becomes much more valuable if
   `conformance.py` is going to split.

3. **Does the conformance kit gate registration, or only advise it?** This determines whether
   recommendation 4(b) is a one-test change or a redesign, and I could not settle it without reading
   1,099 lines of `conformance.py` plus 585 of `registry.py`. It is the question that most affects
   whether a third-party adapter can be trusted.

4. **Should the adapter seam eventually move out of process, as `open-code-review`'s has?** Sync's
   current bet is an in-tree typed protocol with a separately published SDK, which is strictly
   better for correctness than MCP-over-stdio and strictly worse for isolation — a third-party
   adapter runs in Sync's interpreter with Sync's dependency versions. `open-code-review` accepts a
   weaker contract to get total isolation. That is a business decision about who Sync's adapter
   authors are, not an engineering one.

5. **Does anything enforce the boundary at *publish* time?** The import-linter contract runs against
   the source tree. The claim made to adapter authors is about the installed `sync-core` wheel.
   `tests/test_core_distribution.py` exists and asserts the two LICENSE files are byte-identical
   (**REPORTED** — from the comment at `src/pyproject.toml`, I did not read the test). Whether it
   also installs the built wheel into a clean environment and asserts `import sync.core` succeeds
   with only `pydantic` present is the difference between the promise being tested and the promise
   being described.
