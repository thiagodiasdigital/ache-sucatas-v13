import { useAuctions } from "../hooks/useAuctions"
import { AuctionCard } from "./AuctionCard"
import { AuctionCardSkeleton } from "./AuctionCardSkeleton"
import { AlertCircle } from "lucide-react"

/**
 * Grid responsivo de leilões.
 * Layout: 1 col mobile, 2 col tablet, 3-4 col desktop
 */
export function AuctionGrid() {
  const { data: auctions, isLoading, isError, error } = useAuctions()

  // Loading state com skeletons
  if (isLoading) {
    return (
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-4">
        {Array.from({ length: 12 }).map((_, index) => (
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

  // Grid de leilões
  return (
    <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-4">
      {auctions.map((auction) => (
        <AuctionCard key={auction.id} auction={auction} />
      ))}
    </div>
  )
}
