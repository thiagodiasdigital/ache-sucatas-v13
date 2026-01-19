import { useState, useMemo, useCallback, useRef, useEffect } from "react"
import { useSearchParams } from "react-router-dom"
import Map, { Popup, NavigationControl, Source, Layer } from "react-map-gl/maplibre"
import type { MapRef, MapLayerMouseEvent } from "react-map-gl/maplibre"
import type { LayerProps } from "react-map-gl/maplibre"
import { MapPin } from "lucide-react"
import { useAuctionMap, type MapBounds } from "../../contexts/AuctionMapContext"
import { useDebounce } from "../../hooks/useDebounce"
import type { Auction } from "../../types/database"
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

// Cluster layer styles - using Slate/Zinc gray tones as specified
const clusterLayer: LayerProps = {
  id: "clusters",
  type: "circle",
  source: "auctions",
  filter: ["has", "point_count"],
  paint: {
    "circle-color": [
      "step",
      ["get", "point_count"],
      "#71717A", // zinc-500 for small clusters
      10,
      "#52525B", // zinc-600 for medium clusters
      50,
      "#3F3F46", // zinc-700 for large clusters
    ],
    "circle-radius": [
      "step",
      ["get", "point_count"],
      20, // small clusters
      10,
      30, // medium clusters
      50,
      40, // large clusters
    ],
    "circle-stroke-width": 2,
    "circle-stroke-color": "#A1A1AA", // zinc-400
  },
}

const clusterCountLayer: LayerProps = {
  id: "cluster-count",
  type: "symbol",
  source: "auctions",
  filter: ["has", "point_count"],
  layout: {
    "text-field": ["get", "point_count_abbreviated"],
    "text-font": ["Open Sans Bold", "Arial Unicode MS Bold"],
    "text-size": 14,
  },
  paint: {
    "text-color": "#FFFFFF",
  },
}

// Individual point layer
const unclusteredPointLayer: LayerProps = {
  id: "unclustered-point",
  type: "circle",
  source: "auctions",
  filter: ["!", ["has", "point_count"]],
  paint: {
    "circle-color": [
      "case",
      ["==", ["get", "tipo"], "sucata"],
      "#10B981", // emerald-500 for sucata
      ["==", ["get", "tipo"], "documentado"],
      "#3B82F6", // blue-500 for documentado
      "#71717A", // zinc-500 for others
    ],
    "circle-radius": 10,
    "circle-stroke-width": 2,
    "circle-stroke-color": "#FFFFFF",
  },
}

interface MarkerData {
  auction: Auction
  longitude: number
  latitude: number
  tipo: "sucata" | "documentado" | "outro"
}

interface ViewState {
  longitude: number
  latitude: number
  zoom: number
}

// Default view centered on Brazil
const DEFAULT_VIEW: ViewState = {
  longitude: -55.0,
  latitude: -15.0,
  zoom: 4,
}

// Helper to determine auction type from tags
function getAuctionTipo(tags: string[] | null): "sucata" | "documentado" | "outro" {
  if (!tags) return "outro"
  if (tags.some((t) => t.toUpperCase().includes("SUCATA"))) return "sucata"
  if (tags.some((t) => t.toUpperCase().includes("DOCUMENTADO"))) return "documentado"
  return "outro"
}

