-- =====================================================
-- SCRIPT: Paginação de Leilões com Filtros de Data
-- Execute este script no SQL Editor do Supabase
-- =====================================================

-- Remover função antiga se existir
DROP FUNCTION IF EXISTS pub.fetch_auctions_paginated;
DROP FUNCTION IF EXISTS public.fetch_auctions_paginated;

-- Função para buscar leilões com paginação e filtros avançados
-- IMPORTANTE: Criada no schema PUBLIC para ser acessível via API
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
    p_page_size INTEGER DEFAULT 20
)
RETURNS JSON
LANGUAGE plpgsql
SECURITY DEFINER
AS $$
DECLARE
    v_offset INTEGER;
    v_total INTEGER;
    v_data JSON;
BEGIN
    -- Calcular offset
    v_offset := (p_page - 1) * p_page_size;

    -- Contar total de registros com filtros
    SELECT COUNT(*)
    INTO v_total
    FROM pub.v_auction_discovery
    WHERE (p_uf IS NULL OR uf = p_uf)
      AND (p_cidade IS NULL OR cidade = p_cidade)
      AND (p_valor_min IS NULL OR valor_estimado >= p_valor_min)
      AND (p_valor_max IS NULL OR valor_estimado <= p_valor_max)
      AND (p_data_publicacao_de IS NULL OR data_publicacao >= p_data_publicacao_de)
      AND (p_data_publicacao_ate IS NULL OR data_publicacao <= p_data_publicacao_ate)
      AND (p_data_leilao_de IS NULL OR data_leilao >= p_data_leilao_de)
      AND (p_data_leilao_ate IS NULL OR data_leilao <= p_data_leilao_ate);

    -- Buscar dados paginados
    SELECT json_agg(row_to_json(t))
    INTO v_data
    FROM (
        SELECT *
        FROM pub.v_auction_discovery
        WHERE (p_uf IS NULL OR uf = p_uf)
          AND (p_cidade IS NULL OR cidade = p_cidade)
          AND (p_valor_min IS NULL OR valor_estimado >= p_valor_min)
          AND (p_valor_max IS NULL OR valor_estimado <= p_valor_max)
          AND (p_data_publicacao_de IS NULL OR data_publicacao >= p_data_publicacao_de)
          AND (p_data_publicacao_ate IS NULL OR data_publicacao <= p_data_publicacao_ate)
          AND (p_data_leilao_de IS NULL OR data_leilao >= p_data_leilao_de)
          AND (p_data_leilao_ate IS NULL OR data_leilao <= p_data_leilao_ate)
        ORDER BY data_leilao ASC NULLS LAST
        LIMIT p_page_size
        OFFSET v_offset
    ) t;

    -- Retornar resultado com metadados de paginação
    RETURN json_build_object(
        'data', COALESCE(v_data, '[]'::json),
        'total', v_total,
        'page', p_page,
        'pageSize', p_page_size,
        'totalPages', CEIL(v_total::NUMERIC / p_page_size)
    );
END;
$$;

-- Conceder permissão de execução
GRANT EXECUTE ON FUNCTION public.fetch_auctions_paginated TO anon, authenticated;

-- =====================================================
-- PRONTO! Execute e recarregue a página.
-- =====================================================
