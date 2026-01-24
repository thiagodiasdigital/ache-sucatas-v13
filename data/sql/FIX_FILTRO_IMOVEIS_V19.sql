-- ============================================================================
-- ACHE SUCATAS - FIX V19: FILTRO DE IMOVEIS
-- ============================================================================
-- Data: 2026-01-24
-- Problema: Editais de imoveis estavam aparecendo no dashboard
-- Solucao: Adicionar filtro na VIEW para excluir editais com tag IMOVEL
--          que NAO tenham tags VEICULO ou SUCATA
-- ============================================================================

-- ============================================================================
-- PASSO 0: DROPAR VIEW E FUNCOES DEPENDENTES
-- ============================================================================

DROP FUNCTION IF EXISTS pub.fetch_auctions_paginated(TEXT, TEXT, DECIMAL, DECIMAL, DATE, DATE, DATE, DATE, INTEGER, INTEGER, TEXT);
DROP FUNCTION IF EXISTS pub.fetch_auctions_paginated(TEXT, TEXT, DECIMAL, DECIMAL, DATE, DATE, DATE, DATE, INTEGER, INTEGER, TEXT, TEXT);
DROP FUNCTION IF EXISTS public.fetch_auctions_paginated(TEXT, TEXT, NUMERIC, NUMERIC, DATE, DATE, DATE, DATE, INTEGER, INTEGER);
DROP FUNCTION IF EXISTS public.fetch_auctions_paginated(TEXT, TEXT, NUMERIC, NUMERIC, DATE, DATE, DATE, DATE, INTEGER, INTEGER, TEXT, TEXT);
DROP FUNCTION IF EXISTS pub.get_available_ufs();
DROP FUNCTION IF EXISTS pub.get_cities_by_uf(CHAR);
DROP FUNCTION IF EXISTS pub.get_dashboard_stats();

DROP VIEW IF EXISTS pub.v_auction_discovery CASCADE;

-- ============================================================================
-- PASSO 1: CRIAR VIEW COM FILTRO DE IMOVEIS
-- ============================================================================
-- Regra: Excluir editais que tenham tag IMOVEL mas NAO tenham VEICULO/SUCATA
-- Isso permite editais mistos (veiculo + imovel) mas bloqueia imoveis puros

CREATE VIEW pub.v_auction_discovery AS
SELECT
    e.id,
    e.id_interno,
    e.pncp_id,
    e.orgao,
    e.uf,
    e.cidade,
    e.n_edital,
    e.data_publicacao,
    e.data_leilao,
    e.titulo,
    e.descricao,
    e.objeto_resumido,
    e.tags,
    e.link_pncp,
    e.link_leiloeiro,
    e.modalidade_leilao,
    e.valor_estimado,
    e.quantidade_itens,
    e.nome_leiloeiro,
    e.storage_path,
    e.score,
    e.created_at,
    -- Dados geograficos
    m.codigo_ibge,
    m.latitude,
    m.longitude,
    m.nome_municipio AS municipio_oficial,
    -- Campo auxiliar para facilitar filtros no frontend
    CASE
        WHEN e.data_leilao >= CURRENT_DATE THEN 'futuro'
        ELSE 'passado'
    END AS status_temporal
FROM public.editais_leilao e
LEFT JOIN pub.ref_municipios m
    ON UPPER(TRIM(e.cidade)) = UPPER(TRIM(m.nome_municipio))
    AND e.uf = m.uf
WHERE
    -- Filtro obrigatorio: link_pncp
    e.link_pncp IS NOT NULL
    AND e.link_pncp != ''
    -- V19 FIX: Excluir imoveis puros (sem veiculos)
    -- Logica: NAO (tem IMOVEL E NAO tem (VEICULO OU SUCATA OU MOTO OU CAMINHAO OU ONIBUS))
    AND NOT (
        'IMOVEL' = ANY(e.tags)
        AND NOT (
            'VEICULO' = ANY(e.tags) OR
            'SUCATA' = ANY(e.tags) OR
            'MOTO' = ANY(e.tags) OR
            'CAMINHAO' = ANY(e.tags) OR
            'ONIBUS' = ANY(e.tags)
        )
    )
ORDER BY e.data_leilao DESC;

COMMENT ON VIEW pub.v_auction_discovery IS
'View de producao V19 - Exclui imoveis puros. Ache Sucatas e focado em veiculos.';

-- ============================================================================
-- PASSO 2: RECRIAR FUNCAO DE PAGINACAO (pub schema)
-- ============================================================================

