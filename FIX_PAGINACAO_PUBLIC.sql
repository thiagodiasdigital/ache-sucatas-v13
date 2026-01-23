-- ============================================================================
-- FIX: ATUALIZAR FUNCAO fetch_auctions_paginated NO SCHEMA PUBLIC
-- ============================================================================
-- Data: 2026-01-23
-- Problema: Frontend chama public.fetch_auctions_paginated mas a funcao nao
--           aceita os parametros p_ordenacao e p_temporalidade
-- ============================================================================

-- Dropar versao antiga
DROP FUNCTION IF EXISTS public.fetch_auctions_paginated(TEXT, TEXT, NUMERIC, NUMERIC, DATE, DATE, DATE, DATE, INTEGER, INTEGER);
DROP FUNCTION IF EXISTS public.fetch_auctions_paginated(TEXT, TEXT, NUMERIC, NUMERIC, DATE, DATE, DATE, DATE, INTEGER, INTEGER, TEXT, TEXT);

-- Verificar se a VIEW tem o campo status_temporal
DO $$
BEGIN
    -- Tentar adicionar o campo se nao existir
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_schema = 'pub'
        AND table_name = 'v_auction_discovery'
        AND column_name = 'status_temporal'
    ) THEN
        RAISE NOTICE 'VIEW nao tem status_temporal - sera necessario recriar a VIEW';
    ELSE
        RAISE NOTICE 'VIEW ja tem status_temporal - OK';
    END IF;
END $$;

-- ============================================================================
-- CRIAR FUNCAO ATUALIZADA COM TODOS OS PARAMETROS
-- ============================================================================

CREATE OR REPLACE FUNCTION public.fetch_auctions_paginated(
    p_uf TEXT DEFAULT NULL,
    p_cidade TEXT DEFAULT NULL,
    p_valor_min NUMERIC DEFAULT NULL,
    p_valor_max NUMERIC DEFAULT NULL,
    p_data_publicacao_de DATE DEFAULT NULL,
    p_data_publicacao_ate DATE DEFAULT NULL,
    p_data_leilao_de DATE DEFAULT NULL,
    p_data_leilao_ate DATE DEFAULT NULL,
    p_page INTEGER DEFAULT 1,
    p_page_size INTEGER DEFAULT 20,
    p_ordenacao TEXT DEFAULT 'proximos',
    p_temporalidade TEXT DEFAULT 'futuros'
)
RETURNS JSON
LANGUAGE plpgsql
SECURITY DEFINER
AS $$
DECLARE
    v_total INTEGER;
    v_total_pages INTEGER;
    v_offset INTEGER;
    v_data JSON;
