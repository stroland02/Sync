#!/usr/bin/env node
/**
 * The doorbell. `npx` is not the product and cannot be.
 *
 * Sync is Python and TypeScript over Postgres. npm delivers a Node program and nothing else, so a
 * wrapper that claimed to install a Python runtime and a database would fail in front of the
 * person being shown it -- which is the one place it must not. **The container is the artifact;
 * this is the thing you type.** All it does is check the single prerequisite, then hand over to
 * `docker compose`, which is where every real step lives.
 *
 * It deliberately does not reimplement any of that. `docker/entrypoint.sh` waits for the
 * database, applies the schema, starts the API and waits for it to answer before serving the
 * console, and it prints what it is doing. This file's whole job is to make sure the reader
 * reaches those messages rather than a Node traceback, and to say the one thing `docker compose`
 * would say badly: that Docker itself is missing.
 */

import { spawn, spawnSync } from "node:child_process"
import { createHash } from "node:crypto"
import { existsSync, readFileSync } from "node:fs"
import { uvVerdict, environmentVerdict } from "./python-bootstrap.mjs"
import { previousRunVerdict, cacheVerdict } from "./embedded-postgres.mjs"
import { dirname, join } from "node:path"
import { fileURLToPath } from "node:url"

const REPO_ROOT = join(dirname(fileURLToPath(import.meta.url)), "..")
const COMPOSE_FILE = "docker-compose.demo.yml"
const CONSOLE_URL = "http://127.0.0.1:4173"
// Written by the installer once it exists. Absent means no zero-prerequisite install has run
// here, which is a different fact from one that ran and left nothing behind.
const INSTALL_RECORD = ".sync-install.json"
const WANTED_PYTHON = "3.12"
const WANTED_POSTGRES = "16.4"
const MINIMUM_UV = "0.5.0"

/**
 * Whether `docker compose` is usable, and if not, which half is wrong.
 *
 * Three failures read identically to a newcomer and want different answers: Docker is not
 * installed, Docker is installed but its daemon is not running, and Docker is old enough that
 * `compose` is still a separate `docker-compose` binary. `docker compose version` separates them
 * because it needs the CLI, the plugin, and nothing else -- it does not touch the daemon, so a
 * stopped daemon is diagnosed by the next check rather than confused with a missing install.
 */
export function dockerDiagnosis(cliProbe, daemonProbe) {
  if (cliProbe.error || cliProbe.status !== 0) {
    return {
      ok: false,
      message:
        "Docker is required and was not found.\n\n" +
        "  Install Docker Desktop: https://docs.docker.com/get-started/get-docker/\n\n" +
        "It is the only prerequisite. Everything else -- Python, uv, Node, Postgres -- ships\n" +
        "inside the image and is never installed on your machine.",
    }
  }
  if (daemonProbe.error || daemonProbe.status !== 0) {
    return {
      ok: false,
      message:
        "Docker is installed but its daemon is not answering.\n\n" +
        "  Start Docker Desktop and wait for it to report Running, then try again.\n\n" +
        "This is the ordinary case on a machine that has just booted.",
    }
  }
  return { ok: true }
}

/**
 * Whether the tree Docker would build from is actually here.
 *
 * The published tarball carries this script, the compose file and the Dockerfile -- and not the
 * source tree the compose file's `build:` needs, so a registry install used to die mid-build on
 * a missing `src/` with a traceback in front of exactly the person this file exists to protect.
 * Refused up front instead, until a prebuilt image exists to pull (B190 is what retires this).
 */
export function sourceTreeDiagnosis(sourceTreePresent) {
  if (sourceTreePresent) return { ok: true }
  return {
    ok: false,
    message:
      "This package delivers the launcher, not the product: the image is built from a clone of\n" +
      "the repository, and no prebuilt image is published yet.\n\n" +
      "  git clone https://github.com/stroland02/Sync\n" +
      "  cd Sync\n" +
      "  npm run up        (or: pnpm up)\n\n" +
      "The clone is the supported path today. A published image retires this message.",
  }
}

/**
 * What a zero-prerequisite install would do on this machine, without doing any of it.
 *
 * Decisions 97 and 98 decided both lifecycles and `CI-W445`/`CI-W446` built them; this is what
 * calls them. It is also the only honest thing that can be built before the download and the
 * process spawn exist: the decisions are real and testable now, the actions are not.
 *
 * **Every action is reported as something it WOULD do.** The verdict messages are written in
 * the voice of an install that is running -- *Fetching it*, *Reusing the environment* -- so
 * they are printed under a heading that says so rather than reworded here. Rewording would put
 * the same sentence in two files, and the copy that drifts is always the one further from the
 * decision.
 *
 * Decision 99 keeps the `docker compose` path supported while the replacement is unproven, so
 * Docker is reported as a fact about this machine rather than as a failure.
 */
