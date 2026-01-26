import { useSearchParams } from "react-router-dom"
import { AuctionGrid } from "../components/AuctionGrid"
import { ModeSwitcher, type ViewMode } from "../components/ModeSwitcher"
import { AuctionMap } from "../components/dashboard"
import { CalendarView } from "../components/CalendarView"
import { useAuctionMap } from "../contexts/AuctionMapContext"

/**
 * Página principal do Dashboard.
 * Os filtros estão no Header (Layout).
 * Exibe ModeSwitcher e visualizações (Grid, Mapa, Calendário).
 */
export function DashboardPage() {
  const [searchParams] = useSearchParams()
  const { totalItems, isLoading } = useAuctionMap()

  // Get current view mode from URL or default to "grid"
  const currentView: ViewMode = (searchParams.get("view") as ViewMode) || "grid"

  return (
    <div className="flex flex-col">
      {/* Mode Switcher + Contador de resultados */}
      <div className="container py-4">
        <ModeSwitcher totalItems={totalItems} isLoading={isLoading} />
      </div>

      {/* Visualização condicional */}
      <div className="container py-6">
        {currentView === "map" ? (
          <AuctionMap />
        ) : currentView === "calendar" ? (
          <CalendarView />
        ) : (
          <AuctionGrid />
        )}
      </div>
    </div>
  )
}
