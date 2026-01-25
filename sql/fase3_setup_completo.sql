-- ============================================================
-- FASE 3: SQL CONSOLIDADO - Setup Completo do Pipeline DaaS
-- Data: 2026-01-26
-- ============================================================
-- Este script cria/verifica todas as tabelas necessarias para
-- o pipeline de validacao do Ache Sucatas.
--
-- SEGURO: Usa IF NOT EXISTS em tudo, pode rodar multiplas vezes.
-- ============================================================

-- ============================================================
-- 1. TABELA: dataset_rejections (Quarentena)
-- ============================================================
CREATE TABLE IF NOT EXISTS public.dataset_rejections (
    id BIGSERIAL PRIMARY KEY,

    -- Identificacao da execucao
    run_id TEXT NOT NULL,

    -- Identificador do registro original
    id_interno TEXT,

    -- Status de validacao (draft, not_sellable, rejected)
    status TEXT NOT NULL CHECK (status IN ('draft', 'not_sellable', 'rejected')),

    -- Brief 1.2: Codigo e detalhe do erro principal
    reason_code VARCHAR(50),
    reason_detail VARCHAR(500),

    -- Lista de erros encontrados (JSON array)
    errors JSONB NOT NULL DEFAULT '[]'::jsonb,

    -- Registro original (raw) antes de normalizacao
    raw_record JSONB NOT NULL DEFAULT '{}'::jsonb,

    -- Registro apos normalizacao (mesmo com erros)
    normalized_record JSONB NOT NULL DEFAULT '{}'::jsonb,

    -- Timestamps
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    -- Idempotencia: mesmo registro no mesmo run nao duplica
    UNIQUE(run_id, id_interno)
);

-- Indices para consultas frequentes
CREATE INDEX IF NOT EXISTS idx_dataset_rejections_run_id
    ON public.dataset_rejections(run_id);

CREATE INDEX IF NOT EXISTS idx_dataset_rejections_status
    ON public.dataset_rejections(status);

CREATE INDEX IF NOT EXISTS idx_dataset_rejections_id_interno
    ON public.dataset_rejections(id_interno);

CREATE INDEX IF NOT EXISTS idx_dataset_rejections_created_at
    ON public.dataset_rejections(created_at DESC);

CREATE INDEX IF NOT EXISTS idx_dataset_rejections_reason_code
    ON public.dataset_rejections(reason_code);

-- Comentarios
COMMENT ON TABLE public.dataset_rejections IS
    'Quarentena de registros que nao passaram na validacao do contrato';

COMMENT ON COLUMN public.dataset_rejections.run_id IS
    'ID da execucao do pipeline (formato: YYYYMMDDTHHMMSSZ_uuid)';

COMMENT ON COLUMN public.dataset_rejections.status IS
    'Status de validacao: draft (incompleto), not_sellable (nao vendavel), rejected (lixo)';

COMMENT ON COLUMN public.dataset_rejections.reason_code IS
    'Codigo do erro principal (ex: missing_required_field, invalid_date_format)';

COMMENT ON COLUMN public.dataset_rejections.reason_detail IS
    'Mensagem curta explicando o motivo da quarentena (max 500 chars)';

-- Trigger para atualizar updated_at
CREATE OR REPLACE FUNCTION update_dataset_rejections_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trigger_dataset_rejections_updated_at ON public.dataset_rejections;
CREATE TRIGGER trigger_dataset_rejections_updated_at
    BEFORE UPDATE ON public.dataset_rejections
    FOR EACH ROW
    EXECUTE FUNCTION update_dataset_rejections_updated_at();

-- RLS
ALTER TABLE public.dataset_rejections ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS "Service role acesso total dataset_rejections" ON public.dataset_rejections;
CREATE POLICY "Service role acesso total dataset_rejections"
ON public.dataset_rejections
FOR ALL
TO service_role
USING (true)
WITH CHECK (true);