BEGIN
    v_offset := (p_page - 1) * p_page_size;

    -- Contar total com filtro de temporalidade
    SELECT COUNT(*) INTO v_total
    FROM pub.v_auction_discovery v
    WHERE
        (p_uf IS NULL OR v.uf = p_uf)
        AND (p_cidade IS NULL OR UPPER(v.cidade) LIKE UPPER('%' || p_cidade || '%'))
        AND (p_valor_min IS NULL OR v.valor_estimado >= p_valor_min)
        AND (p_valor_max IS NULL OR v.valor_estimado <= p_valor_max)
        AND (p_data_publicacao_de IS NULL OR v.data_publicacao >= p_data_publicacao_de)
        AND (p_data_publicacao_ate IS NULL OR v.data_publicacao <= p_data_publicacao_ate)
        AND (p_data_leilao_de IS NULL OR v.data_leilao::date >= p_data_leilao_de)
        AND (p_data_leilao_ate IS NULL OR v.data_leilao::date <= p_data_leilao_ate)
        AND (
            p_temporalidade = 'todos'
            OR (p_temporalidade = 'futuros' AND v.data_leilao >= CURRENT_DATE)
            OR (p_temporalidade = 'passados' AND v.data_leilao < CURRENT_DATE)
        );

    v_total_pages := CEIL(GREATEST(v_total, 1)::DECIMAL / p_page_size);

    -- Buscar dados paginados com ordenacao
    SELECT json_agg(row_to_json(t))
    INTO v_data
    FROM (
        SELECT
            v.id,
            v.id_interno,
            v.pncp_id,
            v.orgao,
            v.uf,
            v.cidade,
            v.n_edital,
            v.data_publicacao,
            v.data_leilao,
            v.titulo,
            v.descricao,
            v.objeto_resumido,
            v.tags,
            v.link_pncp,
            v.link_leiloeiro,
            v.modalidade_leilao,
            v.valor_estimado,
            v.quantidade_itens,
            v.nome_leiloeiro,
            v.storage_path,
            v.score,
            v.created_at,
            v.codigo_ibge,
            v.latitude,
            v.longitude,
            v.municipio_oficial,
            CASE
                WHEN v.data_leilao >= CURRENT_DATE THEN 'futuro'
                ELSE 'passado'
            END AS status_temporal
        FROM pub.v_auction_discovery v
        WHERE
            (p_uf IS NULL OR v.uf = p_uf)
            AND (p_cidade IS NULL OR UPPER(v.cidade) LIKE UPPER('%' || p_cidade || '%'))
            AND (p_valor_min IS NULL OR v.valor_estimado >= p_valor_min)
            AND (p_valor_max IS NULL OR v.valor_estimado <= p_valor_max)
            AND (p_data_publicacao_de IS NULL OR v.data_publicacao >= p_data_publicacao_de)
            AND (p_data_publicacao_ate IS NULL OR v.data_publicacao <= p_data_publicacao_ate)
            AND (p_data_leilao_de IS NULL OR v.data_leilao::date >= p_data_leilao_de)
            AND (p_data_leilao_ate IS NULL OR v.data_leilao::date <= p_data_leilao_ate)
            AND (
                p_temporalidade = 'todos'
                OR (p_temporalidade = 'futuros' AND v.data_leilao >= CURRENT_DATE)
                OR (p_temporalidade = 'passados' AND v.data_leilao < CURRENT_DATE)
            )
        ORDER BY
            CASE WHEN p_ordenacao = 'proximos' THEN v.data_leilao END ASC NULLS LAST,
            CASE WHEN p_ordenacao = 'distantes' THEN v.data_leilao END DESC NULLS LAST,
            CASE WHEN p_ordenacao = 'recentes' THEN v.data_publicacao END DESC NULLS LAST,
            CASE WHEN p_ordenacao = 'antigos' THEN v.data_publicacao END ASC NULLS LAST
        LIMIT p_page_size
        OFFSET v_offset
    ) t;

    -- Retornar resultado com metadados
    RETURN json_build_object(
        'data', COALESCE(v_data, '[]'::json),
        'total', v_total,
        'page', p_page,
        'pageSize', p_page_size,
        'totalPages', v_total_pages,
        'temporalidade', p_temporalidade
    );
END;
$$;

-- Permissoes
GRANT EXECUTE ON FUNCTION public.fetch_auctions_paginated(TEXT, TEXT, NUMERIC, NUMERIC, DATE, DATE, DATE, DATE, INTEGER, INTEGER, TEXT, TEXT) TO anon, authenticated;

-- ============================================================================
-- VERIFICACAO
-- ============================================================================

-- Testar a funcao
SELECT
    'Teste da funcao' AS info,
    (public.fetch_auctions_paginated(
        NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL,
        1, 20, 'proximos', 'futuros'
    )::json->>'total')::int AS total_futuros,
    (public.fetch_auctions_paginated(
        NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL,
        1, 20, 'proximos', 'todos'
    )::json->>'total')::int AS total_todos,
    (public.fetch_auctions_paginated(
        NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL,
        1, 20, 'proximos', 'futuros'
    )::json->>'totalPages')::int AS total_paginas_futuros;

DO $$
BEGIN
    RAISE NOTICE '========================================';
    RAISE NOTICE 'FUNCAO ATUALIZADA COM SUCESSO!';
    RAISE NOTICE '========================================';
    RAISE NOTICE 'A funcao agora aceita p_ordenacao e p_temporalidade';
    RAISE NOTICE 'Recarregue a pagina do dashboard para testar';
    RAISE NOTICE '========================================';
END $$;

-- ============================================================================
-- FIM
-- ============================================================================
