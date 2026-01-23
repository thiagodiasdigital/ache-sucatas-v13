-- ============================================================================
-- CORREÇÃO DEFINITIVA - ACHE SUCATAS
-- ============================================================================
-- Data: 2026-01-20
-- Problema: Frontend lê de raw.leiloes mas dados corretos estão em editais_leilao
-- Solução: Mudar view para ler diretamente de editais_leilao
-- ============================================================================
--
-- COMO EXECUTAR:
-- 1. Acesse https://supabase.com/dashboard
-- 2. Selecione seu projeto
-- 3. Vá em "SQL Editor" (menu lateral esquerdo)
-- 4. Cole TODO este conteúdo
-- 5. Clique no botão "Run" (ou pressione Ctrl+Enter)
-- 6. Aguarde a mensagem "Success"
-- 7. Atualize o dashboard do frontend (F5)
--
-- ============================================================================

-- ============================================================================
-- PASSO 1: DIAGNÓSTICO (ver situação atual)
-- ============================================================================

DO $$
DECLARE
    v_editais INTEGER;
    v_raw INTEGER;
    v_view INTEGER;
BEGIN
    SELECT COUNT(*) INTO v_editais FROM public.editais_leilao;
    SELECT COUNT(*) INTO v_raw FROM raw.leiloes;
    SELECT COUNT(*) INTO v_view FROM pub.v_auction_discovery;

    RAISE NOTICE '========================================';
    RAISE NOTICE 'DIAGNÓSTICO ANTES DA CORREÇÃO';
    RAISE NOTICE '========================================';
    RAISE NOTICE 'public.editais_leilao: % registros', v_editais;
    RAISE NOTICE 'raw.leiloes: % registros', v_raw;
    RAISE NOTICE 'pub.v_auction_discovery: % registros', v_view;
    RAISE NOTICE '========================================';
END $$;

-- ============================================================================
-- PASSO 2: CRIAR NOVA VIEW (lendo de editais_leilao)
-- ============================================================================

CREATE OR REPLACE VIEW pub.v_auction_discovery AS
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
    -- Dados geográficos do município (para mapa)
    m.codigo_ibge,
    m.latitude,
    m.longitude,
    m.nome_municipio AS municipio_oficial
FROM public.editais_leilao e
LEFT JOIN pub.ref_municipios m
    ON UPPER(TRIM(e.cidade)) = UPPER(TRIM(m.nome_municipio))
    AND e.uf = m.uf
WHERE
    -- Filtro 1: Só leilões com data futura (>= hoje)
    e.data_leilao >= CURRENT_DATE
    -- Filtro 2: Precisa ter link_pncp (obrigatório)
    AND e.link_pncp IS NOT NULL
    AND e.link_pncp != ''
ORDER BY e.data_leilao ASC;  -- Mais próximos primeiro

COMMENT ON VIEW pub.v_auction_discovery IS 'View de produção - Lê de editais_leilao com filtro de data futura';

-- ============================================================================
-- PASSO 3: VERIFICAR RESULTADO
-- ============================================================================

DO $$
DECLARE
    v_view_nova INTEGER;
    v_sem_titulo INTEGER;
    v_sem_link_leiloeiro INTEGER;
    v_com_link_leiloeiro INTEGER;
BEGIN
    SELECT COUNT(*) INTO v_view_nova FROM pub.v_auction_discovery;

    SELECT COUNT(*) INTO v_sem_titulo
    FROM pub.v_auction_discovery
    WHERE titulo IS NULL OR titulo = '';

    SELECT COUNT(*) INTO v_sem_link_leiloeiro
    FROM pub.v_auction_discovery
    WHERE link_leiloeiro IS NULL OR link_leiloeiro = '' OR link_leiloeiro = 'N/D';

    SELECT COUNT(*) INTO v_com_link_leiloeiro
    FROM pub.v_auction_discovery
    WHERE link_leiloeiro IS NOT NULL AND link_leiloeiro != '' AND link_leiloeiro != 'N/D';

    RAISE NOTICE '========================================';
    RAISE NOTICE 'RESULTADO APÓS CORREÇÃO';
    RAISE NOTICE '========================================';
    RAISE NOTICE 'Total na view: % leilões', v_view_nova;
    RAISE NOTICE 'Sem título: %', v_sem_titulo;
    RAISE NOTICE 'Com link_leiloeiro: %', v_com_link_leiloeiro;
    RAISE NOTICE 'Sem link_leiloeiro: %', v_sem_link_leiloeiro;
    RAISE NOTICE '========================================';
    RAISE NOTICE 'PRONTO! Atualize o dashboard (F5)';
    RAISE NOTICE '========================================';
END $$;

-- ============================================================================
-- PASSO 4: ATUALIZAR FUNÇÕES AUXILIARES
-- ============================================================================

