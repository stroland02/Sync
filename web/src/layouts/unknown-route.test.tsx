/**
 * The fallback screen renders through the same skeleton as every other.
 *
 * `UnknownRoute` was the one screen wired to `PageHeader`, and its own docstring says why: the
 * display step had to be mounted somewhere while the nine feature screens had not adopted the
 * frame yet, so it stood as the worked example. All twenty-one screens are on `ScreenFrame` as of
 * `CI-W596`, which discharges that reason -- and leaves the chassis's own screen as the last thing
 * rendering a component nothing else uses.
 */

import { QueryClient, QueryClientProvider } from "@tanstack/react-query"
import { cleanup, render, screen } from "@testing-library/react"
import { MemoryRouter } from "react-router"
import { afterEach, describe, expect, it } from "vitest"

import { UnknownRoute } from "@/layouts/unknown-route"

afterEach(cleanup)

function renderAt(path: string) {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  return render(
    <QueryClientProvider client={client}>
      <MemoryRouter initialEntries={[path]}>
        <UnknownRoute />
      </MemoryRouter>
    </QueryClientProvider>
  )
}

describe("the fallback screen", () => {
  it("renders a content band, the same as every declared screen", () => {
    const { container } = renderAt("/nowhere")

    expect(container.querySelector("[data-band='content']")).not.toBeNull()
  })

  it("still says no screen is at this address", () => {
    renderAt("/nowhere")

    expect(screen.getByText("No screen at this address.")).toBeTruthy()
  })

  it("still names the address that matched nothing", () => {
    renderAt("/repositories/r1/nowhere")

    expect(screen.getByText("/repositories/r1/nowhere")).toBeTruthy()
  })

  it("publishes a status saying why there is nothing to count", () => {
    /** A screen with nothing to count says so rather than rendering an empty band. */
    renderAt("/nowhere")

    expect(screen.getByText(/no route matched, so nothing was asked/i)).toBeTruthy()
  })

  it("does not say the same thing in the band and in the body", () => {
    // The first draft published the address in both. One fact written twice is one that
    // eventually disagrees with itself, and here it would have been the same sentence rendered
    // in two places for a reader to reconcile.
    renderAt("/nowhere")

    expect(screen.getAllByText(/nothing was asked of the API/i)).toHaveLength(1)
  })
})
