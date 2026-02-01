-- ============================================================================
-- Migration 016: Criar tabela assinantes_tokens_acesso
-- ============================================================================
-- Tabela para armazenar tokens de acesso gerados após pagamentos no Asaas.
-- Usada pelo módulo src/integrations para autenticação de assinantes.
--
-- Executar no Supabase SQL Editor ou via CLI:
--   supabase db push
-- ============================================================================

-- 1. Criar tabela principal
CREATE TABLE IF NOT EXISTS public.assinantes_tokens_acesso (
    -- Identificador único
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),

    -- Dados do Asaas
    asaas_payment_id VARCHAR(50) NOT NULL,
    asaas_customer_id VARCHAR(50) NOT NULL,
    asaas_subscription_id VARCHAR(50),

    -- Dados do cliente
    cliente_nome VARCHAR(255),
    cliente_email VARCHAR(255) NOT NULL,
    cliente_cpf_cnpj VARCHAR(20),
    cliente_telefone VARCHAR(20),

    -- Token de acesso
    token VARCHAR(64) NOT NULL UNIQUE,
    token_expira_em TIMESTAMPTZ NOT NULL,
    token_ativo BOOLEAN NOT NULL DEFAULT TRUE,
    token_usado_em TIMESTAMPTZ,

    -- Dados do pagamento
    valor_pago DECIMAL(10, 2),
    forma_pagamento VARCHAR(50),

    -- Payload original (para auditoria/debug)
    webhook_payload JSONB,

    -- Metadados
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- 2. Índices para buscas frequentes
-- Busca por token (validação de acesso)
CREATE INDEX IF NOT EXISTS idx_tokens_acesso_token
    ON public.assinantes_tokens_acesso (token)
    WHERE token_ativo = TRUE;

-- Busca por email do cliente
CREATE INDEX IF NOT EXISTS idx_tokens_acesso_email
    ON public.assinantes_tokens_acesso (cliente_email);

-- Busca por payment_id (idempotência - evitar duplicatas)
CREATE INDEX IF NOT EXISTS idx_tokens_acesso_payment_id
    ON public.assinantes_tokens_acesso (asaas_payment_id);

-- Busca por customer_id (histórico do cliente)
CREATE INDEX IF NOT EXISTS idx_tokens_acesso_customer_id
    ON public.assinantes_tokens_acesso (asaas_customer_id);

-- Tokens ativos que vão expirar (para limpeza)
CREATE INDEX IF NOT EXISTS idx_tokens_acesso_expiracao
    ON public.assinantes_tokens_acesso (token_expira_em)
    WHERE token_ativo = TRUE;

-- 3. Trigger para atualizar updated_at automaticamente
CREATE OR REPLACE FUNCTION public.update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trigger_tokens_acesso_updated_at
    ON public.assinantes_tokens_acesso;

CREATE TRIGGER trigger_tokens_acesso_updated_at
    BEFORE UPDATE ON public.assinantes_tokens_acesso
    FOR EACH ROW
    EXECUTE FUNCTION public.update_updated_at_column();

-- 4. Row Level Security (RLS)
-- Habilitar RLS
ALTER TABLE public.assinantes_tokens_acesso ENABLE ROW LEVEL SECURITY;

-- Policy: Service role tem acesso total (para o backend)
CREATE POLICY "Service role full access"
    ON public.assinantes_tokens_acesso
    FOR ALL
    TO service_role
    USING (TRUE)
    WITH CHECK (TRUE);

-- Policy: Usuários autenticados podem ver apenas seus próprios tokens (pelo email)
CREATE POLICY "Users can view own tokens"
    ON public.assinantes_tokens_acesso
    FOR SELECT
    TO authenticated
    USING (cliente_email = auth.jwt() ->> 'email');

-- 5. Comentários para documentação
COMMENT ON TABLE public.assinantes_tokens_acesso IS
    'Tokens de acesso para assinantes gerados após confirmação de pagamento no Asaas';

COMMENT ON COLUMN public.assinantes_tokens_acesso.asaas_payment_id IS
    'ID do pagamento no Asaas (pay_xxx)';
COMMENT ON COLUMN public.assinantes_tokens_acesso.asaas_customer_id IS
    'ID do cliente no Asaas (cus_xxx)';
COMMENT ON COLUMN public.assinantes_tokens_acesso.asaas_subscription_id IS
    'ID da assinatura no Asaas (sub_xxx), se aplicável';
COMMENT ON COLUMN public.assinantes_tokens_acesso.token IS
    'Token único de 32 bytes URL-safe para acesso';
COMMENT ON COLUMN public.assinantes_tokens_acesso.token_expira_em IS
    'Data/hora de expiração do token (UTC)';
COMMENT ON COLUMN public.assinantes_tokens_acesso.token_ativo IS
    'Se FALSE, token foi usado ou invalidado';
COMMENT ON COLUMN public.assinantes_tokens_acesso.token_usado_em IS
    'Data/hora em que o token foi usado (primeiro acesso)';
COMMENT ON COLUMN public.assinantes_tokens_acesso.webhook_payload IS
    'Payload JSON original do webhook para auditoria';

-- ============================================================================
-- Verificação
-- ============================================================================
-- Executar após a migração para confirmar:
--
-- SELECT
--     column_name,
--     data_type,
--     is_nullable
-- FROM information_schema.columns
-- WHERE table_name = 'assinantes_tokens_acesso'
-- ORDER BY ordinal_position;
-- ============================================================================
