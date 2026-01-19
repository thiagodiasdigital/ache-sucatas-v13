/**
 * PNCP Link Utility
 *
 * REGRA IMUTAVEL (NUNCA ALTERAR):
 * Formato do link PNCP: https://pncp.gov.br/app/editais/{CNPJ}/{ANO}/{SEQUENCIAL}
 *
 * ERRADO: /CNPJ/1/SEQUENCIAL/ANO (NUNCA usar este formato)
 * CORRETO: /CNPJ/ANO/SEQUENCIAL (SEMPRE usar este formato)
 */

/**
 * Gera link PNCP no formato oficial correto.
 *
 * @param cnpj - CNPJ do orgao (14 digitos, com ou sem formatacao)
 * @param ano - Ano da compra (4 digitos)
 * @param sequencial - Numero sequencial da compra
 * @returns URL completa do edital no PNCP ou string vazia se dados invalidos
 *
 * @example
 * getPncpLink("18188243000160", "2025", "161")
 * // => "https://pncp.gov.br/app/editais/18188243000160/2025/161"
 */
export const getPncpLink = (
  cnpj: string,
  ano: string | number,
  sequencial: string | number
): string => {
  // REGRA IMUTAVEL: CNPJ / ANO / SEQUENCIAL

  // Limpar CNPJ - remover tudo que nao for numero
  const cleanCnpj = String(cnpj || '').replace(/\D/g, '');

  // Validar CNPJ (deve ter 14 digitos)
  if (cleanCnpj.length !== 14) {
    console.warn(`[PNCP] CNPJ invalido: ${cnpj} (esperado 14 digitos, recebido ${cleanCnpj.length})`);
    return '';
  }

  // Limpar e validar ano
  const cleanAno = String(ano || '').trim();
  if (!/^\d{4}$/.test(cleanAno)) {
    console.warn(`[PNCP] Ano invalido: ${ano} (esperado 4 digitos)`);
    return '';
  }

  // Limpar sequencial - remover zeros a esquerda
  const cleanSequencial = String(sequencial || '').trim().replace(/^0+/, '') || '0';
  if (!cleanSequencial) {
    console.warn(`[PNCP] Sequencial invalido: ${sequencial}`);
    return '';
  }

  // FORMATO CORRETO: /CNPJ/ANO/SEQUENCIAL
  return `https://pncp.gov.br/app/editais/${cleanCnpj}/${cleanAno}/${cleanSequencial}`;
};

/**
 * Extrai CNPJ, ANO e SEQUENCIAL de um pncp_id e gera link correto.
 *
 * @param pncpId - ID no formato "CNPJ-1-SEQUENCIAL-ANO" ou "CNPJ-1-SEQUENCIAL/ANO"
 * @returns URL completa do edital no PNCP ou string vazia se formato invalido
 *
 * @example
 * getPncpLinkFromId("18188243000160-1-000161-2025")
 * // => "https://pncp.gov.br/app/editais/18188243000160/2025/161"
 */
export const getPncpLinkFromId = (pncpId: string): string => {
  if (!pncpId) return '';

  // Normalizar separadores
  const normalized = pncpId.replace(/\//g, '-');

  // Dividir por hifen
  const parts = normalized.split('-');

  // Esperamos pelo menos 4 partes: CNPJ, algo, SEQUENCIAL, ANO
  if (parts.length < 4) {
    console.warn(`[PNCP] pncp_id com formato inesperado: ${pncpId}`);
    return '';
  }

  const cnpj = parts[0];        // 18188243000160
  const sequencial = parts[2];  // 000161
  const ano = parts[3];         // 2025

  return getPncpLink(cnpj, ano, sequencial);
};
