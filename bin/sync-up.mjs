#!/usr/bin/env node
/**
 * The doorbell. `npx` is not the product and cannot be.
 *
 * Sync is Python and TypeScript over Postgres. npm delivers a Node program and nothing else, so a
 * wrapper that claimed to be the product would fail in front of the person being shown it --
 * which is the one place it must not. **The container is the artifact; this is the thing you
 * type.** It checks the machine, takes the route that can work -- the container where Docker
 * answers, the user-space install where it cannot (`startRoute`) -- and hands over to the one
 * that owns the real steps.
 *
 * It deliberately does not reimplement any of that. `docker/entrypoint.sh` waits for the
 * database, applies the schema, starts the API and waits for it to answer before serving the
 * console, and it prints what it is doing. This file's whole job is to make sure the reader
 * reaches those messages rather than a Node traceback, and to say the one thing `docker compose`
 * would say badly: that Docker itself is missing.
 */

import { spawn, spawnSync } from "node:child_process"
import { createHash } from "node:crypto"
import { createWriteStream, existsSync, mkdirSync, readFileSync, renameSync, rmSync, writeFileSync } from "node:fs"
import { homedir } from "node:os"
import { Readable } from "node:stream"
import { pipeline } from "node:stream/promises"
import { uvVerdict, environmentVerdict, FETCH as UV_FETCH, REBUILD as ENV_REBUILD } from "./python-bootstrap.mjs"
import { previousRunVerdict, cacheVerdict, summarise, ADOPT, REAP, DOWNLOAD } from "./embedded-postgres.mjs"
import { dirname, join } from "node:path"
import { fileURLToPath } from "node:url"

const REPO_ROOT = join(dirname(fileURLToPath(import.meta.url)), "..")
const COMPOSE_FILE = "docker-compose.demo.yml"
const CONSOLE_URL = "http://127.0.0.1:4173"
// Outside the repository, deliberately: binaries and a cluster are once per machine, and a
// second checkout adopting them is the point of recording anything at all.
const PG_HOME = join(homedir(), ".sync-postgres")
const PG_DATA = join(PG_HOME, "data")
const PG_PORT = 5433
// The publisher's own portable binaries for the pinned version. Windows-only by design of the
// no-admin path; the archive unpacks to `pgsql/` under PG_HOME.
const PG_BINARIES_URL =
  "https://get.enterprisedb.com/postgresql/postgresql-16.4-1-windows-x64-binaries.zip"
const PG_BINARIES_SIZE_MB = 340
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
export function dockerDiagnosis(cliProbe, daemonProbe, platform = process.platform) {
  if (cliProbe.error || cliProbe.status !== 0) {
    const install = dockerInstallCommand(platform)
    return {
      ok: false,
      message:
        "Docker is required and was not found.\n\n" +
        "  Install Docker Desktop: https://docs.docker.com/get-started/get-docker/\n" +
        `  Or from this terminal:  ${install.command}\n` +
        (install.runnable
          ? "                          (--install-docker, or `npm run install-docker`, runs it for you)\n"
          : "                          (printed rather than run by --install-docker: review it first)\n") +
        "\nIt is the only prerequisite. Everything else -- Python, uv, Node, Postgres -- ships\n" +
        "inside the image and is never installed on your machine.\n\n" +
        "No admin rights? `npm run no-admin` (or --no-admin) runs everything in user space\n" +
        "instead: an embedded Postgres, a pinned Python, and the console -- no Docker at all.",
    }
  }
  if (daemonProbe.error || daemonProbe.status !== 0) {
    return {
      ok: false,
      message:
        "Docker is installed but its daemon is not answering.\n\n" +
        "  Start Docker Desktop and wait for it to report Running, then try again.\n\n" +
        "This is the ordinary case on a machine that has just booted.\n\n" +
        "If Docker Desktop cannot run here -- no admin rights closes every container runtime\n" +
        "on Windows -- `npm run no-admin` (or --no-admin) runs everything in user space\n" +
        "instead: an embedded Postgres, a pinned Python, and the console. No Docker at all.",
    }
  }
  return { ok: true }
}

