# Getting started

From nothing to a closed loop on your own repository. Every step below is one command, each
command tells you what it decided, and nothing here asks you to assemble anything — a step that
leaves you holding instructions is a defect in the step, not homework.

## 1. Bring Sync up

```bash
git clone https://github.com/stroland02/Sync
cd Sync
npm start
```

`npm start` is the whole install. It checks for updates and fast-forwards a clean checkout,
picks the route that works on your machine — the container where Docker answers, a user-space
install where it cannot — sets up Python, Postgres, the schema, and the console's dependencies,
then serves the console. Rerun the same command after a reboot; it restarts what stopped and
touches nothing else. (`npx @stroland02/sync-up` delivers the same launcher from the registry
and hands you the clone command above.)

When it finishes, the console is at the address it prints, and the **Setup** screen shows each
prerequisite as measured — not assumed.

## 2. Put your own code on the screen

```bash
uv run sync index --repo <your-repo-remote>
```

INDEX reads your repository's call sites into the API Dependency Graph, offline, and the console
shows *your* vendors and *your* call sites. An empty result is reported as exactly that — the
console never fills the gap with somebody else's data.

## 3. Pick what to watch

The [integration catalog](integrations/catalog/index.md) lists every vendor Sync serves today
and every one it recognizes. A *supported* vendor is watched by a registered adapter; a
*recognized* one is named honestly as unwatched, with its page saying what adding it takes —
often one line in `generated-vendors.yaml`.

```bash
uv run sync run --vendor stripe \
    --from-version <pinned> --to-version <target> --repo <your-repo-remote>
```

This joins the vendor's changes against your call sites. Findings land in the console, each
carrying the provenance rung it arrived at — `static`, `resolved`, or `observed` — because a
finding that cannot be attributed cannot be fixed.

## 4. Rehearse the loop before you spend anything

```bash
uv run sync rehearse
```

Rehearsal executes the full pipeline — locate, patch, verify — against a local, zero-remote
fixture repository. No network, no vendor account, no pull request. It is how you watch the
machinery work before pointing it at anything real.

## 5. Close the loop for real

The remediation loop needs two credentials, and it needs them from you because Sync holds no
secrets of its own:

- **An authenticated `gh` CLI** — pull requests are opened as you, onto a branch you configured.
- **An Anthropic API credential** — the patch agent that writes fixes runs on it. The agent is
  contained: it works inside a clone, its tools are gated, and nothing reaches a pull request
  without passing `tsc` and then your repository's own CI.

Then a run that produces a mechanically-safe finding carries it through patch and verification
to a pull request in your repository, and the console shows every step of the reasoning —
including the steps that gave up, because abandoned runs are data.

## What Sync will tell you it cannot tell you

The readiness meter on the console reports axes it has no evidence for as **CANNOT TELL**, not
as green. That is deliberate and permanent: an unmeasured axis is absence, not a passing grade,
and a tool that paints absence green is the tool this one exists to replace.
