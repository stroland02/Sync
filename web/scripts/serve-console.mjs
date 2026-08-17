/**
 * Serve the built console the way a deployment would, behind one shared credential.
 *
 * This exists to make the console *servable* and to prove it locally. It is deliberately not a
 * deployment: where this runs and under what credential are the owner's decisions, and they carry
 * a spend. `docs/superpowers/reports/2026-08-17-console-deployment-note.md` is the other half of
 * this work and says exactly what the owner has to decide.
 *
 * ## Why this process proxies /api rather than letting the browser call the API directly
 *
 * `web/src/api/client.ts` fetches relative paths (`/api/...`). In development `vite.config.ts`
 * proxies them, and its own comment records the reason: "one origin in development is one origin
 * in production, so nothing depends on a permission the deployed app will not have." A static host
 * that served `dist/` while the browser called the API on another origin would need CORS, and
 * `sync.api` declares no CORS middleware — so that arrangement does not work today and is not
 * papered over here. One origin, one process, one gate.
 *
 * ## What the gate is and is not
 *
 * HTTP Basic, one shared credential, checked on **every** request including `/api`. The properties
 * it does not have are enumerated in `scripts/shared-credential.ts` and they are not softened here.
 * Two consequences that belong at the door rather than in a note nobody opens:
 *
 * - **Basic sends the credential on every request, base64-encoded, which is not encryption.**
 *   Served over plain HTTP to anywhere but localhost, the credential is readable in transit by
 *   anything on the path. This server refuses to bind a non-loopback interface unless
 *   `SYNC_CONSOLE_INSECURE=i-understand` is set, because the failure is silent otherwise: it works
 *   perfectly and leaks continuously.
 * - **The gate protects what passes through this process and nothing else.** If the API is also
 *   reachable on its own port from wherever the console is reachable, the gate is decoration —
 *   anyone can read the same data by asking the API directly. The deployment note makes this the
 *   owner's first checklist item.
 *
 * The API is read-only (`tests/test_api_routes.py::test_no_route_reaches_past_the_read_surface`),
 * so what is at stake behind this gate is disclosure of a customer's repository data, not writes.
 * That is the correct thing to be careful about and it is why the gate fails closed.
 */

import { createReadStream } from "node:fs"
import { stat } from "node:fs/promises"
import { createServer } from "node:http"
import path from "node:path"
import { fileURLToPath } from "node:url"

import {
  credentialMatches,
  offeredCredential,
  requireCredential,
} from "./shared-credential.ts"

const HERE = path.dirname(fileURLToPath(import.meta.url))
const DIST = path.resolve(HERE, "..", "dist")

const PORT = Number(process.env.SYNC_CONSOLE_PORT ?? 4173)
const HOST = process.env.SYNC_CONSOLE_HOST ?? "127.0.0.1"
const API_ORIGIN = process.env.SYNC_API_ORIGIN ?? "http://127.0.0.1:8787"

const TYPES = new Map([
  [".html", "text/html; charset=utf-8"],
  [".js", "text/javascript; charset=utf-8"],
  [".css", "text/css; charset=utf-8"],
  [".svg", "image/svg+xml"],
  [".json", "application/json; charset=utf-8"],
  [".woff2", "font/woff2"],
  [".png", "image/png"],
  [".ico", "image/x-icon"],
])

function refuse(reason) {
  process.stderr.write(`${reason}\n`)
  process.exit(1)
}

const credential = requireCredential(process.env)
if (!credential.ok) refuse(credential.reason)

if (HOST !== "127.0.0.1" && HOST !== "localhost" && process.env.SYNC_CONSOLE_INSECURE !== "i-understand") {
  refuse(
    `Refusing to bind ${HOST}. HTTP Basic sends the credential in the clear on every request, so ` +
      "off-loopback this server must sit behind something that terminates TLS. If that is already " +
      "true and this process is only reachable through it, set SYNC_CONSOLE_INSECURE=i-understand."
  )
}

/** Everything under `dist`, and nothing above it. */
function resolveAsset(urlPath) {
  const decoded = decodeURIComponent(urlPath.split("?")[0])
  const candidate = path.resolve(DIST, `.${path.posix.normalize(decoded)}`)
  // `path.resolve` collapses `..` before this check, so a traversal attempt lands outside DIST and
  // is rejected here rather than reaching the filesystem.
  if (candidate !== DIST && !candidate.startsWith(DIST + path.sep)) return null
  return candidate
}

async function serveFile(res, filePath, status = 200) {
  const type = TYPES.get(path.extname(filePath)) ?? "application/octet-stream"
  res.writeHead(status, {
    "Content-Type": type,
    // The console reads live operator data. A shared cache holding it is a second copy of the
    // thing the gate exists to protect.
    "Cache-Control": "no-store",
    "X-Content-Type-Options": "nosniff",
    "Referrer-Policy": "no-referrer",
  })
  createReadStream(filePath).pipe(res)
}

async function proxyApi(req, res) {
  const target = new URL(req.url, API_ORIGIN)
  const headers = { ...req.headers, host: target.host }
  // The console's own credential never travels onward: the API does not check it, and forwarding a
  // secret to a process that ignores it is how it ends up in that process's logs.
  delete headers.authorization
  delete headers.cookie

  try {
    const upstream = await fetch(target, {
      method: req.method,
      headers,
      body: req.method === "GET" || req.method === "HEAD" ? undefined : req,
      duplex: "half",
      redirect: "manual",
    })
    const body = Buffer.from(await upstream.arrayBuffer())
    res.writeHead(upstream.status, {
      "Content-Type": upstream.headers.get("content-type") ?? "application/json; charset=utf-8",
      "Cache-Control": "no-store",
    })
    res.end(body)
  } catch (error) {
    // A dead API is the single most likely local failure and it must not read as a console defect.
    res.writeHead(502, { "Content-Type": "application/json; charset=utf-8" })
    res.end(
      JSON.stringify({
        error: "The console could not reach the API.",
        api_origin: API_ORIGIN,
        detail: String(error),
      })
    )
  }
}

const server = createServer(async (req, res) => {
  const offered = offeredCredential(req.headers.authorization)
  if (offered === null || !credentialMatches(offered, credential.credential)) {
    res.writeHead(401, {
      "WWW-Authenticate": 'Basic realm="Sync console", charset="UTF-8"',
      "Content-Type": "text/plain; charset=utf-8",
      "Cache-Control": "no-store",
    })
    res.end("This console is behind one shared credential.\n")
    return
  }

  if (req.url?.startsWith("/api/")) {
    await proxyApi(req, res)
    return
  }

  const asset = resolveAsset(req.url ?? "/")
  if (asset === null) {
    res.writeHead(400, { "Content-Type": "text/plain; charset=utf-8" })
    res.end("Bad path\n")
    return
  }

  try {
    const found = await stat(asset)
    if (found.isFile()) {
      await serveFile(res, asset)
      return
    }
  } catch {
    // Falls through to the SPA entry below.
  }

  // Every non-asset path is a client route: the console owns its own routing table, so the server
  // hands back the entry document rather than guessing which paths are real.
  try {
    await serveFile(res, path.join(DIST, "index.html"))
  } catch {
    res.writeHead(500, { "Content-Type": "text/plain; charset=utf-8" })
    res.end(
      "dist/index.html is missing. Run `npm run build` in web/ before serving.\n"
    )
  }
})

server.listen(PORT, HOST, () => {
  process.stdout.write(
    `Console on http://${HOST}:${PORT} — one shared credential, /api proxied to ${API_ORIGIN}\n`
  )
})
