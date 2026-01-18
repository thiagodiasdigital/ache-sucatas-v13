import { useEffect, useCallback, useRef } from "react"
import { useSearchParams } from "react-router-dom"
import { LayoutGrid, Map, Calendar } from "lucide-react"
import { ToggleGroup, ToggleGroupItem } from "./ui/toggle-group"

export type ViewMode = "grid" | "map" | "calendar"

const VIEW_MODES = [
  { value: "grid", label: "Grid", icon: LayoutGrid, shortcut: "G" },
  { value: "map", label: "Mapa", icon: Map, shortcut: "M" },
  { value: "calendar", label: "Calendário", icon: Calendar, shortcut: "C" },
] as const

const LOCAL_STORAGE_KEY = "ache-sucatas-view-mode"

export function ModeSwitcher() {
  const [searchParams, setSearchParams] = useSearchParams()
  const initialSyncDone = useRef(false)

  // Get current view from URL or localStorage
  const currentView = (searchParams.get("view") as ViewMode) ||
    (localStorage.getItem(LOCAL_STORAGE_KEY) as ViewMode) ||
    "grid"

  const setView = useCallback((view: ViewMode) => {
    // Update URL
    const newParams = new URLSearchParams(searchParams)
    if (view === "grid") {
      newParams.delete("view")
    } else {
      newParams.set("view", view)
    }
    setSearchParams(newParams, { replace: true })

    // Persist to localStorage
    localStorage.setItem(LOCAL_STORAGE_KEY, view)
  }, [searchParams, setSearchParams])

  // Sync URL with localStorage on mount (only once)
  useEffect(() => {
    if (initialSyncDone.current) return
    initialSyncDone.current = true

    const urlView = searchParams.get("view") as ViewMode
    const storedView = localStorage.getItem(LOCAL_STORAGE_KEY) as ViewMode

    if (!urlView && storedView && storedView !== "grid") {
      // If no URL param but localStorage has a value, update URL
      const newParams = new URLSearchParams(searchParams)
      newParams.set("view", storedView)
      setSearchParams(newParams, { replace: true })
    }
  }, [searchParams, setSearchParams])

  // Keyboard shortcuts
  useEffect(() => {
    function handleKeyDown(event: KeyboardEvent) {
      // Ignore if typing in an input
      if (
        event.target instanceof HTMLInputElement ||
        event.target instanceof HTMLTextAreaElement ||
        event.target instanceof HTMLSelectElement
      ) {
        return
      }

      const key = event.key.toUpperCase()

      if (key === "G" && !event.metaKey && !event.ctrlKey) {
        event.preventDefault()
        setView("grid")
      } else if (key === "M" && !event.metaKey && !event.ctrlKey) {
        event.preventDefault()
        setView("map")
      } else if (key === "C" && !event.metaKey && !event.ctrlKey) {
        event.preventDefault()
        setView("calendar")
      }
    }

    document.addEventListener("keydown", handleKeyDown)
    return () => {
      document.removeEventListener("keydown", handleKeyDown)
    }
  }, [setView])

  return (
    <div className="flex items-center gap-4">
      <span className="text-sm text-muted-foreground">Visualização:</span>
      <ToggleGroup
        type="single"
        value={currentView}
        onValueChange={(value: string) => {
          if (value) setView(value as ViewMode)
        }}
        aria-label="Modo de visualização"
      >
        {VIEW_MODES.map((mode) => (
          <ToggleGroupItem
            key={mode.value}
            value={mode.value}
            aria-label={`${mode.label} (${mode.shortcut})`}
            title={`${mode.label} (${mode.shortcut})`}
          >
            <mode.icon className="h-4 w-4 mr-2" />
            <span className="hidden sm:inline">{mode.label}</span>
          </ToggleGroupItem>
        ))}
      </ToggleGroup>
    </div>
  )
}
