# Sync — Threat Model

**Date:** 2026-07-25, extended 2026-08-06
**Status:** Specified. Contains one finding against code already on the M0 branch. The prompt-injection
section was rewritten on 2026-08-06 from a traced inventory of the inputs rather than from a category,
and the first layer of defence it argues for is built.
**Scope:** What Sync holds, what it must never hold, the blast radius when it is compromised, and the gap
between the architecture the design document claims and the code as written.

This is a security document and a sales document. The design document's promise — *we never execute your code
and never hold your secrets* — is the strongest procurement argument Sync has, and it is only worth making if
it survives inspection. This document is that inspection.

## The precedent that makes this urgent

Kudelski Security published a compromise of CodeRabbit that went from a single pull request to remote code
execution and **write access across approximately one million repositories**.
(`kudelskisecurity.com/research/how-we-exploited-coderabbit-from-a-simple-pr-to-rce-and-write-access-on-1m-repositories/`)

The shape of that failure is the shape of Sync's risk exactly, and it is worth stating precisely because the
lesson is not "be careful":

1. A service analyzes repositories it does not control.
2. It runs a tool from, or configured by, the untrusted repository.
3. That process shares an environment with the credentials of a GitHub App installed across every customer.
4. Therefore one attacker-controlled repository yields the whole installation base.

Steps 1 and 4 are inherent to what Sync is. Steps 2 and 3 are choices, and they are the only two places where
this can be prevented.

## Assets, ranked by what their loss costs

| Asset | Where it lives | Loss means |
|---|---|---|
| GitHub App private key | Control plane | Write access to every installed repository. Total, unrecoverable. |
| Installation access tokens | Control plane, short-lived | Write access to one customer until expiry |
| The API Dependency Graph | Postgres | Discloses a customer's vendor topology and call-site map |
| Model API credentials | Patch node | Billing theft; prompt exfiltration |
| The migration corpus | Postgres | Least sensitive by construction — see `2026-07-25-sync-migration-corpus.md` |

**Sync deliberately holds none of:** customer production credentials, vendor API keys, `.env` contents, CI
secrets, or any ability to deploy. This is the architecturally load-bearing decision. Competitors that execute
customer code in their own environment to run tests must hold or synthesize enough environment to make that code
run; Sync pushes a branch and lets the customer's own CI, holding the customer's own secrets, be the verifier.

## Finding: the "never executes customer code" claim is currently false

`src/sync/index/tsc.py` on the M0 branch prefers the repository's own compiler:

```python
local_tsc = repo_path / "node_modules" / ".bin" / ("tsc.cmd" if _on_windows() else "tsc")
if local_tsc.exists():
    command = [str(local_tsc), "--noEmit"]
```

That is a binary from the customer's dependency tree, executed by Sync, in Sync's process environment. Three
separate execution paths open here, and the first is the one people miss:

- **The compiler binary itself.** `node_modules/.bin/tsc` is whatever the repository put there.
- **`tsconfig.json`.** Even with a trusted compiler, `extends` and `compilerOptions.plugins` resolve into
  `node_modules` and load code into the compiler process. Typechecking a project is not a pure function of its
  source.
- **Populating `node_modules` at all.** A clone does not arrive with dependencies installed. Whatever installs
  them runs `preinstall`/`postinstall` lifecycle scripts from the entire transitive dependency tree unless
  explicitly told not to.

The fallback path has a second, smaller problem: `--package=typescript@latest` fetches an unpinned compiler over
the network at verification time. That is both a supply-chain exposure and a source of non-reproducible
verification results — the same patch can verify differently on two days.

**This is not a bug in the code as written.** The function does exactly what M0 needs, against a fork we
control, and preferring the project's own compiler is the correct behavior for typecheck fidelity. It is a
mismatch between that code and a claim in `CLAUDE.md` that is marked non-negotiable. One of the two has to
move, and the claim is worth more than the convenience.

