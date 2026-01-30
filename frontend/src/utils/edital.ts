/**
 * Edital URL Utility
 *
 * Gera URLs para visualização de editais.
 * Prioriza o Storage interno, com fallback para link_edital ou PNCP.
 */

const SUPABASE_URL = import.meta.env.VITE_SUPABASE_URL
const BUCKET_NAME = 'editais-pdfs'

/**
 * Gera URL para visualização do edital.
 *
 * Estratégia de prioridade:
 * 1. Se tem storage_path → URL do Supabase Storage (interno)
 * 2. Se tem link_edital → URL direta do edital (leiloeiros externos)
 * 3. Se tem pncp_id → URL do PNCP (fallback)
 * 4. Se não tem nenhum → null
 *
 * @param storage_path - Caminho do PDF no Supabase Storage
 * @param pncp_id - ID do edital no PNCP (fallback)
 * @param link_edital - URL direta do edital (usado por leiloeiros externos)
 * @returns URL do edital ou null se indisponível
 *
 * @example
 * // Storage interno (PNCP)
 * getEditalUrl("05182233000176-1-000009/2026/EDITAL.pdf", null, null)
 * // => "https://xxx.supabase.co/storage/v1/object/public/editais-pdfs/..."
 *
 * @example
 * // Link direto de leiloeiro externo
 * getEditalUrl(null, null, "https://leiloesjudiciais.com.br/edital/123.pdf")
 * // => "https://leiloesjudiciais.com.br/edital/123.pdf"
 *
 * @example
 * // Fallback para PNCP
 * getEditalUrl(null, "05182233000176-1-000009/2026", null)
 * // => "https://pncp.gov.br/app/editais/05182233000176/2026/9"
 */
export const getEditalUrl = (
  storage_path: string | null | undefined,
  pncp_id: string | null | undefined,
  link_edital?: string | null
): string | null => {
  // Prioridade 1: Storage interno
  if (storage_path && storage_path.trim() !== '') {
    return `${SUPABASE_URL}/storage/v1/object/public/${BUCKET_NAME}/${storage_path}`
  }

  // Prioridade 2: Link direto do edital (leiloeiros externos)
  if (link_edital && link_edital.trim() !== '') {
    return link_edital.trim()
  }

  // Prioridade 3: Fallback para PNCP
  if (pncp_id && pncp_id.trim() !== '') {
    return getPncpLinkFromId(pncp_id)
  }

  // Sem fonte disponível
  return null
}

/**
 * Converte pncp_id em URL do portal PNCP.
 * Função interna para fallback - não exposta ao usuário.
 *
 * @param pncpId - ID no formato "CNPJ-1-SEQUENCIAL-ANO" ou "CNPJ-1-SEQUENCIAL/ANO"
 * @returns URL do edital no PNCP
 */
function getPncpLinkFromId(pncpId: string): string | null {
  if (!pncpId) return null

  // Normalizar separadores
  const normalized = pncpId.replace(/\//g, '-')
  const parts = normalized.split('-')

  if (parts.length < 4) {
    console.warn(`[Edital] pncp_id com formato inesperado: ${pncpId}`)
    return null
  }

  const cnpj = parts[0]
  const ano = parts[parts.length - 1]
  const sequencial = parts[parts.length - 2]

  // Validações básicas
  if (cnpj.length !== 14) return null
  if (ano.length !== 4) return null
  if (!sequencial) return null

  // Remover zeros à esquerda do sequencial
  const cleanSequencial = sequencial.replace(/^0+/, '') || '0'

  return `https://pncp.gov.br/app/editais/${cnpj}/${ano}/${cleanSequencial}`
}
