import { useState, useMemo } from "react"
import { DayPicker, getDefaultClassNames } from "react-day-picker"
import { ptBR } from "date-fns/locale"
import { useAuctionMap } from "../contexts/AuctionMapContext"
import { AuctionDrawer } from "./AuctionDrawer"
import { MapIcon, AlertCircle } from "lucide-react"
import type { Auction } from "../types/database"
import "react-day-picker/style.css"

// Group auctions by date
function groupAuctionsByDate(
  auctions: Auction[]
): Map<string, { auctions: Auction[]; hasSucata: boolean; hasDocumentado: boolean }> {
  const map = new Map<
    string,
    { auctions: Auction[]; hasSucata: boolean; hasDocumentado: boolean }
  >()

  for (const auction of auctions) {
    if (!auction.data_leilao) continue

    const dateStr = auction.data_leilao.split("T")[0] // YYYY-MM-DD
    const existing = map.get(dateStr) || {
      auctions: [],
      hasSucata: false,
      hasDocumentado: false,
    }

    existing.auctions.push(auction)

    if (auction.tags?.some((t) => t.toUpperCase().includes("SUCATA"))) {
      existing.hasSucata = true
    }
    if (auction.tags?.some((t) => t.toUpperCase().includes("DOCUMENTADO"))) {
      existing.hasDocumentado = true
    }

    map.set(dateStr, existing)
  }

  return map
}

function formatDateKey(date: Date): string {
  // Use local date to avoid timezone issues
  const year = date.getFullYear()
  const month = String(date.getMonth() + 1).padStart(2, "0")
  const day = String(date.getDate()).padStart(2, "0")
  return `${year}-${month}-${day}`
}