**How it was resolved: the claim moved, and one of the three paths closed.** `CLAUDE.md` no
longer asserts the absolute; it states that never executing customer code is the intent rather
than the invariant, and that Sync runs the customer's *toolchain* while never running their
application. The third path above is genuinely closed — every install command in
`src/sync/index/deps.py` passes `--ignore-scripts`, so no lifecycle script from the dependency
tree runs. The first two are open by design: `src/sync/index/tsc.py:132` still prefers
`node_modules/.bin/tsc`, and `tsconfig.json` still resolves plugins into the compiler process.
The unpinned fallback is also still there (`tsc.py:150`, `--package=typescript@latest`), so the
non-reproducibility noted above stands.

### Required mitigations

The rule to adopt, stated so it can be tested rather than remembered:

> **No process that touches customer repository content ever shares an environment with a credential.**

Concretely:

1. **Split the verification sandbox from the control plane.** Clone, install, patch, and typecheck run in an
   ephemeral container with no GitHub App key, no installation token, no model API key, and no database
   credential in its environment or on its filesystem. The patch and its diagnostics come back over a pipe.
   This is the mitigation that would have contained the CodeRabbit compromise, and it is the only one on this
   list that is not optional.
2. **Install with lifecycle scripts disabled.** `npm ci --ignore-scripts`. Accept that a small number of
   packages will not build; a project that cannot typecheck without running arbitrary install scripts is a
   project Sync declines to verify, and declining is a supported outcome — the design already treats an
   unverifiable finding as abandoned rather than as a reason to lower the gate.
3. **No network egress from the sandbox after dependency installation**, and no egress to anything but the
   package registry during it.
4. **Pin the fallback compiler.** Replace `typescript@latest` with a version resolved from the repository's own
   `package.json`, falling back to a version pinned in Sync. Verification must be reproducible.
5. **Run non-root, read-only root filesystem, with the clone on the only writable mount**, and a hard wall-clock
   kill. `_TSC_TIMEOUT_SECONDS` already provides the last of these.

### What stays true after the mitigation

The claim narrows and survives, and the narrowed version is still the strongest in the category:

> Sync never holds customer secrets, never deploys, and never executes customer code anywhere a credential can
> be reached. Typechecking runs in a disposable, credential-free, network-isolated sandbox, and the authoritative
> verification is the customer's own CI, running in the customer's own environment, under the customer's own
> secrets.

That is a claim a security reviewer can check against an architecture diagram, which is the property that makes
it useful in procurement.

## GitHub App permission scope

Request the minimum that the remediation graph actually needs, and be able to justify each line in a security
review:

| Permission | Level | Why |
|---|---|---|
| Contents | Read and write | Clone; push a branch. **Never to a default branch.** |
| Pull requests | Read and write | Open the pull request; read merge outcome |
| Checks / Actions | Read | Poll the CI run in `await_ci` |
| Metadata | Read | Mandatory |

Not requested, and worth saying so explicitly on the trust page: Administration, Secrets, Environments,
Deployments, Packages, Members, Webhooks-write.

Sync writes only to branches it created, opens pull requests, and never merges. Merge authority stays with a
human, which is what keeps the blast radius of a bad patch at "a pull request someone declines."

**Enforce the branch constraint in code, not in policy.** A guard in `sync.forge` that refuses to push to a
repository's default branch or to any branch Sync did not create, with a test that asserts the refusal, is worth
more than any documented intention.

## Prompt injection

The patch node reads content that an attacker can influence: vendor changelog prose, and the customer's own
source and diagnostics. A changelog entry, or a comment in a repository file, can carry instructions aimed at
the model.

The verification gate is the real containment, and this is the second place where "nothing unverified reaches a
pull request" pays for itself: an injected instruction that produces a malicious edit still has to pass `tsc`
and then the customer's CI, and it still lands as a reviewable diff on a branch rather than as a merge.

Two limits worth naming rather than glossing:

- The gate constrains *what reaches a pull request*, not *what the model does while running*. Sandbox isolation
  is what constrains that, which is another reason mitigation 1 is not optional.
