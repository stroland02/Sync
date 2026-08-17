/**
 * Measure the drawn mock and the built console the same way, and print the per-property deltas.
 *
 * `docs/superpowers/plans/2026-08-17-reference-hierarchy-and-visual-eval.md` states the insight this
 * rests on: **the mock is a document, not a picture.** `docs/console-mock/Sync Console.dc.html`
 * renders in a browser, so every property the built console can be asked for the mock can be asked
 * for too. That turns "this does not look like the demo" into "Fleet's card radius is 4px against
 * the mock's 8px" — assignable, fixable, and re-runnable.
 *
 * **No dependency.** It speaks Chrome DevTools Protocol over the `WebSocket` that Node 22+ ships as
 * a global, so there is nothing to install and nothing to keep current. The plan named four
 * extraction tools worth trialling; the trial and its measurement are in
 * `reports/2026-08-17-visual-eval-first-run.md`, and this file is what won.
 *
 * **It does not score.** A single similarity number over these properties would be the composite
 * figure this console refuses everywhere else, and it would hide which property moved. Every row
 * carries the mock's value, the console's value, and nothing else.
 *
 * ## Usage
 *
 *   1. Serve the mock:     cd docs/console-mock && python -m http.server 8910
 *   2. Serve the console:  cd web && npm run build && SYNC_CONSOLE_PASSWORD=… node scripts/serve-console.mjs
 *      (with an API behind it — see .claude/rules/console-dev-loop.md)
 *   3. Start Chrome with a debug port, or reuse one already listening on 9222.
 *   4. node scripts/visual-eval.mjs
 *
 * Every URL and port is an environment variable so nothing here hardcodes a local accident.
 */

const CDP = process.env.EVAL_CDP ?? "http://127.0.0.1:9222"
const MOCK = process.env.EVAL_MOCK ?? "http://127.0.0.1:8910/Sync%20Console.dc.html"
const CONSOLE_URL = process.env.EVAL_CONSOLE ?? "http://127.0.0.1:4210/"
const API = process.env.EVAL_API ?? "http://127.0.0.1:8811"
const WIDTH = Number(process.env.EVAL_WIDTH ?? 1440)
const HEIGHT = Number(process.env.EVAL_HEIGHT ?? 900)

/**
 * The questions both sides are asked.
 *
 * Each is objective and each is something a reader notices. They are deliberately *not* summed:
 * the plan forbids a score, and a reader wants to know which of these moved rather than by how much
 * the whole differs.
 *
 * `main` is the frame of reference on both sides because both render one. Elements are filtered to
 * those actually laid out and carrying text, so a hidden template does not contribute a font size
 * nobody sees.
 */
