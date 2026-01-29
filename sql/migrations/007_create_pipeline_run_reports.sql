-- ============================================
-- Migration 007: Criar tabela pipeline_run_reports
-- Data: 2026-01-27
-- Objetivo: Persistir metricas de qualidade por execucao
-- ============================================
-- CONTRATO:
-- - 1 linha inserida por execucao do Miner ou Auditor
-- - Permite rastrear evolucao da qualidade ao longo do tempo
-- - git_sha vincula ao codigo exato que gerou os dados
-- ============================================

CREATE TABLE IF NOT EXISTS pipeline_run_reports (
    id BIGSERIAL PRIMARY KEY,
    run_id TEXT NOT NULL,
    git_sha TEXT,
    job_name TEXT NOT NULL,  -- 'miner' ou 'auditor'
    created_at TIMESTAMPTZ DEFAULT NOW(),

    -- Metricas de quantidade
    total INTEGER NOT NULL DEFAULT 0,
    com_link INTEGER NOT NULL DEFAULT 0,
    sem_link INTEGER NOT NULL DEFAULT 0,

    -- Metricas de validacao
    com_link_valido_true INTEGER NOT NULL DEFAULT 0,
    com_link_valido_false INTEGER NOT NULL DEFAULT 0,
    com_link_valido_null INTEGER NOT NULL DEFAULT 0,

    -- Metricas de origem
    origem_pncp_api INTEGER NOT NULL DEFAULT 0,
    origem_pdf_anexo INTEGER NOT NULL DEFAULT 0,
    origem_unknown INTEGER NOT NULL DEFAULT 0,
    origem_null INTEGER NOT NULL DEFAULT 0,

    -- Metadados adicionais
    metadata JSONB DEFAULT '{}'::jsonb
);

-- Indices para consultas comuns
CREATE INDEX IF NOT EXISTS idx_pipeline_run_reports_created_at
ON pipeline_run_reports(created_at DESC);

CREATE INDEX IF NOT EXISTS idx_pipeline_run_reports_job_name
ON pipeline_run_reports(job_name, created_at DESC);

CREATE INDEX IF NOT EXISTS idx_pipeline_run_reports_run_id
ON pipeline_run_reports(run_id);

-- Comentarios
COMMENT ON TABLE pipeline_run_reports IS 'Metricas de qualidade por execucao do pipeline (Miner/Auditor)';
COMMENT ON COLUMN pipeline_run_reports.run_id IS 'ID unico da execucao (ex: auditor_v19_20260127T120000_abc123)';
COMMENT ON COLUMN pipeline_run_reports.git_sha IS 'SHA do commit git que gerou esta execucao';
COMMENT ON COLUMN pipeline_run_reports.job_name IS 'Nome do job: miner ou auditor';
COMMENT ON COLUMN pipeline_run_reports.com_link_valido_null IS 'DEVE SER ZERO - indica problema de qualidade se > 0';

-- ============================================
-- RLS: Permitir leitura anonima (dashboard)
-- ============================================
ALTER TABLE pipeline_run_reports ENABLE ROW LEVEL SECURITY;

CREATE POLICY "Allow anonymous read access to pipeline_run_reports"
ON pipeline_run_reports
FOR SELECT
TO anon
USING (true);

CREATE POLICY "Allow service role full access to pipeline_run_reports"
ON pipeline_run_reports
FOR ALL
TO service_role
USING (true)
WITH CHECK (true);

-- ============================================
-- FIM DA MIGRATION 007
-- ============================================