export function CalendarView() {
  // Usar contexto compartilhado (Single Source of Truth) - mesmo do Grid e Map
  const {
    visibleAuctions: auctions,
    allAuctions,
    isLoading,
    isMapActive,
    clearBoundsFilter,
  } = useAuctionMap()

  const [selectedDate, setSelectedDate] = useState<Date | undefined>(undefined)
  const [isDrawerOpen, setIsDrawerOpen] = useState(false)

  // Group auctions by date for dot indicators
  const auctionsByDate = useMemo(() => {
    if (!auctions || auctions.length === 0) return new Map()
    return groupAuctionsByDate(auctions)
  }, [auctions])

  // Get auctions for selected date
  const selectedAuctions = useMemo(() => {
    if (!selectedDate) return []
    const dateStr = formatDateKey(selectedDate)
    return auctionsByDate.get(dateStr)?.auctions || []
  }, [selectedDate, auctionsByDate])

  // Get dates with auctions for modifiers
  const { datesWithSucata, datesWithDocumentado, datesWithAuctions, defaultMonth } = useMemo(() => {
    const sucata: Date[] = []
    const documentado: Date[] = []
    const all: Date[] = []

    auctionsByDate.forEach((data, dateStr) => {
      // Parse date correctly to avoid timezone issues
      const [year, month, day] = dateStr.split("-").map(Number)
      const date = new Date(year, month - 1, day, 12, 0, 0)

      all.push(date)
      if (data.hasSucata) sucata.push(date)
      if (data.hasDocumentado) documentado.push(date)
    })

    // Find the month with most auctions to set as default
    let mostCommonMonth: Date | undefined
    if (all.length > 0) {
      // Sort dates and get the first one (closest to now or earliest)
      const sorted = [...all].sort((a, b) => a.getTime() - b.getTime())
      // Find dates from today onwards, or use the latest date
      const today = new Date()
      today.setHours(0, 0, 0, 0)
      const futureDate = sorted.find(d => d >= today) || sorted[sorted.length - 1]
      mostCommonMonth = futureDate
    }

    return {
      datesWithSucata: sucata,
      datesWithDocumentado: documentado,
      datesWithAuctions: all,
      defaultMonth: mostCommonMonth
    }
  }, [auctionsByDate])

  const defaultClassNames = getDefaultClassNames()

  if (isLoading) {
    return (
      <div className="flex items-center justify-center h-96">
        <div className="text-muted-foreground">Carregando calendário...</div>
      </div>
    )
  }

  // Empty state
  if (!auctions || auctions.length === 0) {
    return (
      <div className="flex flex-col items-center justify-center py-12 text-center">
        <div className="h-12 w-12 rounded-full bg-muted flex items-center justify-center mb-4">
          <AlertCircle className="h-6 w-6 text-muted-foreground" />
        </div>
        <h3 className="text-lg font-semibold mb-2">Nenhum leilão encontrado</h3>
        <p className="text-sm text-muted-foreground max-w-md">
          Tente ajustar os filtros para encontrar mais resultados.
        </p>
      </div>
    )
  }

  return (
    <div className="flex flex-col items-center">
      {/* Indicador de filtro por mapa */}
      {isMapActive && (
        <div className="w-full max-w-md mb-4 flex flex-col sm:flex-row items-start sm:items-center justify-between gap-2 bg-zinc-100 dark:bg-zinc-800 rounded-lg px-4 py-3">
          <div className="flex items-center gap-2 text-sm text-zinc-600 dark:text-zinc-400">
            <MapIcon className="h-4 w-4 shrink-0" />
            <span>
              Mostrando <strong>{auctions.length}</strong> de{" "}
              <strong>{allAuctions.length}</strong> leilões
            </span>
          </div>
          <button
            onClick={clearBoundsFilter}
            className="text-sm text-blue-600 hover:text-blue-700 dark:text-blue-400 dark:hover:text-blue-300 font-medium min-h-[44px] px-3 -mx-3 sm:mx-0"
          >
            Mostrar todos
          </button>
        </div>
      )}

      {/* Stats */}
      <div className="mb-4 text-sm text-muted-foreground">
        {auctionsByDate.size} data{auctionsByDate.size !== 1 ? "s" : ""} com leilões
      </div>

      {/* Calendar */}
      <div className="border rounded-lg p-4 bg-card shadow-sm">
        <style>{`
          /* Custom styles for auction indicators */
          .calendar-day-with-sucata {
            position: relative;
            font-weight: 600;
          }
          .calendar-day-with-sucata::after {
            content: '';
            position: absolute;
            bottom: 4px;
            left: 50%;
            transform: translateX(-50%);
            width: 6px;
            height: 6px;
            border-radius: 50%;
            background-color: #10B981;
          }
          .calendar-day-with-documentado {
            position: relative;
            font-weight: 600;
          }
          .calendar-day-with-documentado::before {
            content: '';
            position: absolute;
            bottom: 4px;
            left: calc(50% + 5px);
            transform: translateX(-50%);
            width: 6px;
            height: 6px;
            border-radius: 50%;
            background-color: #3B82F6;
          }
          /* When both modifiers are present */
          .calendar-day-with-sucata.calendar-day-with-documentado::after {
            left: calc(50% - 5px);
          }
          /* Highlight days with auctions */
          .calendar-day-has-auction {
            background-color: rgba(16, 185, 129, 0.1);
            border-radius: 9999px;
          }
          /* Mobile touch targets for calendar days */
          @media (max-width: 767px) {
            .rdp-custom .rdp-day {
              min-width: 44px;
              min-height: 44px;
            }
          }
        `}</style>
        <DayPicker
          mode="single"
          locale={ptBR}
          selected={selectedDate}
          defaultMonth={defaultMonth}
          onSelect={(day) => {
            if (day) {
              setSelectedDate(day)
              setIsDrawerOpen(true)
            }
          }}
          modifiers={{
            sucata: datesWithSucata,
            documentado: datesWithDocumentado,
            hasAuction: datesWithAuctions,
          }}
          modifiersClassNames={{
            sucata: "calendar-day-with-sucata",
            documentado: "calendar-day-with-documentado",
            hasAuction: "calendar-day-has-auction",
          }}
          classNames={{
            root: `${defaultClassNames.root} rdp-custom`,
            day: `${defaultClassNames.day} relative`,
          }}
          showOutsideDays
          fixedWeeks
        />
      </div>

      {/* Legend */}
      <div className="mt-6 flex flex-wrap items-center justify-center gap-4 sm:gap-6 text-sm text-muted-foreground">
        <div className="flex items-center gap-2">
          <span className="w-3 h-3 rounded-full shrink-0" style={{ backgroundColor: "#10B981" }} />
          <span>Sucata</span>
        </div>
        <div className="flex items-center gap-2">
          <span className="w-3 h-3 rounded-full shrink-0" style={{ backgroundColor: "#3B82F6" }} />
          <span>Documentado</span>
        </div>
      </div>

      {/* Instructions */}
      <p className="mt-4 text-sm text-muted-foreground text-center">
        Clique em uma data para ver os leilões
      </p>

      {/* Drawer */}
      <AuctionDrawer
        isOpen={isDrawerOpen}
        onClose={() => setIsDrawerOpen(false)}
        selectedDate={selectedDate || null}
        auctions={selectedAuctions}
      />
    </div>
  )
}
