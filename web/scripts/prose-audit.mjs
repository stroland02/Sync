/**
 * Dump one screen's paragraphs so each can be classified as protected or discretionary.
 *
 * The prose half of the visual eval cannot be answered by a character count: `CLAUDE.md` protects
 * four distinctions and the console architecture plan's *Establish 2* reproduces twenty-four
 * sentences that may be restyled and never shortened. **Protected prose is not a gap.** Fleet looked
 * 2.7x wordier than the drawing and turned out to be five characters from parity once its protected
 * sentences were set aside, so the audit has to happen before any cut is proposed.
 *
 * It authenticates the same way `visual-eval.mjs` does, because measuring a console whose panels
 * failed counts error prose as console prose — a mistake this lane has now made twice and caught
 * twice.
 *
 *   node scripts/prose-audit.mjs "/repositories/<id>/observed"
 */

const CDP = process.env.EVAL_CDP ?? "http://127.0.0.1:9222"
const CONSOLE_URL = process.env.EVAL_CONSOLE ?? "http://127.0.0.1:4215/"
const WIDTH = Number(process.env.EVAL_WIDTH ?? 1440)
const HEIGHT = Number(process.env.EVAL_HEIGHT ?? 900)
const route = process.argv[2] ?? "/"

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

const target = `${CONSOLE_URL.replace(/\/$/, "")}${route}`
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

  // Readiness means every panel has resolved, not that the document has text. Panels fetch
  // independently, so a screen can carry laid-out prose while half of it is still a skeleton --
  // and a skeleton's "Loading..." counts as prose. `visual-eval.mjs` returned a different answer on
  // every run before this was fixed there; the same defect lived here.
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
  if (!settled) {
    throw new Error(
      "panels never settled within 30s. Refusing to audit: a loading state's text would be counted " +
        "as console prose."
    )
  }

  const result = await page.send("Runtime.evaluate", {
    expression: `(() => {
      const main = document.querySelector("main")
      const failed = (() => {
        // Structural rather than phrase-matching. Every failed panel renders ErrorState, and every
        // ErrorState with a retry renders a "Try again" control -- so the control is the marker.
        // The phrase list is kept for the states that predate the retry affordance. This is the
        // fourth failure mode of this shape: a "not found (/api/...)" panel slipped past a regex
        // listing only unreachable-style wordings, and counted 302 characters of error prose as
        // console prose on the codebase screen.
        const buttons = [...main.querySelectorAll("button")].map((b) => b.textContent.trim())
        if (buttons.includes("Try again")) return true
        return /never reached a server|did not answer|Could not reach the API|unreachable|not found [(][/]api[/]/i.test(
          main.textContent
        )
      })()
      const paragraphs = [...main.querySelectorAll("p")].map((p) => p.textContent.trim())
      return { failed, total: paragraphs.reduce((n, t) => n + t.length, 0), paragraphs }
    })()`,
    returnByValue: true,
  })

  const { failed, total, paragraphs } = result.result.value
  // A failed panel writes its own prose. Measuring that and calling it console prose is the defect
  // this script exists to avoid, so it refuses rather than reporting a number that looks fine.
  if (failed) {
    throw new Error(
      "a panel on this screen failed to load, so its error prose would be counted as console " +
        "prose. Fix the API or the credential before trusting any number from this run."
    )
  }

  console.log(`route: ${route}`)
  console.log(`paragraphs: ${paragraphs.length}, total characters: ${total}\n`)
  paragraphs.forEach((text, index) => {
    console.log(`--- [${index}] ${text.length} chars`)
    console.log(text)
  })
} finally {
  await page.send("Emulation.clearDeviceMetricsOverride").catch(() => {})
  page.close()
  await fetch(`${CDP}/json/close/${tab.id}`).catch(() => {})
}
