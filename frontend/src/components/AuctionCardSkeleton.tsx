import { Card, CardContent, CardFooter, CardHeader } from "./ui/card"
import { Skeleton } from "./ui/skeleton"

/**
 * Skeleton para o card de leilão durante loading.
 * Mantém layout compatível com AuctionCard.
 */
export function AuctionCardSkeleton() {
  return (
    <Card className="flex flex-col h-full">
      <CardHeader className="pb-2">
        {/* Tags skeleton */}
        <div className="flex gap-1.5 mb-2">
          <Skeleton className="h-5 w-16 rounded-full" />
          <Skeleton className="h-5 w-20 rounded-full" />
        </div>

        {/* Título skeleton */}
        <Skeleton className="h-5 w-full mb-1" />
        <Skeleton className="h-5 w-3/4" />

        {/* Órgão skeleton */}
        <Skeleton className="h-4 w-2/3 mt-2" />
      </CardHeader>

      <CardContent className="flex-1 space-y-3">
        {/* Localização skeleton */}
        <div className="flex items-center gap-2">
          <Skeleton className="h-4 w-4 rounded" />
          <Skeleton className="h-4 w-32" />
        </div>

        {/* Data skeleton */}
        <div className="flex items-center gap-2">
          <Skeleton className="h-4 w-4 rounded" />
          <Skeleton className="h-4 w-28" />
        </div>

        {/* Valor skeleton */}
        <div className="pt-2 border-t">
          <Skeleton className="h-3 w-24 mb-1" />
          <Skeleton className="h-7 w-32" />
        </div>
      </CardContent>

      <CardFooter className="pt-2 gap-2">
        <Skeleton className="h-9 flex-1" />
        <Skeleton className="h-9 flex-1" />
      </CardFooter>
    </Card>
  )
}
