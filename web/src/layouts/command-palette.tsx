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
  CommandShortcut,
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

  function select(path: string, hasSubject: boolean) {
    if (hasSubject) return
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
            const routesAtLevel = ROUTES.filter((route) => route.level === level)
            if (routesAtLevel.length === 0) return null

            return (
              <CommandGroup key={level} heading={level}>
                {routesAtLevel.map((route) => {
                  const hasSubject = route.params.length > 0
                  return (
                    <CommandItem
                      key={route.path}
                      value={`${route.label} ${route.question}`}
                      disabled={hasSubject}
                      onSelect={() => select(route.path, hasSubject)}
                    >
                      <span>{route.label}</span>
                      {hasSubject && <CommandShortcut>needs a subject</CommandShortcut>}
                    </CommandItem>
                  )
                })}
              </CommandGroup>
            )
          })}
        </CommandList>
      </Command>
    </CommandDialog>
  )
}
