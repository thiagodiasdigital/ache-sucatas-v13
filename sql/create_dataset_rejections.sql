-- ============================================================
-- CREATE TABLE: dataset_rejections (quarentena de validação)
-- Ache Sucatas DaaS - Pipeline de Validação
-- ============================================================
-- Esta tabela armazena registros que não passaram na validação:
--   - draft: incompleto (faltam campos obrigatórios)
--   - not_sellable: não vendável (falha na regra de vendabilidade)
--   - rejected: rejeitado (formato inválido, lixo)
--
-- Registros "valid" vão para a tabela principal (editais_leilao)
-- ============================================================

CREATE TABLE IF NOT EXISTS public.dataset_rejections (
    id BIGSERIAL PRIMARY KEY,

    -- Identificação da execução
    run_id TEXT NOT NULL,

    -- Identificador do registro original
    id_interno TEXT,

    -- Status de validação (draft, not_sellable, rejected)
    status TEXT NOT NULL CHECK (status IN ('draft', 'not_sellable', 'rejected')),

    -- Lista de erros encontrados (JSON array)
    errors JSONB NOT NULL DEFAULT '[]'::jsonb,

    -- Registro original (raw) antes de normalização
    raw_record JSONB NOT NULL DEFAULT '{}'::jsonb,

    -- Registro após normalização (mesmo com erros)
    normalized_record JSONB NOT NULL DEFAULT '{}'::jsonb,

    -- Timestamps
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    -- Idempotência: mesmo registro no mesmo run não duplica
    UNIQUE(run_id, id_interno)
);

-- Índices para consultas frequentes
CREATE INDEX IF NOT EXISTS idx_dataset_rejections_run_id
    ON public.dataset_rejections(run_id);

CREATE INDEX IF NOT EXISTS idx_dataset_rejections_status
    ON public.dataset_rejections(status);

CREATE INDEX IF NOT EXISTS idx_dataset_rejections_id_interno
    ON public.dataset_rejections(id_interno);

CREATE INDEX IF NOT EXISTS idx_dataset_rejections_created_at
    ON public.dataset_rejections(created_at DESC);

-- Comentários
COMMENT ON TABLE public.dataset_rejections IS
    'Quarentena de registros que não passaram na validação do contrato';

COMMENT ON COLUMN public.dataset_rejections.run_id IS
    'ID da execução do pipeline (formato: YYYYMMDDTHHMMSSZ_uuid)';

COMMENT ON COLUMN public.dataset_rejections.status IS
    'Status de validação: draft (incompleto), not_sellable (não vendável), rejected (lixo)';

COMMENT ON COLUMN public.dataset_rejections.errors IS
    'Array JSON com erros encontrados: [{code, field, message}, ...]';

COMMENT ON COLUMN public.dataset_rejections.raw_record IS
    'Registro original antes da validação/normalização';

COMMENT ON COLUMN public.dataset_rejections.normalized_record IS
    'Registro após normalização (mesmo com erros, para auditoria)';

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

-- ============================================================
-- QUERIES DE VALIDAÇÃO (usar após rodar o pipeline)
-- ============================================================

-- 1. Verificar que tabela principal só tem status = valid
-- (A tabela principal não tem coluna "status", então verificamos
-- que todos os pncp_id na principal NÃO estão na quarentena)
/*
SELECT COUNT(*) as total_na_principal
FROM editais_leilao;

SELECT COUNT(*) as total_na_quarentena
FROM dataset_rejections;
*/

-- 2. Contar registros na quarentena por status e run_id
/*
SELECT
    run_id,
    status,
    COUNT(*) as contagem
FROM dataset_rejections
WHERE run_id = '<RUN_ID>'
GROUP BY run_id, status
ORDER BY run_id, status;
*/

-- 3. Ver erros mais comuns
/*
SELECT
    error->>'code' as codigo_erro,
    error->>'field' as campo,
    COUNT(*) as ocorrencias
FROM dataset_rejections,
     LATERAL jsonb_array_elements(errors) as error
GROUP BY error->>'code', error->>'field'
ORDER BY ocorrencias DESC
LIMIT 20;
*/