- A patch can be malicious and still typecheck and still pass CI. The evidence bundle is the answer — the pull
  request carries the specification diff, the changelog entry, the affected call sites, and the CI link, so a
  reviewer can see whether the diff matches the justification. A diff that does something the evidence does not
  explain is the signal to look for, and it is visible precisely because Sync shows its reasoning rather than
  presenting a black box.

### The paragraph above was written before anyone traced the inputs

It says "vendor changelog prose" as a category. This section says which bytes, from which line, under
whose control, and what each one buys an attacker. It was written on 2026-08-06 against the code as it
then stood, and it corrects one claim the reference study left open.

That open question was whether Sync should build an injection defence now or wait for "a future adapter
reading a vendor's freeform release notes"
(`docs/superpowers/references/engineering/llm-engineering-practice.md`, §5), on the reasoning that
`VendorChange.raw` held only structured oasdiff records, which are lower risk. **That adapter already
exists and has since before the question was asked.** `sync.signals.deprecations.parameters` parses a
vendor's published markdown page and keeps the behaviour cell verbatim — deliberately, because a pull
request body quotes the vendor's own wording and that wording is what makes the finding credible
(`src/sync/signals/deprecations/parameters.py:121`). The cell is filed as `raw["behavior"]`
(`:174`), `sync.detect.parameter_deprecation` interpolates it into `Finding.rationale`
(`src/sync/detect/parameter_deprecation.py:147`), and `build_patch_prompt` renders that under "Why this
matters". The precondition for treating this as urgent was met before the note that named it was filed.

### Where untrusted bytes enter

Ranked by how easily an attacker reaches the byte, not by where it sits in the pipeline.

| Entry | Field it becomes | Who can write it | Reaches the patch prompt |
|---|---|---|---|
| `signals/deprecations/parameters.py:121` → `:174` | `raw["behavior"]`, `raw["applies_from"]` | Anyone who can change a vendor's published documentation page, plus anyone who can serve it — `signals/deprecations/adapter.py:137-151` is a plain urllib GET | Yes, via `Finding.rationale` |
| `signals/oasdiff.py:166` (`raw=record`) | `raw["text"]`, and through it `changed_field` (`:202-210`) | Anyone who can land a property name or description in a vendor's OpenAPI specification | Yes — "Affected field", and inside the "Required edit" sentence |
| `signals/oasdiff.py` (`kind`, `operation_id`, versions) | `VendorChange.kind`, `.operation_id` | The same | Yes, three prompt lines |
| `signals/feed/consumer.py:79` | Every field of `VendorChange`, unvalidated | Whoever holds the feed signing key | Yes, all of it |
| `index/typescript.py:594-618`, `index/python_lang.py:768-783`, `index/literals.py:140` | `CallSite.path`, `.symbol`, `.args_keys`, `.response_fields_read`, `.operation_id` | Anyone who can merge — or in most workflows merely open — a pull request against the customer's own repository | Yes, four prompt lines |
| `remediate/nodes.py:295, 439, 522` | `diagnostics` | `tsc` output over customer source and the vendor's shipped `.d.ts`; a CI verdict; the rejected diff | Yes, the retry section |
| The clone itself | Nothing — read by the agent's own `Read`, `Grep` and `Bash` calls | Anyone who can write a file in the repository | **Not through the prompt at all.** See "what the first layer does not cover" |

`VendorChange`'s string fields are bare `str` with no validator, no length bound and no charset constraint
(`src/sync/core/models.py:97-110`). The three accidental filters that exist — `_looks_like_a_model_id`,
`_IDENTIFIER` in the parameter parser, and oasdiff's newline check — each cover one field and none covers
`raw["behavior"]`.

