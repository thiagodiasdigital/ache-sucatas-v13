-- ============================================================
-- Migration: Auditor V19 - Campos de Proveniência e Quarentena
-- ============================================================
-- Data: 2026-01-21
-- Versão: V19_URL_GATE_PROVENIENCIA
-- 
-- Descrição:
--   Adiciona campos para rastreabilidade e quarentena de links
--   extraídos pelo Auditor, permitindo auditoria completa da
--   origem de cada link_leiloeiro.
--
-- Campos adicionados:
--   - link_leiloeiro_raw: candidato extraído antes da validação
--   - link_leiloeiro_valido: resultado do gate de validação
--   - link_leiloeiro_origem_tipo: fonte do link (pncp_api, pdf_anexo, etc)
--   - link_leiloeiro_origem_ref: referência completa (arquivo:página)
--   - link_leiloeiro_evidencia_trecho: trecho de texto que gerou o match
--   - link_leiloeiro_confianca: score de confiança (100=whitelist, 80=http, 60=www)
-- ============================================================

-- Adicionar novos campos na tabela editais_leilao
-- Cada campo é adicionado individualmente para compatibilidade

-- Campo: link_leiloeiro_raw
-- Armazena o candidato extraído ANTES da validação final
-- Permite auditoria mesmo de links rejeitados
ALTER TABLE editais_leilao
ADD COLUMN IF NOT EXISTS link_leiloeiro_raw TEXT;

COMMENT ON COLUMN editais_leilao.link_leiloeiro_raw IS 
'Candidato a URL extraído antes da validação final (V19). Permite auditoria de links rejeitados.';


-- Campo: link_leiloeiro_valido
-- Boolean indicando se o link passou no gate de validação
ALTER TABLE editais_leilao
ADD COLUMN IF NOT EXISTS link_leiloeiro_valido BOOLEAN DEFAULT NULL;

COMMENT ON COLUMN editais_leilao.link_leiloeiro_valido IS 
'Resultado do gate de validação V19: true=passou, false=rejeitado, null=não processado.';


-- Campo: link_leiloeiro_origem_tipo
-- Enum de texto indicando a fonte do link
-- Valores possíveis: pncp_api, pdf_anexo, pdf_edital, xlsx_anexo, csv_anexo, titulo_descricao, manual, unknown
ALTER TABLE editais_leilao
ADD COLUMN IF NOT EXISTS link_leiloeiro_origem_tipo TEXT;

COMMENT ON COLUMN editais_leilao.link_leiloeiro_origem_tipo IS 
'Fonte de extração do link: pncp_api | pdf_anexo | pdf_edital | xlsx_anexo | csv_anexo | titulo_descricao | manual | unknown';


-- Campo: link_leiloeiro_origem_ref
-- Referência completa da origem (arquivo, página, linha)
-- Exemplo: "pdf:Relacao_Lotes_2026_800100_1.pdf:page=143"
ALTER TABLE editais_leilao
ADD COLUMN IF NOT EXISTS link_leiloeiro_origem_ref TEXT;

COMMENT ON COLUMN editais_leilao.link_leiloeiro_origem_ref IS 
'Referência detalhada da origem: pdf:<arquivo>:page=<n> ou xlsx:<arquivo>:row=<n>:col=<c>';


-- Campo: link_leiloeiro_evidencia_trecho
-- Trecho curto do texto que gerou o match (limitado a 200 chars)
-- Útil para debug e validação manual
ALTER TABLE editais_leilao
ADD COLUMN IF NOT EXISTS link_leiloeiro_evidencia_trecho TEXT;

COMMENT ON COLUMN editais_leilao.link_leiloeiro_evidencia_trecho IS 
'Trecho do texto original que gerou o match (max 200 chars). Útil para auditoria.';


-- Campo: link_leiloeiro_confianca
-- Score de confiança do link (0-100)
-- 100 = whitelist, 80 = http(s), 60 = www, 0 = rejeitado
ALTER TABLE editais_leilao
ADD COLUMN IF NOT EXISTS link_leiloeiro_confianca SMALLINT;

COMMENT ON COLUMN editais_leilao.link_leiloeiro_confianca IS 
'Score de confiança: 100=whitelist, 80=http(s), 60=www, 0=rejeitado';


-- ============================================================
-- Índices para queries de auditoria
-- ============================================================

-- Índice para buscar links inválidos
CREATE INDEX IF NOT EXISTS idx_editais_link_valido 
ON editais_leilao(link_leiloeiro_valido) 
WHERE link_leiloeiro_valido = false;

-- Índice para buscar por tipo de origem
CREATE INDEX IF NOT EXISTS idx_editais_origem_tipo 
ON editais_leilao(link_leiloeiro_origem_tipo);

-- Índice para buscar por confiança baixa
CREATE INDEX IF NOT EXISTS idx_editais_confianca_baixa 
ON editais_leilao(link_leiloeiro_confianca) 
WHERE link_leiloeiro_confianca < 80;


-- ============================================================
-- Constraint de validação (opcional mas recomendado)
-- ============================================================