export function preflight({ docker, uv, environment, postgres }) {
  const supported = docker.ok
    ? "Docker is usable, so the supported install path works on this machine today."
    : `Docker is not usable here: ${docker.message.split("\n")[0]}`

  return {
    supported,
    heading: "A zero-prerequisite install would:",
    actions: [uv.message, environment.message, postgres.message],
    // Stated every time rather than only when something is missing. A check that lists four
    // confident lines and omits what is unbuilt reads as a readiness report.
    caveat:
      "None of the above has been done: the download, the process start and the port bind are " +
      "not written yet, and nothing here has been run on a machine that never had this " +
      "repository. This says what the decisions are, not that the install works.",
  }
}

function probe(args) {
  return spawnSync("docker", args, { stdio: "ignore", shell: false })
}

function installRecord() {
  const path = join(REPO_ROOT, INSTALL_RECORD)
  if (!existsSync(path)) return null
  try {
    return JSON.parse(readFileSync(path, "utf-8"))
  } catch {
    // A record we cannot read is not a record. Treating a corrupt one as absent is right:
    // the install can rebuild, and pretending to know what it said would be worse.
    return null
  }
}

function uvProbe() {
  const result = spawnSync("uv", ["--version"], { encoding: "utf-8", shell: false })
  if (result.error || result.status !== 0) return null
  const match = /([0-9]+\.[0-9]+(?:\.[0-9]+)?)/.exec(result.stdout ?? "")
  return match ? match[1] : null
}

function environmentProbe(record) {
  const venv = join(REPO_ROOT, ".venv")
  const lock = join(REPO_ROOT, "uv.lock")
  const lockDigest = existsSync(lock)
    ? createHash("sha256").update(readFileSync(lock)).digest("hex")
    : null
  let pythonVersion = null
  const cfg = join(venv, "pyvenv.cfg")
  if (existsSync(cfg)) {
    // `version_info = 3.12.10`, and the pin is on the minor: uv writes the patch it happened
    // to fetch, and rebuilding an environment because a patch moved would be noise.
    const found = /version_info\s*=\s*([0-9]+\.[0-9]+)/.exec(readFileSync(cfg, "utf-8"))
    pythonVersion = found ? found[1] : null
  }
  return {
    exists: existsSync(venv),
    lockDigest,
    recordedDigest: record?.lockDigest ?? null,
    pythonVersion,
    wantedPython: WANTED_PYTHON,
  }
}

function runCheck() {
  const record = installRecord()
  const docker = dockerDiagnosis(probe(["compose", "version"]), probe(["info"]))
  const report = preflight({
    docker,
    uv: uvVerdict({ foundVersion: uvProbe(), minimumVersion: MINIMUM_UV }),
    environment: environmentVerdict(environmentProbe(record)),
    postgres: previousRunVerdict({
      record: record?.postgres ?? null,
      alive: false,
      wantedVersion: WANTED_POSTGRES,
    }),
  })

  process.stdout.write(
    `
${report.supported}

${report.heading}
` +
      report.actions.map((line) => `  - ${line}
`).join("") +
      `
${report.caveat}

`,
  )
}

function main() {
  if (!existsSync(join(REPO_ROOT, COMPOSE_FILE))) {
    process.stderr.write(
      `Cannot find ${COMPOSE_FILE} next to this script.\n` +
        "Run this from a clone of the repository rather than in isolation.\n",
    )
    process.exit(1)
  }

  // Before the Docker exit, not after: `--check` exists to tell a stranger what their machine
  // still lacks, and a machine lacking Docker is its primary audience. Gating it behind a working
  // Docker made it unrunnable exactly where it mattered -- found on such a machine, not theorised.
  if (process.argv.includes("--check")) {
    runCheck()
    return
  }

  const source = sourceTreeDiagnosis(existsSync(join(REPO_ROOT, "pyproject.toml")))
  if (!source.ok) {
    process.stderr.write(`\n${source.message}\n\n`)
    process.exit(1)
  }

  const diagnosis = dockerDiagnosis(probe(["compose", "version"]), probe(["info"]))
  if (!diagnosis.ok) {
    process.stderr.write(`\n${diagnosis.message}\n\n`)
    process.exit(1)
  }

  const down = process.argv.includes("down")
  const args = down
    ? ["compose", "-f", COMPOSE_FILE, "down", "-v"]
    : ["compose", "-f", COMPOSE_FILE, "up", "--build"]

  if (!down) {
    process.stdout.write(
      `\nStarting Sync. The first build takes a few minutes; after that it is seconds.\n` +
        `When it is up, open ${CONSOLE_URL} and use the password printed below.\n\n`,
    )
  }

  // Inherited stdio rather than captured: the entrypoint's messages are the user interface here,
  // and buffering them until the end would turn a live bring-up into a silent wait.
  const child = spawn("docker", args, { cwd: REPO_ROOT, stdio: "inherit", shell: false })
  child.on("exit", (code, signal) => process.exit(signal ? 1 : (code ?? 1)))
}

// Importable for the tests without running: the diagnosis above is the part worth pinning, and a
// module that started containers on import could not be tested at all.
if (process.argv[1] && process.argv[1].endsWith("sync-up.mjs")) {
  main()
}