**The distinction the table exists to make: "vendor" and "customer" are not two grades of the same thing.**
A vendor's changelog is a public document. Nobody needs an account to read it, the vendor's own review
process is the only thing standing between a contributor and its contents, and Sync fetches it for every
customer at once — so a single successful edit is a payload delivered to Sync's entire installed base.
A customer's repository is private and the attacker has to already be inside it, which sounds like a
smaller problem and is a different one: it reaches only that customer, but it reaches them with Sync's
credentials rather than the attacker's, which is the whole point of doing it.

### What an attacker gains, ranked by damage

1. **Exfiltration of the customer's own secrets, with nothing left behind in the diff.** This is the worst
   case and it is not the obvious one. The patch agent holds `Bash` inside a clone, and a clone of a real
   application repository routinely contains `.env` files, `.npmrc` tokens, fixture credentials and CI
   configuration. Sync holds no customer secrets, which is exactly why this matters: the secrets are in the
   clone, and `Bash` is a general egress channel. `WebSearch` and `WebFetch` are in `DISALLOWED_TOOLS`
   (`agent_patch.py:69`), which is a real block, but `curl` is not a tool — it is a program, and the agent
   was given a shell. Nothing in the verification gate looks at this: the exfiltration happens during the
   run and the diff can be empty or innocent afterwards. **Damage is unbounded and detection is zero.**
   *Amended 2026-08-06: a tool gate now refuses any shell command outside a fixed list of three and
   records every call. `curl` no longer runs and the attempt is in the log. The clone is still
   credential-bearing and the process still has a network stack, so this reads "the agent may not ask
   for egress", not "egress is impossible" — see "The first predicate on the run" below.*
2. **Arbitrary code in a customer's repository behind a green CI.** A patch that compiles and passes the
   customer's tests, plus one line that does something else. The gates do their job and the pull request
   arrives looking exactly like every other one Sync opens. Bounded by a human review that Sync's own
   product position invites — a reviewer reads the evidence bundle — but a one-line addition inside an
   otherwise correct migration is a hard thing to spot, and Sync's pull requests are designed to be
   routine.
3. **Poisoning the migration corpus and the routing matrix.** Abandoned attempts are how routing learns
   which change kinds are not mechanically safe. An attacker who can cause abandonment at will can steer
   which changes Sync stops attempting, which is a durable, quiet degradation rather than an incident.
4. **Burning model spend.** An instruction that sends the agent on a long fruitless search costs `xhigh`
   effort per attempt against a per-attempt budget that does not exist. Cheapest to execute and the least
   interesting.

Note what is *not* on this list. The GitHub App key is not reachable from the patch agent as designed,
because mitigation 1 puts the clone in a credential-free sandbox. That mitigation is still unbuilt, and
until it is, the CodeRabbit shape at the top of this document is reachable from item 1 by a shorter path
than any of these four.

### What the existing gates genuinely stop, and where the boundary sits

They stop a patch that does not compile, and a patch the customer's own tests reject. `static_verify`
measures the tree a push would carry rather than whatever the agent left in the clone
(`sync.index.shipped_tree`), an edit inside an installed dependency fails the verification by name
before the compiler runs (`sync.index.dependency_edits`), and an unstaged new file fails the gate rather
than shipping (`agent_patch.py:299-305`). Those are real and they are more than most tools in this
category have.

**The boundary is this: every one of those gates is a predicate on the artifact. None of them is a
predicate on the run.** They ask what the branch contains. They do not ask what the agent did, what it
read, or what left the machine while it was working. An attack that wants to ship something has to beat
them; an attack that wants to take something never meets them.

That sentence was true of every gate Sync had until 2026-08-06. `sync.remediate.tool_gate` is the
first predicate on the run, and the section below is careful about how much of the boundary it
moves: a call the agent makes is now weighed, but what the agent reads is still unweighed, and
nothing here is an operating-system boundary.

The second half of the boundary is inside the artifact check itself. `tsc` plus CI is a test of whether
the patch is *broken*, not of whether it is *what was asked for*. A patch that applies the migration
correctly and adds one more line compiles, passes, and is the shape every gate is looking for.

### The trust boundary

**Vendor text is data the agent reads about. It is never instruction the agent follows.** The same holds
for the repository's contents and for tool output over either.