-- Função para listar UFs disponíveis
CREATE OR REPLACE FUNCTION pub.get_available_ufs()
RETURNS TABLE(uf CHAR(2), count BIGINT)
LANGUAGE sql
STABLE
AS $$
    SELECT uf, COUNT(*) as count
    FROM pub.v_auction_discovery
    WHERE uf IS NOT NULL
    GROUP BY uf
    ORDER BY count DESC;
$$;

-- Função para listar cidades de uma UF
CREATE OR REPLACE FUNCTION pub.get_cities_by_uf(p_uf CHAR(2))
RETURNS TABLE(cidade VARCHAR, count BIGINT)
LANGUAGE sql
STABLE
AS $$
    SELECT cidade, COUNT(*) as count
    FROM pub.v_auction_discovery
    WHERE uf = p_uf AND cidade IS NOT NULL
    GROUP BY cidade
    ORDER BY count DESC;
$$;

-- Função para estatísticas do dashboard
CREATE OR REPLACE FUNCTION pub.get_dashboard_stats()
RETURNS TABLE(
    total_leiloes BIGINT,
    total_ufs BIGINT,
    total_cidades BIGINT,
    valor_total_estimado DECIMAL,
    leiloes_proximos_7_dias BIGINT
)
LANGUAGE sql
STABLE
AS $$
    SELECT
        COUNT(*) as total_leiloes,
        COUNT(DISTINCT uf) as total_ufs,
        COUNT(DISTINCT cidade) as total_cidades,
        COALESCE(SUM(valor_estimado), 0) as valor_total_estimado,
        COUNT(*) FILTER (WHERE data_leilao BETWEEN NOW() AND NOW() + INTERVAL '7 days') as leiloes_proximos_7_dias
    FROM pub.v_auction_discovery;
$$;

-- ============================================================================
-- PASSO 5: VERIFICAÇÃO FINAL - AMOSTRA DE DADOS
-- ============================================================================

-- Mostrar 5 leilões mais próximos para verificar se dados estão corretos
SELECT
    id_interno,
    orgao,
    uf,
    cidade,
    data_leilao,
    CASE WHEN titulo IS NULL OR titulo = '' THEN '❌ SEM TÍTULO' ELSE '✓' END AS tem_titulo,
    CASE WHEN link_leiloeiro IS NULL OR link_leiloeiro = '' OR link_leiloeiro = 'N/D' THEN '❌' ELSE '✓' END AS tem_link_leiloeiro,
    modalidade_leilao,
    array_to_string(tags, ', ') AS tags
FROM pub.v_auction_discovery
ORDER BY data_leilao ASC
LIMIT 10;

-- ============================================================================
-- PASSO 6: CRIAR FUNÇÃO DE PAGINAÇÃO COM ORDENAÇÃO
-- ============================================================================

-- Função para buscar leilões com paginação e ordenação
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
    p_ordenacao TEXT DEFAULT 'proximos'
)
RETURNS JSON
LANGUAGE plpgsql
SECURITY DEFINER
AS $$
DECLARE
    v_total INTEGER;
    v_total_pages INTEGER;
    v_offset INTEGER;
    v_order_by TEXT;
BEGIN
    -- Calcular offset
    v_offset := (p_page - 1) * p_page_size;

    -- Definir ordenação baseado no parâmetro
    CASE p_ordenacao
        WHEN 'proximos' THEN v_order_by := 'data_leilao ASC NULLS LAST';
        WHEN 'distantes' THEN v_order_by := 'data_leilao DESC NULLS LAST';
        WHEN 'recentes' THEN v_order_by := 'data_publicacao DESC NULLS LAST';
        WHEN 'antigos' THEN v_order_by := 'data_publicacao ASC NULLS LAST';
        ELSE v_order_by := 'data_leilao ASC NULLS LAST';
    END CASE;

    -- Contar total de registros
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
        AND (p_data_leilao_ate IS NULL OR v.data_leilao::date <= p_data_leilao_ate);

    -- Calcular total de páginas
    v_total_pages := CEIL(v_total::DECIMAL / p_page_size);

    -- Retornar JSON com dados e metadados
    RETURN (
        SELECT json_build_object(
            'data', COALESCE((
                SELECT json_agg(row_to_json(t))
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
                        v.municipio_oficial
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
            'totalPages', v_total_pages
        )
    );
END;
$$;

-- Permissões
GRANT EXECUTE ON FUNCTION pub.fetch_auctions_paginated TO authenticated;
GRANT EXECUTE ON FUNCTION pub.fetch_auctions_paginated TO anon;

COMMENT ON FUNCTION pub.fetch_auctions_paginated IS 'Busca leilões com paginação, filtros e ordenação';

-- ============================================================================
-- FIM DO SCRIPT
-- ============================================================================
