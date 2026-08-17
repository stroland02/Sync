/**
 * Capture every console route at a fixed viewport into a dated directory.
 *
 * `docs/superpowers/reports/screens/` held exactly one dated directory, `2026-08-07`, taken before
 * the M7 substrate port, the mock-parity plan, `DetailGrid`, the Fleet change-unit grain and
 * Settings. **There was no current picture of the built console at all**, so "compare the build to
 * the demo" had nothing on one side of it.
 *
 * Same zero-dependency approach as `visual-eval.mjs`: Chrome DevTools Protocol over the `WebSocket`
 * Node ships. These captures are for a human to read; the machine comparison is the eval's job, and
 * neither replaces the other.
 *
 *   node scripts/capture-console.mjs
 *
 * Subjects come from the running API rather than being hardcoded, so a reseed does not silently
 * produce a directory full of not-found screens.
 */

import { mkdir, writeFile } from "node:fs/promises"
import path from "node:path"

const CDP = process.env.EVAL_CDP ?? "http://127.0.0.1:9222"
const BASE = process.env.EVAL_CONSOLE ?? "http://127.0.0.1:4210"
const API = process.env.EVAL_API ?? "http://127.0.0.1:8811"
const WIDTH = Number(process.env.EVAL_WIDTH ?? 1440)
const HEIGHT = Number(process.env.EVAL_HEIGHT ?? 900)
const OUT = process.env.EVAL_OUT ?? path.resolve("..", "docs", "superpowers", "reports", "screens")

/**
 * Credentials as a header, not embedded in the URL.
 *
 * Chrome uses URL-embedded credentials for the document but not for the page's own `fetch` calls,
 * so a capture taken that way photographs a console whose every panel failed. Three separate
 * measurements in this work were invalidated by exactly that before it was understood; a screenshot
 * is the one artifact where the mistake is invisible to the person reading it later.
 */
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
  let nextId = 1
  const ready = new Promise((resolve, reject) => {
    socket.addEventListener("open", () => resolve())
    socket.addEventListener("error", (e) => reject(new Error(String(e.message ?? e))))
  })
  socket.addEventListener("message", (event) => {
    const message = JSON.parse(event.data)
    const settle = pending.get(message.id)
    if (settle === undefined) return
    pending.delete(message.id)
    if (message.error) settle.reject(new Error(message.error.message))
    else settle.resolve(message.result)
  })
  return {
    ready,
    send(method, params = {}) {
      const id = nextId++
      socket.send(JSON.stringify({ id, method, params }))
      return new Promise((resolve, reject) => pending.set(id, { resolve, reject }))
    },
    close: () => socket.close(),
  }
}

/** Subjects read off the API, so a reseed cannot leave this capturing not-found screens. */
async function subjects() {
  const json = async (p) => (await fetch(`${API}${p}`)).json()
  const repos = await json("/api/repositories")
  const overview = await json("/api/overview")
  const runs = await json("/api/runs")
  const repo = repos.repo_ids?.[0] ?? null
  const vendor = overview.vendors?.[0]?.vendor_id ?? null
  const finding = runs.items?.[0]?.finding_id ?? null
  return { repo, vendor, finding }
}

const { repo, vendor, finding } = await subjects()
const enc = encodeURIComponent

const ROUTES = [
  ["01-fleet", "/"],
  ["02-codebase", repo && `/repositories/${enc(repo)}`],
  ["03-vendor", vendor && `/vendors/${enc(vendor)}`],
  ["04-signals", repo && `/repositories/${enc(repo)}/observed`],
  ["06-finding", finding && `/findings/${enc(finding)}`],
  ["07-workflow", finding && `/findings/${enc(finding)}/workflow`],
  ["08-pull-request", finding && `/findings/${enc(finding)}/workflow/pull-request`],
  ["09-detectors", "/detectors"],
  ["10-settings", "/settings"],
].filter(([, route]) => route !== null && route !== undefined)

const stamp = new Date().toISOString().slice(0, 10)
const dir = path.join(OUT, stamp)
await mkdir(dir, { recursive: true })

for (const [name, route] of ROUTES) {
  const target = `${BASE}${route}`
  const tab = await (await fetch(`${CDP}/json/new?${encodeURIComponent(target)}`, { method: "PUT" })).json()
  const page = session(tab.webSocketDebuggerUrl)
  await page.ready
  try {
    await page.send("Page.enable")
    const auth = basicAuthHeader(target)
    if (auth !== null) {
      await page.send("Network.enable")
      await page.send("Network.setExtraHTTPHeaders", { headers: { Authorization: auth } })
      await page.send("Page.navigate", { url: withoutCredentials(target) })
    }
    await page.send("Emulation.setDeviceMetricsOverride", {
      width: WIDTH,
      height: HEIGHT,
      deviceScaleFactor: 1,
      mobile: false,
    })
    // Wait for laid-out text rather than a load event, for the reason visual-eval.mjs records: a
    // half-rendered capture is a picture of nothing and looks like a defect in the console.
    // Wait for panels to resolve, not just for the document to have text. A screenshot of a
    // half-loaded screen looks like a design decision to whoever opens it later.
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
    if (!settled) console.log(`  (warning) ${name} never settled; captured anyway`)
    const shot = await page.send("Page.captureScreenshot", { format: "png" })
    await writeFile(path.join(dir, `${name}.png`), Buffer.from(shot.data, "base64"))
    console.log(`captured ${name} <- ${route}`)
  } finally {
    await page.send("Emulation.clearDeviceMetricsOverride").catch(() => {})
    page.close()
    await fetch(`${CDP}/json/close/${tab.id}`).catch(() => {})
  }
}

console.log(`\n${ROUTES.length} screens at ${WIDTH}x${HEIGHT} -> ${dir}`)