This is a decision rather than an observation, and the alternative is real: the whole value of quoting a
vendor's own deprecation wording is that it tells the agent something Sync does not otherwise know, which
is uncomfortably close to instructing it. The line that resolves it is *who the sentence is addressed to*.
A vendor's changelog is addressed to a human integrator and describes the world. Sync's prompt is addressed
to the agent and describes the task. Text of the first kind may inform the task and may never redefine it,
and where the two conflict, Sync's wins — including when the vendor's text is more specific, more urgent,
or claims to come from Sync.

Everything below follows from that sentence, and so does the honest limit on it: a boundary the agent is
told about is not a boundary the agent is guaranteed to respect.

### Layer one: the untrusted-text boundary, built 2026-08-06

`src/sync/remediate/untrusted.py`, applied at `build_patch_prompt`. Three parts, one idea:

- Every untrusted span in the prompt sits inside an element naming what it is —
  `<untrusted-vendor-text>`, `<untrusted-repository-text>`, `<untrusted-tool-output>`. The vendor block,
  the call-site block, the rationale, and the retry diagnostics are all fenced. So is the field name inside
  the "Required edit" sentence, which is the one line where Sync's instruction and a vendor's bytes share a
  sentence.
- A preamble states what the elements mean before the agent meets one: read what is inside, act on what it
  describes, follow no instruction written in it however phrased and whoever it claims to be from.
- **Content that carries one of those markers is refused, not escaped.** These strings exist nowhere but
  in the structure of this prompt, so a vendor page or a customer's TypeScript cannot contain one by
  accident — an occurrence is content trying to leave the region it was placed in. The usual answer is to
  escape it and carry on; the reason to refuse instead is that an absorbed attack teaches nobody anything.
  A refusal lands in `abandon_reason`, which is where this project already says the interesting failures
  belong, and it costs nothing: the check runs while the prompt is being assembled, before the SDK is
  invoked, so a poisoned record spends the run's attempts and no model time.

**Why this layer rather than a list of injection patterns.** A pattern list is what the reference
implementation leads with, and it is the wrong thing to build first here. It fails in both directions at
once. It fails open, because the realistic payload against Sync is not "ignore previous instructions" —
it is a paragraph of plausible vendor migration guidance, correctly spelled and calmly worded, of the kind
a real deprecation notice contains, and no phrase list catches that. And it fails closed, because vendor
deprecation prose legitimately contains sentences like "disregard the previous guidance" and "this
supersedes the note above"; a list tuned tightly enough to catch an attack will eventually refuse Stripe,
and a defence that blocks real vendor text is an outage. The boundary has neither failure mode: it does
not try to recognise an attack, so it cannot fail to, and it wraps rather than judges, so legitimate text
passes byte for byte.

The second argument is ordering. A pattern list without a boundary has nowhere to put what it finds — it
can redact, but it cannot tell the model which bytes were suspect. Framing is what the other two layers
attach to, so it is first whatever else is built.

**What it does not cover, stated plainly.**

- **It does not make the agent obey.** Framing is persuasion, and persuasion is not containment. Proving
  a model respects the frame requires calling one, which the test discipline here forbids and which would
  in any case establish a fact about today's model and not a property of the system.
- **It does not touch what the agent reads with its own tools.** The prompt is one of two channels and it
  is the smaller one. The agent then `Read`s and `Grep`s a repository whose files can hold anything, and a
  comment in the file it was sent to edit arrives with no fence around it at all. That channel cannot be
  fenced at the prompt layer by construction; it is a sandbox and egress problem, which is mitigation 1.
- **It does nothing about exfiltration**, the top-ranked item above. `Bash` in a clone holding the
  customer's `.env` is unaffected by how the prompt is punctuated.
- **It is not a defence against a compromised feed key.** A feed that can construct a whole `VendorChange`
  can construct one whose fenced contents are perfectly ordinary and whose instruction is the finding
  itself.

