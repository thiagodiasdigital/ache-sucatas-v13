-- ============================================================================
-- MIGRACAO 014: Criar RPC unificada para dashboard
-- Data: 2026-01-30
-- Autor: Claude Code
-- Descricao: Funcao RPC que busca dados da view unificada com suporte a
--            filtro por fonte (p_source), paginacao e ordenacao.
-- ============================================================================

-- ============================================================================
-- FASE 1: CRIAR FUNCAO fetch_auctions_unified
-- ============================================================================

CREATE OR REPLACE FUNCTION public.fetch_auctions_unified(
    -- Filtros de localizacao
    p_uf TEXT DEFAULT NULL,
    p_cidade TEXT DEFAULT NULL,
    -- Filtros de valor
    p_valor_min NUMERIC DEFAULT NULL,
    p_valor_max NUMERIC DEFAULT NULL,
    -- Filtros de data
    p_data_leilao_de DATE DEFAULT NULL,
    p_data_leilao_ate DATE DEFAULT NULL,
    -- Paginacao
    p_page INTEGER DEFAULT 1,
    p_page_size INTEGER DEFAULT 20,
    -- Ordenacao
    p_ordenacao TEXT DEFAULT 'proximos',  -- 'proximos', 'distantes', 'valor_desc', 'valor_asc'
    -- Temporalidade
    p_temporalidade TEXT DEFAULT 'futuros',  -- 'futuros', 'passados', 'todos'
    -- NOVO: Filtro por fonte
    p_source TEXT DEFAULT NULL  -- 'pncp', 'leiloeiro', ou NULL para ambos
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
    -- Calcula offset
    v_offset := (COALESCE(p_page, 1) - 1) * COALESCE(p_page_size, 20);

    -- Conta total de registros com filtros
    SELECT COUNT(*) INTO v_total
    FROM pub.v_dashboard_lotes_unificado v
    WHERE
        -- Filtros de localizacao
        (p_uf IS NULL OR v.uf = p_uf)
        AND (p_cidade IS NULL OR UPPER(TRIM(v.cidade)) LIKE UPPER(TRIM('%' || p_cidade || '%')))
        -- Filtros de valor
        AND (p_valor_min IS NULL OR v.valor_estimado >= p_valor_min)
        AND (p_valor_max IS NULL OR v.valor_estimado <= p_valor_max)
        -- Filtros de data
        AND (p_data_leilao_de IS NULL OR v.data_leilao::DATE >= p_data_leilao_de)
        AND (p_data_leilao_ate IS NULL OR v.data_leilao::DATE <= p_data_leilao_ate)
        -- Temporalidade
        AND (
            p_temporalidade = 'todos'
            OR (p_temporalidade = 'futuros' AND v.status_temporal = 'futuro')
            OR (p_temporalidade = 'passados' AND v.status_temporal = 'passado')
        )
        -- NOVO: Filtro por fonte
        AND (p_source IS NULL OR v.source_type = p_source);

    -- Calcula total de paginas
    v_total_pages := CEIL(GREATEST(v_total, 1)::DECIMAL / COALESCE(p_page_size, 20));

    -- Busca dados paginados
    SELECT json_agg(row_to_json(t)) INTO v_data
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
            v.link_edital,
            v.link_leiloeiro,
            v.modalidade_leilao,
            v.valor_estimado,
            v.quantidade_itens,
            v.nome_leiloeiro,
            v.storage_path,
            v.score,
            v.created_at,
            v.source_type,
            v.source_name,
            v.metadata,
            v.codigo_ibge,
            v.latitude,
            v.longitude,
            v.municipio_oficial,
            v.status_temporal
        FROM pub.v_dashboard_lotes_unificado v
        WHERE
            -- Filtros de localizacao
            (p_uf IS NULL OR v.uf = p_uf)
            AND (p_cidade IS NULL OR UPPER(TRIM(v.cidade)) LIKE UPPER(TRIM('%' || p_cidade || '%')))
            -- Filtros de valor
            AND (p_valor_min IS NULL OR v.valor_estimado >= p_valor_min)
            AND (p_valor_max IS NULL OR v.valor_estimado <= p_valor_max)
            -- Filtros de data
            AND (p_data_leilao_de IS NULL OR v.data_leilao::DATE >= p_data_leilao_de)
            AND (p_data_leilao_ate IS NULL OR v.data_leilao::DATE <= p_data_leilao_ate)
            -- Temporalidade
            AND (
                p_temporalidade = 'todos'
                OR (p_temporalidade = 'futuros' AND v.status_temporal = 'futuro')
                OR (p_temporalidade = 'passados' AND v.status_temporal = 'passado')
            )
            -- NOVO: Filtro por fonte
            AND (p_source IS NULL OR v.source_type = p_source)
        ORDER BY
            -- Ordenacao por data do leilao
            CASE WHEN p_ordenacao = 'proximos' THEN v.data_leilao END ASC NULLS LAST,
            CASE WHEN p_ordenacao = 'distantes' THEN v.data_leilao END DESC NULLS LAST,
            -- Ordenacao por valor
            CASE WHEN p_ordenacao = 'valor_desc' THEN v.valor_estimado END DESC NULLS LAST,
            CASE WHEN p_ordenacao = 'valor_asc' THEN v.valor_estimado END ASC NULLS LAST
        LIMIT p_page_size
        OFFSET v_offset
    ) t;

    -- Retorna JSON com dados e metadata de paginacao
    RETURN json_build_object(
        'data', COALESCE(v_data, '[]'::JSON),
        'total', v_total,
        'page', COALESCE(p_page, 1),
        'pageSize', COALESCE(p_page_size, 20),
        'totalPages', v_total_pages,
        'source_filter', p_source
    );
