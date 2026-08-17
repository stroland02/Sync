/**
 * Cmd/Ctrl-K over the route registry.
 *
 * Scope is routes only. Finding a specific finding id or a file path is a different problem
 * — it needs a search route in the view model and a relevance rule that can be wrong, which
 * is a slice of its own, not a widening of this one. This palette answers "where is the
 * screen that does X", not "where is entity X".
 *
 * Reads `ROUTES` — the same array the router and `AppFrame` read — so a route removed from the
 * registry disappears from here in the same edit, not as a follow-up.
 *
 * A route whose `params` is non-empty needs a subject this palette cannot supply — a vendor
 * id, a repository id, a finding id. **It is listed anyway, as a place to look one up.** This
 * file used to filter those seven of nine routes out, which reads as honesty and is not: an
 * operator who opens the console's own list of destinations and finds two of them learns that
 * the console has two screens. Dropping the row hides a destination and linking it produces
 * `/findings//workflow`; the row that names where to pick a subject is the only answer that is
 * neither, and it is the rule the mock's footer states. `AppFrame`'s sidebar already made this
 * call, and shows `reachedFrom` beside the destination for the same reason.
 *
 * Each row carries its route pattern, so the list doubles as the map of what exists. Wiring the
 * palette to accept a subject and jump straight to a named vendor is a real feature and a later
 * slice; until it exists, `reachedFrom` is what a reader can act on.
 *
 * **The open state lives here rather than in the chassis, and the trigger reads it through a
 * context.** The palette was a keybind with nothing on screen naming it — an affordance nobody can
 * discover, which the fidelity report measured as the only piece of Studio's right-hand furniture
 * that transfers honestly. The trigger sits in the top bar, several elements away from the dialog,
 * so one of the two had to own the state and the owner is the component that also owns the keybind:
 * two sources for one boolean is how a trigger and a shortcut end up disagreeing.
 */

import { createContext, useContext, useEffect, useState, type ReactNode } from "react"
import { useNavigate } from "react-router"

import {
  Command,
  CommandDialog,
  CommandEmpty,
  CommandGroup,
  CommandInput,
  CommandItem,
  CommandList,
} from "@/components/ui/command"
import {
  DESTINATIONS,
  GRAPH_LEVELS,
  ROUTES,
  type DestinationEntry,
  type GraphLevel,
  type RouteEntry,
} from "@/lib/routes"

/** What the palette calls itself, in one place: the dialog's placeholder and the trigger agree. */
const PALETTE_LABEL = "Jump to a destination"

export interface PaletteRow {
  path: string
  /** The registry's path, shown to the reader. Equal to `path`; named for what it is on screen. */
  pattern: string
  label: string
  question: string
  /**
   * `null` on a destination this palette can navigate to. Otherwise the operator's words for
   * where a subject is picked — the row is listed and cannot be followed.
   */
  lookUpFrom: string | null
}

export interface PaletteGroup {
  /** A graph level, or the heading a destination that is not a level is grouped under. */
  level: GraphLevel | typeof DESTINATIONS_HEADING
  rows: readonly PaletteRow[]
}

/**
 * Where a destination that is not a level is listed.
 *
 * Its own group rather than folded into one of the nine. `.claude/rules/console-hierarchy.md`
 * is explicit that a screen may exist without being a level, and a palette that filed Settings
 * under `Fleet` would be the console asserting a place on the ladder that the specification does
 * not give it.
 */
export const DESTINATIONS_HEADING = "Deployment" as const

/**
 * The registry, grouped for the list.
 *
 * Pure over its arguments so the rule it encodes is testable as a derivation rather than by
 * driving a dialog — `.claude/rules/console-dev-loop.md` bounds the frontend suite to exactly
 * that. A level with no route under it is dropped, so an unbuilt level costs nothing here.
 */
export function paletteGroups(
  routes: readonly RouteEntry[],
  levels: readonly GraphLevel[]
): readonly PaletteGroup[] {
  return levels
    .map((level) => ({
      level,
      rows: routes
        .filter((route) => route.level === level)
        .map((route) => ({
          path: route.path,
          pattern: route.path,
          label: route.label,
          question: route.question,
          lookUpFrom: route.params.length === 0 ? null : route.reachedFrom,
        })),
    }))
    .filter((group) => group.rows.length > 0)
}

