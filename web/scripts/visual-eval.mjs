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
    cells,
    proseChars: prose,
  }
})()`

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

async function measure(url, label) {
  const tab = await cdp(url)
  const page = session(tab.webSocketDebuggerUrl)
  await page.ready
  try {
    await page.send("Page.enable")
    await page.send("Emulation.setDeviceMetricsOverride", {
      width: WIDTH,
      height: HEIGHT,
      deviceScaleFactor: 1,
      mobile: false,
    })
    // Both sides need longer than a load event, and waiting for `main` alone is not enough — the
    // first run of this script measured the mock mid-compile and reported a heading of `{{ title }}`
    // with every font size null, which is a false result rather than a slow one. The mock templates
    // its own markup before `support.js` compiles it, so readiness is: a `main` exists, it has laid
    // out text with real font sizes, and no unrendered `{{ … }}` placeholder remains in the heading.
    let ready = false
    for (let attempt = 0; attempt < 80; attempt++) {
      const probe = await page.send("Runtime.evaluate", {
        expression: `(() => {
          const main = document.querySelector("main")
          if (main === null) return false
          const heading = document.querySelector("h1")?.textContent ?? ""
          if (heading.includes("{{")) return false
          const sized = [...main.querySelectorAll("*")].some(
            (el) => el.offsetParent !== null && el.textContent.trim() !== ""
          )
          return sized
        })()`,
        returnByValue: true,
      })
      if (probe.result.value === true) {
        ready = true
        break
      }
      await new Promise((r) => setTimeout(r, 250))
    }
    if (!ready) {
      throw new Error(
        `${label} never finished rendering within 20s (${url}). Refusing to measure a page that ` +
          "is still compiling: a half-rendered measurement is worse than none."
      )
    }
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

function row(name, mockValue, builtValue) {
  const same = JSON.stringify(mockValue) === JSON.stringify(builtValue)
  const show = (v) => (Array.isArray(v) ? v.join(" ") : String(v))
  return `| ${name} | ${show(mockValue)} | ${show(builtValue)} | ${same ? "same" : "DIFFERS"} |`
}

const mock = await measure(MOCK, "mock")
const built = await measure(CONSOLE_URL, "built")

console.log(`# Visual eval — mock against built, ${WIDTH}x${HEIGHT}\n`)
console.log(`mock:  ${MOCK}`)
console.log(`built: ${CONSOLE_URL}\n`)
console.log("| property | mock | built | |")
console.log("|---|---|---|---|")
for (const key of [
  "heading",
  "typeMax",
  "typeMin",
  "typeRange",
  "weights",
  "radii",
  "bodyBackground",
  "bodyColor",
  "framePadding",
  "sideBySide",
  "cells",
  "proseChars",
]) {
  console.log(row(key, mock[key], built[key]))
}
console.log(
  "\nNo score, by design: a single number over these would hide which property moved, and it is the" +
    " composite figure this console refuses everywhere else."
)
