# Serving the console off this machine — what is built, and what the owner must decide

**Prepared, not deployed.** Beta scope Ruling 1 shrinks M4's obligation to one sentence: somebody
who is not on this machine can reach the console and see their repository's real data, behind one
shared credential rather than a user system. This note is the preparation. Where it runs and under
what credential are two of the three decisions reserved for the owner, and they involve a spend, so
nothing here has been deployed and no account has been created.

## What was built

`web/scripts/serve-console.mjs` serves the production build the way a deployment would:

- **A real production build**, `npm run build` into `web/dist`, served as static assets. Not the
  Vite dev server and not `vite preview`.
- **`/api` proxied to the API from the same origin.** The console's client fetches relative paths,
  and `vite.config.ts` already records why: "one origin in development is one origin in production,
  so nothing depends on a permission the deployed app will not have." This process keeps that true.
- **HTTP Basic in front of everything, including `/api`**, with the credential in
  `SYNC_CONSOLE_PASSWORD`. Node built-ins only — it adds no dependency to `package.json`.
- **It fails closed.** No credential, a blank one, or one under twelve characters and the process
  refuses to start and says which variable is wrong. The alternative fails silently: a console that
  works perfectly with no gate, which nobody has a reason to check.
- **It refuses to bind a non-loopback interface** unless `SYNC_CONSOLE_INSECURE=i-understand` is
  set, because Basic sends the credential on every request and base64 is not encryption.

`web/scripts/shared-credential.ts` holds the credential logic, with the properties it does *not*
have written into its docstring rather than left to be assumed. `web/scripts/shared-credential.test.ts`
asserts each of them, including the two that would be invisible in a working console: that an empty
configured credential rejects everything rather than accepting everything, and that a prefix of the
credential is refused.

## Proven locally, by measurement rather than by reading the code

Run against the real build on 2026-08-17, `curl` against `127.0.0.1:4199`:

| Request | Result |
|---|---|
| `GET /` with no credential | `401` |
| `GET /` with a wrong credential | `401` |
| `GET /` with the credential | `200` |
| **`GET /api/repositories` with no credential** | **`401` — the API is behind the gate, not beside it** |
| `GET /detectors` (a client route, not a file) | `200`, serves the entry document |
| `GET /favicon.svg` | `200` |
| `GET /../../package.json`, raw and percent-encoded | `200` serving `index.html` — **not** the file |
| Start with no `SYNC_CONSOLE_PASSWORD` | refuses, naming the variable |
| Start with an 5-character credential | refuses, naming the floor |
| Start with `SYNC_CONSOLE_HOST=0.0.0.0` | refuses, explaining the TLS requirement |

## What does NOT work when it is served this way

Stated here rather than discovered at deploy time.

1. **A static host serving `dist/` while the browser calls the API on another origin does not
   work.** The console fetches relative `/api/...` paths, and `sync.api` declares no CORS
   middleware — no `allow_origin`, no middleware stack at all. Split the origins and every request
   fails in the browser with nothing wrong in either process. Either something proxies `/api` from
   the console's own origin (what this script does), or CORS has to be added to `sync.api`, which
   is Lane E's file and a decision with its own security surface. **The proxy is the cheaper and
   safer of the two.**
2. **There is no path-prefix support.** The build assumes it is served from the root of its origin.
   Serving it at `https://host/console/` would need Vite's `base` set at build time and the router
   given a matching basename. Neither is done, and neither is hard — but it must be decided before
   the build, not after.
3. **The gate protects only what passes through this process.** If the API is independently
   reachable from wherever the console is reachable, the gate is decoration: the same data is one
   unauthenticated request away on the API's own port. **This is the owner's first checklist item.**
4. **The API needs its database.** `SYNC_GRAPH_DSN` and, for the workflow route,
   `SYNC_CHECKPOINTER_DSN` — which falls back to the graph DSN. A console with no database behind
   it renders a screenful of unreachable errors that look like a console defect and are not.
5. **No TLS is terminated here.** This process speaks plain HTTP. Off localhost it must sit behind
   something that terminates TLS, and the refusal above enforces that rather than trusting it.
6. **No rate limiting, no lockout, no logging of failed attempts.** One shared credential with
   unlimited guesses is guessable given time. Whatever fronts this in production is where that
   belongs.
7. **`npm run build` passing is not evidence the payload matches.** `.claude/rules/console-dev-loop.md`
   records why: TypeScript checks the console against the types the console declares, not against
   what the API sends.

## What the owner has to decide and provide

Four things, and none of them can be decided here:

1. **Where it runs.** A host for one small Node process plus the Python API and a Postgres, or a
   static host plus a separately hosted API — the second needs item 1 above resolved first. This
   is the spend.
2. **The credential itself**, and who receives it. It is one secret with no revocation short of
   rotating it for everybody, so the list of people who have it is the whole access-control model.
3. **Whether the API is exposed at all.** The strong answer is that only this process is reachable
   and the API listens on loopback beside it. Anything else makes item 3 above live.
4. **Which repository's data a design partner sees.** The console is single-tenant and renders
   whatever the configured graph holds. There is no tenancy boundary in the product, so the
   boundary is which database the deployment points at.

## What this note deliberately does not claim

The console is *servable*, and that is proven. It is not *deployed*, not *hardened*, and not
*multi-tenant*. One shared credential is not authentication — it has no identity, no revocation per
person, and no audit trail that can say which viewer looked, only that a viewer did. That is
adequate for a beta with a handful of named design partners who each received the secret from the
owner, and it stops being adequate the moment the answer to "who saw this" matters.