const PROBE = `(() => {
  const main = document.querySelector("main") ?? document.body
  const laidOut = [...main.querySelectorAll("*")].filter(
    (el) => el.offsetParent !== null && el.textContent.trim() !== ""
  )
  const sizes = laidOut
    .map((el) => parseFloat(getComputedStyle(el).fontSize))
    .filter(Number.isFinite)
  const weights = [...new Set(laidOut.map((el) => getComputedStyle(el).fontWeight))]

  // A radius is counted once per distinct value: the question is which radii the design uses, not
  // how many elements happen to use them.
  const radii = [...new Set(
    [...main.querySelectorAll("*")]
      .map((el) => getComputedStyle(el).borderRadius)
      .filter((r) => r && r !== "0px")
  )]

  // Two children sharing a row is the "one vertical stack where it should be a grid" complaint,
  // counted rather than described.
  //
  // **sideBySide alone is not comparable between these two documents, and reporting it as though
  // it were would be measuring the wrong thing.** The mock contains zero <table> elements and 33
  // grid-template-columns: it draws every table as CSS-grid rows, so each data row counts as a
  // side-by-side placement. The built console uses semantic <table>, whose <tr> is neither grid
  // nor flex and so counts as nothing. On a screen with a fifty-row table that difference is worth
  // more than a dozen phantom "regions", and chasing it would mean abandoning table semantics --
  // worse for assistive technology -- to move a number nobody reads.
  //
  // So regionsBeside is the honest form of the owner's complaint: how many *panels* sit beside
  // another panel. A child counts as a region when it is a landmark, or carries its own heading, or
  // is drawn as a card with its own border or background. Table rows are excluded by construction,
  // because a row is not a region.
  const isRegion = (el) =>
    ["SECTION", "ARTICLE", "ASIDE", "NAV", "FORM"].includes(el.tagName) ||
    el.querySelector("h1, h2, h3") !== null ||
    (() => {
      const s = getComputedStyle(el)
      return s.borderTopWidth !== "0px" || (s.backgroundColor !== "rgba(0, 0, 0, 0)" && s.backgroundColor !== "transparent")
    })()

  const regionsBeside = [...main.querySelectorAll("*")].filter((el) => {
    const style = getComputedStyle(el)
    if (style.display !== "grid" && style.display !== "flex") return false
    if (style.display === "flex" && style.flexDirection.startsWith("column")) return false
    if (el.closest("table") !== null) return false
    const kids = [...el.children].filter((k) => k.offsetParent !== null && isRegion(k))
    if (kids.length < 2) return false
    const tops = kids.map((k) => Math.round(k.getBoundingClientRect().top))
    return new Set(tops).size < kids.length
  }).length

  const sideBySide = [...main.querySelectorAll("*")].filter((el) => {
    const style = getComputedStyle(el)
    if (style.display !== "grid" && style.display !== "flex") return false
    if (style.display === "flex" && style.flexDirection.startsWith("column")) return false
    const kids = [...el.children].filter((k) => k.offsetParent !== null)
    if (kids.length < 2) return false
    const tops = kids.map((k) => Math.round(k.getBoundingClientRect().top))
    return new Set(tops).size < kids.length
  }).length

  // Density counts what a reader reads. The mock draws some tables as divs rather than <td>, so a
  // <td> count alone would report zero for a screen dense with data — rows are counted too and the
  // larger is taken, which is the honest reading of "cells on screen".
  const cells = Math.max(
    main.querySelectorAll("td").length,
    main.querySelectorAll('[role="cell"], [role="gridcell"]').length
  )
  const prose = [...main.querySelectorAll("p")].reduce((n, p) => n + p.textContent.trim().length, 0)

  const body = getComputedStyle(document.body)
  return {
    heading: document.querySelector("h1")?.textContent.trim() ?? null,
    typeMax: sizes.length ? Math.max(...sizes) : null,
    typeMin: sizes.length ? Math.min(...sizes) : null,
    typeRange: sizes.length ? Number((Math.max(...sizes) / Math.min(...sizes)).toFixed(2)) : null,
    weights: weights.sort(),
    radii: radii.sort(),
    bodyBackground: body.backgroundColor,
    bodyColor: body.color,
    framePadding: getComputedStyle(main).paddingLeft,
    sideBySide,
    regionsBeside,
    cells,
    proseChars: prose,
  }
})()`

