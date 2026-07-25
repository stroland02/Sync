# Sync — Threat Model

**Date:** 2026-07-25
**Status:** Specified. Contains one finding against code already on the M0 branch.
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
