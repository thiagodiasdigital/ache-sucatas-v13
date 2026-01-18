import { useSearchParams } from "react-router-dom"

export type ViewMode = "grid" | "map" | "calendar"

const LOCAL_STORAGE_KEY = "ache-sucatas-view-mode"

export function useViewMode(): ViewMode {
  const [searchParams] = useSearchParams()
  return (
    (searchParams.get("view") as ViewMode) ||
    (localStorage.getItem(LOCAL_STORAGE_KEY) as ViewMode) ||
    "grid"
  )
}
