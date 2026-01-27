-- ============================================
-- Migration 005: Adicionar rastreamento do Auditor V19
-- Data: 2026-01-26
-- Objetivo: Garantir idempotência no Cloud Auditor V19
-- ============================================
-- PROBLEMA:
-- O Auditor V19 não sabe se já processou um edital antes.
-- Editais sem link_leiloeiro são reprocessados toda execução.
--
-- SOLUÇÃO:
-- Adicionar campos para rastrear quando e como o V19 processou.
-- Isso permite distinguir "nunca processado" de "processado sem resultado".
-- ============================================

-- Adicionar colunas de rastreamento V19 (idempotente)
DO $$
BEGIN
    -- Campo 1: Timestamp de quando o V19 processou
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_name = 'editais_leilao' AND column_name = 'auditor_v19_processed_at'
    ) THEN
        ALTER TABLE editais_leilao ADD COLUMN auditor_v19_processed_at TIMESTAMPTZ;
        COMMENT ON COLUMN editais_leilao.auditor_v19_processed_at IS 'Timestamp de quando o Auditor V19 processou este edital';
    END IF;

    -- Campo 2: Run ID da execução do V19
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_name = 'editais_leilao' AND column_name = 'auditor_v19_run_id'
    ) THEN
        ALTER TABLE editais_leilao ADD COLUMN auditor_v19_run_id TEXT;
        COMMENT ON COLUMN editais_leilao.auditor_v19_run_id IS 'Run ID da execução do Auditor V19 que processou';
    END IF;

    -- Campo 3: Resultado do processamento V19
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_name = 'editais_leilao' AND column_name = 'auditor_v19_result'
    ) THEN
        ALTER TABLE editais_leilao ADD COLUMN auditor_v19_result TEXT;
        COMMENT ON COLUMN editais_leilao.auditor_v19_result IS 'Resultado: found_link, no_link, error, skipped';
    END IF;
END $$;

-- Índice para buscar editais não processados pelo V19
CREATE INDEX IF NOT EXISTS idx_editais_auditor_v19_processed
ON editais_leilao(auditor_v19_processed_at)
WHERE auditor_v19_processed_at IS NULL;

-- Índice para correlacionar com run_id
CREATE INDEX IF NOT EXISTS idx_editais_auditor_v19_run_id
ON editais_leilao(auditor_v19_run_id);

-- ============================================
-- CONSTRAINT de valores válidos para resultado
-- ============================================
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.constraint_column_usage
        WHERE table_name = 'editais_leilao' AND constraint_name = 'check_auditor_v19_result'
    ) THEN
        ALTER TABLE editais_leilao ADD CONSTRAINT check_auditor_v19_result
        CHECK (auditor_v19_result IS NULL OR auditor_v19_result IN ('found_link', 'no_link', 'error', 'skipped'));
    END IF;
END $$;

-- ============================================
-- FIM DA MIGRATION 005
-- ============================================
