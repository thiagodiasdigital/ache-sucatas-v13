import { useState, useMemo, useCallback, useRef, useEffect } from "react"
import { useSearchParams } from "react-router-dom"
import Map, { Marker, Popup, NavigationControl } from "react-map-gl/maplibre"
import type { MapRef } from "react-map-gl/maplibre"
import { MapPin, Map as MapIcon, Filter } from "lucide-react"
import Supercluster from "supercluster"
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

// GeoJSON Point type for supercluster
type AuctionPointProperties = {
  cluster: false
  auctionId: number
  auction: Auction
}

type ClusterPointProperties = {
  cluster: true
  cluster_id: number
  point_count: number
  point_count_abbreviated: string
}

type PointFeature = GeoJSON.Feature<GeoJSON.Point, AuctionPointProperties>
type ClusterFeature = GeoJSON.Feature<GeoJSON.Point, ClusterPointProperties>

// Active filters indicator component
function ActiveFiltersIndicator({
  uf,
  cidade,
  valorMin,
  totalResults,
}: {
  uf: string | null
  cidade: string | null
  valorMin: string | null
  totalResults: number
}) {
  const hasFilters = uf || cidade || valorMin

  if (!hasFilters) return null

  return (
    <div className="absolute top-4 left-4 z-10 bg-background/95 backdrop-blur-sm border rounded-lg shadow-lg p-3 max-w-xs">
      <div className="flex items-center gap-2 mb-2">
        <Filter className="h-4 w-4 text-muted-foreground" />
        <span className="text-sm font-medium">Filtros ativos</span>
      </div>
      <div className="flex flex-wrap gap-1.5">
        {uf && (
          <span className="inline-flex items-center gap-1 px-2 py-1 bg-primary/10 text-primary text-xs font-medium rounded-full">
            UF: {uf}
          </span>
        )}
        {cidade && (
          <span className="inline-flex items-center gap-1 px-2 py-1 bg-blue-500/10 text-blue-600 text-xs font-medium rounded-full">
            {cidade}
          </span>
        )}
        {valorMin && (
          <span className="inline-flex items-center gap-1 px-2 py-1 bg-green-500/10 text-green-600 text-xs font-medium rounded-full">
            Min: R$ {Number(valorMin).toLocaleString("pt-BR")}
          </span>
        )}
      </div>
      <div className="mt-2 pt-2 border-t text-xs text-muted-foreground">
        {totalResults} {totalResults === 1 ? "leilão encontrado" : "leilões encontrados"}
      </div>
    </div>
  )
}

function getMarkerColor(tags: string[] | null): string {
  if (!tags) return "#6B7280" // gray
  if (tags.some((t) => t.toUpperCase().includes("SUCATA"))) return "#10B981" // green
  if (tags.some((t) => t.toUpperCase().includes("DOCUMENTADO"))) return "#3B82F6" // blue
  return "#6B7280" // gray
}

function getClusterColor(leaves: PointFeature[]): string {
  // Check if any auction in the cluster has SUCATA or DOCUMENTADO tags
  const hasSucata = leaves.some((leaf) =>
    leaf.properties.auction.tags?.some((t) => t.toUpperCase().includes("SUCATA"))
  )
  const hasDocumentado = leaves.some((leaf) =>
    leaf.properties.auction.tags?.some((t) => t.toUpperCase().includes("DOCUMENTADO"))
  )

  // Prioritize Sucata (Emerald) color
  if (hasSucata) return "#10B981"
  if (hasDocumentado) return "#3B82F6"
  return "#6B7280"
}

