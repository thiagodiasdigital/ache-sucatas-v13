-- ============================================================
-- CREATE TABLE: miner_execucoes
-- Tabela de tracking de execuções do Miner V18
-- Data: 2026-01-26
-- ============================================================
-- Esta tabela registra cada execução do Miner com métricas
-- detalhadas para análise histórica e debugging.
-- ============================================================

CREATE TABLE IF NOT EXISTS miner_execucoes (
    id BIGSERIAL PRIMARY KEY,

    -- Identificação da execução
    run_id TEXT,                                    -- Brief 2.2: Correlação com QualityReport
    versao_miner TEXT NOT NULL DEFAULT 'V18',

    -- Configuração
    janela_temporal_horas INTEGER,
    termos_buscados INTEGER,
    paginas_por_termo INTEGER,
    modo_processamento TEXT DEFAULT 'INCREMENTAL',  -- Brief 2.1: INCREMENTAL ou FULL

    -- Timestamps
    inicio TIMESTAMPTZ DEFAULT NOW(),
    fim TIMESTAMPTZ,

    -- Resultados básicos
    editais_encontrados INTEGER DEFAULT 0,
    editais_novos INTEGER DEFAULT 0,
    editais_enriquecidos INTEGER DEFAULT 0,
    editais_skip_existe INTEGER DEFAULT 0,          -- Brief 2.1: Pulados por já existir
    arquivos_baixados INTEGER DEFAULT 0,
    erros INTEGER DEFAULT 0,

    -- Métricas do QualityReport (Brief 2.2)
    total_processados INTEGER DEFAULT 0,
    total_validos INTEGER DEFAULT 0,
    total_quarentena INTEGER DEFAULT 0,
    taxa_validos_percent NUMERIC(5,2) DEFAULT 0,
    taxa_quarentena_percent NUMERIC(5,2) DEFAULT 0,
    duracao_segundos NUMERIC(10,2) DEFAULT 0,

    -- Status
    status TEXT NOT NULL DEFAULT 'RUNNING',

    -- Metadata
    created_at TIMESTAMPTZ DEFAULT NOW(),

    -- Constraints
    CONSTRAINT check_miner_status CHECK (status IN ('RUNNING', 'SUCCESS', 'FAILED'))
);

-- Índices
CREATE INDEX IF NOT EXISTS idx_miner_exec_inicio ON miner_execucoes(inicio DESC);
CREATE INDEX IF NOT EXISTS idx_miner_exec_status ON miner_execucoes(status);
CREATE INDEX IF NOT EXISTS idx_miner_exec_run_id ON miner_execucoes(run_id);
CREATE INDEX IF NOT EXISTS idx_miner_exec_modo ON miner_execucoes(modo_processamento);

-- Comentários
COMMENT ON TABLE miner_execucoes IS 'Log de execuções do Miner V18 com métricas de qualidade';
COMMENT ON COLUMN miner_execucoes.run_id IS 'ID único para correlação com QualityReport e dataset_rejections';
COMMENT ON COLUMN miner_execucoes.modo_processamento IS 'INCREMENTAL (pula existentes) ou FULL (--force)';
COMMENT ON COLUMN miner_execucoes.editais_skip_existe IS 'Editais ignorados por já existirem (modo incremental)';
COMMENT ON COLUMN miner_execucoes.total_processados IS 'Total de registros processados pelo validador';
COMMENT ON COLUMN miner_execucoes.total_validos IS 'Registros com status VALID';
COMMENT ON COLUMN miner_execucoes.total_quarentena IS 'Registros em quarentena (draft + not_sellable + rejected)';
COMMENT ON COLUMN miner_execucoes.taxa_validos_percent IS 'Percentual de válidos sobre total';
COMMENT ON COLUMN miner_execucoes.taxa_quarentena_percent IS 'Percentual de quarentena sobre total';

-- ============================================================
-- RLS (Row Level Security)
-- ============================================================
ALTER TABLE miner_execucoes ENABLE ROW LEVEL SECURITY;

-- Política: service_role tem acesso total
CREATE POLICY "Service role acesso total miner_execucoes"
ON miner_execucoes
FOR ALL
TO service_role
USING (true)
WITH CHECK (true);

-- ============================================================
-- VERIFICAÇÃO
-- ============================================================
-- Executar após criar:
-- SELECT column_name, data_type FROM information_schema.columns
-- WHERE table_name = 'miner_execucoes' ORDER BY ordinal_position;
-- ============================================================
