export type Json =
  | string
  | number
  | boolean
  | null
  | { [key: string]: Json | undefined }
  | Json[]

export interface Database {
  public: {
    Tables: {
      pipeline_alerts: {
        Row: {
          id: number
          run_id: string | null
          execucao_id: number | null
          tipo: string
          severidade: "info" | "warning" | "critical"
          titulo: string
          mensagem: string
          dados: Json
          status: "open" | "acknowledged" | "resolved"
          created_at: string
          acknowledged_at: string | null
          resolved_at: string | null
        }
        Insert: {
          run_id?: string | null
          execucao_id?: number | null
          tipo: string
          severidade: "info" | "warning" | "critical"
          titulo: string
          mensagem: string
          dados?: Json
          status?: "open" | "acknowledged" | "resolved"
          created_at?: string
          acknowledged_at?: string | null
          resolved_at?: string | null
        }
        Update: {
          run_id?: string | null
          execucao_id?: number | null
          tipo?: string
          severidade?: "info" | "warning" | "critical"
          titulo?: string
          mensagem?: string
          dados?: Json
          status?: "open" | "acknowledged" | "resolved"
          created_at?: string
          acknowledged_at?: string | null
          resolved_at?: string | null
        }
      }
      miner_execucoes: {
        Row: {
          id: number
          run_id: string | null
          versao_miner: string
          modo_processamento: string
          inicio: string
          fim: string | null
          status: string
          editais_encontrados: number
          editais_novos: number
          editais_skip_existe: number
          erros: number
          total_processados: number
          total_validos: number
          total_quarentena: number
          taxa_validos_percent: number
          taxa_quarentena_percent: number
          duracao_segundos: number
          cost_estimated_total: number
          cost_openai_estimated: number
        }
        Insert: {
          run_id?: string | null
          versao_miner: string
          modo_processamento: string
          inicio: string
          fim?: string | null
          status: string
          editais_encontrados?: number
          editais_novos?: number
          editais_skip_existe?: number
          erros?: number
          total_processados?: number
          total_validos?: number
          total_quarentena?: number
          taxa_validos_percent?: number
          taxa_quarentena_percent?: number
          duracao_segundos?: number
          cost_estimated_total?: number
          cost_openai_estimated?: number
        }
        Update: {
          run_id?: string | null
          versao_miner?: string
          modo_processamento?: string
          inicio?: string
          fim?: string | null
          status?: string
          editais_encontrados?: number
          editais_novos?: number
          editais_skip_existe?: number
          erros?: number
          total_processados?: number
          total_validos?: number
          total_quarentena?: number
          taxa_validos_percent?: number
          taxa_quarentena_percent?: number
          duracao_segundos?: number
          cost_estimated_total?: number
          cost_openai_estimated?: number
        }
      }
      pipeline_events: {
        Row: {
          id: number
          run_id: string
          etapa: string
          evento: string
          nivel: string
          mensagem: string | null
          created_at: string
        }
        Insert: {
          run_id: string
          etapa: string
          evento: string
          nivel: string
          mensagem?: string | null
          created_at?: string
        }
        Update: {
          run_id?: string
          etapa?: string
          evento?: string
          nivel?: string
          mensagem?: string | null
          created_at?: string
        }
      }
      dataset_rejections: {
        Row: {
          id: number
          reason_code: string | null
          created_at: string
        }
        Insert: {
          reason_code?: string | null
          created_at?: string
        }
        Update: {
          reason_code?: string | null
          created_at?: string
        }
      }
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
      lotes_leilao: {
        Row: {
          id: number
          id_interno: string
          edital_id: number
          numero_lote_raw: string | null
          numero_lote: string
          descricao_raw: string | null
          descricao_completa: string
          valor_raw: string | null
          avaliacao_valor: number | null
          texto_fonte_completo: string | null
          placa: string | null
          chassi: string | null
          renavam: string | null
          marca: string | null
          modelo: string | null
          ano_fabricacao: number | null
          categoria_id: string | null
          tipo_venda: string | null
          confidence_score: number | null
          fonte_tipo: string | null
          fonte_arquivo: string | null
          fonte_pagina: number | null
          hash_conteudo_fonte: string | null
          versao_extrator: string | null
          familia_pdf: string | null
          data_extracao: string | null
          created_at: string
          updated_at: string
        }
        Insert: {
          id_interno: string
          edital_id: number
          numero_lote: string
          descricao_completa: string
          numero_lote_raw?: string | null
          descricao_raw?: string | null
          valor_raw?: string | null
          avaliacao_valor?: number | null
          texto_fonte_completo?: string | null
          placa?: string | null
          chassi?: string | null
          renavam?: string | null
          marca?: string | null
          modelo?: string | null
          ano_fabricacao?: number | null
          categoria_id?: string | null
          tipo_venda?: string | null
          confidence_score?: number | null
          fonte_tipo?: string | null
          fonte_arquivo?: string | null
          fonte_pagina?: number | null
          hash_conteudo_fonte?: string | null
          versao_extrator?: string | null
          familia_pdf?: string | null
          data_extracao?: string | null
          created_at?: string
          updated_at?: string
        }
        Update: {
          id_interno?: string
          edital_id?: number
          numero_lote?: string
          descricao_completa?: string
          numero_lote_raw?: string | null
          descricao_raw?: string | null
          valor_raw?: string | null
          avaliacao_valor?: number | null
          texto_fonte_completo?: string | null
          placa?: string | null
          chassi?: string | null
          renavam?: string | null
          marca?: string | null
          modelo?: string | null
          ano_fabricacao?: number | null
          categoria_id?: string | null
          tipo_venda?: string | null
          confidence_score?: number | null
          fonte_tipo?: string | null
          fonte_arquivo?: string | null
          fonte_pagina?: number | null
          hash_conteudo_fonte?: string | null
          versao_extrator?: string | null
          familia_pdf?: string | null
          data_extracao?: string | null
          created_at?: string
          updated_at?: string
        }
      }
    }
    Views: {
      v_auction_discovery: {
        Row: {
          id: number
          id_interno: string
          pncp_id: string | null
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
          // NOVO: link_edital para UI limpa (alias de link_pncp)
          link_edital: string | null
          // MANTIDO: link_pncp para compatibilidade temporária
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
          // Novos campos para diferenciação de origem
          source_type: 'pncp' | 'leiloeiro' | null
          source_name: string | null
          metadata: Json | null
        }
      }
    }
    Functions: {
      fetch_auctions_audit: {
        Args: {
          filter_params?: Json
        }
        Returns: Database["public"]["Views"]["v_auction_discovery"]["Row"][]
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
      get_lotes_by_id_interno: {
        Args: {
          p_id_interno: string
        }
        Returns: Database["public"]["Tables"]["lotes_leilao"]["Row"][]
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
export type Auction = Database["public"]["Views"]["v_auction_discovery"]["Row"]

// Tipo auxiliar para Lote
export type Lote = Database["public"]["Tables"]["lotes_leilao"]["Row"]

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
