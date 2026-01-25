-- ============================================================
-- MIGRATION: Brief 2.2 - Tracking de Execuções Aprimorado
-- Data: 2026-01-26
-- ============================================================
-- Adiciona campos para correlação com QualityReport e métricas
-- detalhadas de cada execução do Miner.
-- ============================================================

-- 1. Adicionar run_id para correlação com QualityReport
ALTER TABLE miner_execucoes
ADD COLUMN IF NOT EXISTS run_id TEXT;

-- 2. Adicionar modo de processamento (INCREMENTAL ou FULL)
ALTER TABLE miner_execucoes
ADD COLUMN IF NOT EXISTS modo_processamento TEXT DEFAULT 'INCREMENTAL';

-- 3. Adicionar contador de editais pulados (modo incremental)
ALTER TABLE miner_execucoes
ADD COLUMN IF NOT EXISTS editais_skip_existe INTEGER DEFAULT 0;

-- 4. Adicionar métricas do QualityReport
ALTER TABLE miner_execucoes
ADD COLUMN IF NOT EXISTS total_processados INTEGER DEFAULT 0;

ALTER TABLE miner_execucoes
ADD COLUMN IF NOT EXISTS total_validos INTEGER DEFAULT 0;

ALTER TABLE miner_execucoes
ADD COLUMN IF NOT EXISTS total_quarentena INTEGER DEFAULT 0;

ALTER TABLE miner_execucoes
ADD COLUMN IF NOT EXISTS taxa_validos_percent NUMERIC(5,2) DEFAULT 0;

ALTER TABLE miner_execucoes
ADD COLUMN IF NOT EXISTS taxa_quarentena_percent NUMERIC(5,2) DEFAULT 0;

ALTER TABLE miner_execucoes
ADD COLUMN IF NOT EXISTS duracao_segundos NUMERIC(10,2) DEFAULT 0;

-- 5. Índice para busca por run_id
CREATE INDEX IF NOT EXISTS idx_miner_execucoes_run_id
ON miner_execucoes(run_id);

-- 6. Índice para filtrar por modo de processamento
CREATE INDEX IF NOT EXISTS idx_miner_execucoes_modo
ON miner_execucoes(modo_processamento);

-- ============================================================
-- COMENTÁRIOS DESCRITIVOS
-- ============================================================
COMMENT ON COLUMN miner_execucoes.run_id IS 'ID único da execução para correlação com QualityReport e dataset_rejections';
COMMENT ON COLUMN miner_execucoes.modo_processamento IS 'Modo de execução: INCREMENTAL (pula existentes) ou FULL (reprocessa tudo)';
COMMENT ON COLUMN miner_execucoes.editais_skip_existe IS 'Quantidade de editais ignorados por já existirem no banco (modo incremental)';
COMMENT ON COLUMN miner_execucoes.total_processados IS 'Total de registros processados pelo validador';
COMMENT ON COLUMN miner_execucoes.total_validos IS 'Total de registros válidos (status=VALID)';
COMMENT ON COLUMN miner_execucoes.total_quarentena IS 'Total de registros em quarentena (draft + not_sellable + rejected)';
COMMENT ON COLUMN miner_execucoes.taxa_validos_percent IS 'Percentual de registros válidos sobre total processado';
COMMENT ON COLUMN miner_execucoes.taxa_quarentena_percent IS 'Percentual de registros em quarentena sobre total processado';
COMMENT ON COLUMN miner_execucoes.duracao_segundos IS 'Duração total da execução em segundos';

-- ============================================================
-- VERIFICAÇÃO
-- ============================================================
-- Executar após a migração:
-- SELECT column_name, data_type FROM information_schema.columns
-- WHERE table_name = 'miner_execucoes'
-- ORDER BY ordinal_position;
-- ============================================================
