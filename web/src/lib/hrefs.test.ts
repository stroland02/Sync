/**
 * Every path builder produces a path the route registry actually serves.
 *
 * **This is the test that did not exist when `M14-W386` scoped every route under
 * `/repositories/:repoId/`.** Nineteen call sites went on building the old unscoped paths, the
 * compiler had nothing to say because a `to` is a string, and 771 console tests stayed green. The
 * defect was only visible by clicking.
 *
 * So each builder is checked against `ROUTES` itself with react-router's own matcher, rather than
 * against a path spelled out here. A literal expectation would be a second copy of the route table
 * and would drift the same way the call sites did -- the assertion has to fail when a route moves,
 * which means it has to read the route.
 *
 * Scope is `.claude/rules/console-dev-loop.md`'s: a structural invariant, no class names, no
 * snapshot.
 */

import { matchPath } from "react-router"
import { describe, expect, it } from "vitest"

import {
  bindingSurfaceHref,
  detectorsHref,
  findingHref,
  graphHref,
  overviewHref,
  pullRequestHref,
  runsHref,
  servicesHref,
  signalsHref,
  vendorHref,
  vendorsHref,
  workflowHref,
} from "@/lib/hrefs"
import { ROUTES } from "@/lib/routes"

const REPO = "org/one"
const VENDOR = "stripe"
const OPERATION = "GetCharge"
const FINDING = "f-91ac"

/** The declared route whose pattern this path matches, or `null` if the console serves none. */
function servedBy(href: string): string | null {
  const path = href.split("?")[0]
  for (const route of ROUTES) {
    if (matchPath(route.path, path) !== null) return route.path
  }
  return null
}

describe("every builder lands on a declared route", () => {
  const cases: ReadonlyArray<readonly [string, string]> = [
    ["overview", overviewHref(REPO)],
    ["graph", graphHref(REPO)],
    ["runs", runsHref(REPO)],
    ["services", servicesHref(REPO)],
    ["vendors", vendorsHref(REPO)],
    ["signals", signalsHref(REPO)],
    ["detectors", detectorsHref(REPO)],
    ["vendor", vendorHref(REPO, VENDOR)],
    ["binding surface", bindingSurfaceHref(REPO, VENDOR, OPERATION)],
    ["finding", findingHref(REPO, FINDING)],
    ["workflow", workflowHref(REPO, FINDING)],
    ["pull request", pullRequestHref(REPO, FINDING)],
  ]

  for (const [name, href] of cases) {
    it(`serves the ${name} path`, () => {
      expect(servedBy(href)).not.toBeNull()
    })
  }

  it("covers every declared route, so a new route cannot arrive without a builder", () => {
    // The gap this closes is the one that produced the defect: a route existed, nothing built a
    // path to it through the registry, and every caller hand-rolled a string instead. If a route
    // is added and no builder reaches it, that route's callers will hand-roll too.
    const served = new Set(cases.map(([, href]) => servedBy(href)))
    const unreachable = ROUTES.filter((route) => !served.has(route.path)).map((r) => r.path)
    expect(unreachable).toEqual([])
  })
})

describe("what the builders escape", () => {
  it("escapes a repository id containing a slash, because every real one does", () => {
    // `org/one` is the shape of every repository id in this product, and an unescaped slash makes
    // the path match a different route or none at all.
    expect(overviewHref("org/one")).toBe("/repositories/org%2Fone")
  })

  it("escapes a finding id and an operation id", () => {
    expect(findingHref("org/one", "f/91")).toContain("f%2F91")
    expect(bindingSurfaceHref("org/one", "v/1", "op/2")).toContain("op%2F2")
  })

  it("carries no repo_id query parameter, because the path now says the scope", () => {
    // The old unscoped paths passed scope as `?repo_id=`. The path itself is the scope now, and a
    // surviving query parameter would be a second statement of it -- free to disagree with the
    // path it sits on, which is the failure `CLAUDE.md` names as the most expensive kind.
    for (const [, href] of [
      ["vendor", vendorHref(REPO, VENDOR)],
      ["detectors", detectorsHref(REPO)],
      ["binding surface", bindingSurfaceHref(REPO, VENDOR, OPERATION)],
    ] as const) {
      expect(href).not.toContain("repo_id=")
    }
  })
})
