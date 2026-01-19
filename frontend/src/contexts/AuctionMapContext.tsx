import {
  createContext,
  useContext,
  useState,
  useCallback,
  useMemo,
  type ReactNode,
} from "react"
import { useAuctions } from "../hooks/useAuctions"
import type { Auction } from "../types/database"

/**
 * Interface para Bounding Box do Mapa
 */
export interface MapBounds {
  north: number // latitude max
  south: number // latitude min
  east: number  // longitude max
  west: number  // longitude min
}

/**
 * Interface do Estado Compartilhado Map <-> Grid
 */
interface AuctionMapState {
  // Dados
  allAuctions: Auction[]
  visibleAuctions: Auction[]

  // Paginação
  currentPage: number
  totalPages: number
  totalItems: number

  // Estado do Mapa
  currentBounds: MapBounds | null
  isMapActive: boolean

  // Loading/Error do useAuctions
  isLoading: boolean
  isError: boolean
  error: Error | null

  // Actions
  setBounds: (bounds: MapBounds | null) => void
  setMapActive: (active: boolean) => void
  clearBoundsFilter: () => void
}

const AuctionMapContext = createContext<AuctionMapState | null>(null)

/**
 * Provider para sincronização Map <-> Grid
 *
 * Single Source of Truth para:
 * - Todos os leilões (allAuctions)
 * - Leilões visíveis no viewport (visibleAuctions)
 * - Bounding box atual do mapa (currentBounds)
 */
export function AuctionMapProvider({ children }: { children: ReactNode }) {
  // Fonte de dados única (agora retorna dados paginados)
  const { data: paginatedData, isLoading, isError, error } = useAuctions()

  // Estado do bounds do mapa
  const [currentBounds, setCurrentBounds] = useState<MapBounds | null>(null)
  const [isMapActive, setIsMapActive] = useState(false)

  // Extrair dados da resposta paginada
  const allAuctions = useMemo(() => paginatedData?.data || [], [paginatedData])
  const currentPage = paginatedData?.page || 1
  const totalPages = paginatedData?.totalPages || 1
  const totalItems = paginatedData?.total || 0

  // Filtrar leilões pelo bounding box
  const visibleAuctions = useMemo(() => {
    // Se não há bounds ou mapa não está ativo, retorna todos
    if (!currentBounds || !isMapActive) {
      return allAuctions
    }

    // Filtrar apenas leilões dentro do viewport
    return allAuctions.filter((auction) => {
      // Ignorar leilões sem coordenadas
      if (auction.latitude === null || auction.longitude === null) {
        return false
      }

      const { north, south, east, west } = currentBounds
      const lat = auction.latitude
      const lng = auction.longitude

      // Verificar se está dentro do bounding box
      return lat >= south && lat <= north && lng >= west && lng <= east
    })
  }, [allAuctions, currentBounds, isMapActive])

  // Action: Atualizar bounds (chamado pelo Map no moveend)
  const setBounds = useCallback((bounds: MapBounds | null) => {
    setCurrentBounds(bounds)
  }, [])

  // Action: Ativar/desativar filtro por mapa
  const setMapActive = useCallback((active: boolean) => {
    setIsMapActive(active)
  }, [])

  // Action: Limpar filtro de bounds
  const clearBoundsFilter = useCallback(() => {
    setCurrentBounds(null)
    setIsMapActive(false)
  }, [])

  const value: AuctionMapState = {
    allAuctions,
    visibleAuctions,
    currentPage,
    totalPages,
    totalItems,
    currentBounds,
    isMapActive,
    isLoading,
    isError,
    error: error || null,
    setBounds,
    setMapActive,
    clearBoundsFilter,
  }

  return (
    <AuctionMapContext.Provider value={value}>
      {children}
    </AuctionMapContext.Provider>
  )
}

/**
 * Hook para consumir o contexto
 */
export function useAuctionMap() {
  const context = useContext(AuctionMapContext)
  if (!context) {
    throw new Error("useAuctionMap must be used within AuctionMapProvider")
  }
  return context
}