-- Garantir que origem_tipo seja um valor válido
ALTER TABLE editais_leilao
DROP CONSTRAINT IF EXISTS chk_origem_tipo_valido;

ALTER TABLE editais_leilao
ADD CONSTRAINT chk_origem_tipo_valido 
CHECK (
    link_leiloeiro_origem_tipo IS NULL 
    OR link_leiloeiro_origem_tipo IN (
        'pncp_api', 
        'pdf_anexo', 
        'pdf_edital', 
        'xlsx_anexo', 
        'csv_anexo', 
        'titulo_descricao', 
        'manual', 
        'unknown'
    )
);

-- Garantir que confiança esteja no range válido
ALTER TABLE editais_leilao
DROP CONSTRAINT IF EXISTS chk_confianca_range;

ALTER TABLE editais_leilao
ADD CONSTRAINT chk_confianca_range 
CHECK (
    link_leiloeiro_confianca IS NULL 
    OR (link_leiloeiro_confianca >= 0 AND link_leiloeiro_confianca <= 100)
);


-- ============================================================
-- Atualizar registros existentes com link_leiloeiro preenchido
-- Marca como "unknown" para origem, já que foram processados
-- por versões anteriores do Auditor
-- ============================================================

UPDATE editais_leilao
SET 
    link_leiloeiro_valido = true,
    link_leiloeiro_origem_tipo = 'unknown',
    link_leiloeiro_confianca = 50  -- Confiança média (processado antes do V19)
WHERE 
    link_leiloeiro IS NOT NULL 
    AND link_leiloeiro != ''
    AND link_leiloeiro != 'N/D'
    AND link_leiloeiro_valido IS NULL;


-- ============================================================
-- View para auditoria de links
-- ============================================================

CREATE OR REPLACE VIEW pub.v_link_leiloeiro_auditoria AS
SELECT 
    pncp_id,
    titulo,
    link_leiloeiro,
    link_leiloeiro_raw,
    link_leiloeiro_valido,
    link_leiloeiro_origem_tipo,
    link_leiloeiro_origem_ref,
    link_leiloeiro_evidencia_trecho,
    link_leiloeiro_confianca,
    versao_auditor,
    updated_at
FROM editais_leilao
WHERE 
    link_leiloeiro IS NOT NULL 
    OR link_leiloeiro_raw IS NOT NULL
ORDER BY updated_at DESC;

COMMENT ON VIEW pub.v_link_leiloeiro_auditoria IS 
'View para auditoria de links de leiloeiro com campos de proveniência V19';


-- ============================================================
-- Função para identificar falsos positivos conhecidos
-- ============================================================

CREATE OR REPLACE FUNCTION pub.identificar_falsos_positivos()
RETURNS TABLE (
    pncp_id TEXT,
    link_leiloeiro TEXT,
    motivo TEXT
) AS $$
BEGIN
    RETURN QUERY
    SELECT 
        e.pncp_id,
        e.link_leiloeiro,
        CASE 
            -- Padrão: TLD colado em palavra (ex: venezuelano-ed.com)
            WHEN e.link_leiloeiro ~* '[a-z]-[a-z]+\.(com|net|org)[a-z]' 
            THEN 'tld_colado_em_palavra'
            -- Domínios claramente inválidos
            WHEN e.link_leiloeiro ILIKE '%venezuelano%'
            THEN 'dominio_invalido_conhecido'
            -- URLs sem path que não são de leilão
            WHEN e.link_leiloeiro !~* '(leilao|leiloes|leil|bid|lance|franca|sold|hasta)'
                AND e.link_leiloeiro !~* '\.(com\.br|net\.br)/'
            THEN 'dominio_sem_indicador_leilao'
            ELSE 'verificar_manualmente'
        END as motivo
    FROM editais_leilao e
    WHERE 
        e.link_leiloeiro IS NOT NULL
        AND e.link_leiloeiro != ''
        AND e.link_leiloeiro != 'N/D'
        AND (
            -- Critérios de falso positivo
            e.link_leiloeiro ~* '[a-z]-[a-z]+\.(com|net|org)[a-z]'
            OR e.link_leiloeiro ILIKE '%venezuelano%'
            OR (
                e.link_leiloeiro !~* '(leilao|leiloes|leil|bid|lance|franca|sold|hasta)'
                AND e.link_leiloeiro_origem_tipo IS NULL  -- Não processado pelo V19
            )
        );
END;
$$ LANGUAGE plpgsql;

COMMENT ON FUNCTION pub.identificar_falsos_positivos() IS 
'Identifica registros com link_leiloeiro potencialmente inválido para saneamento';


-- ============================================================
-- Fim da migration
-- ============================================================

-- Log da migration
DO $$
BEGIN
    RAISE NOTICE 'Migration V19_URL_GATE_PROVENIENCIA aplicada com sucesso';
    RAISE NOTICE 'Campos adicionados: link_leiloeiro_raw, link_leiloeiro_valido, link_leiloeiro_origem_tipo, link_leiloeiro_origem_ref, link_leiloeiro_evidencia_trecho, link_leiloeiro_confianca';
END $$;