/** `paletteGroups`, plus the destinations that are not levels, as a group of their own. */
export function paletteSections(
  routes: readonly RouteEntry[],
  levels: readonly GraphLevel[],
  destinations: readonly DestinationEntry[]
): readonly PaletteGroup[] {
  const groups = paletteGroups(routes, levels)
  if (destinations.length === 0) return groups
  return [
    ...groups,
    {
      level: DESTINATIONS_HEADING,
      rows: destinations.map((destination) => ({
        path: destination.path,
        pattern: destination.path,
        label: destination.label,
        question: destination.question,
        lookUpFrom: null,
      })),
    },
  ]
}

const OpenPalette = createContext<(() => void) | null>(null)

/**
 * The keybind hint the trigger prints.
 *
 * The palette answers either modifier, so the hint is about the keyboard in front of the reader
 * rather than about the handler. A hint naming the wrong key is worse than no hint: it is a fact
 * about the console, stated wrongly, on every screen.
 */
export function shortcutHint(userAgent: string): string {
  return /Mac|iPhone|iPad/.test(userAgent) ? "⌘ K" : "Ctrl K"
}

/**
 * The on-screen way in.
 *
 * Deliberately the only thing on the right of the bar. We have no account, no organisation, no
 * assistant and no feedback channel, and rendering furniture for them would be chrome with nothing
 * behind it — the gap report's ruling, kept.
 */
export function CommandPaletteTrigger() {
  const open = useContext(OpenPalette)
  if (open === null) {
    throw new Error("CommandPaletteTrigger must render inside CommandPaletteProvider")
  }

  return (
    <button
      type="button"
      onClick={open}
      className="flex h-7 shrink-0 items-center gap-row rounded-full border border-line bg-surface-subtle px-row text-meta text-ink-muted hover:text-foreground"
    >
      <span>{PALETTE_LABEL}</span>
      <span className="font-mono">{shortcutHint(navigator.userAgent)}</span>
    </button>
  )
}

export function CommandPaletteProvider({ children }: { children: ReactNode }) {
  const [open, setOpen] = useState(false)
  const navigate = useNavigate()

  useEffect(() => {
    function onKeyDown(event: KeyboardEvent) {
      if (event.key.toLowerCase() === "k" && (event.metaKey || event.ctrlKey)) {
        event.preventDefault()
        setOpen((value) => !value)
      }
    }
    document.addEventListener("keydown", onKeyDown)
    return () => document.removeEventListener("keydown", onKeyDown)
  }, [])

  function select(path: string) {
    setOpen(false)
    navigate(path)
  }

  return (
    <OpenPalette.Provider value={() => setOpen(true)}>
      {children}
      <CommandDialog
        open={open}
        onOpenChange={setOpen}
        title={PALETTE_LABEL}
        description="Search the console's declared routes."
      >
        <Command>
          <CommandInput placeholder={`${PALETTE_LABEL}…`} />
          <CommandList>
            <CommandEmpty>No declared route matches.</CommandEmpty>
            {paletteSections(ROUTES, GRAPH_LEVELS, DESTINATIONS).map((group) => (
              <CommandGroup key={group.level} heading={group.level}>
                {group.rows.map((row) => (
                  <CommandItem
                    key={row.path}
                    value={`${row.label} ${row.question} ${row.pattern}`}
                    disabled={row.lookUpFrom !== null}
                    onSelect={row.lookUpFrom === null ? () => select(row.path) : undefined}
                  >
                    <span className="flex w-full items-baseline justify-between gap-row">
                      <span className="flex items-baseline gap-row">
                        <span>{row.label}</span>
                        {row.lookUpFrom !== null && (
                          <span className="text-meta text-ink-muted">
                            reached from {row.lookUpFrom}
                          </span>
                        )}
                      </span>
                      <span className="font-mono text-meta text-ink-muted">{row.pattern}</span>
                    </span>
                  </CommandItem>
                ))}
              </CommandGroup>
            ))}
          </CommandList>
        </Command>
      </CommandDialog>
    </OpenPalette.Provider>
  )
}