/**
 * Which bring-up the plain command takes, decided rather than asked.
 *
 * Owner's ruling, 2026-08-18: everything is set from `npm start`, and the person never runs a
 * Docker chore. A serving daemon keeps the container path, because the container is the
 * artifact. An unusable Docker on a platform that has the user-space route falls through to it
 * automatically -- carrying the Docker diagnosis, so a reader who wanted the container knows
 * what to start before trying again. Only a platform with neither route left gets a refusal.
 */
export function startRoute(docker, noAdmin) {
  if (docker.ok) return { route: "docker" }
  if (noAdmin.ok) {
    return {
      route: "no-admin",
      message:
        "Docker is not usable here, so the user-space route is taken instead: an embedded\n" +
        "Postgres, a pinned Python, and the console -- no Docker at all.\n\n" +
        "If the container is what you wanted, this is what Docker said:\n\n" +
        docker.message,
    }
  }
  return { route: "stop", message: docker.message }
}

/**
 * Whether this checkout builds today's code, decided where automation cannot lose work.
 *
 * Owner's ruling, 2026-08-18: the build commands always build the most recent code, and the
 * person never wonders whether the screen is behind `main`. So a clean checkout that is only
 * behind fast-forwards on its own. The other three cases stay a person's: local changes are
 * never pulled over, a divergence is named rather than resolved, and an unreachable origin is
 * stated and stepped past, because offline is a place people run software. Every branch says
 * what it decided -- five dev servers once ran stale on this machine and nothing said so.
 */
export function updateVerdict({ fetched, behind, ahead, dirty }) {
  if (!fetched) {
    return { action: "keep", message: "Could not reach origin to check for updates. Building the code exactly as it is." }
  }
  if (behind === 0) {
    return {
      action: "keep",
      message: ahead > 0
        ? `The checkout is current with origin/main, and ${ahead} commit(s) ahead of it.`
        : "The checkout is current with origin/main.",
    }
  }
  if (dirty) {
    return {
      action: "hold",
      message:
        `The checkout is ${behind} commit(s) behind origin/main, but it carries local changes and ` +
        "nothing is pulled over somebody's work. Building as it is; `git pull` when you are ready.",
    }
  }
  if (ahead > 0) {
    return {
      action: "hold",
      message:
        `The checkout and origin/main have diverged (${ahead} ahead, ${behind} behind). ` +
        "Nothing is pulled; resolve that deliberately, then run this again.",
    }
  }
  return {
    action: "pull",
    message: `The checkout is ${behind} commit(s) behind origin/main. Fast-forwarding, so this run builds today's code.`,
  }
}

/**
 * The console's dependency tree, decided the same way as the venv and the cluster: a verdict
 * on the lockfile digest, never an mtime. Absent installs; a changed lockfile reinstalls; an
 * unknown digest on either side keeps what is there rather than churning a tree that was just
 * built -- the record catches up at the end of the run. Before this, `dev_up.py` refused on an
 * absent `web/node_modules` and named the command -- a correct refusal that was still a
 * defect in the one command, by the owner's own bar: after it, nothing is left to figure out.
 */
export function consoleDependenciesVerdict(present, lockDigest, recordedDigest) {
  if (!present) {
    return { action: "install", message: "The console dependencies are absent (web/node_modules). Installing them once." }
  }
  if (lockDigest && recordedDigest && lockDigest !== recordedDigest) {
    return { action: "install", message: "The console lockfile changed since the last install. Reinstalling to match it." }
  }
  return { action: "keep", message: "The console dependencies are already installed. Nothing was fetched." }
}

