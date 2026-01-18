-- ============================================================================
-- SCHEMA SEMANA 2: NOTIFICAÇÕES E FILTROS DE USUÁRIO
-- Execute este arquivo no Supabase SQL Editor
-- ============================================================================

-- ============================================================================
-- TABELA: user_filters (Alertas Salvos do Usuário)
-- ============================================================================

CREATE TABLE IF NOT EXISTS pub.user_filters (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID REFERENCES auth.users(id) ON DELETE CASCADE NOT NULL,
    label TEXT NOT NULL,                          -- Ex: "Sucatas em SP até 50k"
    filter_params JSONB NOT NULL DEFAULT '{}',    -- Ex: {"uf": "SP", "tags": ["SUCATA"], "valor_max": 50000}
    is_active BOOLEAN DEFAULT true,               -- Permite desativar sem deletar
    created_at TIMESTAMPTZ DEFAULT now(),
    updated_at TIMESTAMPTZ DEFAULT now()
);

-- Comentário descritivo
COMMENT ON TABLE pub.user_filters IS 'Filtros salvos pelos usuários para receber alertas de novos leilões';
COMMENT ON COLUMN pub.user_filters.filter_params IS 'Parâmetros do filtro: uf, cidade, tags[], valor_min, valor_max';

-- ============================================================================
-- TABELA: notifications (Matches Gerados)
-- ============================================================================

CREATE TABLE IF NOT EXISTS pub.notifications (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID REFERENCES auth.users(id) ON DELETE CASCADE NOT NULL,
    auction_id BIGINT REFERENCES raw.leiloes(id) ON DELETE CASCADE NOT NULL,
    filter_id UUID REFERENCES pub.user_filters(id) ON DELETE SET NULL,  -- Qual filtro gerou
    is_read BOOLEAN DEFAULT false,
    created_at TIMESTAMPTZ DEFAULT now()
);

-- Comentário descritivo
COMMENT ON TABLE pub.notifications IS 'Notificações de novos leilões que correspondem aos filtros do usuário';

-- ============================================================================
-- ÍNDICES PARA PERFORMANCE
-- ============================================================================

CREATE INDEX IF NOT EXISTS idx_user_filters_user_id ON pub.user_filters(user_id);
CREATE INDEX IF NOT EXISTS idx_user_filters_active ON pub.user_filters(user_id) WHERE is_active = true;
CREATE INDEX IF NOT EXISTS idx_notifications_user_unread ON pub.notifications(user_id, created_at DESC) WHERE is_read = false;
CREATE INDEX IF NOT EXISTS idx_notifications_auction ON pub.notifications(auction_id);

-- ============================================================================
-- ROW LEVEL SECURITY (RLS)
-- ============================================================================

ALTER TABLE pub.user_filters ENABLE ROW LEVEL SECURITY;
ALTER TABLE pub.notifications ENABLE ROW LEVEL SECURITY;

-- Políticas para user_filters: usuários gerenciam apenas seus próprios dados
DROP POLICY IF EXISTS "Users can manage own filters" ON pub.user_filters;
CREATE POLICY "Users can manage own filters" ON pub.user_filters
    FOR ALL TO authenticated
    USING (auth.uid() = user_id)
    WITH CHECK (auth.uid() = user_id);

-- Políticas para notifications: usuários visualizam e atualizam suas próprias
DROP POLICY IF EXISTS "Users can view own notifications" ON pub.notifications;
CREATE POLICY "Users can view own notifications" ON pub.notifications
    FOR SELECT TO authenticated
    USING (auth.uid() = user_id);

DROP POLICY IF EXISTS "Users can update own notifications" ON pub.notifications;
CREATE POLICY "Users can update own notifications" ON pub.notifications
    FOR UPDATE TO authenticated
    USING (auth.uid() = user_id);

