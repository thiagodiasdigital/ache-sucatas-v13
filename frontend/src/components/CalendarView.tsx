import { useState, useMemo } from "react"
import { DayPicker } from "react-day-picker"
import { ptBR } from "date-fns/locale"
import { useAuctions } from "../hooks/useAuctions"
import { AuctionDrawer } from "./AuctionDrawer"
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
  return date.toISOString().split("T")[0]
}

export function CalendarView() {
  const { data: auctions, isLoading } = useAuctions()
  const [selectedDate, setSelectedDate] = useState<Date | undefined>(undefined)
  const [isDrawerOpen, setIsDrawerOpen] = useState(false)

  // Group auctions by date for dot indicators
  const auctionsByDate = useMemo(() => {
    if (!auctions) return new Map()
    return groupAuctionsByDate(auctions)
  }, [auctions])

  // Get auctions for selected date
  const selectedAuctions = useMemo(() => {
    if (!selectedDate) return []
    const dateStr = formatDateKey(selectedDate)
    return auctionsByDate.get(dateStr)?.auctions || []
  }, [selectedDate, auctionsByDate])

  if (isLoading) {
    return (
      <div className="flex items-center justify-center h-96">
        <div className="text-muted-foreground">Carregando calendário...</div>
      </div>
    )
  }

  // Get dates with auctions for modifiers
  const datesWithSucata: Date[] = []
  const datesWithDocumentado: Date[] = []

  auctionsByDate.forEach((data, dateStr) => {
    const date = new Date(dateStr + "T12:00:00")
    if (data.hasSucata) datesWithSucata.push(date)
    if (data.hasDocumentado) datesWithDocumentado.push(date)
  })

  return (
    <div className="flex flex-col items-center">
      {/* Calendar */}
      <div className="border rounded-lg p-4 bg-card">
        <style>{`
          .rdp-day_sucata { position: relative; }
          .rdp-day_sucata::after {
            content: '';
            position: absolute;
            bottom: 2px;
            left: 50%;
            transform: translateX(-50%);
            width: 6px;
            height: 6px;
            border-radius: 50%;
            background-color: #10B981;
          }
          .rdp-day_documentado { position: relative; }
          .rdp-day_documentado::before {
            content: '';
            position: absolute;
            bottom: 2px;
            left: calc(50% + 4px);
            transform: translateX(-50%);
            width: 6px;
            height: 6px;
            border-radius: 50%;
            background-color: #3B82F6;
          }
          .rdp-day_sucata.rdp-day_documentado::after {
            left: calc(50% - 4px);
          }
        `}</style>
        <DayPicker
          mode="single"
          locale={ptBR}
          selected={selectedDate}
          onSelect={(day) => {
            if (day) {
              setSelectedDate(day)
              setIsDrawerOpen(true)
            }
          }}
          modifiers={{
            sucata: datesWithSucata,
            documentado: datesWithDocumentado,
          }}
          modifiersClassNames={{
            sucata: "rdp-day_sucata font-bold",
            documentado: "rdp-day_documentado font-bold",
          }}
        />
      </div>

      {/* Legend */}
      <div className="mt-6 flex items-center gap-6 text-sm text-muted-foreground">
        <div className="flex items-center gap-2">
          <span className="w-3 h-3 rounded-full bg-sucata" />
          <span>Sucata</span>
        </div>
        <div className="flex items-center gap-2">
          <span className="w-3 h-3 rounded-full bg-documentado" />
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
