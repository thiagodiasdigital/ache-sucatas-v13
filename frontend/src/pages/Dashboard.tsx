import { useSearchParams } from "react-router-dom"
import { TopFilterBar } from "../components/TopFilterBar"
import { AuctionGrid } from "../components/AuctionGrid"
import { ModeSwitcher, type ViewMode } from "../components/ModeSwitcher"
import { AuctionMap } from "../components/dashboard"
import { CalendarView } from "../components/CalendarView"
import { useDashboardStats } from "../hooks/useAuctions"
import { Card, CardContent } from "../components/ui/card"
import { Skeleton } from "../components/ui/skeleton"
import { formatCurrency } from "../lib/utils"
import { Gavel, MapPin, Building2, TrendingUp, Calendar } from "lucide-react"

/**
 * Página principal do Dashboard.
 * Exibe estatísticas, filtros e grid de leilões.
 */
export function DashboardPage() {
  const [searchParams] = useSearchParams()
  const { data: stats, isLoading: loadingStats } = useDashboardStats()

  // Get current view mode from URL or default to "grid"
  const currentView: ViewMode = (searchParams.get("view") as ViewMode) || "grid"

  const statCards = [
    {
      label: "Total de Leilões",
      value: stats?.total_leiloes ?? 0,
      icon: Gavel,
      format: (v: number) => v.toLocaleString("pt-BR"),
    },
    {
      label: "Estados",
      value: stats?.total_ufs ?? 0,
      icon: MapPin,
      format: (v: number) => v.toString(),
    },
    {
      label: "Cidades",
      value: stats?.total_cidades ?? 0,
      icon: Building2,
      format: (v: number) => v.toLocaleString("pt-BR"),
    },
    {
      label: "Valor Total Estimado",
      value: stats?.valor_total_estimado ?? 0,
      icon: TrendingUp,
      format: (v: number) => formatCurrency(v),
    },
    {
      label: "Próximos 7 dias",
      value: stats?.leiloes_proximos_7_dias ?? 0,
      icon: Calendar,
      format: (v: number) => v.toLocaleString("pt-BR"),
    },
  ]

  return (
    <div className="flex flex-col">
      {/* Stats Cards */}
      <div className="container py-6">
        <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-5 gap-4">
          {statCards.map((stat, index) => (
            <Card key={index}>
              <CardContent className="pt-6">
                <div className="flex items-center gap-2 text-muted-foreground mb-2">
                  <stat.icon className="h-4 w-4" />
                  <span className="text-xs font-medium uppercase tracking-wide">
                    {stat.label}
                  </span>
                </div>
                {loadingStats ? (
                  <Skeleton className="h-8 w-24" />
                ) : (
                  <p className="text-2xl font-bold">
                    {stat.format(stat.value)}
                  </p>
                )}
              </CardContent>
            </Card>
          ))}
        </div>
      </div>

      {/* Filtros */}
      <TopFilterBar />

      {/* Mode Switcher */}
      <div className="container py-4">
        <ModeSwitcher />
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
