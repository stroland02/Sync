/**
 * Dashboard 9's frame — test suite for what the chart says around itself.
 *
 * The bars are not asserted here; `adapter-coverage-option.test.ts` covers what is counted. What
 * this file holds is the prose, because the sentences under the chart are the difference between
 * a count a reader can use and a count a reader will guess a denominator for.
 */

import { cleanup, render, screen } from "@testing-library/react"
import { afterEach, describe, expect, it } from "vitest"

import type { AdapterRow } from "@/api/types"
import { AdapterCoverageChart } from "@/features/settings/adapter-coverage-chart"

afterEach(cleanup)

const row = (vendor_id: string, kind: AdapterRow["kind"]): AdapterRow => ({
  vendor_id,
  kind,
  source: null,
  changes: null,
  operations: null,
  last_change_at: null,
  sources: null,
})

describe("AdapterCoverageChart", () => {
  it("says a tier showing nought was counted, not skipped", () => {
    render(<AdapterCoverageChart adapters={[row("stripe", "coded")]} />)

    expect(screen.getByText(/counted and found empty/)).toBeTruthy()
  })

  it("states the denominator rather than leaving a reader to supply one", () => {
    render(<AdapterCoverageChart adapters={[row("stripe", "coded"), row("gone", "unregistered")]} />)

    expect(screen.getByText(/1 of 2 rows in the inventory/)).toBeTruthy()
  })

  it("names unregistered rows as excluded, and says why", () => {
    render(<AdapterCoverageChart adapters={[row("stripe", "coded"), row("gone", "unregistered")]} />)

    expect(screen.getByText(/absence of coverage rather than a kind of it/)).toBeTruthy()
  })

  it("says nothing about unregistered rows when there are none", () => {
    render(<AdapterCoverageChart adapters={[row("stripe", "coded")]} />)

    expect(screen.queryByText(/unregistered/)).toBeNull()
  })

  /** An empty inventory is a read that found nothing, which is not a read that never happened. */
  it("distinguishes an empty inventory from an unread one", () => {
    render(<AdapterCoverageChart adapters={[]} />)

    expect(screen.getByText(/read that found nothing, not a read that did not happen/)).toBeTruthy()
  })

  it("gives the chart an accessible name saying what it counts", () => {
    render(<AdapterCoverageChart adapters={[row("stripe", "coded")]} />)

    expect(
      screen.getByRole("img", { name: "Number of vendors served, by adapter tier" }),
    ).toBeTruthy()
  })
})
