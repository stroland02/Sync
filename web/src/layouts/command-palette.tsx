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
 * id, a repository id, a finding id — so it is left out rather than listed disabled. Wiring
 * the palette to accept a subject and jump straight to, say, a named vendor is a real feature
 * and a later slice; a disabled row that never becomes enabled is not a placeholder for it,
 * it is dead weight in the list. `AppFrame`'s sidebar makes the same call for the same reason,
 * and shows `reachedFrom` beside the destination rather than dropping it.
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
import { GRAPH_LEVELS, ROUTES } from "@/lib/routes"

/** What the palette calls itself, in one place: the dialog's placeholder and the trigger agree. */
const PALETTE_LABEL = "Jump to a destination"

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
            {GRAPH_LEVELS.map((level) => {
              const routesAtLevel = ROUTES.filter(
                (route) => route.level === level && route.params.length === 0
              )
              if (routesAtLevel.length === 0) return null

              return (
                <CommandGroup key={level} heading={level}>
                  {routesAtLevel.map((route) => (
                    <CommandItem
                      key={route.path}
                      value={`${route.label} ${route.question}`}
                      onSelect={() => select(route.path)}
                    >
                      <span>{route.label}</span>
                    </CommandItem>
                  ))}
                </CommandGroup>
              )
            })}
          </CommandList>
        </Command>
      </CommandDialog>
    </OpenPalette.Provider>
  )
}