END;
$$;

-- ============================================================================
-- FASE 2: GRANT PERMISSIONS
-- ============================================================================

GRANT EXECUTE ON FUNCTION public.fetch_auctions_unified TO authenticated;
GRANT EXECUTE ON FUNCTION public.fetch_auctions_unified TO anon;

-- ============================================================================
-- FASE 3: FUNCAO PARA LISTAR UFs DISPONIVEIS (UNIFICADA)
-- ============================================================================

CREATE OR REPLACE FUNCTION public.get_available_ufs_unified(
    p_source TEXT DEFAULT NULL  -- 'pncp', 'leiloeiro', ou NULL para ambos
)
RETURNS TABLE (
    uf CHAR(2),
    count BIGINT
)
LANGUAGE plpgsql
SECURITY DEFINER
AS $$
BEGIN
    RETURN QUERY
    SELECT
        v.uf::CHAR(2),
        COUNT(*)::BIGINT
    FROM pub.v_dashboard_lotes_unificado v
    WHERE
        v.uf IS NOT NULL
        AND v.status_temporal = 'futuro'
        AND (p_source IS NULL OR v.source_type = p_source)
    GROUP BY v.uf
    ORDER BY COUNT(*) DESC;
END;
$$;

GRANT EXECUTE ON FUNCTION public.get_available_ufs_unified TO authenticated;
GRANT EXECUTE ON FUNCTION public.get_available_ufs_unified TO anon;

-- ============================================================================
-- FASE 4: FUNCAO PARA LISTAR CIDADES POR UF (UNIFICADA)
-- ============================================================================

CREATE OR REPLACE FUNCTION public.get_cities_by_uf_unified(
    p_uf CHAR(2),
    p_source TEXT DEFAULT NULL  -- 'pncp', 'leiloeiro', ou NULL para ambos
)
RETURNS TABLE (
    cidade TEXT,
    count BIGINT
)
LANGUAGE plpgsql
SECURITY DEFINER
AS $$
BEGIN
    RETURN QUERY
    SELECT
        v.cidade::TEXT,
        COUNT(*)::BIGINT
    FROM pub.v_dashboard_lotes_unificado v
    WHERE
        v.uf = p_uf
        AND v.cidade IS NOT NULL
        AND v.status_temporal = 'futuro'
        AND (p_source IS NULL OR v.source_type = p_source)
    GROUP BY v.cidade
    ORDER BY COUNT(*) DESC;
END;
$$;

GRANT EXECUTE ON FUNCTION public.get_cities_by_uf_unified TO authenticated;
GRANT EXECUTE ON FUNCTION public.get_cities_by_uf_unified TO anon;

-- ============================================================================
-- FASE 5: COMENTARIOS
-- ============================================================================

COMMENT ON FUNCTION public.fetch_auctions_unified IS
'RPC principal para buscar lotes do dashboard unificado.
Suporta filtros por UF, cidade, valor, data, temporalidade e fonte.
Retorna JSON com dados paginados e metadata.

Parametros:
- p_source: "pncp", "leiloeiro", ou NULL para ambos
- p_ordenacao: "proximos", "distantes", "valor_desc", "valor_asc"
- p_temporalidade: "futuros", "passados", "todos"';

COMMENT ON FUNCTION public.get_available_ufs_unified IS
'Lista UFs disponiveis com contagem de lotes futuros.
Suporta filtro por fonte (p_source).';

COMMENT ON FUNCTION public.get_cities_by_uf_unified IS
'Lista cidades de uma UF com contagem de lotes futuros.
Suporta filtro por fonte (p_source).';

-- ============================================================================
-- VERIFICACAO FINAL
-- ============================================================================

DO $$
BEGIN
    IF EXISTS (
        SELECT 1 FROM pg_proc
        WHERE proname = 'fetch_auctions_unified'
    ) THEN
        RAISE NOTICE '========================================';
        RAISE NOTICE 'MIGRACAO 014 CONCLUIDA!';
        RAISE NOTICE '========================================';
        RAISE NOTICE 'Funcoes criadas:';
        RAISE NOTICE '  - fetch_auctions_unified(...)';
        RAISE NOTICE '  - get_available_ufs_unified(p_source)';
        RAISE NOTICE '  - get_cities_by_uf_unified(p_uf, p_source)';
        RAISE NOTICE '';
        RAISE NOTICE 'Novo parametro p_source aceita:';
        RAISE NOTICE '  - NULL: retorna ambas fontes';
        RAISE NOTICE '  - "pncp": apenas PNCP';
        RAISE NOTICE '  - "leiloeiro": apenas leiloeiros';
        RAISE NOTICE '';
        RAISE NOTICE 'Grants: anon, authenticated';
        RAISE NOTICE '========================================';
    ELSE
        RAISE EXCEPTION 'ERRO: Funcao fetch_auctions_unified nao foi criada!';
    END IF;
END $$;
