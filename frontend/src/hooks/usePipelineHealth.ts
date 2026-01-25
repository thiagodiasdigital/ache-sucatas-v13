import { useQuery } from "@tanstack/react-query"
import { supabase } from "../lib/supabase"

/**
 * Tipos para o Dashboard de Saude do Pipeline
 */
export interface MinerExecution {
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

export interface TopReasonCode {
  reason_code: string
  total: number
  percentual: number
}

export interface PipelineEvent {
  id: number
  run_id: string
  etapa: string
  evento: string
  nivel: string
  mensagem: string | null
  created_at: string
}

export interface HealthMetrics {
  totalExecutions: number
  totalProcessados: number
  totalValidos: number
  totalQuarentena: number
  taxaValidosMedia: number
  taxaQuarentenaMedia: number
  custoTotal: number
}

/**
 * Hook para buscar ultimas execucoes do miner
 */
export function useExecutions(limit = 10) {
  return useQuery({
    queryKey: ["pipeline-executions", limit],
    queryFn: async () => {
      const { data, error } = await supabase
        .from("miner_execucoes")
        .select("*")
        .order("inicio", { ascending: false })
        .limit(limit)

      if (error) throw error
      return data as MinerExecution[]
    },
    refetchInterval: 30000, // Atualiza a cada 30s
  })
}

/**
 * Hook para buscar top reason codes (ultimos 7 dias)
 */
export function useTopReasonCodes(limit = 10) {
  return useQuery({
    queryKey: ["top-reason-codes", limit],
    queryFn: async () => {
      // Buscar da view vw_top_reason_codes ou fazer query direta
      const { data, error } = await supabase
        .from("dataset_rejections")
        .select("reason_code")
        .gte("created_at", new Date(Date.now() - 7 * 24 * 60 * 60 * 1000).toISOString())

      if (error) throw error

      // Agregar no cliente
      const counts: Record<string, number> = {}
      const rows = data as { reason_code: string | null }[] | null
      rows?.forEach((row) => {
        const code = row.reason_code || "unknown"
        counts[code] = (counts[code] || 0) + 1
      })

      const total = Object.values(counts).reduce((a, b) => a + b, 0)
      const result: TopReasonCode[] = Object.entries(counts)
        .map(([code, count]) => ({
          reason_code: code,
          total: count,
          percentual: total > 0 ? Math.round((count / total) * 100 * 100) / 100 : 0,
        }))
        .sort((a, b) => b.total - a.total)
        .slice(0, limit)

      return result
    },
    refetchInterval: 60000, // Atualiza a cada 1 minuto
  })
}

/**
 * Hook para buscar eventos recentes do pipeline
 */
export function usePipelineEvents(limit = 20) {
  return useQuery({
    queryKey: ["pipeline-events", limit],
    queryFn: async () => {
      const { data, error } = await supabase
        .from("pipeline_events")
        .select("*")
        .order("created_at", { ascending: false })
        .limit(limit)

      if (error) throw error
      return data as PipelineEvent[]
    },
    refetchInterval: 15000, // Atualiza a cada 15s
  })
}

/**
 * Hook para calcular metricas agregadas
 */
export function useHealthMetrics() {
  return useQuery({
    queryKey: ["health-metrics"],
    queryFn: async () => {
      // Buscar ultimas 30 execucoes para calcular medias
      const { data, error } = await supabase
        .from("miner_execucoes")
        .select("*")
        .order("inicio", { ascending: false })
        .limit(30)

      if (error) throw error

      const executions = data as MinerExecution[]

      if (executions.length === 0) {
        return {
          totalExecutions: 0,
          totalProcessados: 0,
          totalValidos: 0,
          totalQuarentena: 0,
          taxaValidosMedia: 0,
          taxaQuarentenaMedia: 0,
          custoTotal: 0,
        } as HealthMetrics
      }

      const metrics: HealthMetrics = {
        totalExecutions: executions.length,
        totalProcessados: executions.reduce((sum, e) => sum + (e.total_processados || 0), 0),
        totalValidos: executions.reduce((sum, e) => sum + (e.total_validos || 0), 0),
        totalQuarentena: executions.reduce((sum, e) => sum + (e.total_quarentena || 0), 0),
        taxaValidosMedia:
          executions.reduce((sum, e) => sum + (e.taxa_validos_percent || 0), 0) / executions.length,
        taxaQuarentenaMedia:
          executions.reduce((sum, e) => sum + (e.taxa_quarentena_percent || 0), 0) / executions.length,
        custoTotal: executions.reduce((sum, e) => sum + (e.cost_estimated_total || 0), 0),
      }

      return metrics
    },
    refetchInterval: 60000,
  })
}