-- ============================================================
-- 2. TABELA: miner_execucoes (Tracking + QualityReport)
-- ============================================================
CREATE TABLE IF NOT EXISTS public.miner_execucoes (
    id BIGSERIAL PRIMARY KEY,

    -- Identificacao da execucao
    run_id TEXT,
    versao_miner TEXT NOT NULL DEFAULT 'V18',

    -- Configuracao
    janela_temporal_horas INTEGER,
    termos_buscados INTEGER,
    paginas_por_termo INTEGER,
    modo_processamento TEXT DEFAULT 'INCREMENTAL',

    -- Timestamps
    inicio TIMESTAMPTZ DEFAULT NOW(),
    fim TIMESTAMPTZ,

    -- Resultados basicos
    editais_encontrados INTEGER DEFAULT 0,
    editais_novos INTEGER DEFAULT 0,
    editais_enriquecidos INTEGER DEFAULT 0,
    editais_skip_existe INTEGER DEFAULT 0,
    arquivos_baixados INTEGER DEFAULT 0,
    erros INTEGER DEFAULT 0,

    -- Metricas do QualityReport (Brief 2.2)
    total_processados INTEGER DEFAULT 0,
    total_validos INTEGER DEFAULT 0,
    total_quarentena INTEGER DEFAULT 0,
    taxa_validos_percent NUMERIC(5,2) DEFAULT 0,
    taxa_quarentena_percent NUMERIC(5,2) DEFAULT 0,
    duracao_segundos NUMERIC(10,2) DEFAULT 0,

    -- FinOps (Brief 3.6)
    cost_estimated_total NUMERIC(10,4) DEFAULT 0,
    cost_openai_estimated NUMERIC(10,4) DEFAULT 0,
    num_pdfs INTEGER DEFAULT 0,
    custo_por_mil_registros NUMERIC(10,4) DEFAULT 0,

    -- Status
    status TEXT NOT NULL DEFAULT 'RUNNING',

    -- Metadata
    created_at TIMESTAMPTZ DEFAULT NOW(),

    -- Constraints
    CONSTRAINT check_miner_status CHECK (status IN ('RUNNING', 'SUCCESS', 'FAILED'))
);

-- Indices
CREATE INDEX IF NOT EXISTS idx_miner_exec_inicio ON public.miner_execucoes(inicio DESC);
CREATE INDEX IF NOT EXISTS idx_miner_exec_status ON public.miner_execucoes(status);
CREATE INDEX IF NOT EXISTS idx_miner_exec_run_id ON public.miner_execucoes(run_id);
CREATE INDEX IF NOT EXISTS idx_miner_exec_modo ON public.miner_execucoes(modo_processamento);

-- Comentarios
COMMENT ON TABLE public.miner_execucoes IS 'Log de execucoes do Miner V18 com metricas de qualidade e custos';
COMMENT ON COLUMN public.miner_execucoes.run_id IS 'ID unico para correlacao com QualityReport e dataset_rejections';
COMMENT ON COLUMN public.miner_execucoes.modo_processamento IS 'INCREMENTAL (pula existentes) ou FULL (--force)';
COMMENT ON COLUMN public.miner_execucoes.cost_estimated_total IS 'Custo estimado total da execucao em USD';
COMMENT ON COLUMN public.miner_execucoes.cost_openai_estimated IS 'Custo estimado de chamadas OpenAI em USD';
COMMENT ON COLUMN public.miner_execucoes.custo_por_mil_registros IS 'Custo medio por 1000 registros processados';

-- RLS
ALTER TABLE public.miner_execucoes ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS "Service role acesso total miner_execucoes" ON public.miner_execucoes;
CREATE POLICY "Service role acesso total miner_execucoes"
ON public.miner_execucoes
FOR ALL
TO service_role
USING (true)
WITH CHECK (true);


-- ============================================================
-- 3. TABELA: quality_reports (Historico detalhado)
-- ============================================================
-- Tabela separada para persistir QualityReports completos
-- com breakdown por reason_code (top errors)

