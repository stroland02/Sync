# Quickstart, self-hosting, GitHub integration, agent settings: where each actually is

**Owner asked directly: "where is that development being built out right now?"** Audited against the
tree rather than answered from memory, 2026-08-18.

| Surface | State | Owner | Gap |
|---|---|---|---|
| **Agent settings — API** | **Built.** `app.py` carries `merge_policy` and a `REFUSED_MERGE_POLICIES` set, so the `immediately` refusal is real code | Lane G | **Unlanded.** Sits on `lane-e-graph`, not `main` |
| **Agent settings — UI** | Not built | Lane B | Settings is still read-only (`M4-W231`) |
| **Self-host container** | `Dockerfile`, `docker-compose.yml` and `docker-compose.demo.yml` all exist | Lane C | Compose runs **Postgres only**; the product itself has never been containerised, and nothing verifies one command brings it up |
| **`npx` entry point** | **Not built.** No root `package.json`, no `bin/` | Lane C | The doorbell in `M0-W312` does not exist |
| **Quickstart journey** | README mentions it twice; the value-before-configuration journey from `M0-W310` is not written | Lane C | No page a stranger can follow |
| **GitHub integration** | `gh` CLI only, authenticated on this machine. No settings, no status, no per-repo binding | **unassigned** | See below |

## GitHub integration: my P2 ruling was too broad and is corrected

`M0-W311` put GitHub integration out of scope because the reference's flow is a **GitHub App OAuth
install**, which needs a hosted callback we deliberately do not have. That part stands.

**But it took the whole surface out with it, and most of the surface does not need OAuth.** What a
reader actually wants to know is: *which repository will Sync open a pull request against, as whom,
onto which branch, and is that connection working right now.* Every one of those is answerable from
the `gh` CLI we already authenticate with.

**So the buildable version, and it is not a lesser one for a local-first product:** a Connection panel
in Settings showing the authenticated account, the repositories Sync may act on, the base branch per
repository, and a live check that the token still works — with the OAuth install flow explicitly
absent and *stated as absent*, because hosting is out of scope by the owner's own ruling.

## What this changes today

1. **Lane G lands the settings API.** It is written and it is invisible until it is on `main`.
2. **Lane C owns the container, the `npx` entry point and the quickstart** — one chain, ending in a
   stranger typing one command.
3. **Lane B builds the Settings UI** over Lane G's API, including the Connection panel.
