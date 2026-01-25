-- ============================================================
-- FASE 3: Migration Fix - Adicionar colunas faltantes
-- Data: 2026-01-26
-- ============================================================
-- Execute ANTES do fase3_setup_completo.sql se der erro de coluna
-- ============================================================

-- 1. Adicionar colunas FinOps em miner_execucoes
ALTER TABLE public.miner_execucoes
ADD COLUMN IF NOT EXISTS cost_estimated_total NUMERIC(10,4) DEFAULT 0;

ALTER TABLE public.miner_execucoes
ADD COLUMN IF NOT EXISTS cost_openai_estimated NUMERIC(10,4) DEFAULT 0;

ALTER TABLE public.miner_execucoes
ADD COLUMN IF NOT EXISTS num_pdfs INTEGER DEFAULT 0;

ALTER TABLE public.miner_execucoes
ADD COLUMN IF NOT EXISTS custo_por_mil_registros NUMERIC(10,4) DEFAULT 0;

-- 2. Adicionar colunas em dataset_rejections (se existir)
ALTER TABLE public.dataset_rejections
ADD COLUMN IF NOT EXISTS reason_code VARCHAR(50);

ALTER TABLE public.dataset_rejections
ADD COLUMN IF NOT EXISTS reason_detail VARCHAR(500);

-- 3. Verificar resultado
SELECT 'miner_execucoes' as tabela, column_name, data_type
FROM information_schema.columns
WHERE table_name = 'miner_execucoes'
AND column_name IN ('cost_estimated_total', 'cost_openai_estimated', 'num_pdfs', 'custo_por_mil_registros')
UNION ALL
SELECT 'dataset_rejections' as tabela, column_name, data_type
FROM information_schema.columns
WHERE table_name = 'dataset_rejections'
AND column_name IN ('reason_code', 'reason_detail')
ORDER BY tabela, column_name;
