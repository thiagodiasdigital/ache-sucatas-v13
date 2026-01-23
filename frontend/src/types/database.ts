export type Json =
  | string
  | number
  | boolean
  | null
  | { [key: string]: Json | undefined }
  | Json[]

export interface Database {
  pub: {
    Tables: {
      ref_municipios: {
        Row: {
          codigo_ibge: number
          nome_municipio: string
          uf: string
          latitude: number | null
          longitude: number | null
          created_at: string
        }
        Insert: {
          codigo_ibge: number
          nome_municipio: string
          uf: string
          latitude?: number | null
          longitude?: number | null
          created_at?: string
        }
        Update: {
          codigo_ibge?: number
          nome_municipio?: string
          uf?: string
          latitude?: number | null
          longitude?: number | null
          created_at?: string
        }
      }
    }
    Views: {
      v_auction_discovery: {
        Row: {
          id: number
          id_interno: string
          pncp_id: string
          orgao: string | null
          uf: string | null
          cidade: string | null
          n_edital: string | null
          data_publicacao: string | null
          data_leilao: string | null
          titulo: string | null
          descricao: string | null
          objeto_resumido: string | null
          tags: string[] | null
          link_pncp: string | null
          link_leiloeiro: string | null
          modalidade_leilao: string | null
          valor_estimado: number | null
          quantidade_itens: number | null
          nome_leiloeiro: string | null
          storage_path: string | null
          score: number | null
          created_at: string
          codigo_ibge: number | null
          latitude: number | null
          longitude: number | null
          municipio_oficial: string | null
          status_temporal: 'futuro' | 'passado' | null
        }
      }
    }
    Functions: {
      fetch_auctions_audit: {
        Args: {
          filter_params?: Json
        }
        Returns: Database["pub"]["Views"]["v_auction_discovery"]["Row"][]
      }
      get_available_ufs: {
        Args: Record<string, never>
        Returns: {
          uf: string
          count: number
        }[]
      }
      get_cities_by_uf: {
        Args: {
          p_uf: string
        }
        Returns: {
          cidade: string
          count: number
        }[]
      }
      get_dashboard_stats: {
        Args: Record<string, never>
        Returns: {
          total_leiloes: number
          total_ufs: number
          total_cidades: number
          valor_total_estimado: number
          leiloes_proximos_7_dias: number
        }[]
      }
    }
  }
  audit: {
    Tables: {
      consumption_logs: {
        Row: {
          id: number
          user_id: string | null
          queried_at: string
          filter_applied: Json
          results_count: number | null
          response_time_ms: number | null
          ip_address: string | null
          user_agent: string | null
          session_id: string | null
          created_at: string
        }
        Insert: {
          user_id?: string | null
          queried_at?: string
          filter_applied?: Json
          results_count?: number | null
          response_time_ms?: number | null
          ip_address?: string | null
          user_agent?: string | null
          session_id?: string | null
          created_at?: string
        }
        Update: {
          user_id?: string | null
          queried_at?: string
          filter_applied?: Json
          results_count?: number | null
          response_time_ms?: number | null
          ip_address?: string | null
          user_agent?: string | null
          session_id?: string | null
          created_at?: string
        }
      }
    }
  }
}

// Tipo auxiliar para Auction
export type Auction = Database["pub"]["Views"]["v_auction_discovery"]["Row"]

// Tipo para filtros
export interface AuctionFilters {
  uf?: string
  cidade?: string
  valor_min?: number
  valor_max?: number
  data_inicio?: string
  data_fim?: string
  // Novos filtros de data com intervalo
  data_publicacao_de?: string
  data_publicacao_ate?: string
  data_leilao_de?: string
  data_leilao_ate?: string
  limit?: number
  offset?: number
}

// Tipo para resposta paginada
export interface PaginatedAuctionsResponse {
  data: Auction[]
  total: number
  page: number
  pageSize: number
  totalPages: number
  temporalidade?: string
}
