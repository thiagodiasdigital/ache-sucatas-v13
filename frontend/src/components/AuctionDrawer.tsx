import {
  Drawer,
  DrawerContent,
  DrawerHeader,
  DrawerTitle,
  DrawerDescription,
} from "./ui/drawer"
import { AuctionCard } from "./AuctionCard"
import { formatDate } from "../lib/utils"
import type { Auction } from "../types/database"

interface AuctionDrawerProps {
  isOpen: boolean
  onClose: () => void
  selectedDate: Date | null
  auctions: Auction[]
}

export function AuctionDrawer({
  isOpen,
  onClose,
  selectedDate,
  auctions,
}: AuctionDrawerProps) {
  return (
    <Drawer open={isOpen} onOpenChange={(open) => !open && onClose()}>
      <DrawerContent side="right">
        <DrawerHeader>
          <DrawerTitle>
            Leilões em {selectedDate ? formatDate(selectedDate.toISOString()) : ""}
          </DrawerTitle>
          <DrawerDescription>
            {auctions.length} leilão{auctions.length !== 1 ? "s" : ""} encontrado
            {auctions.length !== 1 ? "s" : ""}
          </DrawerDescription>
        </DrawerHeader>

        <div className="flex-1 overflow-y-auto px-6 pb-6">
          {auctions.length === 0 ? (
            <p className="text-muted-foreground text-center py-8">
              Nenhum leilão nesta data
            </p>
          ) : (
            <div className="space-y-4">
              {auctions.map((auction) => (
                <AuctionCard key={auction.id} auction={auction} />
              ))}
            </div>
          )}
        </div>
      </DrawerContent>
    </Drawer>
  )
}