// Calculate optimal view from markers
// Returns DEFAULT_VIEW if calculation results in invalid values
function calculateViewFromMarkers(markers: MarkerData[]): ViewState {
  if (markers.length === 0) return DEFAULT_VIEW

  if (markers.length === 1) {
    const lng = markers[0].longitude
    const lat = markers[0].latitude
    // Validate single marker coordinates
    if (!Number.isFinite(lng) || !Number.isFinite(lat)) {
      return DEFAULT_VIEW
    }
    return {
      longitude: lng,
      latitude: lat,
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

  // Final validation - return DEFAULT_VIEW if any value is invalid
  if (!Number.isFinite(centerLng) || !Number.isFinite(centerLat) || !Number.isFinite(zoom)) {
    return DEFAULT_VIEW
  }

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
  filters,
}: {
  markers: MarkerData[]
  initialView: ViewState
  filters: {
    uf: string | null
    cidade: string | null
    valorMin: string | null
  }
}) {
  const mapRef = useRef<MapRef>(null)
  const [selectedAuction, setSelectedAuction] = useState<Auction | null>(null)
  const [viewState, setViewState] = useState<ViewState>(initialView)
  const [bounds, setBounds] = useState<[number, number, number, number] | null>(null)

  // Create GeoJSON points from markers
  const points: PointFeature[] = useMemo(
    () =>
      markers.map((marker) => ({
        type: "Feature" as const,
        properties: {
          cluster: false as const,
          auctionId: marker.auction.id,
          auction: marker.auction,
        },
        geometry: {
          type: "Point" as const,
          coordinates: [marker.longitude, marker.latitude],
        },
      })),
    [markers]
  )

  // Create supercluster instance
  const supercluster = useMemo(() => {
    const index = new Supercluster<AuctionPointProperties, ClusterPointProperties>({
      radius: 60,
      maxZoom: 16,
    })
    index.load(points)
    return index
  }, [points])

  // Get clusters for current view
  const clusters = useMemo(() => {
    if (!bounds) return []
    const zoom = Math.floor(viewState.zoom)
    return supercluster.getClusters(bounds, zoom) as (PointFeature | ClusterFeature)[]
  }, [supercluster, bounds, viewState.zoom])

  // Update bounds when map moves
  useEffect(() => {
    const map = mapRef.current?.getMap()
    if (!map) return

    const updateBounds = () => {
      const b = map.getBounds()
      if (b) {
        setBounds([b.getWest(), b.getSouth(), b.getEast(), b.getNorth()])
      }
    }

    // Initial bounds
    updateBounds()

    // Update on move end
    map.on("moveend", updateBounds)
    return () => {
      map.off("moveend", updateBounds)
    }
  }, [])

  const handleClusterClick = useCallback(
    (clusterId: number, longitude: number, latitude: number) => {
      const zoom = supercluster.getClusterExpansionZoom(clusterId)
      setViewState({
        longitude,
        latitude,
        zoom: Math.min(zoom, 16),
      })
    },
    [supercluster]
  )

  const handleMarkerClick = useCallback((auction: Auction) => {
    setSelectedAuction(auction)
  }, [])

  return (
    <div className="h-[600px] w-full rounded-lg overflow-hidden border relative">
      {/* Active filters indicator */}
      <ActiveFiltersIndicator
        uf={filters.uf}
        cidade={filters.cidade}
        valorMin={filters.valorMin}
        totalResults={markers.length}
      />

      <Map
        ref={mapRef}
        {...viewState}
        onMove={(evt) => setViewState(evt.viewState)}
        mapStyle={MAP_STYLE}
        style={{ width: "100%", height: "100%" }}
      >
        <NavigationControl position="top-right" />

        {/* Clusters and Markers */}
        {clusters.map((feature) => {
          const [longitude, latitude] = feature.geometry.coordinates
          const properties = feature.properties

          // Cluster marker
          if (properties.cluster) {
            const { cluster_id, point_count } = properties
            const leaves = supercluster.getLeaves(cluster_id, Infinity) as PointFeature[]
            const clusterColor = getClusterColor(leaves)

            // Size based on point count
            const size = Math.min(40 + (point_count / markers.length) * 30, 60)

            return (
              <Marker
                key={`cluster-${cluster_id}`}
                longitude={longitude}
                latitude={latitude}
                anchor="center"
                onClick={(e) => {
                  e.originalEvent.stopPropagation()
                  handleClusterClick(cluster_id, longitude, latitude)
                }}
              >
                <div
                  className="cursor-pointer flex items-center justify-center rounded-full text-white font-bold shadow-lg hover:scale-110 transition-transform"
                  style={{
                    width: size,
                    height: size,
                    backgroundColor: clusterColor,
                  }}
                >
                  {point_count}
                </div>
              </Marker>
            )
          }

          // Individual marker
          const { auction } = properties
          return (
            <Marker
              key={`marker-${auction.id}`}
              longitude={longitude}
              latitude={latitude}
              anchor="bottom"
              onClick={(e) => {
                e.originalEvent.stopPropagation()
                handleMarkerClick(auction)
              }}
            >
              <div
                className="cursor-pointer transform hover:scale-110 transition-transform"
                style={{ color: getMarkerColor(auction.tags) }}
              >
                <MapPin className="h-8 w-8 drop-shadow-md" fill="currentColor" />
              </div>
            </Marker>
          )
        })}

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
        <div className="flex items-center gap-2">
          <div className="w-4 h-4 rounded-full bg-sucata text-[8px] text-white flex items-center justify-center font-bold">
            N
          </div>
          <span>Cluster</span>
        </div>
      </div>
    </div>
  )
}

export function MapView() {
  const [searchParams] = useSearchParams()
  const { data: paginatedData, isLoading } = useAuctions()

  // Read all active filters from URL
  const currentUF = searchParams.get("uf")
  const currentCidade = searchParams.get("cidade")
  const currentValorMin = searchParams.get("valor_min")

  // Filter auctions with valid coordinates
  // Uses Number.isFinite() to reject null, undefined, NaN, and Infinity
  const markers: MarkerData[] = useMemo(() => {
    const auctions = paginatedData?.data
    if (!auctions) return []
    return auctions
      .filter(
        (auction) =>
          Number.isFinite(auction.latitude) &&
          Number.isFinite(auction.longitude) &&
          auction.latitude !== 0 &&
          auction.longitude !== 0
      )
      .map((auction) => ({
        auction,
        longitude: auction.longitude!,
        latitude: auction.latitude!,
      }))
  }, [paginatedData])

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
  return (
    <MapContent
      key={markersKey}
      markers={markers}
      initialView={initialView}
      filters={{
        uf: currentUF,
        cidade: currentCidade,
        valorMin: currentValorMin,
      }}
    />
  )
}
