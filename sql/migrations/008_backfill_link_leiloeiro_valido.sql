-- ============================================
-- Migration 008: Backfill link_leiloeiro_valido NULL
-- Data: 2026-01-27
-- Objetivo: Garantir que todo link tenha validacao TRUE/FALSE
-- ============================================
-- CONTRATO OPERACIONAL:
-- Para todo registro com link_leiloeiro presente e != 'N/D':
-- - link_leiloeiro_valido NAO PODE ser NULL
-- - Deve ser TRUE ou FALSE
--
-- HEURISTICA DE BACKFILL:
-- - Se link comeca com http:// ou https:// -> TRUE (estruturalmente valido)
-- - Se link comeca com www. -> TRUE
-- - Se link contem dominio conhecido (whitelist) -> TRUE
-- - Caso contrario -> FALSE (requer revisao manual)
-- ============================================

-- STEP 1: Ver estado ANTES
DO $$
DECLARE
    antes_null INTEGER;
    antes_true INTEGER;
    antes_false INTEGER;
BEGIN
    SELECT COUNT(*) INTO antes_null FROM editais_leilao
    WHERE link_leiloeiro IS NOT NULL AND link_leiloeiro != 'N/D' AND link_leiloeiro_valido IS NULL;

    SELECT COUNT(*) INTO antes_true FROM editais_leilao
    WHERE link_leiloeiro IS NOT NULL AND link_leiloeiro != 'N/D' AND link_leiloeiro_valido IS TRUE;

    SELECT COUNT(*) INTO antes_false FROM editais_leilao
    WHERE link_leiloeiro IS NOT NULL AND link_leiloeiro != 'N/D' AND link_leiloeiro_valido IS FALSE;

    RAISE NOTICE 'ANTES DO BACKFILL:';
    RAISE NOTICE '  link_leiloeiro_valido = NULL:  %', antes_null;
    RAISE NOTICE '  link_leiloeiro_valido = TRUE:  %', antes_true;
    RAISE NOTICE '  link_leiloeiro_valido = FALSE: %', antes_false;
END $$;

-- STEP 2: Listar os registros afetados (para auditoria)
-- SELECT id_interno, pncp_id, link_leiloeiro, link_leiloeiro_valido
-- FROM editais_leilao
-- WHERE link_leiloeiro IS NOT NULL AND link_leiloeiro != 'N/D' AND link_leiloeiro_valido IS NULL;

-- STEP 3: Backfill - Marcar como TRUE se estruturalmente valido
UPDATE editais_leilao
SET
    link_leiloeiro_valido = TRUE,
    link_leiloeiro_origem_ref = COALESCE(link_leiloeiro_origem_ref, '') || ' [backfill:008:estrutura_valida]'
WHERE
    link_leiloeiro IS NOT NULL
    AND link_leiloeiro != 'N/D'
    AND link_leiloeiro_valido IS NULL
    AND (
        link_leiloeiro ILIKE 'http://%'
        OR link_leiloeiro ILIKE 'https://%'
        OR link_leiloeiro ILIKE 'www.%'
    );

-- STEP 4: Backfill - Marcar restantes como FALSE (requer revisao)
UPDATE editais_leilao
SET
    link_leiloeiro_valido = FALSE,
    link_leiloeiro_origem_ref = COALESCE(link_leiloeiro_origem_ref, '') || ' [backfill:008:requer_revisao]'
WHERE
    link_leiloeiro IS NOT NULL
    AND link_leiloeiro != 'N/D'
    AND link_leiloeiro_valido IS NULL;

-- STEP 5: Ver estado DEPOIS
DO $$
DECLARE
    depois_null INTEGER;
    depois_true INTEGER;
    depois_false INTEGER;
BEGIN
    SELECT COUNT(*) INTO depois_null FROM editais_leilao
    WHERE link_leiloeiro IS NOT NULL AND link_leiloeiro != 'N/D' AND link_leiloeiro_valido IS NULL;

    SELECT COUNT(*) INTO depois_true FROM editais_leilao
    WHERE link_leiloeiro IS NOT NULL AND link_leiloeiro != 'N/D' AND link_leiloeiro_valido IS TRUE;

    SELECT COUNT(*) INTO depois_false FROM editais_leilao
    WHERE link_leiloeiro IS NOT NULL AND link_leiloeiro != 'N/D' AND link_leiloeiro_valido IS FALSE;

    RAISE NOTICE 'DEPOIS DO BACKFILL:';
    RAISE NOTICE '  link_leiloeiro_valido = NULL:  % (DEVE SER 0)', depois_null;
    RAISE NOTICE '  link_leiloeiro_valido = TRUE:  %', depois_true;
    RAISE NOTICE '  link_leiloeiro_valido = FALSE: %', depois_false;
END $$;

-- ============================================
-- CONSTRAINT: Garantir que NULL nao volte a acontecer
-- ============================================
-- NOTA: Constraint comentado para nao bloquear inserts legados.
-- Ativar apos confirmar que todo o pipeline esta atualizado.
--
-- ALTER TABLE editais_leilao ADD CONSTRAINT check_link_valido_not_null
-- CHECK (
--     link_leiloeiro IS NULL
--     OR link_leiloeiro = 'N/D'
--     OR link_leiloeiro_valido IS NOT NULL
-- );

-- ============================================
-- FIM DA MIGRATION 008
-- ============================================
