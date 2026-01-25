-- ============================================================
-- MIGRATION: Adicionar constraint UNIQUE para idempotência
-- Tabela: dataset_rejections
-- Data: 2026-01-25
-- ============================================================
-- OBJETIVO: Garantir que rodar o pipeline 2x não duplique registros
-- na quarentena. Mesmo (run_id, id_interno) = mesmo registro.
-- ============================================================

-- 1. Remover duplicatas existentes (manter apenas o mais recente)
DELETE FROM public.dataset_rejections a
USING public.dataset_rejections b
WHERE a.id < b.id
  AND a.run_id = b.run_id
  AND a.id_interno = b.id_interno;

-- 2. Adicionar constraint UNIQUE
ALTER TABLE public.dataset_rejections
ADD CONSTRAINT uq_dataset_rejections_run_id_interno
UNIQUE (run_id, id_interno);

-- 3. Verificar que constraint foi criada
-- SELECT constraint_name FROM information_schema.table_constraints
-- WHERE table_name = 'dataset_rejections' AND constraint_type = 'UNIQUE';

-- ============================================================
-- ROLLBACK (se necessário):
-- ALTER TABLE public.dataset_rejections
-- DROP CONSTRAINT IF EXISTS uq_dataset_rejections_run_id_interno;
-- ============================================================
