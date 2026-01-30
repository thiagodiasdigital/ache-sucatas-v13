/**
 * Edital URL Utility
 *
 * Gera URLs para visualização de editais.
 * Prioriza o Storage interno, com fallback para PNCP.
 */

const SUPABASE_URL = import.meta.env.VITE_SUPABASE_URL
const BUCKET_NAME = 'editais-pdfs'

/**
 * Gera URL para visualização do edital.
 *
 * Estratégia:
 * 1. Se tem storage_path → URL do Supabase Storage (interno)
 * 2. Se não tem storage_path mas tem pncp_id → URL do PNCP (fallback)
 * 3. Se não tem nenhum → null
 *
 * @param storage_path - Caminho do PDF no Supabase Storage
 * @param pncp_id - ID do edital no PNCP (fallback)
 * @returns URL do edital ou null se indisponível
 *
 * @example
 * getEditalUrl("05182233000176-1-000009/2026/EDITAL.pdf", null)
 * // => "https://xxx.supabase.co/storage/v1/object/public/editais-pdfs/05182233000176-1-000009/2026/EDITAL.pdf"
 *
 * @example
 * getEditalUrl(null, "05182233000176-1-000009/2026")
 * // => "https://pncp.gov.br/app/editais/05182233000176/2026/9" (fallback)
 */
export const getEditalUrl = (
  storage_path: string | null | undefined,
  pncp_id: string | null | undefined
): string | null => {
  // Prioridade 1: Storage interno
  if (storage_path && storage_path.trim() !== '') {
    return `${SUPABASE_URL}/storage/v1/object/public/${BUCKET_NAME}/${storage_path}`
  }

  // Prioridade 2: Fallback para PNCP
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
