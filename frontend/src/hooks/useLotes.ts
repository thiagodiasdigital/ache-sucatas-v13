import { useQuery } from "@tanstack/react-query"
import { supabase } from "../lib/supabase"
import type { Lote } from "../types/database"

/**
 * Hook para buscar lotes de um edital específico.
 * Usa RPC get_lotes_by_id_interno para resolver incompatibilidade
 * entre raw.leiloes.id e editais_leilao.id.
 *
 * @param idInterno - id_interno do edital (campo único compartilhado)
 * @returns { lotes, isLoading, error, totalLotes }
 */
export function useLotes(idInterno: string | null) {
  const query = useQuery<Lote[], Error>({
    queryKey: ["lotes", idInterno],
    queryFn: async () => {
      if (!idInterno) return []

      // eslint-disable-next-line @typescript-eslint/no-explicit-any
      const { data, error } = await supabase
        .rpc("get_lotes_by_id_interno", { p_id_interno: idInterno } as any)

      if (error) {
        throw new Error(error.message)
      }

      return (data as Lote[]) || []
    },
    enabled: !!idInterno,
    staleTime: 1000 * 60 * 5, // 5 minutos
  })

  return {
    lotes: query.data || [],
    isLoading: query.isLoading,
    error: query.error,
    totalLotes: query.data?.length || 0,
  }
}

/**
 * Gera um preview resumido dos lotes para exibir no card.
 * Formato: "Lote 1: Fiat Uno 2010, Lote 2: VW Gol 2015..."
 *
 * @param lotes - Lista de lotes
 * @param maxChars - Máximo de caracteres (padrão: 100)
 * @returns String resumida dos lotes
 */
export function getLotesPreview(lotes: Lote[], maxChars: number = 100): string {
  if (!lotes || lotes.length === 0) {
    return "Sem lotes cadastrados"
  }

  const previews = lotes.map((lote) => {
    const partes: string[] = []

    // Número do lote
    if (lote.numero_lote) {
      partes.push(lote.numero_lote)
    }

    // Marca/Modelo/Ano se disponível
    if (lote.marca || lote.modelo) {
      const veiculo = [lote.marca, lote.modelo, lote.ano_fabricacao]
        .filter(Boolean)
        .join(" ")
      if (veiculo) partes.push(veiculo)
    } else if (lote.descricao_completa) {
      // Fallback: primeiros 30 chars da descrição
      partes.push(lote.descricao_completa.substring(0, 30))
    }

    return partes.join(": ")
  })

  const texto = previews.join(" | ")

  if (texto.length <= maxChars) {
    return texto
  }

  return texto.substring(0, maxChars - 3) + "..."
}

/**
 * Formata o valor do lote para exibição.
 *
 * @param valor - Valor numérico
 * @returns String formatada em BRL
 */
export function formatLoteValor(valor: number | null): string {
  if (valor === null || valor === undefined) {
    return "Valor não informado"
  }

  return new Intl.NumberFormat("pt-BR", {
    style: "currency",
    currency: "BRL",
  }).format(valor)
}
