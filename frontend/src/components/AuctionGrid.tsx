import { useAuctionMap } from "../contexts/AuctionMapContext"
import { AuctionCardGrid } from "./AuctionCardGrid"
import { AuctionCardSkeleton } from "./AuctionCardSkeleton"
import { Pagination } from "./Pagination"
import { AlertCircle, MapIcon } from "lucide-react"

/**
 * Grid responsivo de leilões com paginação server-side.
 * Layout: 1 col mobile, 2 col tablet, 3-4 col desktop
 *
 * Sincronizado com Mapa via AuctionMapContext.
 * Exibe apenas leilões visíveis no viewport do mapa (quando ativo).
 */
export function AuctionGrid() {
  // Usar contexto compartilhado (Single Source of Truth)
  const {
    visibleAuctions: auctions,
    allAuctions,
    currentPage,
    totalPages,
    totalItems,
    isLoading,
    isError,
    error,
    isMapActive,
    clearBoundsFilter,
  } = useAuctionMap()

  // Loading state com skeletons (20 itens por página)
  if (isLoading) {
    return (
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-4">
        {Array.from({ length: 20 }).map((_, index) => (
          <AuctionCardSkeleton key={index} />
        ))}
      </div>
    )
  }

  // Error state
  if (isError) {
    return (
      <div className="flex flex-col items-center justify-center py-12 text-center">
        <AlertCircle className="h-12 w-12 text-muted-foreground mb-4" />
        <h3 className="text-lg font-semibold mb-2">Erro ao carregar leilões</h3>
        <p className="text-sm text-muted-foreground max-w-md">
          {error?.message || "Ocorreu um erro ao buscar os leilões. Tente novamente."}
        </p>
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

  // Grid de leilões com paginação
  return (
    <div className="space-y-4">
      {/* Indicador de filtro por mapa */}
      {isMapActive && (
        <div className="flex items-center justify-between bg-zinc-100 dark:bg-zinc-800 rounded-lg px-4 py-2">
          <div className="flex items-center gap-2 text-sm text-zinc-600 dark:text-zinc-400">
            <MapIcon className="h-4 w-4" />
            <span>
              Mostrando <strong>{auctions.length}</strong> de{" "}
              <strong>{allAuctions.length}</strong> leilões no viewport do mapa
            </span>
          </div>
          <button
            onClick={clearBoundsFilter}
            className="text-sm text-blue-600 hover:text-blue-700 dark:text-blue-400 dark:hover:text-blue-300 font-medium"
          >
            Mostrar todos
          </button>
        </div>
      )}

      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-4">
        {auctions.map((auction) => (
          <AuctionCardGrid key={auction.id} auction={auction} />
        ))}
      </div>

      {/* Paginação (não exibir quando mapa está ativo pois filtra client-side) */}
      {!isMapActive && (
        <Pagination
          currentPage={currentPage}
          totalPages={totalPages}
          totalItems={totalItems}
        />
      )}
    </div>
  )
}
