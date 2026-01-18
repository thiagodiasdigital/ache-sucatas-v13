import { useQuery } from "@tanstack/react-query"
import { useSearchParams } from "react-router-dom"
import { supabase } from "../lib/supabase"
import type { Auction, AuctionFilters } from "../types/database"

const ITEMS_PER_PAGE = 12

/**
 * Hook para buscar leilões com auditoria.
 * Usa URL Search Params como única fonte de verdade para os filtros.
 */
export function useAuctions() {
  const [searchParams] = useSearchParams()

  // Extrair filtros da URL
  const filters: AuctionFilters = {
    uf: searchParams.get("uf") || undefined,
    cidade: searchParams.get("cidade") || undefined,
    valor_min: searchParams.get("valor_min")
      ? Number(searchParams.get("valor_min"))
      : undefined,
    valor_max: searchParams.get("valor_max")
      ? Number(searchParams.get("valor_max"))
      : undefined,
    data_inicio: searchParams.get("data_inicio") || undefined,
    data_fim: searchParams.get("data_fim") || undefined,
    limit: ITEMS_PER_PAGE,
    offset: searchParams.get("page")
      ? (Number(searchParams.get("page")) - 1) * ITEMS_PER_PAGE
      : 0,
  }

  return useQuery<Auction[], Error>({
    queryKey: ["auctions", filters],
    queryFn: async () => {
      // Usar a RPC com auditoria
      const { data, error } = await supabase.rpc(
        "fetch_auctions_audit" as never,
        { filter_params: filters } as never
      )

      if (error) {
        throw new Error(error.message)
      }

      return data as Auction[]
    },
    staleTime: 1000 * 60 * 5, // 5 minutos
  })
}

/**
 * Hook para buscar UFs disponíveis
 */
export function useAvailableUFs() {
  return useQuery({
    queryKey: ["available-ufs"],
    queryFn: async () => {
      const { data, error } = await supabase.rpc("get_available_ufs" as never)

      if (error) {
        throw new Error(error.message)
      }

      return data as { uf: string; count: number }[]
    },
    staleTime: 1000 * 60 * 30, // 30 minutos
  })
}

/**
 * Hook para buscar cidades de uma UF
 */
export function useCitiesByUF(uf: string | undefined) {
  return useQuery({
    queryKey: ["cities", uf],
    queryFn: async () => {
      if (!uf) return []

      const { data, error } = await supabase.rpc(
        "get_cities_by_uf" as never,
        { p_uf: uf } as never
      )

      if (error) {
        throw new Error(error.message)
      }

      return data as { cidade: string; count: number }[]
    },
    enabled: !!uf,
    staleTime: 1000 * 60 * 30, // 30 minutos
  })
}

/**
 * Hook para buscar estatísticas do dashboard
 */
export function useDashboardStats() {
  return useQuery({
    queryKey: ["dashboard-stats"],
    queryFn: async () => {
      const { data, error } = await supabase.rpc("get_dashboard_stats" as never)

      if (error) {
        throw new Error(error.message)
      }

      return (data as { total_leiloes: number; total_ufs: number; total_cidades: number; valor_total_estimado: number; leiloes_proximos_7_dias: number }[])?.[0]
    },
    staleTime: 1000 * 60 * 5, // 5 minutos
  })
}
