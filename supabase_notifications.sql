-- =====================================================
-- SCRIPT: Sistema de Notificações
-- Execute este script no SQL Editor do Supabase
-- =====================================================

-- 1. Criar tabela de notificações (se não existir)
CREATE TABLE IF NOT EXISTS pub.notifications (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
    auction_id INTEGER REFERENCES pub.v_auction_discovery(id),
    filter_id UUID NULL,
    filter_label TEXT NULL,
    is_read BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Índices para performance
CREATE INDEX IF NOT EXISTS idx_notifications_user_id ON pub.notifications(user_id);
CREATE INDEX IF NOT EXISTS idx_notifications_is_read ON pub.notifications(user_id, is_read);
CREATE INDEX IF NOT EXISTS idx_notifications_created_at ON pub.notifications(created_at DESC);

-- 2. Habilitar RLS (Row Level Security)
ALTER TABLE pub.notifications ENABLE ROW LEVEL SECURITY;

-- Política: usuários só veem suas próprias notificações
DROP POLICY IF EXISTS "Users can view own notifications" ON pub.notifications;
CREATE POLICY "Users can view own notifications" ON pub.notifications
    FOR SELECT USING (auth.uid() = user_id);

-- Política: usuários podem atualizar suas próprias notificações
DROP POLICY IF EXISTS "Users can update own notifications" ON pub.notifications;
CREATE POLICY "Users can update own notifications" ON pub.notifications
    FOR UPDATE USING (auth.uid() = user_id);

-- =====================================================
-- 3. Função: get_unread_notifications
-- Retorna notificações não lidas do usuário logado
-- =====================================================
CREATE OR REPLACE FUNCTION pub.get_unread_notifications(p_limit INTEGER DEFAULT 20)
RETURNS TABLE (
    id UUID,
    auction_id INTEGER,
    filter_id UUID,
    filter_label TEXT,
    created_at TIMESTAMPTZ,
    titulo TEXT,
    orgao TEXT,
    uf TEXT,
    cidade TEXT,
    valor_estimado NUMERIC,
    tags TEXT[],
    data_leilao DATE
)
LANGUAGE plpgsql
SECURITY DEFINER
AS $$
BEGIN
    RETURN QUERY
    SELECT
        n.id,
        n.auction_id,
        n.filter_id,
        n.filter_label,
        n.created_at,
        a.titulo,
        a.orgao,
        a.uf,
        a.cidade,
        a.valor_estimado,
        a.tags,
        a.data_leilao
    FROM pub.notifications n
    LEFT JOIN pub.v_auction_discovery a ON a.id = n.auction_id
    WHERE n.user_id = auth.uid()
      AND n.is_read = FALSE
    ORDER BY n.created_at DESC
    LIMIT p_limit;
END;
$$;

-- =====================================================
-- 4. Função: mark_notification_read
-- Marca uma notificação específica como lida
-- =====================================================
CREATE OR REPLACE FUNCTION pub.mark_notification_read(p_notification_id UUID)
RETURNS VOID
LANGUAGE plpgsql
SECURITY DEFINER
AS $$
BEGIN
    UPDATE pub.notifications
    SET is_read = TRUE
    WHERE id = p_notification_id
      AND user_id = auth.uid();
END;
$$;

-- =====================================================
-- 5. Função: mark_all_notifications_read
-- Marca todas as notificações do usuário como lidas
-- =====================================================
CREATE OR REPLACE FUNCTION pub.mark_all_notifications_read()
RETURNS VOID
LANGUAGE plpgsql
SECURITY DEFINER
AS $$
BEGIN
    UPDATE pub.notifications
    SET is_read = TRUE
    WHERE user_id = auth.uid()
      AND is_read = FALSE;
END;
$$;

-- =====================================================
-- 6. Conceder permissões
-- =====================================================
GRANT USAGE ON SCHEMA pub TO authenticated;
GRANT SELECT, UPDATE ON pub.notifications TO authenticated;
GRANT EXECUTE ON FUNCTION pub.get_unread_notifications TO authenticated;
GRANT EXECUTE ON FUNCTION pub.mark_notification_read TO authenticated;
GRANT EXECUTE ON FUNCTION pub.mark_all_notifications_read TO authenticated;

-- =====================================================
-- PRONTO! As funções foram criadas.
-- =====================================================