/**
 * Whether the no-admin path is built for this platform.
 *
 * Windows is where the wall is real: every container runtime — Docker Desktop, WSL2, Podman,
 * Rancher — needs the "Virtual Machine Platform" feature enabled, which is elevated, so a user
 * without admin rights has no container route at all. That is who this path exists for, and it
 * was proven by hand on exactly such a machine before it was automated. macOS and Linux have
 * user-space routes of their own and this path has never run there; offering it untested would
 * fail in front of exactly the person it claims to rescue. B191 carries building them.
 */
export function noAdminSupport(platform) {
  if (platform === "win32") return { ok: true }
  return {
    ok: false,
    message:
      "The no-admin path is built and tested on Windows only, where elevation gates every\n" +
      "container runtime. On this platform use Docker (root or rootless), or the from-source\n" +
      "path in docs/developing.md — both run in user space here. B191 tracks extending this.",
  }
}

/**
 * The case Decision 97's four verdicts do not cover: a cluster at our path with no record.
 *
 * It happens exactly one way — a person built the cluster by hand, which is how this path was
 * proven before it was automated. Running `initdb` onto that directory would destroy a working
 * database to satisfy a bookkeeping gap, so: adopt what serves (and write the record so the
 * next run knows it), start what is stopped, and only a genuinely absent directory is a first
 * run.
 */
export function unrecordedClusterVerdict({ dataDirExists, serving }) {
  if (!dataDirExists) {
    return { action: "fresh", message: "No cluster here. Creating one." }
  }
  if (serving) {
    return {
      action: "adopt",
      message:
        `A Postgres cluster this installer did not record is already serving from ${PG_DATA}. ` +
        "Using it — this run started nothing, and wrote the record so the next run knows it.",
    }
  }
  return {
    action: "start-existing",
    message:
      `A cluster exists at ${PG_DATA} and is not running. Starting it — nothing is created ` +
      "and nothing is overwritten.",
  }
}

/**
 * The settings that hold the embedded cluster to what the shipped database runs.
 *
 * Measured before this existed: a hand-built cluster inherited the machine's timezone from
 * `initdb` and full durability, so timestamptz views rendered correct instants in `-05:00` and
 * the test suite crawled on immediate fsyncs. The compose files run UTC with durability traded
 * for speed because everything in a dev database is rebuilt by a seed; the embedded cluster is
 * held to the same trade, adopted or created, or the two environments disagree about rendered
 * time and wall-clock cost while both are correct.
 */
export function parityStatements() {
  return [
    "ALTER SYSTEM SET timezone TO 'UTC'",
    "ALTER SYSTEM SET log_timezone TO 'UTC'",
    "ALTER SYSTEM SET fsync TO off",
    "ALTER SYSTEM SET synchronous_commit TO off",
    "SELECT pg_reload_conf()",
  ]
}

/**
 * The command that installs Docker on this platform, and whether the doorbell may run it.
 *
 * Measured on the first fresh-clone run anybody did: the refusal said Docker was missing and
 * left the reader to a browser, when the terminal they were already in could have said
 * `winget install`. Linux is deliberately `runnable: false` -- the convenience script is
 * remote code, and piping it into `sh` unread is a different product decision than the one
 * made here, so it is printed for the reader to run themselves. Elevation is not requested
 * either way; the OS prompts for it, which is the consent step staying with the person.
 */
export function dockerInstallCommand(platform) {
  if (platform === "win32") {
    return {
      command: "winget install -e --id Docker.DockerDesktop",
      runnable: true,
      note: "Windows asks for elevation. Start Docker Desktop once after it finishes and wait for Running.",
    }
  }
  if (platform === "darwin") {
    return {
      command: "brew install --cask docker",
      runnable: true,
      note: "Open Docker.app once after it finishes so the daemon starts.",
    }
  }
  return {
    command: "curl -fsSL https://get.docker.com | sh",
    runnable: false,
    note: "Review the script before running it, or use your distribution's own docker packages.",
  }
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
      "  npm start         (or: pnpm start)\n\n" +
      "The clone is the supported path today. A published image retires this message.",
  }
}

