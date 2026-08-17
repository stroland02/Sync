/**
 * What each screen asks the API for, and how many times.
 *
 * **This reports; it does not fail.** Over-fetching is a cost finding rather than a correctness one,
 * and a gate that failed on it would block correct work — the console can be entirely honest and
 * still ask for the same page twice. Every number here is for a reader to act on, not for CI to
 * refuse.
 *
 * Two questions, because they are the two shapes the waste takes:
 *
 * 1. **The same route requested more than once for one screen.** React Query deduplicates by query
 *    key, so a repeat means two call sites built *different* keys for the same answer — usually by
 *    passing different pagination defaults. That is a real second round trip.
 * 2. **A payload nobody reads.** This script cannot see into a component, so it reports the request
 *    and leaves the judgement to a reader with the source open. What it can say is which routes a
 *    screen fetched at all, which is the list to check against what the screen renders.
 *
 * It shares `visual-eval.mjs`'s readiness and refusal rules, for the same reason: a screen measured
 * mid-load under-counts its requests, and a screen with a failed panel counts a retry as traffic.
 *
 *   node scripts/fetch-audit.mjs
 */

const CDP = process.env.EVAL_CDP ?? "http://127.0.0.1:9222"
const CONSOLE_URL = process.env.EVAL_CONSOLE ?? "http://127.0.0.1:4225/"
const API = process.env.EVAL_API ?? "http://127.0.0.1:8841"
const WIDTH = Number(process.env.EVAL_WIDTH ?? 1440)
const HEIGHT = Number(process.env.EVAL_HEIGHT ?? 900)

function basicAuthHeader(rawUrl) {
  const url = new URL(rawUrl)
  if (url.username === "" && url.password === "") return null
  const pair = `${decodeURIComponent(url.username)}:${decodeURIComponent(url.password)}`
  return `Basic ${Buffer.from(pair).toString("base64")}`
}

function withoutCredentials(rawUrl) {
  const url = new URL(rawUrl)
  url.username = ""
  url.password = ""
  return url.toString()
}

function session(wsUrl) {
  const socket = new WebSocket(wsUrl)
  const pending = new Map()
  const listeners = []
  let nextId = 1
  const ready = new Promise((resolve, reject) => {
    socket.addEventListener("open", () => resolve())
    socket.addEventListener("error", (e) => reject(new Error(String(e.message ?? e))))
  })
  socket.addEventListener("message", (event) => {
    const message = JSON.parse(event.data)
    if (message.method !== undefined) {
      for (const listener of listeners) listener(message)
      return
    }
    const settle = pending.get(message.id)
    if (settle === undefined) return
    pending.delete(message.id)
    if (message.error) settle.reject(new Error(message.error.message))
    else settle.resolve(message.result)
  })
  return {
    ready,
    on: (fn) => listeners.push(fn),
    send(method, params = {}) {
      const id = nextId++
      socket.send(JSON.stringify({ id, method, params }))
      return new Promise((resolve, reject) => pending.set(id, { resolve, reject }))
    },
    close: () => socket.close(),
  }
}

/** The path without its query string: two pages of one route are still one route. */
function routeOf(rawUrl) {
  try {
    return new URL(rawUrl).pathname
  } catch {
    return rawUrl
  }
}

async function subjects() {
  const json = async (p) => (await fetch(`${API}${p}`)).json()
  try {
    const [repos, overview, runs] = await Promise.all([
      json("/api/repositories"),
      json("/api/overview"),
      json("/api/runs"),
    ])
    return {
      repo: repos.repo_ids?.[0] ?? null,
      vendor: overview.vendors?.[0]?.vendor_id ?? null,
      finding: runs.items?.[0]?.finding_id ?? null,
    }
  } catch {
    return { repo: null, vendor: null, finding: null }
  }
}

const found = await subjects()
const enc = encodeURIComponent