Evidence it does something: `tests/test_patch_prompt_injection.py`. A hostile deprecation cell carrying
migration instructions for "the automated migration tool" reaches the agent inside the fence and nowhere
outside it; the same cell with a closing tag appended is refused; the refusal survives whitespace and
capitalisation variants; the refusal message does not quote what it rejected, because it becomes the next
attempt's input; a real Stripe-shaped deprecation entry still builds a prompt with its wording intact; and
ordinary TypeScript — `Array<untrustedInput>`, `a<untrusted_count` — is not mistaken for a marker.
Two mutations were run against those tests and each was caught by a different one: disabling the refusal
reddens the three smuggling tests, and widening the marker to any `<untrusted` reddens the outage guard.

### The first predicate on the run, built 2026-08-06

`src/sync/remediate/tool_gate.py`, registered as a `PreToolUse` hook on every `ClaudeAgentOptions`
the patch node builds. Three refusals and one record:

- **A tool outside the set a patch needs is refused.** `Read`, `Grep`, `Glob`, `Edit`, `Write`,
  `Bash` are what making a patch takes. Everything else is denied, including tools that do not
  exist yet, because the set is stated as what is permitted rather than as a list of what is not.
- **A shell command outside a fixed list of three is refused.** `git add`, `git status`, `npx tsc`
  — the first and third are what the patch prompt asks for by name, the second is how an agent
  confirms the staging that prompt makes load-bearing. The command must be one simple command:
  a second command, a pipe, a redirection, a substitution or a line break refuses the call before
  the first word is read. The match is on the first two tokens rather than on a prefix, because
  `git -c core.pager=… add` is not `git add` — several git configuration keys name a program git
  then executes.
- **A write under `.git/` is refused.** This one is not about the patch, and it is the thing this
  work found that was not on anybody's list. `push_branch` runs `git` in this clone *after* the
  agent has finished, so a file left in `.git/hooks/` runs under Sync, and `.git/config` is the
  same shape by a different route — `core.fsmonitor` and its neighbours name a program the next
  git command executes. Neither is visible to `tsc`, to `shipped_tree`, to `dependency_edits` or
  to the customer's CI, and none of them ships in the diff.
- **Every call is recorded**, permitted ones at debug and refused ones at warning, tagged with the
  finding and repository so a line joins back to a run. The refusal handed to the agent names the
  rule and quotes nothing, on `sync.remediate.untrusted`'s reasoning: the agent composed that
  command, possibly out of text a vendor page put in front of it, and echoing it is a second
  delivery. The log is operator-facing, so it carries the command in full. That asymmetry is the
  whole of the detection half — before this, an exfiltration left nothing anywhere.

**Why a `PreToolUse` hook and not `can_use_tool`.** The installed SDK settles it rather than the
documentation: `claude_agent_sdk.types._get_can_use_tool_shadowed_warning` says that an
`allowed_tools` entry allowing a whole tool auto-approves it *before* the permission callback is
consulted, and that "to gate every tool call, use a PreToolUse hook". Every entry in
`ALLOWED_TOOLS` is a whole-tool entry, so a `can_use_tool` callback would have been consulted for
nothing the agent actually calls. It would also have required restructuring the prompt into
streaming mode, which the same package raises on.

**Why this step and not the other one on the table.** The alternative was to record what the agent
ran and change nothing about what it may run — cheaper, and it answers the "detection is zero"
half. It loses on what is at stake. The asset here is a customer's production credentials, and a
recorded exfiltration is still an exfiltration: you learn which secrets to rotate, which is worth
something, and you learn it after they are gone. Reduction had been treated as the harder half
because `git add` and `npx tsc` are load-bearing and removing `Bash` breaks the patch — but the
gate is per invocation rather than per tool, so the two commands the pipeline depends on stay and
everything else goes. And the record comes with it: the same hook that decides is the only place
that sees every call, so choosing reduction does not cost the detection it was competing with.

**What it does not cover, stated plainly.**