/**
 * What a zero-prerequisite install would do on this machine, without doing any of it.
 *
 * Decisions 97 and 98 decided both lifecycles and `CI-W445`/`CI-W446` built them; this is what
 * calls them. It reports rather than acts, which is the whole difference between `--check` and
 * `--no-admin`.
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
    // confident lines and omits what it has not done reads as a readiness report.
    //
    // This sentence said the download, the process start and the port bind were "not written
    // yet". They were written below in this same file (`--no-admin` runs them), and the caveat
    // outlived the gap it described -- so the first thing a newcomer read was that the install
    // does not exist, which would stop them before they ran it. What is still true is narrower
    // and worth keeping: this command reports, it does not install, and the path has not been
    // proven on a machine that never had this repository.
    caveat:
      "None of the above has been done here: --check reports, it does not install. Run " +
      "`npm run no-admin` (or --no-admin) to do it. The steps exist; what is still unproven is " +
      "a machine that has never had this repository, which is the run that would tell us.",
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
    // Probed, not assumed. This passed `alive: false` unconditionally, so `--check` told every
    // reader with a healthy server that their previous run "did not shut down cleanly" and a
    // fresh Postgres was needed -- alarming, wrong, and the opposite of what `--no-admin` would
    // actually do with the same record. `clusterServing` is `pg_ctl status`: it reads, starts
    // nothing, and is the same probe the install path branches on, so the two cannot disagree
    // about one machine.
    postgres: previousRunVerdict({
      record: record?.postgres ?? null,
      alive: clusterServing(),
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

// -- The no-admin action layer. Decisions 97-99 are the pure functions above and in the two
// bootstrap modules; everything below is the part they said was "not written yet": the
// download, the process start and the port bind. Windows-only — `noAdminSupport` is the gate.

const EXE = process.platform === "win32" ? ".exe" : ""

function pgBin(tool) {
  return join(PG_HOME, "pgsql", "bin", `${tool}${EXE}`)
}

function pgBinariesVersion() {
  if (!existsSync(pgBin("pg_ctl"))) return null
  const result = spawnSync(pgBin("pg_ctl"), ["--version"], { encoding: "utf-8", shell: false })
  if (result.error || result.status !== 0) return null
  const match = /([0-9]+\.[0-9]+)/.exec(result.stdout ?? "")
  return match ? match[1] : null
}

function clusterServing() {
  if (!existsSync(pgBin("pg_ctl"))) return false
  const result = spawnSync(pgBin("pg_ctl"), ["status", "-D", PG_DATA], { stdio: "ignore", shell: false })
  return !result.error && result.status === 0
}

function postmasterRecord() {
  const path = join(PG_DATA, "postmaster.pid")
  if (!existsSync(path)) return null
  const lines = readFileSync(path, "utf-8").split(/\r?\n/)
  const pid = Number(lines[0])
  const port = Number(lines[3])
  if (!Number.isInteger(pid) || pid <= 0) return null
  return { pid, port: Number.isInteger(port) && port > 0 ? port : PG_PORT }
}

/** Runs a step whose failure ends the install, naming the step rather than a stack. */
function mustRun(label, command, args, options = {}) {
  const result = spawnSync(command, args, { stdio: "inherit", shell: false, ...options })
  if (result.error || result.status !== 0) {
    process.stderr.write(`\n${label} failed${result.error ? `: ${result.error.message}` : ` (exit ${result.status})`}.\n`)
    process.exit(1)
  }
}

/**
 * The extractor, named absolutely rather than resolved from PATH. This code path is
 * Windows-only, and Windows' own `tar` (bsdtar) is the only one guaranteed to read both a
 * `C:\` archive path and the zip format: a Git Bash PATH puts GNU tar first, which parses the
 * drive letter as a remote hostname -- `tar: Cannot connect to C: resolve failed` -- and
 * cannot read zip at all. Measured on the first no-admin install run from such a shell.
 */
