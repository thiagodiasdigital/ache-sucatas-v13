import { useQuery } from "@tanstack/react-query"
import { useSearchParams } from "react-router-dom"
import { supabase } from "../lib/supabase"
import type { Auction, AuctionFilters, PaginatedAuctionsResponse } from "../types/database"

const ITEMS_PER_PAGE = 20 // Atualizado para 20 conforme requisito

/**
 * Hook para buscar leilões com paginação server-side.
 * Usa URL Search Params como única fonte de verdade para os filtros.
 * Retorna dados paginados com contagem total.
 */
export function useAuctions() {
  const [searchParams] = useSearchParams()

  // Extrair página atual
  const currentPage = Number(searchParams.get("page")) || 1

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
    // Novos filtros de data com intervalo
    data_publicacao_de: searchParams.get("data_publicacao_de") || undefined,
    data_publicacao_ate: searchParams.get("data_publicacao_ate") || undefined,
    data_leilao_de: searchParams.get("data_leilao_de") || undefined,
    data_leilao_ate: searchParams.get("data_leilao_ate") || undefined,
  }

  return useQuery<PaginatedAuctionsResponse, Error>({
    queryKey: ["auctions", filters, currentPage],
    queryFn: async () => {
      // Chamar RPC com paginação
      const { data, error } = await supabase.rpc(
        "fetch_auctions_paginated" as never,
        {
          p_uf: filters.uf || null,
          p_cidade: filters.cidade || null,
          p_valor_min: filters.valor_min || null,
          p_valor_max: filters.valor_max || null,
          p_data_publicacao_de: filters.data_publicacao_de || null,
          p_data_publicacao_ate: filters.data_publicacao_ate || null,
          p_data_leilao_de: filters.data_leilao_de || null,
          p_data_leilao_ate: filters.data_leilao_ate || null,
          p_page: currentPage,
          p_page_size: ITEMS_PER_PAGE,
        } as never
      )

      if (error) {
        throw new Error(error.message)
      }

      // A RPC retorna JSON com { data, total, page, pageSize, totalPages }
      const result = data as PaginatedAuctionsResponse

      return {
        data: result.data || [],
        total: result.total || 0,
        page: result.page || currentPage,
        pageSize: result.pageSize || ITEMS_PER_PAGE,
        totalPages: result.totalPages || 1,
      }
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
