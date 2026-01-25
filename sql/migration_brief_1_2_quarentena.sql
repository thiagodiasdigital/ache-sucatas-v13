-- ============================================================
-- MIGRATION BRIEF 1.2: Adicionar campos reason_code e reason_detail
-- Tabela: dataset_rejections
-- Data: 2026-01-26
-- ============================================================
-- OBJETIVO: Facilitar queries sem precisar parsear o array JSON de errors
-- reason_code = código do primeiro erro (mais relevante)
-- reason_detail = mensagem resumida do motivo
-- ============================================================

-- 1. Adicionar coluna reason_code (extraído do primeiro erro)
ALTER TABLE public.dataset_rejections
ADD COLUMN IF NOT EXISTS reason_code VARCHAR(50);

-- 2. Adicionar coluna reason_detail (mensagem curta)
ALTER TABLE public.dataset_rejections
ADD COLUMN IF NOT EXISTS reason_detail VARCHAR(500);

-- 3. Preencher campos para registros existentes
UPDATE public.dataset_rejections
SET
    reason_code = COALESCE(
        errors->0->>'code',
        status
    ),
    reason_detail = LEFT(
        COALESCE(
            errors->0->>'message',
            'Status: ' || status
        ),
        500
    )
WHERE reason_code IS NULL;

-- 4. Criar índice para queries por reason_code
CREATE INDEX IF NOT EXISTS idx_dataset_rejections_reason_code
ON public.dataset_rejections(reason_code);

-- 5. Comentários
COMMENT ON COLUMN public.dataset_rejections.reason_code IS
    'Código do erro principal (ex: missing_required_field, invalid_date_format)';

COMMENT ON COLUMN public.dataset_rejections.reason_detail IS
    'Mensagem curta explicando o motivo da quarentena (max 500 chars)';

-- ============================================================
-- QUERY DE VERIFICAÇÃO (executar após migration):
-- ============================================================
-- SELECT reason_code, COUNT(*) as total
-- FROM public.dataset_rejections
-- GROUP BY reason_code
-- ORDER BY total DESC;
-- ============================================================

-- ============================================================
-- ROLLBACK (se necessário):
-- ALTER TABLE public.dataset_rejections DROP COLUMN IF EXISTS reason_code;
-- ALTER TABLE public.dataset_rejections DROP COLUMN IF EXISTS reason_detail;
-- ============================================================