CREATE TABLE IF NOT EXISTS public.quality_reports (
    id BIGSERIAL PRIMARY KEY,

    -- Correlacao
    run_id TEXT NOT NULL UNIQUE,
    execucao_id BIGINT REFERENCES public.miner_execucoes(id),

    -- Metricas principais
    total_processados INTEGER NOT NULL DEFAULT 0,
    total_validos INTEGER NOT NULL DEFAULT 0,
    total_draft INTEGER NOT NULL DEFAULT 0,
    total_not_sellable INTEGER NOT NULL DEFAULT 0,
    total_rejected INTEGER NOT NULL DEFAULT 0,

    -- Percentuais
    taxa_validos_percent NUMERIC(5,2) DEFAULT 0,
    taxa_quarentena_percent NUMERIC(5,2) DEFAULT 0,

    -- Duracao
    duracao_segundos NUMERIC(10,2) DEFAULT 0,

    -- Top errors (JSON array com reason_code e contagem)
    top_errors JSONB DEFAULT '[]'::jsonb,

    -- Breakdown por etapa (JSON)
    metricas_por_etapa JSONB DEFAULT '{}'::jsonb,

    -- Timestamps
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    -- Storage reference (se exportado para JSON)
    storage_path TEXT
);

-- Indices
CREATE INDEX IF NOT EXISTS idx_quality_reports_run_id ON public.quality_reports(run_id);
CREATE INDEX IF NOT EXISTS idx_quality_reports_created_at ON public.quality_reports(created_at DESC);

-- Comentarios
COMMENT ON TABLE public.quality_reports IS 'Relatorios de qualidade detalhados por execucao do pipeline';
COMMENT ON COLUMN public.quality_reports.top_errors IS 'Array JSON: [{reason_code, count, percent}, ...]';
COMMENT ON COLUMN public.quality_reports.metricas_por_etapa IS 'Metricas por etapa: {coleta: {tempo, count}, validate: {...}, ...}';
COMMENT ON COLUMN public.quality_reports.storage_path IS 'Caminho no Supabase Storage se exportado como JSON';

-- RLS
ALTER TABLE public.quality_reports ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS "Service role acesso total quality_reports" ON public.quality_reports;
CREATE POLICY "Service role acesso total quality_reports"
ON public.quality_reports
FOR ALL
TO service_role
USING (true)
WITH CHECK (true);


-- ============================================================
-- 4. TABELA: pipeline_events (Observabilidade - Brief 3.4)
-- ============================================================
-- Log estruturado de eventos do pipeline por etapa