export function tarExecutable(systemRoot = process.env.SystemRoot, present = existsSync) {
  if (!systemRoot) return "tar"
  const system = join(systemRoot, "System32", "tar.exe")
  return present(system) ? system : "tar"
}

async function downloadPostgresBinaries() {
  mkdirSync(PG_HOME, { recursive: true })
  const archive = join(PG_HOME, "postgresql-binaries.zip")
  const response = await fetch(PG_BINARIES_URL)
  if (!response.ok || !response.body) {
    process.stderr.write(`\nThe binaries download answered ${response.status} for ${PG_BINARIES_URL}.\n`)
    process.exit(1)
  }
  await pipeline(Readable.fromWeb(response.body), createWriteStream(archive))
  // A stale `pgsql/` of another version would shadow the one just fetched; the archive itself
  // is deleted because the extracted tree is the cache, not the zip.
  rmSync(join(PG_HOME, "pgsql"), { recursive: true, force: true })
  mustRun("Extracting the Postgres binaries", tarExecutable(), ["-xf", archive, "-C", PG_HOME])
  rmSync(archive, { force: true })
}

function startCluster() {
  mustRun("Starting Postgres", pgBin("pg_ctl"), [
    "start", "-D", PG_DATA, "-l", join(PG_HOME, "postgres.log"), "-o", `-p ${PG_PORT}`, "-w",
  ])
}

/** The freshness action: fetch, measure, and fast-forward only where nothing can be lost. */
function freshenCheckout() {
  if (!existsSync(join(REPO_ROOT, ".git"))) return
  const git = (args, capture) =>
    spawnSync("git", args, {
      cwd: REPO_ROOT, shell: false, timeout: 30000,
      ...(capture ? { encoding: "utf-8" } : { stdio: "ignore" }),
    })
  const fetch = git(["fetch", "origin", "main"])
  const counts = git(["rev-list", "--left-right", "--count", "HEAD...origin/main"], true)
  const fetched = !fetch.error && fetch.status === 0 && !counts.error && counts.status === 0
  let ahead = 0
  let behind = 0
  const m = /(\d+)\s+(\d+)/.exec(counts.stdout ?? "")
  if (fetched && m) [ahead, behind] = [Number(m[1]), Number(m[2])]
  const status = git(["status", "--porcelain"], true)
  const dirty = Boolean((status.stdout ?? "").trim())
  const verdict = updateVerdict({ fetched, behind, ahead, dirty })
  process.stdout.write(`${verdict.message}\n`)
  if (verdict.action === "pull") {
    mustRun("Fast-forwarding to origin/main", "git", ["merge", "--ff-only", "origin/main"], { cwd: REPO_ROOT })
  }
}

function webLockDigest() {
  const lock = join(REPO_ROOT, "web", "package-lock.json")
  return existsSync(lock) ? createHash("sha256").update(readFileSync(lock)).digest("hex") : null
}

function writeInstallRecord(lockDigest, webDigest) {
  const postmaster = postmasterRecord()
  const record = {
    lockDigest,
    webLockDigest: webDigest,
    postgres: postmaster
      ? { pid: postmaster.pid, port: postmaster.port, version: pgBinariesVersion() ?? WANTED_POSTGRES }
      : null,
  }
  writeFileSync(join(REPO_ROOT, INSTALL_RECORD), JSON.stringify(record, null, 2) + "\n", "utf-8")
}