// Calculate optimal view from markers
function calculateViewFromMarkers(markers: MarkerData[]): ViewState {
  if (markers.length === 0) return DEFAULT_VIEW

  if (markers.length === 1) {
    return {
      longitude: markers[0].longitude,
      latitude: markers[0].latitude,
      zoom: 10,
    }
  }

  const lngs = markers.map((m) => m.longitude)
  const lats = markers.map((m) => m.latitude)
  const minLng = Math.min(...lngs)
  const maxLng = Math.max(...lngs)
  const minLat = Math.min(...lats)
  const maxLat = Math.max(...lats)

  const centerLng = (minLng + maxLng) / 2
  const centerLat = (minLat + maxLat) / 2

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

// Inner map component
function MapContent({
  markers,
  initialView,
  onMarkerClick,
  onBoundsChange,
}: {
  markers: MarkerData[]
  initialView: ViewState
  onMarkerClick: (auction: Auction) => void
  onBoundsChange: (bounds: MapBounds) => void
}) {
  const mapRef = useRef<MapRef>(null)
  const [viewState, setViewState] = useState<ViewState>(initialView)
  const [hoveredAuction, setHoveredAuction] = useState<Auction | null>(null)
  const [selectedAuction, setSelectedAuction] = useState<Auction | null>(null)

  // Debounced bounds update (400ms) - evita re-renders durante pan
  const debouncedBoundsChange = useDebounce((bounds: MapBounds) => {
    onBoundsChange(bounds)
  }, 400)

  // Extrair bounds do mapa e notificar
  const handleMoveEnd = useCallback(() => {
    const map = mapRef.current?.getMap()
    if (!map) return

    const mapBounds = map.getBounds()
    if (!mapBounds) return

    const bounds: MapBounds = {
      north: mapBounds.getNorth(),
      south: mapBounds.getSouth(),
      east: mapBounds.getEast(),
      west: mapBounds.getWest(),
    }

    debouncedBoundsChange(bounds)
  }, [debouncedBoundsChange])

  // Emitir bounds inicial quando o mapa carregar
  useEffect(() => {
    // Pequeno delay para garantir que o mapa renderizou
    const timer = setTimeout(handleMoveEnd, 100)
    return () => clearTimeout(timer)
  }, [handleMoveEnd])

  // Create GeoJSON data for clustering
  const geojsonData = useMemo(
    () => ({
      type: "FeatureCollection" as const,
      features: markers.map((marker) => ({
        type: "Feature" as const,
        properties: {
          id: marker.auction.id,
          tipo: marker.tipo,
          nome_leilao: marker.auction.titulo || marker.auction.objeto_resumido || "Leilão",
          cidade: marker.auction.cidade,
          uf: marker.auction.uf,
        },
        geometry: {
          type: "Point" as const,
          coordinates: [marker.longitude, marker.latitude],
        },
      })),
    }),
    [markers]
  )

  // Create a lookup object for quick auction access (avoiding Map constructor conflict)
  const auctionLookup = useMemo(() => {
    const lookup: Record<number, MarkerData> = {}
    markers.forEach((m) => { lookup[m.auction.id] = m })
    return lookup
  }, [markers])

  // Handle cluster click to zoom in
  const handleMapClick = useCallback(
    (event: MapLayerMouseEvent) => {
      const map = mapRef.current?.getMap()
      if (!map) return

      // Check for cluster click
      const clusterFeatures = map.queryRenderedFeatures(event.point, {
        layers: ["clusters"],
      })

      if (clusterFeatures.length > 0) {
        const clusterId = clusterFeatures[0].properties?.cluster_id
        if (clusterId !== undefined) {
          const source = map.getSource("auctions") as maplibregl.GeoJSONSource
          source.getClusterExpansionZoom(clusterId).then((zoom) => {
            if (zoom === undefined) return
            const coords = (clusterFeatures[0].geometry as GeoJSON.Point).coordinates
            setViewState({
              longitude: coords[0],
              latitude: coords[1],
              zoom: Math.min(zoom, 16),
            })
          }).catch(() => {
            // Silently ignore cluster zoom errors
          })
        }
        return
      }

      // Check for point click
      const pointFeatures = map.queryRenderedFeatures(event.point, {
        layers: ["unclustered-point"],
      })

      if (pointFeatures.length > 0) {
        const auctionId = pointFeatures[0].properties?.id
        const markerData = auctionLookup[auctionId]
        if (markerData) {
          setSelectedAuction(markerData.auction)
          onMarkerClick(markerData.auction)
        }
      }
    },
    [auctionLookup, onMarkerClick]
  )

  // Handle mouse move for hover effect
  const handleMouseMove = useCallback(
    (event: MapLayerMouseEvent) => {
      const map = mapRef.current?.getMap()
      if (!map) return

      const features = map.queryRenderedFeatures(event.point, {
        layers: ["unclustered-point", "clusters"],
      })

      if (features.length > 0) {
        map.getCanvas().style.cursor = "pointer"

        // Show tooltip for unclustered points
        if (features[0].layer?.id === "unclustered-point") {
          const auctionId = features[0].properties?.id
          const markerData = auctionLookup[auctionId]
          if (markerData) {
            setHoveredAuction(markerData.auction)
          }
        } else {
          setHoveredAuction(null)
        }
      } else {
        map.getCanvas().style.cursor = ""
        setHoveredAuction(null)
      }
    },
    [auctionLookup]
  )

  const handleMouseLeave = useCallback(() => {
    setHoveredAuction(null)
  }, [])

  return (
    <div className="h-[600px] w-full rounded-lg overflow-hidden border relative">
      <Map
        ref={mapRef}
        {...viewState}
        onMove={(evt) => setViewState(evt.viewState)}
        onMoveEnd={handleMoveEnd}
        onClick={handleMapClick}
        onMouseMove={handleMouseMove}
        onMouseLeave={handleMouseLeave}
        mapStyle={MAP_STYLE}
        style={{ width: "100%", height: "100%" }}
      >
        <NavigationControl position="top-right" />

        <Source
          id="auctions"
          type="geojson"
          data={geojsonData}
          cluster={true}
          clusterMaxZoom={14}
          clusterRadius={50}
        >
          <Layer {...clusterLayer} />
          <Layer {...clusterCountLayer} />
          <Layer {...unclusteredPointLayer} />
        </Source>

        {/* Hover tooltip */}
        {hoveredAuction && hoveredAuction.latitude && hoveredAuction.longitude && (
          <Popup
            longitude={hoveredAuction.longitude}
            latitude={hoveredAuction.latitude}
            anchor="bottom"
            closeButton={false}
            closeOnClick={false}
            offset={15}
          >
            <div className="bg-zinc-900 text-white px-3 py-2 rounded-lg text-sm">
              <p className="font-medium">{hoveredAuction.titulo || hoveredAuction.objeto_resumido || "Leilão"}</p>
              <p className="text-zinc-400">{hoveredAuction.cidade}, {hoveredAuction.uf}</p>
            </div>
          </Popup>
        )}

        {/* Selected auction popup */}
        {selectedAuction && selectedAuction.latitude && selectedAuction.longitude && (
          <Popup
            longitude={selectedAuction.longitude}
            latitude={selectedAuction.latitude}
            anchor="top"
            onClose={() => setSelectedAuction(null)}
            closeOnClick={false}
            maxWidth="320px"
          >
            <div className="p-2">
              <h3 className="font-semibold text-sm mb-1">
                {selectedAuction.titulo || selectedAuction.objeto_resumido || "Leilão"}
              </h3>
              <p className="text-xs text-muted-foreground mb-2">
                {selectedAuction.cidade}, {selectedAuction.uf}
              </p>
              {selectedAuction.valor_estimado && (
                <p className="text-xs font-medium text-emerald-600">
                  R$ {selectedAuction.valor_estimado.toLocaleString("pt-BR")}
                </p>
              )}
              {selectedAuction.data_leilao && (
                <p className="text-xs text-muted-foreground mt-1">
                  Data: {new Date(selectedAuction.data_leilao).toLocaleDateString("pt-BR")}
                </p>
              )}
            </div>
          </Popup>
        )}
      </Map>

      {/* Legend */}
      <div className="absolute bottom-4 left-4 bg-background/95 backdrop-blur-sm border rounded-lg shadow-lg p-3">
        <p className="text-xs font-medium mb-2 text-muted-foreground">Legenda</p>
        <div className="flex flex-col gap-1.5">
          <div className="flex items-center gap-2">
            <div className="w-3 h-3 rounded-full bg-emerald-500" />
            <span className="text-xs">Sucata</span>
          </div>
          <div className="flex items-center gap-2">
            <div className="w-3 h-3 rounded-full bg-blue-500" />
            <span className="text-xs">Documentado</span>
          </div>
          <div className="flex items-center gap-2">
            <div className="w-3 h-3 rounded-full bg-zinc-500" />
            <span className="text-xs">Outros</span>
          </div>
          <div className="flex items-center gap-2">
            <div className="w-4 h-4 rounded-full bg-zinc-600 text-[8px] text-white flex items-center justify-center font-bold">
              N
            </div>
            <span className="text-xs">Cluster</span>
          </div>
        </div>
      </div>
    </div>
  )
}

/**
 * AuctionMap - Mapa Tático para visualização geoespacial de leilões.
 *
 * Sincronizado com Grid via AuctionMapContext.
 * Emite bounds no moveend (debounced) para filtrar o Grid.
 */
export function AuctionMap() {
  const [searchParams] = useSearchParams()

  // Usar contexto compartilhado (Single Source of Truth)
  const { allAuctions, isLoading, setBounds, setMapActive } = useAuctionMap()

  // UF Safety Lock - Check if UF is selected
  const currentUF = searchParams.get("uf")

  // IMPORTANT: All hooks must be called before any conditional returns!
  // Filter auctions with valid coordinates
  const markers: MarkerData[] = useMemo(() => {
    if (!allAuctions) return []
    return allAuctions
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
        tipo: getAuctionTipo(auction.tags),
      }))
  }, [allAuctions])

  // Calculate initial view from markers
  const initialView = useMemo(() => calculateViewFromMarkers(markers), [markers])

  // Create a stable key for remounting when markers change
  const markersKey = useMemo(
    () => markers.map((m) => m.auction.id).join(","),
    [markers]
  )

  // Handle marker click - open drawer or log
  const handleMarkerClick = useCallback((auction: Auction) => {
    console.log("Marker clicked:", auction)
  }, [])

  // Handle bounds change from map (sync with Grid)
  const handleBoundsChange = useCallback(
    (bounds: MapBounds) => {
      setBounds(bounds)
      setMapActive(true)
    },
    [setBounds, setMapActive]
  )

  // Requirement #1: UF Safety Lock
  // If no UF selected, render gray placeholder
  if (!currentUF) {
    return (
      <div className="h-[600px] w-full rounded-lg overflow-hidden border bg-zinc-100 dark:bg-zinc-900 flex items-center justify-center">
        <div className="text-center max-w-md px-4">
          <MapPin className="h-16 w-16 text-zinc-400 mx-auto mb-4" />
          <h3 className="text-lg font-semibold text-zinc-700 dark:text-zinc-300 mb-2">
            Selecione um Estado (UF)
          </h3>
          <p className="text-zinc-500 dark:text-zinc-400">
            Selecione um Estado (UF) para visualizar o mapa tático.
          </p>
        </div>
      </div>
    )
  }

  // Loading state
  if (isLoading) {
    return (
      <div className="h-[600px] w-full rounded-lg overflow-hidden border bg-zinc-50 dark:bg-zinc-900 flex items-center justify-center">
        <div className="text-center">
          <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-zinc-500 mx-auto mb-4" />
          <p className="text-zinc-500">Carregando mapa...</p>
        </div>
      </div>
    )
  }

  // No results with coordinates
  if (markers.length === 0) {
    return (
      <div className="h-[600px] w-full rounded-lg overflow-hidden border bg-zinc-100 dark:bg-zinc-900 flex items-center justify-center">
        <div className="text-center max-w-md px-4">
          <MapPin className="h-16 w-16 text-zinc-400 mx-auto mb-4" />
          <h3 className="text-lg font-semibold text-zinc-700 dark:text-zinc-300 mb-2">
            Sem dados geográficos
          </h3>
          <p className="text-zinc-500 dark:text-zinc-400">
            Os leilões encontrados não possuem coordenadas geográficas disponíveis.
            Tente usar a visualização em Grid.
          </p>
        </div>
      </div>
    )
  }

  return (
    <MapContent
      key={markersKey}
      markers={markers}
      initialView={initialView}
      onMarkerClick={handleMarkerClick}
      onBoundsChange={handleBoundsChange}
    />
  )
}