CREATE TABLE IF NOT EXISTS public.pipeline_events (
    id BIGSERIAL PRIMARY KEY,

    -- Correlacao
    run_id TEXT NOT NULL,

    -- Etapa do pipeline
    etapa TEXT NOT NULL CHECK (etapa IN (
        'inicio', 'busca', 'coleta', 'pdf_download', 'pdf_parse',
        'extract', 'enrich', 'validate', 'upsert', 'quarantine', 'fim'
    )),

    -- Evento
    evento TEXT NOT NULL,  -- 'start', 'success', 'error', 'skip', 'metric'
    nivel TEXT NOT NULL DEFAULT 'info' CHECK (nivel IN ('debug', 'info', 'warning', 'error')),

    -- Detalhes
    mensagem TEXT,
    dados JSONB DEFAULT '{}'::jsonb,

    -- Metricas de tempo
    duracao_ms INTEGER,

    -- Contadores
    items_processados INTEGER DEFAULT 0,
    items_sucesso INTEGER DEFAULT 0,
    items_erro INTEGER DEFAULT 0,

    -- Timestamp
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Indices
CREATE INDEX IF NOT EXISTS idx_pipeline_events_run_id ON public.pipeline_events(run_id);
CREATE INDEX IF NOT EXISTS idx_pipeline_events_etapa ON public.pipeline_events(etapa);
CREATE INDEX IF NOT EXISTS idx_pipeline_events_nivel ON public.pipeline_events(nivel);
CREATE INDEX IF NOT EXISTS idx_pipeline_events_created_at ON public.pipeline_events(created_at DESC);

-- Indice composto para queries de observabilidade
CREATE INDEX IF NOT EXISTS idx_pipeline_events_run_etapa
    ON public.pipeline_events(run_id, etapa, created_at);

-- Comentarios
COMMENT ON TABLE public.pipeline_events IS 'Log estruturado de eventos do pipeline para observabilidade';
COMMENT ON COLUMN public.pipeline_events.etapa IS 'Etapa do pipeline: busca, coleta, pdf_parse, validate, upsert, etc';
COMMENT ON COLUMN public.pipeline_events.evento IS 'Tipo de evento: start, success, error, skip, metric';

-- RLS
ALTER TABLE public.pipeline_events ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS "Service role acesso total pipeline_events" ON public.pipeline_events;
CREATE POLICY "Service role acesso total pipeline_events"
ON public.pipeline_events
FOR ALL
TO service_role
USING (true)
WITH CHECK (true);


-- ============================================================
-- 5. VIEW: dashboard_execucoes (Brief 3.3)
-- ============================================================
-- View consolidada para o Dashboard de Saude

CREATE OR REPLACE VIEW public.vw_dashboard_execucoes AS
SELECT
    me.id,
    me.run_id,
    me.versao_miner,
    me.modo_processamento,
    me.inicio,
    me.fim,
    me.status,

    -- Duracao formatada
    CASE
        WHEN me.fim IS NOT NULL THEN
            EXTRACT(EPOCH FROM (me.fim - me.inicio))::INTEGER
        ELSE
            EXTRACT(EPOCH FROM (NOW() - me.inicio))::INTEGER
    END as duracao_segundos_calc,

    -- Metricas de volume
    me.editais_encontrados,
    me.editais_novos,
    me.editais_skip_existe,
    me.erros,

    -- Metricas de qualidade
    me.total_processados,
    me.total_validos,
    me.total_quarentena,
    me.taxa_validos_percent,
    me.taxa_quarentena_percent,

    -- FinOps
    me.cost_estimated_total,
    me.cost_openai_estimated,
    me.custo_por_mil_registros,

    -- Indicadores de saude
    CASE
        WHEN me.taxa_quarentena_percent > 30 THEN 'critical'
        WHEN me.taxa_quarentena_percent > 15 THEN 'warning'
        ELSE 'healthy'
    END as health_status,

    CASE
        WHEN me.status = 'FAILED' THEN 'error'
        WHEN me.status = 'RUNNING' AND me.inicio < NOW() - INTERVAL '2 hours' THEN 'stale'
        ELSE me.status
    END as status_check

FROM public.miner_execucoes me
ORDER BY me.inicio DESC;

COMMENT ON VIEW public.vw_dashboard_execucoes IS 'View consolidada para Dashboard de Saude do Pipeline';


-- ============================================================
-- 6. VIEW: top_reason_codes (Brief 3.3)
-- ============================================================
-- Top erros de quarentena para o dashboard

CREATE OR REPLACE VIEW public.vw_top_reason_codes AS
SELECT
    reason_code,
    COUNT(*) as total,
    ROUND(100.0 * COUNT(*) / NULLIF(SUM(COUNT(*)) OVER (), 0), 2) as percentual
FROM public.dataset_rejections
WHERE created_at > NOW() - INTERVAL '7 days'
GROUP BY reason_code
ORDER BY total DESC
LIMIT 20;

COMMENT ON VIEW public.vw_top_reason_codes IS 'Top 20 reason_codes dos ultimos 7 dias';


-- ============================================================
-- 7. FUNCAO: calcular_custo_execucao (Brief 3.6)
-- ============================================================
-- Funcao para calcular custo estimado de uma execucao

CREATE OR REPLACE FUNCTION public.calcular_custo_execucao(
    p_num_pdfs INTEGER,
    p_num_editais INTEGER,
    p_num_tokens_openai INTEGER DEFAULT 0
)
RETURNS JSONB AS $$
DECLARE
    v_custo_pdf NUMERIC := 0.001;           -- $0.001 por PDF (storage + processing)
    v_custo_edital NUMERIC := 0.0005;       -- $0.0005 por edital (validacao)
    v_custo_token NUMERIC := 0.00001;       -- $0.00001 por token OpenAI (estimativa)
    v_custo_total NUMERIC;
    v_custo_openai NUMERIC;
    v_custo_por_mil NUMERIC;
BEGIN
    v_custo_openai := p_num_tokens_openai * v_custo_token;
    v_custo_total := (p_num_pdfs * v_custo_pdf) + (p_num_editais * v_custo_edital) + v_custo_openai;

    IF p_num_editais > 0 THEN
        v_custo_por_mil := (v_custo_total / p_num_editais) * 1000;
    ELSE
        v_custo_por_mil := 0;
    END IF;

    RETURN jsonb_build_object(
        'custo_total', ROUND(v_custo_total, 4),
        'custo_openai', ROUND(v_custo_openai, 4),
        'custo_por_mil_registros', ROUND(v_custo_por_mil, 4),
        'breakdown', jsonb_build_object(
            'pdfs', ROUND(p_num_pdfs * v_custo_pdf, 4),
            'editais', ROUND(p_num_editais * v_custo_edital, 4),
            'openai', ROUND(v_custo_openai, 4)
        )
    );
END;
$$ LANGUAGE plpgsql;

COMMENT ON FUNCTION public.calcular_custo_execucao IS 'Calcula custo estimado de uma execucao do pipeline';


-- ============================================================
-- 8. MIGRATION: Adicionar colunas faltantes (se tabelas ja existem)
-- ============================================================
-- Garante que colunas novas existam em tabelas pre-existentes

-- dataset_rejections: adicionar reason_code/reason_detail se nao existir
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_name = 'dataset_rejections' AND column_name = 'reason_code'
    ) THEN
        ALTER TABLE public.dataset_rejections ADD COLUMN reason_code VARCHAR(50);
        ALTER TABLE public.dataset_rejections ADD COLUMN reason_detail VARCHAR(500);
    END IF;