const PAGES = [
  ["fleet", "/"],
  ["codebase", found.repo && `/repositories/${enc(found.repo)}`],
  ["api-services", found.vendor && `/vendors/${enc(found.vendor)}`],
  ["signals", found.repo && `/repositories/${enc(found.repo)}/observed`],
  ["observe", "/detectors"],
  ["remediation", found.finding && `/findings/${enc(found.finding)}/workflow`],
  ["settings", "/settings"],
].filter(([, route]) => Boolean(route))

async function auditPage(name, route) {
  const target = `${CONSOLE_URL.replace(/\/$/, "")}${route}`
  const tab = await (await fetch(`${CDP}/json/new?${encodeURIComponent(target)}`, { method: "PUT" })).json()
  const page = session(tab.webSocketDebuggerUrl)
  await page.ready

  const requests = []
  page.on((message) => {
    if (message.method !== "Network.requestWillBeSent") return
    const url = message.params?.request?.url ?? ""
    if (url.includes("/api/")) requests.push({ url, route: routeOf(url) })
  })

  try {
    await page.send("Page.enable")
    await page.send("Network.enable")
    const auth = basicAuthHeader(target)
    if (auth !== null) {
      await page.send("Network.setExtraHTTPHeaders", { headers: { Authorization: auth } })
      await page.send("Page.navigate", { url: withoutCredentials(target) })
    }
    await page.send("Emulation.setDeviceMetricsOverride", {
      width: WIDTH,
      height: HEIGHT,
      deviceScaleFactor: 1,
      mobile: false,
    })

    let settled = false
    for (let attempt = 0; attempt < 120; attempt++) {
      const probe = await page.send("Runtime.evaluate", {
        expression: `(() => {
          const main = document.querySelector("main")
          if (main === null || main.textContent.trim().length < 40) return false
          return !/Loading |Waiting for the API/i.test(main.textContent)
        })()`,
        returnByValue: true,
      })
      if (probe.result.value === true) {
        settled = true
        break
      }
      await new Promise((r) => setTimeout(r, 250))
    }
    // A screen measured mid-load under-counts its own requests, so an unsettled page is reported as
    // unmeasured rather than as a low number somebody would read as good news.
    if (!settled) return { name, route, settled: false, requests: [] }

    // Polling routes keep fetching after the screen settles. One extra beat, then stop counting, so
    // the figure is "what one render costs" rather than "how long the script watched".
    await new Promise((r) => setTimeout(r, 750))
    return { name, route, settled: true, requests: [...requests] }
  } finally {
    await page.send("Emulation.clearDeviceMetricsOverride").catch(() => {})
    page.close()
    await fetch(`${CDP}/json/close/${tab.id}`).catch(() => {})
  }
}

console.log(`# Fetch audit — what each screen asks for, ${WIDTH}x${HEIGHT}\n`)
console.log("Reported, not enforced: over-fetching is a cost finding, and a gate that failed on it")
console.log("would block correct work.\n")

for (const [name, route] of PAGES) {
  const result = await auditPage(name, route)
  console.log(`## ${name} — ${route}\n`)
  if (!result.settled) {
    console.log("_not measured: the screen never settled, so its request count would be an undercount._\n")
    continue
  }

  const byRoute = new Map()
  for (const request of result.requests) {
    const seen = byRoute.get(request.route) ?? []
    seen.push(request.url)
    byRoute.set(request.route, seen)
  }

  console.log(`${result.requests.length} API request(s), ${byRoute.size} distinct route(s).\n`)
  console.log("| route | times | distinct URLs |")
  console.log("|---|---|---|")
  for (const [apiRoute, urls] of [...byRoute.entries()].sort()) {
    const distinct = new Set(urls).size
    const flag = urls.length > 1 ? (distinct === 1 ? " ← same URL twice" : " ← same route, different queries") : ""
    console.log(`| ${apiRoute} | ${urls.length} | ${distinct}${flag} |`)
  }
  console.log("")
}