CREATE OR REPLACE FUNCTION pub.fetch_auctions_paginated(
    p_uf TEXT DEFAULT NULL,
    p_cidade TEXT DEFAULT NULL,
    p_valor_min DECIMAL DEFAULT NULL,
    p_valor_max DECIMAL DEFAULT NULL,
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

    RETURN (
        SELECT json_build_object(
            'data', COALESCE((
                SELECT json_agg(row_to_json(t))
                FROM (
                    SELECT
                        v.id, v.id_interno, v.pncp_id, v.orgao, v.uf, v.cidade,
                        v.n_edital, v.data_publicacao, v.data_leilao, v.titulo,
                        v.descricao, v.objeto_resumido, v.tags, v.link_pncp,
                        v.link_leiloeiro, v.modalidade_leilao, v.valor_estimado,
                        v.quantidade_itens, v.nome_leiloeiro, v.storage_path,
                        v.score, v.created_at, v.codigo_ibge, v.latitude,
                        v.longitude, v.municipio_oficial, v.status_temporal
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
                ) t
            ), '[]'::json),
            'total', v_total,
            'page', p_page,
            'pageSize', p_page_size,
            'totalPages', v_total_pages,
            'temporalidade', p_temporalidade
        )
    );
END;
$$;

-- ============================================================================
-- PASSO 3: RECRIAR FUNCAO DE PAGINACAO (public schema - usado pelo frontend)
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

    SELECT json_agg(row_to_json(t))
    INTO v_data
    FROM (
        SELECT
            v.id, v.id_interno, v.pncp_id, v.orgao, v.uf, v.cidade,
            v.n_edital, v.data_publicacao, v.data_leilao, v.titulo,
            v.descricao, v.objeto_resumido, v.tags, v.link_pncp,
            v.link_leiloeiro, v.modalidade_leilao, v.valor_estimado,
            v.quantidade_itens, v.nome_leiloeiro, v.storage_path,
            v.score, v.created_at, v.codigo_ibge, v.latitude,
            v.longitude, v.municipio_oficial,
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

-- ============================================================================
-- PASSO 4: RECRIAR FUNCOES AUXILIARES
-- ============================================================================

CREATE OR REPLACE FUNCTION pub.get_available_ufs()
RETURNS TABLE(uf CHAR(2), count BIGINT)
LANGUAGE sql STABLE
AS $$
    SELECT uf, COUNT(*) as count
    FROM pub.v_auction_discovery
    WHERE uf IS NOT NULL
    GROUP BY uf
    ORDER BY count DESC;
$$;

CREATE OR REPLACE FUNCTION pub.get_cities_by_uf(p_uf CHAR(2))
RETURNS TABLE(cidade VARCHAR, count BIGINT)
LANGUAGE sql STABLE
AS $$
    SELECT cidade, COUNT(*) as count
    FROM pub.v_auction_discovery
    WHERE uf = p_uf AND cidade IS NOT NULL
    GROUP BY cidade
    ORDER BY count DESC;
$$;

CREATE OR REPLACE FUNCTION pub.get_dashboard_stats()
RETURNS TABLE(
    total_leiloes BIGINT,
    total_futuros BIGINT,
    total_passados BIGINT,
    total_ufs BIGINT,
    total_cidades BIGINT,
    valor_total_estimado DECIMAL,
    leiloes_proximos_7_dias BIGINT
)
LANGUAGE sql STABLE
AS $$
    SELECT
        COUNT(*) as total_leiloes,
        COUNT(*) FILTER (WHERE data_leilao >= CURRENT_DATE) as total_futuros,
        COUNT(*) FILTER (WHERE data_leilao < CURRENT_DATE) as total_passados,
        COUNT(DISTINCT uf) as total_ufs,
        COUNT(DISTINCT cidade) as total_cidades,
        COALESCE(SUM(valor_estimado), 0) as valor_total_estimado,
        COUNT(*) FILTER (WHERE data_leilao BETWEEN CURRENT_DATE AND CURRENT_DATE + INTERVAL '7 days') as leiloes_proximos_7_dias
    FROM pub.v_auction_discovery;
$$;

-- ============================================================================
-- PASSO 5: PERMISSOES
-- ============================================================================

GRANT SELECT ON pub.v_auction_discovery TO authenticated, anon;
GRANT EXECUTE ON FUNCTION pub.fetch_auctions_paginated TO authenticated, anon;
GRANT EXECUTE ON FUNCTION public.fetch_auctions_paginated(TEXT, TEXT, NUMERIC, NUMERIC, DATE, DATE, DATE, DATE, INTEGER, INTEGER, TEXT, TEXT) TO anon, authenticated;
GRANT EXECUTE ON FUNCTION pub.get_available_ufs TO authenticated, anon;
GRANT EXECUTE ON FUNCTION pub.get_cities_by_uf TO authenticated, anon;
GRANT EXECUTE ON FUNCTION pub.get_dashboard_stats TO authenticated, anon;

-- ============================================================================
-- PASSO 6: VERIFICACAO
-- ============================================================================

SELECT '=== FIX V19: FILTRO DE IMOVEIS ===' AS info;

SELECT
    'Total na VIEW (sem imoveis)' AS metrica,
    COUNT(*)::TEXT AS valor
FROM pub.v_auction_discovery

UNION ALL SELECT 'Leiloes futuros', COUNT(*)::TEXT
FROM pub.v_auction_discovery WHERE status_temporal = 'futuro'

UNION ALL SELECT 'Leiloes passados', COUNT(*)::TEXT
FROM pub.v_auction_discovery WHERE status_temporal = 'passado';

-- Verificar se ainda existem imoveis puros na VIEW (deve ser 0)
SELECT
    'Imoveis puros na VIEW (deve ser 0)' AS verificacao,
    COUNT(*)::TEXT AS quantidade
FROM pub.v_auction_discovery
WHERE
    'IMOVEL' = ANY(tags)
    AND NOT (
        'VEICULO' = ANY(tags) OR
        'SUCATA' = ANY(tags) OR
        'MOTO' = ANY(tags) OR
        'CAMINHAO' = ANY(tags) OR
        'ONIBUS' = ANY(tags)
    );

DO $$
BEGIN
    RAISE NOTICE '========================================';
    RAISE NOTICE 'FIX V19 APLICADO COM SUCESSO!';
    RAISE NOTICE '========================================';
    RAISE NOTICE 'VIEW recriada com filtro de imoveis';
    RAISE NOTICE 'Imoveis puros nao aparecerao mais';
    RAISE NOTICE 'Editais mistos (veiculo+imovel) continuam';
    RAISE NOTICE '========================================';
END $$;

-- ============================================================================
-- FIM DO SCRIPT
-- ============================================================================