END $$;

-- miner_execucoes: adicionar colunas FinOps se nao existir
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_name = 'miner_execucoes' AND column_name = 'cost_estimated_total'
    ) THEN
        ALTER TABLE public.miner_execucoes ADD COLUMN cost_estimated_total NUMERIC(10,4) DEFAULT 0;
        ALTER TABLE public.miner_execucoes ADD COLUMN cost_openai_estimated NUMERIC(10,4) DEFAULT 0;
        ALTER TABLE public.miner_execucoes ADD COLUMN num_pdfs INTEGER DEFAULT 0;
        ALTER TABLE public.miner_execucoes ADD COLUMN custo_por_mil_registros NUMERIC(10,4) DEFAULT 0;
    END IF;
END $$;


-- ============================================================
-- VERIFICACAO FINAL
-- ============================================================
-- Execute apos rodar este script:

/*
-- 1. Verificar tabelas criadas
SELECT table_name FROM information_schema.tables
WHERE table_schema = 'public'
AND table_name IN ('dataset_rejections', 'miner_execucoes', 'quality_reports', 'pipeline_events')
ORDER BY table_name;

-- 2. Verificar views
SELECT table_name FROM information_schema.views
WHERE table_schema = 'public'
AND table_name LIKE 'vw_%';

-- 3. Verificar colunas de dataset_rejections
SELECT column_name, data_type
FROM information_schema.columns
WHERE table_name = 'dataset_rejections'
ORDER BY ordinal_position;

-- 4. Verificar colunas de miner_execucoes
SELECT column_name, data_type
FROM information_schema.columns
WHERE table_name = 'miner_execucoes'
ORDER BY ordinal_position;

-- 5. Testar funcao de custo
SELECT public.calcular_custo_execucao(100, 500, 50000);
*/

-- ============================================================
-- FIM DO SCRIPT CONSOLIDADO
-- ============================================================
