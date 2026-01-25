-- ============================================================
-- CREATE TABLE: pipeline_alerts (Sistema de Alarmes)
-- Ache Sucatas DaaS - Fase 3.4 Observabilidade
-- Data: 2026-01-25
-- ============================================================
-- Esta tabela armazena alertas gerados automaticamente quando:
--   - Taxa de quarentena > 30% (critical)
--   - Taxa de quarentena > 15% (warning)
--   - Execução falhou (critical)
--   - Duração anormal (warning)
-- ============================================================

CREATE TABLE IF NOT EXISTS public.pipeline_alerts (
    id BIGSERIAL PRIMARY KEY,

    -- Identificação
    run_id TEXT,
    execucao_id BIGINT REFERENCES public.miner_execucoes(id),

    -- Tipo e severidade
    tipo TEXT NOT NULL CHECK (tipo IN (
        'high_quarantine_rate',    -- Taxa quarentena alta
        'execution_failed',        -- Execução falhou
        'long_duration',           -- Duração muito longa
        'no_valid_records',        -- Nenhum registro válido
        'api_error',               -- Erro de API externa
        'storage_error',           -- Erro de storage
        'openai_error'             -- Erro de OpenAI
    )),

    severidade TEXT NOT NULL CHECK (severidade IN ('info', 'warning', 'critical')),

    -- Detalhes
    titulo TEXT NOT NULL,
    mensagem TEXT NOT NULL,
    dados JSONB DEFAULT '{}'::jsonb,

    -- Status do alerta
    status TEXT NOT NULL DEFAULT 'open' CHECK (status IN ('open', 'acknowledged', 'resolved')),
    acknowledged_at TIMESTAMPTZ,
    acknowledged_by TEXT,
    resolved_at TIMESTAMPTZ,

    -- Notificações
    email_enviado BOOLEAN DEFAULT FALSE,
    email_enviado_at TIMESTAMPTZ,

    -- Timestamps
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Índices
CREATE INDEX IF NOT EXISTS idx_pipeline_alerts_status
    ON public.pipeline_alerts(status);

CREATE INDEX IF NOT EXISTS idx_pipeline_alerts_severidade
    ON public.pipeline_alerts(severidade);

CREATE INDEX IF NOT EXISTS idx_pipeline_alerts_created_at
    ON public.pipeline_alerts(created_at DESC);

CREATE INDEX IF NOT EXISTS idx_pipeline_alerts_run_id
    ON public.pipeline_alerts(run_id);

-- Índice composto para dashboard (alertas abertos recentes)
CREATE INDEX IF NOT EXISTS idx_pipeline_alerts_open_recent
    ON public.pipeline_alerts(status, created_at DESC)
    WHERE status = 'open';

-- Comentários
COMMENT ON TABLE public.pipeline_alerts IS 'Alertas automáticos do pipeline para observabilidade';
COMMENT ON COLUMN public.pipeline_alerts.tipo IS 'Tipo do alerta: high_quarantine_rate, execution_failed, etc';
COMMENT ON COLUMN public.pipeline_alerts.severidade IS 'Severidade: info, warning, critical';
COMMENT ON COLUMN public.pipeline_alerts.status IS 'Status: open (novo), acknowledged (visto), resolved (resolvido)';

-- RLS
ALTER TABLE public.pipeline_alerts ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS "Service role acesso total pipeline_alerts" ON public.pipeline_alerts;
CREATE POLICY "Service role acesso total pipeline_alerts"
ON public.pipeline_alerts
FOR ALL
TO service_role
USING (true)
WITH CHECK (true);

-- Permitir leitura para usuários autenticados
DROP POLICY IF EXISTS "Authenticated read pipeline_alerts" ON public.pipeline_alerts;
CREATE POLICY "Authenticated read pipeline_alerts"
ON public.pipeline_alerts
FOR SELECT
TO authenticated
USING (true);


-- ============================================================
-- VIEW: Alertas abertos para o dashboard
-- ============================================================
CREATE OR REPLACE VIEW public.vw_open_alerts AS
SELECT
    id,
    run_id,
    tipo,
    severidade,
    titulo,
    mensagem,
    dados,
    status,
    created_at,
    CASE
        WHEN created_at > NOW() - INTERVAL '1 hour' THEN 'recent'
        WHEN created_at > NOW() - INTERVAL '24 hours' THEN 'today'
        ELSE 'old'
    END as age_category
FROM public.pipeline_alerts
WHERE status = 'open'
ORDER BY
    CASE severidade
        WHEN 'critical' THEN 1
        WHEN 'warning' THEN 2
        ELSE 3
    END,
    created_at DESC;

COMMENT ON VIEW public.vw_open_alerts IS 'Alertas abertos ordenados por severidade e data';


-- ============================================================
-- FUNÇÃO: Criar alerta (chamada pelo miner)
-- ============================================================
CREATE OR REPLACE FUNCTION public.criar_alerta(
    p_run_id TEXT,
    p_execucao_id BIGINT,
    p_tipo TEXT,
    p_severidade TEXT,
    p_titulo TEXT,
    p_mensagem TEXT,
    p_dados JSONB DEFAULT '{}'::jsonb
)
RETURNS BIGINT AS $$
DECLARE
    v_alert_id BIGINT;
BEGIN
    INSERT INTO public.pipeline_alerts (
        run_id, execucao_id, tipo, severidade, titulo, mensagem, dados
    ) VALUES (
        p_run_id, p_execucao_id, p_tipo, p_severidade, p_titulo, p_mensagem, p_dados
    )
    RETURNING id INTO v_alert_id;

    RETURN v_alert_id;
END;
$$ LANGUAGE plpgsql;

COMMENT ON FUNCTION public.criar_alerta IS 'Cria um novo alerta no sistema';


-- ============================================================
-- FUNÇÃO: Contar alertas abertos por severidade
-- ============================================================
CREATE OR REPLACE FUNCTION public.contar_alertas_abertos()
RETURNS TABLE (
    severidade TEXT,
    total BIGINT
) AS $$
BEGIN
    RETURN QUERY
    SELECT
        pa.severidade,
        COUNT(*)::BIGINT as total
    FROM public.pipeline_alerts pa
    WHERE pa.status = 'open'
    GROUP BY pa.severidade;
END;
$$ LANGUAGE plpgsql;


-- ============================================================
-- VERIFICAÇÃO
-- ============================================================
/*
-- Verificar tabela criada
SELECT column_name, data_type
FROM information_schema.columns
WHERE table_name = 'pipeline_alerts'
ORDER BY ordinal_position;

-- Testar criação de alerta
SELECT public.criar_alerta(
    'test_run_123',
    NULL,
    'high_quarantine_rate',
    'warning',
    'Taxa de quarentena alta',
    'A taxa de quarentena está em 25%, acima do limite de 15%',
    '{"taxa": 25, "limite": 15}'::jsonb
);

-- Ver alertas abertos
SELECT * FROM public.vw_open_alerts;

-- Contar por severidade
SELECT * FROM public.contar_alertas_abertos();
*/
