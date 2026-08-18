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
import { existsSync } from "node:fs"
import { dirname, join } from "node:path"
import { fileURLToPath } from "node:url"

const REPO_ROOT = join(dirname(fileURLToPath(import.meta.url)), "..")
const COMPOSE_FILE = "docker-compose.demo.yml"
const CONSOLE_URL = "http://127.0.0.1:4173"

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

function probe(args) {
  return spawnSync("docker", args, { stdio: "ignore", shell: false })
}

function main() {
  if (!existsSync(join(REPO_ROOT, COMPOSE_FILE))) {
    process.stderr.write(
      `Cannot find ${COMPOSE_FILE} next to this script.\n` +
        "Run this from a clone of the repository rather than in isolation.\n",
    )
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