async function runNoAdmin() {
  const support = noAdminSupport(process.platform)
  if (!support.ok) {
    process.stderr.write(`\n${support.message}\n\n`)
    process.exit(1)
  }

  // uv. Fetch-if-absent is not built, and printing the verdict's "Fetching it" without
  // fetching would be the overstatement these modules forbid -- so absence gets directions
  // instead of the verdict, and B191 carries building the fetch.
  const uv = uvVerdict({ foundVersion: uvProbe(), minimumVersion: MINIMUM_UV })
  if (uv.action === UV_FETCH) {
    process.stderr.write(
      "\nuv is required and was not found (or is too old). Install it in user space, no admin:\n\n" +
        '  powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"\n\n' +
        "then run this again.\n\n",
    )
    process.exit(1)
  }
  process.stdout.write(`\n${uv.message}\n`)

  // The Python environment, decided on the lockfile digest and never an mtime.
  const previous = installRecord()
  const environment = environmentVerdict(environmentProbe(previous))
  process.stdout.write(`${environment.message}\n`)
  if (environment.action === ENV_REBUILD) {
    mustRun("Installing the Python environment", "uv", ["sync"], { cwd: REPO_ROOT })
  }
  const lock = join(REPO_ROOT, "uv.lock")
  const lockDigest = existsSync(lock)
    ? createHash("sha256").update(readFileSync(lock)).digest("hex")
    : null

  // The binaries, then the cluster.
  const cache = cacheVerdict({
    cachedVersion: pgBinariesVersion(),
    wantedVersion: WANTED_POSTGRES,
    sizeMb: PG_BINARIES_SIZE_MB,
  })
  process.stdout.write(`${cache.message}\n`)
  if (cache.action === DOWNLOAD) await downloadPostgresBinaries()

  let cluster
  let freshDatabase = false
  const recorded = previous?.postgres ?? null
  if (recorded) {
    cluster = previousRunVerdict({ record: recorded, alive: clusterServing(), wantedVersion: WANTED_POSTGRES })
    process.stdout.write(`${cluster.message}\n`)
    if (cluster.action === REAP) {
      mustRun("Stopping the other-version Postgres", pgBin("pg_ctl"), ["stop", "-D", PG_DATA, "-m", "fast", "-w"])
      // Its data belongs to the version being replaced; kept beside the new cluster rather
      // than deleted, because a stopped database is somebody's data until they say otherwise.
      renameSync(PG_DATA, `${PG_DATA}.pg${recorded.version}.bak`)
    }
    if (cluster.action === REAP || (cluster.action !== ADOPT && !existsSync(PG_DATA))) {
      freshDatabase = true
    }
  } else {
    cluster = unrecordedClusterVerdict({ dataDirExists: existsSync(PG_DATA), serving: clusterServing() })
    process.stdout.write(`${cluster.message}\n`)
    if (cluster.action === "fresh") freshDatabase = true
    if (cluster.action === "start-existing") startCluster()
  }

  if (freshDatabase) {
    mustRun("Creating the database cluster", pgBin("initdb"), ["-D", PG_DATA, "-U", "sync", "-A", "trust", "-E", "UTF8"])
    startCluster()
    mustRun("Creating the sync database", pgBin("createdb"), ["-p", String(PG_PORT), "-U", "sync", "sync"])
    process.stdout.write("Seeding the schema and a fixture to look at.\n")
    mustRun("Seeding the console", "uv", ["run", "python", "scripts/seed_console.py"], { cwd: REPO_ROOT })
  } else {
    process.stdout.write("The existing database rows are kept exactly as they are. Nothing was seeded.\n")
    // The rows are the adopter's; the schema is the code's. A checkout that just pulled
    // today's main can adopt a database created before today's tables existed, and the first
    // fresh clone after run_heartbeat landed proved it: every precondition green except the
    // schema. Converged here the same way the settings are -- idempotently, rows untouched.
    mustRun("Holding the database to the shipped schema", "uv", ["run", "python", "scripts/apply_schema.py"], { cwd: REPO_ROOT })
  }

  // Settings, not data: rows are never touched here. Idempotent by construction, so an
  // adopted cluster pays a no-op and a drifted one is brought back without a restart.
  process.stdout.write("Holding the cluster to the shipped database settings: UTC, durability traded for speed.\n")
  for (const statement of parityStatements()) {
    mustRun("Applying database settings", pgBin("psql"), [
      "-p", String(PG_PORT), "-U", "sync", "-d", "sync", "-v", "ON_ERROR_STOP=1", "-q", "-c", statement,
    ])
  }

  const web = consoleDependenciesVerdict(
    existsSync(join(REPO_ROOT, "web", "node_modules")),
    webLockDigest(),
    previous?.webLockDigest ?? null,
  )
  process.stdout.write(`${web.message}\n`)
  if (web.action === "install") {
    // On Windows npm is npm.cmd, which Node will not spawn without a shell (CVE-2024-27980),
    // and a shell spawn with an args array prints DEP0190 into the middle of the first-run
    // output -- so the command goes as one string there, and as a plain binary elsewhere.
    if (process.platform === "win32") {
      mustRun("Installing the console dependencies", "npm install --prefix web", [], { cwd: REPO_ROOT, shell: true })
    } else {
      mustRun("Installing the console dependencies", "npm", ["install", "--prefix", "web"], { cwd: REPO_ROOT })
    }
  }
  // After the install, deliberately: a record claiming the new lockfile before the install
  // succeeded would tell the next run there is nothing to do.
  writeInstallRecord(lockDigest, webLockDigest())

  process.stdout.write(`\nIn short: ${summarise({ postgres: cluster, cache })}.\n`)
  process.stdout.write("Handing over to the dev bring-up, which starts the API and the console.\n\n")
  const child = spawn("uv", ["run", "python", "scripts/dev_up.py"], { cwd: REPO_ROOT, stdio: "inherit", shell: false })
  child.on("exit", (code, signal) => process.exit(signal ? 1 : (code ?? 1)))
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

  if (process.argv.includes("--no-admin")) {
    freshenCheckout()
    runNoAdmin().catch((error) => {
      process.stderr.write(`\nThe no-admin install stopped: ${error.message}\n`)
      process.exit(1)
    })
    return
  }

  if (process.argv.includes("--install-docker")) {
    const install = dockerInstallCommand(process.platform)
    if (!install.runnable) {
      process.stdout.write(`\nRun this yourself, after reading it:\n\n  ${install.command}\n\n${install.note}\n\n`)
      return
    }
    process.stdout.write(`\nRunning: ${install.command}\n${install.note}\n\n`)
    const [installer, ...installerArgs] = install.command.split(" ")
    const installChild = spawn(installer, installerArgs, { stdio: "inherit", shell: false })
    installChild.on("error", () => {
      process.stderr.write(`\n${installer} is not available here. Install Docker Desktop instead:\nhttps://docs.docker.com/get-started/get-docker/\n\n`)
      process.exit(1)
    })
    installChild.on("exit", (code, signal) => process.exit(signal ? 1 : (code ?? 1)))
    return
  }

  const source = sourceTreeDiagnosis(existsSync(join(REPO_ROOT, "pyproject.toml")))
  if (!source.ok) {
    process.stderr.write(`\n${source.message}\n\n`)
    process.exit(1)
  }

  if (!process.argv.includes("down")) freshenCheckout()

  const diagnosis = dockerDiagnosis(probe(["compose", "version"]), probe(["info"]))
  const route = startRoute(diagnosis, noAdminSupport(process.platform))
  if (route.route === "stop") {
    process.stderr.write(`\n${route.message}\n\n`)
    process.exit(1)
  }

  const down = process.argv.includes("down")

  if (route.route === "no-admin") {
    if (down) {
      if (clusterServing()) {
        mustRun("Stopping the embedded Postgres", pgBin("pg_ctl"), ["stop", "-D", PG_DATA, "-m", "fast", "-w"])
        process.stdout.write("\nThe embedded Postgres is stopped. Its data stays; the next start adopts it.\n")
      } else {
        process.stdout.write("\nNothing is serving on the user-space route. There is nothing to bring down.\n")
      }
      return
    }
    process.stdout.write(`\n${route.message}\n`)
    runNoAdmin().catch((error) => {
      process.stderr.write(`\nThe no-admin install stopped: ${error.message}\n`)
      process.exit(1)
    })
    return
  }
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