- **It is not containment, and not an operating-system boundary.** It constrains what the agent may
  *ask for*. The process still has a network stack, a filesystem and a credential-adjacent clone;
  anything that gets past the tool layer is unaffected by it. Mitigation 1 remains the containment
  and remains unbuilt.
- **`npx tsc` still runs the customer's own compiler**, resolved through their `.npmrc`, exactly as
  `CLAUDE.md`'s qualification says. A permitted command is not a safe one; it is a needed one.
- **It has not been observed enforcing.** The decision function and the wiring are tested; that the
  CLI honours a returned `permissionDecision: "deny"` is taken from the SDK's own contract and from
  the bundled binary carrying the field, not from a run. Observing it needs a model API call, which
  the test discipline here forbids. This is the weakest claim on the page and it should be read as
  such.
- **It does nothing about what the agent reads.** `Read` and `Grep` over the clone stay permitted
  and unfenced, which is B99 and is the larger channel. The gate now records those calls, so the
  exposure is at least legible; it is not reduced.
- **A permitted command can still be wrong.** `git add` on a path the patch does not need is
  permitted, and the gate deliberately does not arbitrate that — `sync.index.shipped_tree` and the
  unstaged-additions check own it, and mixing a patch-quality rule into a security refusal would
  make both harder to reason about.
- **It is per call, so it cannot see a sequence.** Three permitted commands that together do
  something a single refused one would have done are three permitted commands.

### Sequencing, revised

Layers two and three of the reference's shape — the injection-pattern list and further prompt hardening —
are deliberately not built, and are filed in the backlog with this reasoning. Neither is the next most
valuable thing. **The next most valuable thing is mitigation 1**, the credential-free sandbox, because it
is the only item on this page that touches the top-ranked attack, and because both remaining prompt layers
defend the channel that is already the smaller of the two.

The tool gate does not displace that. It is the cheap part of the same job done a layer higher, and
it was worth building first only because it took a day rather than a milestone. Read the two
together: the gate decides what the agent may ask for, the sandbox decides what the process can do
regardless of what it asks. A gate with no sandbox under it is one bug away from nothing.

## What a security reviewer will ask, and the answer

Written in the order a review actually goes.

1. *Do you store our source code?* No. The ADG stores call-site locations and shapes. Clones are ephemeral and
   destroyed with the sandbox.
2. *Do you hold any of our secrets?* No — not vendor keys, CI secrets, or environment files. Sync cannot run
   your application and does not try to.
3. *Do you run our code?* Only a typecheck, in a disposable container with no credentials and no network. Your
   CI is the authoritative verifier.
4. *Can you merge?* No. Sync opens pull requests. It cannot merge and does not request the permission that
   would let it.
5. *What can you write to?* Branches Sync created. Enforced in code, with a test.
6. *What happens if you are breached?* The App key is the crown jewel and is isolated from every process that
   touches customer content. Rotation revokes every installation token. No customer secret exists to leak
   because none was ever collected.
7. *Do you train on our code?* No. The corpus records structural shapes, salted hashes, and outcomes — never
   source. See `2026-07-25-sync-migration-corpus.md`, which specifies a test asserting no source text can
   appear in it.

## Sequencing

| Milestone | Security work |
|---|---|
| M0 | The branch-guard in `sync.forge` with its test. Pin the fallback compiler. Document the sandbox requirement. The M0 target is a fork we control, so the sandbox itself is not yet load-bearing. |
| M1 | The credential-free verification sandbox, before any repository Sync does not own is indexed. This is the gate on touching a real customer, and it should be treated as one. |
| M4 | SOC 2 Type II observation period, subprocessor list, DPA, and the public trust page built from the seven answers above. |

The honest constraint: SOC 2 Type II requires an observation window and money, and neither is available to a
solo, self-funded operator inside twelve months. The architecture above is what can be offered in the meantime,
and it is a stronger answer than most certified vendors can give — but it is not a substitute for the
certificate, and no proposal here should pretend otherwise.
