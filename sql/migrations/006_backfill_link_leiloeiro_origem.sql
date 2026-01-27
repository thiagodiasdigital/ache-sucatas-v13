-- ============================================
-- Migration 006: Backfill link_leiloeiro_origem_tipo
-- Data: 2026-01-27
-- Objetivo: Preencher origem dos links existentes com heuristica
-- ============================================
-- PROBLEMA:
-- A coluna link_leiloeiro_origem_tipo estava sendo setada como 'unknown'
-- mesmo para editais que tinham link vindo do Miner (pncp_api).
--
-- SOLUCAO:
-- 1. Editais COM link_leiloeiro preenchido E origem_tipo NULL -> pncp_api (Miner setou o link)
-- 2. Editais COM link_leiloeiro preenchido E origem_tipo 'unknown' E auditor_v19_result='found_link' -> pdf_anexo
-- 3. Editais SEM link_leiloeiro E auditor_v19_result='no_link' -> manter NULL (processado sem encontrar)
-- ============================================

-- STEP 1: Registrar estado ANTES (para auditoria)
DO $$
DECLARE
    antes_unknown INTEGER;
    antes_null INTEGER;
    antes_pncp_api INTEGER;
    antes_pdf_anexo INTEGER;
BEGIN
    SELECT COUNT(*) INTO antes_unknown FROM editais_leilao WHERE link_leiloeiro_origem_tipo = 'unknown';
    SELECT COUNT(*) INTO antes_null FROM editais_leilao WHERE link_leiloeiro_origem_tipo IS NULL;
    SELECT COUNT(*) INTO antes_pncp_api FROM editais_leilao WHERE link_leiloeiro_origem_tipo = 'pncp_api';
    SELECT COUNT(*) INTO antes_pdf_anexo FROM editais_leilao WHERE link_leiloeiro_origem_tipo = 'pdf_anexo';

    RAISE NOTICE 'ANTES DO BACKFILL:';
    RAISE NOTICE '  origem_tipo=unknown: %', antes_unknown;
    RAISE NOTICE '  origem_tipo=NULL: %', antes_null;
    RAISE NOTICE '  origem_tipo=pncp_api: %', antes_pncp_api;
    RAISE NOTICE '  origem_tipo=pdf_anexo: %', antes_pdf_anexo;
END $$;

-- STEP 2: Backfill para editais COM link mas origem NULL
-- Esses vieram do Miner via API PNCP
UPDATE editais_leilao
SET
    link_leiloeiro_origem_tipo = 'pncp_api',
    link_leiloeiro_origem_ref = 'backfill:006:pncp_api_heuristica'
WHERE
    link_leiloeiro IS NOT NULL
    AND link_leiloeiro != 'N/D'
    AND link_leiloeiro_origem_tipo IS NULL;

-- STEP 3: Backfill para editais COM link E origem='unknown' E found_link
-- O Auditor encontrou link no PDF mas marcou unknown erroneamente
UPDATE editais_leilao
SET
    link_leiloeiro_origem_tipo = 'pdf_anexo',
    link_leiloeiro_origem_ref = 'backfill:006:auditor_found_link'
WHERE
    link_leiloeiro IS NOT NULL
    AND link_leiloeiro != 'N/D'
    AND link_leiloeiro_origem_tipo = 'unknown'
    AND auditor_v19_result = 'found_link';

-- STEP 4: Para editais COM link E origem='unknown' mas SEM auditor_v19_result
-- Provavelmente vieram do Miner
UPDATE editais_leilao
SET
    link_leiloeiro_origem_tipo = 'pncp_api',
    link_leiloeiro_origem_ref = 'backfill:006:presumido_pncp_api'
WHERE
    link_leiloeiro IS NOT NULL
    AND link_leiloeiro != 'N/D'
    AND link_leiloeiro_origem_tipo = 'unknown'
    AND (auditor_v19_result IS NULL OR auditor_v19_result NOT IN ('found_link', 'no_link'));

-- STEP 5: Limpar origem='unknown' de editais SEM link
-- Esses devem ter origem NULL, nao unknown
UPDATE editais_leilao
SET
    link_leiloeiro_origem_tipo = NULL
WHERE
    (link_leiloeiro IS NULL OR link_leiloeiro = 'N/D')
    AND link_leiloeiro_origem_tipo = 'unknown';

-- STEP 6: Registrar estado DEPOIS
DO $$
DECLARE
    depois_unknown INTEGER;
    depois_null INTEGER;
    depois_pncp_api INTEGER;
    depois_pdf_anexo INTEGER;
BEGIN
    SELECT COUNT(*) INTO depois_unknown FROM editais_leilao WHERE link_leiloeiro_origem_tipo = 'unknown';
    SELECT COUNT(*) INTO depois_null FROM editais_leilao WHERE link_leiloeiro_origem_tipo IS NULL;
    SELECT COUNT(*) INTO depois_pncp_api FROM editais_leilao WHERE link_leiloeiro_origem_tipo = 'pncp_api';
    SELECT COUNT(*) INTO depois_pdf_anexo FROM editais_leilao WHERE link_leiloeiro_origem_tipo = 'pdf_anexo';

    RAISE NOTICE 'DEPOIS DO BACKFILL:';
    RAISE NOTICE '  origem_tipo=unknown: %', depois_unknown;
    RAISE NOTICE '  origem_tipo=NULL: %', depois_null;
    RAISE NOTICE '  origem_tipo=pncp_api: %', depois_pncp_api;
    RAISE NOTICE '  origem_tipo=pdf_anexo: %', depois_pdf_anexo;
END $$;

-- ============================================
-- FIM DA MIGRATION 006
-- ============================================