/**
 * Credentials for a gated console, sent as a header rather than embedded in the URL.
 *
 * `serve-console.mjs` puts HTTP Basic in front of everything including `/api`. Chrome uses
 * credentials embedded in a navigation URL for the document itself but does **not** attach them to
 * the page's own `fetch` calls, so every panel failed and the console rendered its "never reached a
 * server" state. Measuring that would have counted error prose as console prose and missing panels
 * as missing composition -- a false result in both directions, and the second time this script has
 * nearly produced one.
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

async function cdp(url) {
  const response = await fetch(`${CDP}/json/new?${encodeURIComponent(url)}`, { method: "PUT" })
  if (!response.ok) throw new Error(`could not open a tab: ${response.status}`)
  return response.json()
}

/** One CDP session, driven over the WebSocket Node ships. */
function session(wsUrl) {
  const socket = new WebSocket(wsUrl)
  const pending = new Map()
  let nextId = 1
  const ready = new Promise((resolve, reject) => {
    socket.addEventListener("open", () => resolve())
    socket.addEventListener("error", (event) => reject(new Error(String(event.message ?? event))))
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

/**
 * Wait until a page has actually rendered, and refuse to measure one that has not.
 *
 * Waiting for `main` alone is not enough: the first run of this script measured the mock mid-compile
 * and reported a heading of `{{ title }}` with every font size null, which is a false result rather
 * than a slow one. The mock templates its markup before `support.js` compiles it, so readiness means
 * a `main` exists, it carries laid-out text, and no unrendered placeholder remains in the heading.
 *
 * It throws rather than returning a partial reading, for the same reason this console distinguishes
 * absence from zero: a half-rendered measurement is worse than none.
 */
async function waitForRender(page, label, url) {
  for (let attempt = 0; attempt < 80; attempt++) {
    const probe = await page.send("Runtime.evaluate", {
      expression: `(() => {
        const main = document.querySelector("main")
        if (main === null) return false
        const heading = document.querySelector("h1")?.textContent ?? ""
        if (heading.includes("{{")) return false
        return [...main.querySelectorAll("*")].some(
          (el) => el.offsetParent !== null && el.textContent.trim() !== ""
        )
      })()`,
      returnByValue: true,
    })
    if (probe.result.value === true) return
    await new Promise((r) => setTimeout(r, 250))
  }
  throw new Error(
    `${label} never finished rendering within 20s (${url}). Refusing to measure a page that is ` +
      "still compiling: a half-rendered measurement is worse than none."
  )
}

async function measure(url, label) {
  const tab = await cdp(url)
  const page = session(tab.webSocketDebuggerUrl)
  await page.ready
  try {
    await page.send("Page.enable")
    const auth = basicAuthHeader(url)
    if (auth !== null) {
      await page.send("Network.enable")
      await page.send("Network.setExtraHTTPHeaders", { headers: { Authorization: auth } })
      // Re-navigate now the header is set, so the panels' own fetches carry it too.
      await page.send("Page.navigate", { url: withoutCredentials(url) })
    }
    await page.send("Emulation.setDeviceMetricsOverride", {
      width: WIDTH,
      height: HEIGHT,
      deviceScaleFactor: 1,
      mobile: false,
    })
    await waitForRender(page, label, url)
    const result = await page.send("Runtime.evaluate", {
      expression: PROBE,
      returnByValue: true,
      awaitPromise: true,
    })
    return { label, url, ...result.result.value }
  } finally {
    await page.send("Emulation.clearDeviceMetricsOverride").catch(() => {})
    page.close()
    await fetch(`${CDP}/json/close/${tab.id}`).catch(() => {})
  }
}

/**
 * Every mock screen, from one tab, by clicking the mock's own navigation.
 *
 * The mock is a single document rather than a set of routes, so there is no URL per screen. Its nav
 * buttons are the only way in, which also means this measures what a reader would actually see
 * rather than some internal state a URL might have skipped to.
 */
async function measureMockPages(pages) {
  const tab = await cdp(MOCK)
  const page = session(tab.webSocketDebuggerUrl)
  await page.ready
  const out = new Map()
  try {
    await page.send("Page.enable")
    await page.send("Emulation.setDeviceMetricsOverride", {
      width: WIDTH,
      height: HEIGHT,
      deviceScaleFactor: 1,
      mobile: false,
    })
    await waitForRender(page, "mock", MOCK)

    for (const entry of pages) {
      const clicked = await page.send("Runtime.evaluate", {
        expression: `(() => {
          const nav = document.querySelector("nav")
          const buttons = nav ? [...nav.querySelectorAll("button")] : []
          const target = buttons[${entry.nav}]
          if (!target) return false
          target.click()
          return true
        })()`,
        returnByValue: true,
      })
      if (clicked.result.value !== true) continue
      // The mock swaps its own content synchronously, but give the frame a beat to lay out before
      // asking for computed styles: a measurement taken mid-swap is the false result this script
      // already produced once.
      await new Promise((r) => setTimeout(r, 400))
      const result = await page.send("Runtime.evaluate", {
        expression: PROBE,
        returnByValue: true,
      })
      out.set(entry.name, result.result.value)
    }
  } finally {
    await page.send("Emulation.clearDeviceMetricsOverride").catch(() => {})
    page.close()
    await fetch(`${CDP}/json/close/${tab.id}`).catch(() => {})
  }
  return out
}

function row(name, mockValue, builtValue) {
  const same = JSON.stringify(mockValue) === JSON.stringify(builtValue)
  const show = (v) => (Array.isArray(v) ? v.join(" ") : String(v))
  return `| ${name} | ${show(mockValue)} | ${show(builtValue)} | ${same ? "same" : "DIFFERS"} |`
}

/**
 * The pages, and how each side reaches one.
 *
 * The mock is a single document that swaps screens when its own navigation is clicked, so it is
 * driven by nav index rather than by URL. The console has real routes, so it is driven by URL, with
 * the subjects read off the API — a hardcoded finding id would silently compare a not-found screen
 * against a drawn one and report the difference as a design gap.
 *
 * The pairing is by *level*, not by name: the mock still says "Fleet" where `M7-W217` renamed the
 * level to Codebases, and that difference is a finding rather than a reason to leave the row out.
 */
const PAGES = [
  { name: "fleet", nav: 0, route: () => "/" },
  { name: "codebase", nav: 1, route: (s) => s.repo && `/repositories/${encodeURIComponent(s.repo)}` },
  { name: "api-services", nav: 2, route: (s) => s.vendor && `/vendors/${encodeURIComponent(s.vendor)}` },
  { name: "signals", nav: 3, route: (s) => s.repo && `/repositories/${encodeURIComponent(s.repo)}/observed` },
  { name: "observe", nav: 4, route: () => "/detectors" },
  { name: "remediation", nav: 5, route: (s) => s.finding && `/findings/${encodeURIComponent(s.finding)}/workflow` },
  { name: "settings", nav: 6, route: () => "/settings" },
]

const KEYS = [
  "heading",
  "typeMax",
  "typeMin",
  "typeRange",
  "weights",
  "radii",
  "bodyBackground",
  "bodyColor",
  "sideBySide",
  "regionsBeside",
  "cells",
  "proseChars",
]

/** Subjects from the running API, so a reseed cannot turn this into a comparison of error screens. */
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

// One mock tab, clicked through its own navigation; the console gets a tab per route.
const mockPages = await measureMockPages(PAGES)
const builtPages = new Map()
for (const page of PAGES) {
  const route = page.route(found)
  if (!route) continue
  builtPages.set(page.name, await measure(`${CONSOLE_URL.replace(/\/$/, "")}${route}`, page.name))
}

console.log(`# Visual eval — the drawn mock against the built console, ${WIDTH}x${HEIGHT}\n`)
console.log(`mock:  ${MOCK}`)
console.log(`built: ${CONSOLE_URL}\n`)
console.log(
  "No score, by design: a single number over these properties would hide which one moved, and it is" +
    " the composite figure this console refuses everywhere else.\n"
)

for (const page of PAGES) {
  const mock = mockPages.get(page.name)
  const built = builtPages.get(page.name)
  console.log(`## ${page.name}\n`)
  if (mock === undefined || built === undefined) {
    console.log(
      `_not compared: ${mock === undefined ? "the mock screen did not render" : "no subject for this route"}._\n`
    )
    continue
  }
  console.log("| property | mock | built | |")
  console.log("|---|---|---|---|")
  for (const key of KEYS) console.log(row(key, mock[key], built[key]))
  console.log("")
}