-- Service role pode inserir notificações (usado pelo trigger)
DROP POLICY IF EXISTS "Service can insert notifications" ON pub.notifications;
CREATE POLICY "Service can insert notifications" ON pub.notifications
    FOR INSERT TO service_role
    WITH CHECK (true);

-- ============================================================================
-- HABILITAR REALTIME PARA NOTIFICAÇÕES
-- ============================================================================

-- Nota: Execute apenas se ainda não estiver na publicação
-- ALTER PUBLICATION supabase_realtime ADD TABLE pub.notifications;

-- Verificar se já existe antes de adicionar
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_publication_tables
        WHERE pubname = 'supabase_realtime'
        AND tablename = 'notifications'
    ) THEN
        ALTER PUBLICATION supabase_realtime ADD TABLE pub.notifications;
    END IF;
END $$;

-- ============================================================================
-- FUNÇÃO DE MATCH-MAKING (Trigger)
-- ============================================================================

CREATE OR REPLACE FUNCTION audit.fn_match_and_notify()
RETURNS TRIGGER AS $$
DECLARE
    f RECORD;
    filter_tags TEXT[];
    leilao_tags TEXT[];
    tags_match BOOLEAN;
BEGIN
    -- Converter tags do leilão para array (pode ser NULL)
    leilao_tags := NEW.tags;

    -- Itera sobre todos os filtros ATIVOS
    FOR f IN SELECT * FROM pub.user_filters WHERE is_active = true LOOP

        -- Extrair tags do filtro (JSONB array -> PostgreSQL array)
        -- Se não houver tags no filtro, será NULL
        IF f.filter_params ? 'tags' AND jsonb_array_length(f.filter_params->'tags') > 0 THEN
            filter_tags := ARRAY(
                SELECT jsonb_array_elements_text(f.filter_params->'tags')
            );
        ELSE
            filter_tags := NULL;
        END IF;

        -- Verificar match de tags (se filtro tem tags, leilão deve ter pelo menos uma)
        -- Operador && verifica overlap (elementos em comum)
        tags_match := (
            filter_tags IS NULL OR
            array_length(filter_tags, 1) IS NULL OR
            (leilao_tags IS NOT NULL AND leilao_tags && filter_tags)
        );

        -- Lógica de Match Completa
        IF (
            -- UF (se definida no filtro)
            (
                f.filter_params->>'uf' IS NULL OR
                f.filter_params->>'uf' = '' OR
                f.filter_params->>'uf' = NEW.uf
            ) AND

            -- Cidade (case insensitive, partial match)
            (
                f.filter_params->>'cidade' IS NULL OR
                f.filter_params->>'cidade' = '' OR
                UPPER(COALESCE(NEW.cidade, '')) LIKE '%' || UPPER(f.filter_params->>'cidade') || '%'
            ) AND

            -- Tags (overlap)
            tags_match AND

            -- Valor máximo
            (
                f.filter_params->>'valor_max' IS NULL OR
                f.filter_params->>'valor_max' = '' OR
                NEW.valor_estimado IS NULL OR
                NEW.valor_estimado <= (f.filter_params->>'valor_max')::numeric
            ) AND

            -- Valor mínimo
            (
                f.filter_params->>'valor_min' IS NULL OR
                f.filter_params->>'valor_min' = '' OR
                NEW.valor_estimado IS NULL OR
                NEW.valor_estimado >= (f.filter_params->>'valor_min')::numeric
            )
        ) THEN
            -- Match encontrado! Criar notificação
            -- Evitar duplicatas (mesmo user, mesmo auction)
            INSERT INTO pub.notifications (user_id, auction_id, filter_id)
            VALUES (f.user_id, NEW.id, f.id)
            ON CONFLICT DO NOTHING;
        END IF;

    END LOOP;

    RETURN NEW;
END;
$$ LANGUAGE plpgsql SECURITY DEFINER;

