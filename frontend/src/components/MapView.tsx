import { useState, useMemo, useCallback } from "react"
import { useSearchParams } from "react-router-dom"
import Map, { Marker, Popup, NavigationControl } from "react-map-gl/maplibre"
import { MapPin, Map as MapIcon } from "lucide-react"
import { useAuctions } from "../hooks/useAuctions"
import { AuctionCard } from "./AuctionCard"
import type { Auction } from "../types/database"
import "maplibre-gl/dist/maplibre-gl.css"

// Free OpenStreetMap tile server
const MAP_STYLE = {
  version: 8 as const,
  sources: {
    osm: {
      type: "raster" as const,
      tiles: ["https://tile.openstreetmap.org/{z}/{x}/{y}.png"],
      tileSize: 256,
      attribution: "&copy; OpenStreetMap Contributors",
      maxzoom: 19,
    },
  },
  layers: [
    {
      id: "osm",
      type: "raster" as const,
      source: "osm",
    },
  ],
}

// Brazil default bounds
const DEFAULT_VIEW = {
  longitude: -55.0,
  latitude: -15.0,
  zoom: 4,
}

interface MarkerData {
  auction: Auction
  longitude: number
  latitude: number
}

interface ViewState {
  longitude: number
  latitude: number
  zoom: number
}

function getMarkerColor(tags: string[] | null): string {
  if (!tags) return "#6B7280" // gray
  if (tags.some((t) => t.toUpperCase().includes("SUCATA"))) return "#10B981" // green
  if (tags.some((t) => t.toUpperCase().includes("DOCUMENTADO"))) return "#3B82F6" // blue
  return "#6B7280" // gray
}

function calculateViewFromMarkers(markers: MarkerData[]): ViewState {
  if (markers.length === 0) return DEFAULT_VIEW

  if (markers.length === 1) {
    return {
      longitude: markers[0].longitude,
      latitude: markers[0].latitude,
      zoom: 10,
    }
  }

  // Calculate bounds
  const lngs = markers.map((m) => m.longitude)
  const lats = markers.map((m) => m.latitude)
  const minLng = Math.min(...lngs)
  const maxLng = Math.max(...lngs)
  const minLat = Math.min(...lats)
  const maxLat = Math.max(...lats)

  // Center point
  const centerLng = (minLng + maxLng) / 2
  const centerLat = (minLat + maxLat) / 2

  // Calculate zoom based on bounds
  const lngDiff = maxLng - minLng
  const latDiff = maxLat - minLat
  const maxDiff = Math.max(lngDiff, latDiff)
  const zoom = Math.max(4, Math.min(12, 8 - Math.log2(maxDiff + 0.1)))

  return {
    longitude: centerLng,
    latitude: centerLat,
    zoom,
  }
}

// Inner map component that receives markers and initial view
function MapContent({
  markers,
  initialView,
}: {
  markers: MarkerData[]
  initialView: ViewState
}) {
  const [selectedAuction, setSelectedAuction] = useState<Auction | null>(null)
  const [viewState, setViewState] = useState<ViewState>(initialView)

  const handleMarkerClick = useCallback((auction: Auction) => {
    setSelectedAuction(auction)
  }, [])

  return (
    <div className="h-[600px] w-full rounded-lg overflow-hidden border">
      <Map
        {...viewState}
        onMove={(evt) => setViewState(evt.viewState)}
        mapStyle={MAP_STYLE}
        style={{ width: "100%", height: "100%" }}
      >
        <NavigationControl position="top-right" />

        {/* Markers */}
        {markers.map((marker) => (
          <Marker
            key={marker.auction.id}
            longitude={marker.longitude}
            latitude={marker.latitude}
            anchor="bottom"
            onClick={(e) => {
              e.originalEvent.stopPropagation()
              handleMarkerClick(marker.auction)
            }}
          >
            <div
              className="cursor-pointer transform hover:scale-110 transition-transform"
              style={{ color: getMarkerColor(marker.auction.tags) }}
            >
              <MapPin className="h-8 w-8 drop-shadow-md" fill="currentColor" />
            </div>
          </Marker>
        ))}

        {/* Popup */}
        {selectedAuction && selectedAuction.latitude && selectedAuction.longitude && (
          <Popup
            longitude={selectedAuction.longitude}
            latitude={selectedAuction.latitude}
            anchor="top"
            onClose={() => setSelectedAuction(null)}
            closeOnClick={false}
            maxWidth="320px"
          >
            <div className="pt-2">
              <AuctionCard auction={selectedAuction} />
            </div>
          </Popup>
        )}
      </Map>

      {/* Legend */}
      <div className="mt-4 flex items-center gap-6 text-sm text-muted-foreground">
        <div className="flex items-center gap-2">
          <MapPin className="h-4 w-4 text-sucata" fill="#10B981" />
          <span>Sucata</span>
        </div>
        <div className="flex items-center gap-2">
          <MapPin className="h-4 w-4 text-documentado" fill="#3B82F6" />
          <span>Documentado</span>
        </div>
        <div className="flex items-center gap-2">
          <MapPin className="h-4 w-4 text-gray-500" fill="#6B7280" />
          <span>Outros</span>
        </div>
      </div>
    </div>
  )
}

export function MapView() {
  const [searchParams] = useSearchParams()
  const { data: auctions, isLoading } = useAuctions()

  const currentUF = searchParams.get("uf")

  // Filter auctions with valid coordinates
  const markers: MarkerData[] = useMemo(() => {
    if (!auctions) return []
    return auctions
      .filter(
        (auction) =>
          auction.latitude !== null &&
          auction.longitude !== null &&
          auction.latitude !== 0 &&
          auction.longitude !== 0
      )
      .map((auction) => ({
        auction,
        longitude: auction.longitude!,
        latitude: auction.latitude!,
      }))
  }, [auctions])

  // Create a key to remount MapContent when markers change significantly
  const markersKey = useMemo(
    () => markers.map((m) => m.auction.id).join(","),
    [markers]
  )

  // Empty state: no UF selected
  if (!currentUF) {
    return (
      <div className="flex flex-col items-center justify-center h-96 text-center">
        <MapIcon className="h-16 w-16 text-muted-foreground/50 mb-4" />
        <h3 className="text-lg font-semibold mb-2">Selecione um Estado</h3>
        <p className="text-muted-foreground max-w-md">
          Para visualizar os leilões no mapa, primeiro selecione um estado (UF)
          nos filtros acima.
        </p>
      </div>
    )
  }

  // Loading state
  if (isLoading) {
    return (
      <div className="flex items-center justify-center h-96">
        <div className="text-muted-foreground">Carregando mapa...</div>
      </div>
    )
  }

  // No results with coordinates
  if (markers.length === 0) {
    return (
      <div className="flex flex-col items-center justify-center h-96 text-center">
        <MapPin className="h-16 w-16 text-muted-foreground/50 mb-4" />
        <h3 className="text-lg font-semibold mb-2">Sem dados geográficos</h3>
        <p className="text-muted-foreground max-w-md">
          Os leilões encontrados não possuem coordenadas geográficas disponíveis.
          Tente usar a visualização em Grid.
        </p>
      </div>
    )
  }

  // Calculate initial view from markers
  const initialView = calculateViewFromMarkers(markers)

  // Use key to remount when markers change, ensuring fresh initial view calculation
  return <MapContent key={markersKey} markers={markers} initialView={initialView} />
}
