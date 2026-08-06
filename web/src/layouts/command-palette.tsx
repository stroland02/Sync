/**
 * Cmd/Ctrl-K over the route registry.
 *
 * Scope is routes only. Finding a specific finding id or a file path is a different problem
 * — it needs a search route in the view model and a relevance rule that can be wrong, which
 * is a slice of its own, not a widening of this one. This palette answers "where is the
 * screen that does X", not "where is entity X".
 *
 * Reads `ROUTES` — the same array the router and `SiteNav` read — so a route removed from the
 * registry disappears from here in the same edit, not as a follow-up.
 *
 * A route whose `params` is non-empty needs a subject this palette cannot supply — a vendor
 * id, a repository id, a finding id — so it is left out rather than listed disabled. Wiring
 * the palette to accept a subject and jump straight to, say, a named vendor is a real feature
 * and a later slice; a disabled row that never becomes enabled is not a placeholder for it,
 * it is dead weight in the list. `SiteNav` makes the same call for the same reason.
 */

import { useEffect, useState } from "react"
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

export function CommandPalette() {
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
    <CommandDialog
      open={open}
      onOpenChange={setOpen}
      title="Jump to a destination"
      description="Search the console's declared routes."
    >
      <Command>
        <CommandInput placeholder="Jump to a destination…" />
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
  )
}