-- Comentário para documentação
COMMENT ON FUNCTION audit.fn_match_and_notify() IS
'Verifica novos leilões contra filtros de usuários e cria notificações para matches';

-- ============================================================================
-- TRIGGER: Dispara a cada INSERT em raw.leiloes
-- ============================================================================

-- Remover trigger antigo se existir
DROP TRIGGER IF EXISTS trg_check_matches_on_insert ON raw.leiloes;

-- Criar trigger
CREATE TRIGGER trg_check_matches_on_insert
AFTER INSERT ON raw.leiloes
FOR EACH ROW
EXECUTE FUNCTION audit.fn_match_and_notify();

-- ============================================================================
-- CONSTRAINT ÚNICA PARA EVITAR NOTIFICAÇÕES DUPLICADAS
-- ============================================================================

-- Adicionar constraint única para evitar múltiplas notificações do mesmo leilão para o mesmo usuário
ALTER TABLE pub.notifications
DROP CONSTRAINT IF EXISTS unique_user_auction_notification;

ALTER TABLE pub.notifications
ADD CONSTRAINT unique_user_auction_notification
UNIQUE (user_id, auction_id);

-- ============================================================================
-- FUNÇÕES RPC PARA O FRONTEND
-- ============================================================================

-- Função para buscar notificações não lidas
CREATE OR REPLACE FUNCTION pub.get_unread_notifications(p_limit INT DEFAULT 10)
RETURNS TABLE (
    id UUID,
    auction_id BIGINT,
    filter_id UUID,
    filter_label TEXT,
    created_at TIMESTAMPTZ,
    -- Dados do leilão
    titulo TEXT,
    orgao TEXT,
    uf TEXT,
    cidade TEXT,
    valor_estimado NUMERIC,
    tags TEXT[],
    data_leilao TIMESTAMPTZ
) AS $$
BEGIN
    RETURN QUERY
    SELECT
        n.id,
        n.auction_id,
        n.filter_id,
        uf.label as filter_label,
        n.created_at,
        l.titulo,
        l.orgao,
        l.uf,
        l.cidade,
        l.valor_estimado,
        l.tags,
        l.data_leilao
    FROM pub.notifications n
    JOIN raw.leiloes l ON l.id = n.auction_id
    LEFT JOIN pub.user_filters uf ON uf.id = n.filter_id
    WHERE n.user_id = auth.uid()
      AND n.is_read = false
    ORDER BY n.created_at DESC
    LIMIT p_limit;
END;
$$ LANGUAGE plpgsql SECURITY DEFINER;

-- Função para marcar notificação como lida
CREATE OR REPLACE FUNCTION pub.mark_notification_read(p_notification_id UUID)
RETURNS BOOLEAN AS $$
BEGIN
    UPDATE pub.notifications
    SET is_read = true
    WHERE id = p_notification_id
      AND user_id = auth.uid();

    RETURN FOUND;
END;
$$ LANGUAGE plpgsql SECURITY DEFINER;

-- Função para marcar todas as notificações como lidas
CREATE OR REPLACE FUNCTION pub.mark_all_notifications_read()
RETURNS INT AS $$
DECLARE
    updated_count INT;
BEGIN
    UPDATE pub.notifications
    SET is_read = true
    WHERE user_id = auth.uid()
      AND is_read = false;

    GET DIAGNOSTICS updated_count = ROW_COUNT;
    RETURN updated_count;
END;
$$ LANGUAGE plpgsql SECURITY DEFINER;

-- Função para contar notificações não lidas
CREATE OR REPLACE FUNCTION pub.count_unread_notifications()
RETURNS INT AS $$
BEGIN
    RETURN (
        SELECT COUNT(*)::INT
        FROM pub.notifications
        WHERE user_id = auth.uid()
          AND is_read = false
    );
END;
$$ LANGUAGE plpgsql SECURITY DEFINER;

-- ============================================================================
-- FIM DO SCHEMA SEMANA 2
-- ============================================================================
