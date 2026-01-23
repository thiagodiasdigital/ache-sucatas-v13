-- ============================================================================
-- CORREÇÃO DEFINITIVA - CONSENSO DE 3 ANÁLISES TÉCNICAS
-- ============================================================================
-- Data: 2026-01-20
-- Autor: Consolidação Staff Engineer + 2 auditorias independentes
-- Status: VERDADE ABSOLUTA - EXECUTAR CONFORME ESPECIFICADO
-- ============================================================================
--
-- COMO EXECUTAR:
-- 1. Acesse https://supabase.com/dashboard
-- 2. Selecione seu projeto
-- 3. Vá em "SQL Editor" (menu lateral esquerdo)
-- 4. Cole TODO este conteúdo
-- 5. Clique no botão "Run" (ou pressione Ctrl+Enter)
-- 6. Aguarde a mensagem "Success"
-- 7. No terminal: cd frontend && npm run dev
-- 8. Atualize o dashboard (F5)
--
-- REGRA ABSOLUTA: Leilões passados NÃO são deletados (mantidos para histórico)
-- ============================================================================

-- ============================================================================
-- SEÇÃO 1: DIAGNÓSTICO PRÉ-CORREÇÃO
-- ============================================================================

SELECT '=== SITUAÇÃO ATUAL ===' AS info;

SELECT
    'Total editais' AS metrica,
    COUNT(*)::TEXT AS valor
FROM public.editais_leilao

UNION ALL SELECT 'Com data futura', COUNT(*)::TEXT
FROM public.editais_leilao WHERE data_leilao >= CURRENT_DATE

UNION ALL SELECT 'Com data passada (MANTER NO BANCO)', COUNT(*)::TEXT
FROM public.editais_leilao WHERE data_leilao < CURRENT_DATE

UNION ALL SELECT 'Sem título', COUNT(*)::TEXT
FROM public.editais_leilao WHERE titulo IS NULL OR titulo = ''

UNION ALL SELECT 'Sem link_leiloeiro', COUNT(*)::TEXT
FROM public.editais_leilao WHERE link_leiloeiro IS NULL OR link_leiloeiro = '' OR link_leiloeiro = 'N/D'

UNION ALL SELECT 'Com tag SYNC/LEILAO (lixo)', COUNT(*)::TEXT
FROM public.editais_leilao WHERE 'SYNC' = ANY(tags) OR 'sync' = ANY(tags) OR 'LEILAO' = ANY(tags) OR 'leilao' = ANY(tags)

UNION ALL SELECT 'Modalidade não normalizada', COUNT(*)::TEXT
FROM public.editais_leilao WHERE modalidade_leilao NOT IN ('Eletrônico', 'Presencial', 'Híbrido') OR modalidade_leilao IS NULL;

-- ============================================================================
-- SEÇÃO 2: VIEW PRINCIPAL - FILTRA LEILÕES PASSADOS (NÃO DELETA)
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
    -- Dados geográficos (JOIN opcional)
    m.codigo_ibge,
    m.latitude,
    m.longitude,
    m.nome_municipio AS municipio_oficial
FROM public.editais_leilao e
LEFT JOIN pub.ref_municipios m
    ON UPPER(TRIM(e.cidade)) = UPPER(TRIM(m.nome_municipio))
    AND e.uf = m.uf
WHERE
    -- FILTRO 1: Só leilões com data FUTURA (passados ficam no banco, não aparecem aqui)
    e.data_leilao >= CURRENT_DATE
    -- FILTRO 2: Precisa ter link_pncp
    AND e.link_pncp IS NOT NULL
    AND e.link_pncp != ''
ORDER BY e.data_leilao ASC;

COMMENT ON VIEW pub.v_auction_discovery IS
'View de produção - Lê de editais_leilao. Filtra leilões passados (eles permanecem no banco para histórico). Ordenação: mais próximos primeiro.';

-- ============================================================================
-- SEÇÃO 3: LIMPEZA DE TAGS PROIBIDAS (SYNC, LEILAO)
-- ============================================================================

UPDATE public.editais_leilao
SET
    tags = array_remove(array_remove(array_remove(array_remove(
        tags,
        'SYNC'), 'sync'), 'LEILAO'), 'leilao'),
    updated_at = NOW()
WHERE
    'SYNC' = ANY(tags)
    OR 'sync' = ANY(tags)
    OR 'LEILAO' = ANY(tags)
    OR 'leilao' = ANY(tags);

-- ============================================================================
-- SEÇÃO 4: NORMALIZAÇÃO DE MODALIDADES (apenas 3 valores válidos)
-- ============================================================================

-- Eletrônico
UPDATE public.editais_leilao
SET modalidade_leilao = 'Eletrônico', updated_at = NOW()
WHERE modalidade_leilao IN (
    'Leilão - Eletrônico', 'Leil�o - Eletr�nico', 'ELETRONICO',
    'Eletronico', 'ELETRÔNICO', 'Leilao - Eletronico'
);

-- Presencial
UPDATE public.editais_leilao
SET modalidade_leilao = 'Presencial', updated_at = NOW()
WHERE modalidade_leilao IN (
    'Leilão - Presencial', 'Leil�o - Presencial',
    'PRESENCIAL', 'Leilao - Presencial'
);

-- Híbrido
UPDATE public.editais_leilao
SET modalidade_leilao = 'Híbrido', updated_at = NOW()
WHERE modalidade_leilao IN (
    'HÍBRIDO', 'H�BRIDO', 'Hibrido', 'H�brido'
);

-- Correção por contradição título vs modalidade
UPDATE public.editais_leilao
SET modalidade_leilao = 'Eletrônico', updated_at = NOW()
WHERE
    modalidade_leilao = 'Presencial'
    AND (
        LOWER(titulo) LIKE '%online%'
        OR LOWER(descricao) LIKE '%online%'
        OR LOWER(titulo) LIKE '%eletrônico%'
        OR LOWER(titulo) LIKE '%eletronico%'
    )
    AND LOWER(titulo) NOT LIKE '%presencial%';

-- Se menciona ambos = Híbrido
UPDATE public.editais_leilao
SET modalidade_leilao = 'Híbrido', updated_at = NOW()
WHERE
    (LOWER(titulo) LIKE '%online%' OR LOWER(titulo) LIKE '%eletrônico%' OR LOWER(titulo) LIKE '%eletronico%')
    AND LOWER(titulo) LIKE '%presencial%';

-- ============================================================================
-- SEÇÃO 5: PATCH BUG 1 - CORREÇÃO DE TÍTULOS VAZIOS (PRECEDÊNCIA AND/OR CORRIGIDA)
-- ============================================================================
-- ATENÇÃO: Este SQL NÃO sobrescreve títulos válidos (bug original corrigido)

UPDATE public.editais_leilao
SET
    titulo = COALESCE(objeto_resumido, SUBSTRING(descricao FROM 1 FOR 200)),
    updated_at = NOW()
WHERE
    (titulo IS NULL OR titulo = '')
    AND (
        (objeto_resumido IS NOT NULL AND objeto_resumido <> '')
        OR (descricao IS NOT NULL AND descricao <> '')
    );

-- ============================================================================
-- SEÇÃO 6: PATCH BUG 3 - EXTRAÇÃO DE LINK SEM DOMÍNIOS GOVERNAMENTAIS
-- ============================================================================

UPDATE public.editais_leilao
SET
    link_leiloeiro = (
        SELECT candidate
        FROM (
            SELECT
                CASE
                    WHEN descricao ~* 'https?://[^\s<>"'']+'
                        THEN (regexp_match(descricao, '(https?://[^\s<>"'']+)', 'i'))[1]
                    WHEN descricao ~* 'www\.[^\s<>"'']+'
                        THEN 'https://' || (regexp_match(descricao, '(www\.[^\s<>"'']+)', 'i'))[1]
                    ELSE NULL
                END AS candidate
        ) s
        WHERE candidate IS NOT NULL
          AND candidate !~* '(pncp\.gov\.br|\.gov\.br|compras\.gov\.br|comprasnet\.gov\.br|licitacoes-e\.com\.br)'
    ),
    updated_at = NOW()
WHERE
    (link_leiloeiro IS NULL OR link_leiloeiro = '' OR link_leiloeiro = 'N/D')
    AND descricao IS NOT NULL
    AND descricao <> '';

-- ============================================================================
-- SEÇÃO 7: RPC - PAGINAÇÃO COM FILTROS E ORDENAÇÃO
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
BEGIN
    v_offset := (p_page - 1) * p_page_size;

    -- Contar total
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

    v_total_pages := CEIL(v_total::DECIMAL / p_page_size);

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
                        v.longitude, v.municipio_oficial
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

-- ============================================================================
-- SEÇÃO 8: FUNÇÕES AUXILIARES
-- ============================================================================

-- UFs disponíveis
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

-- Cidades por UF
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

-- Estatísticas do dashboard
CREATE OR REPLACE FUNCTION pub.get_dashboard_stats()
RETURNS TABLE(
    total_leiloes BIGINT,
    total_ufs BIGINT,
    total_cidades BIGINT,
    valor_total_estimado DECIMAL,
    leiloes_proximos_7_dias BIGINT
)
LANGUAGE sql STABLE
AS $$
    SELECT
        COUNT(*) as total_leiloes,
        COUNT(DISTINCT uf) as total_ufs,
        COUNT(DISTINCT cidade) as total_cidades,
        COALESCE(SUM(valor_estimado), 0) as valor_total_estimado,
        COUNT(*) FILTER (WHERE data_leilao BETWEEN NOW() AND NOW() + INTERVAL '7 days') as leiloes_proximos_7_dias
    FROM pub.v_auction_discovery;
$$;

GRANT EXECUTE ON FUNCTION pub.get_available_ufs TO authenticated, anon;
GRANT EXECUTE ON FUNCTION pub.get_cities_by_uf TO authenticated, anon;
GRANT EXECUTE ON FUNCTION pub.get_dashboard_stats TO authenticated, anon;

-- ============================================================================
-- SEÇÃO 9: DIAGNÓSTICO PÓS-CORREÇÃO
-- ============================================================================

SELECT '=== RESULTADO FINAL ===' AS info;

SELECT
    COUNT(*) AS total_no_banco,
    COUNT(*) FILTER (WHERE data_leilao >= CURRENT_DATE) AS visiveis_no_dashboard,
    COUNT(*) FILTER (WHERE data_leilao < CURRENT_DATE) AS historico_preservado,
    COUNT(*) FILTER (WHERE titulo IS NOT NULL AND titulo != '') AS com_titulo,
    COUNT(*) FILTER (WHERE link_leiloeiro IS NOT NULL AND link_leiloeiro != '' AND link_leiloeiro != 'N/D') AS com_link_leiloeiro,
    COUNT(*) FILTER (WHERE modalidade_leilao IN ('Eletrônico', 'Presencial', 'Híbrido')) AS modalidade_ok
FROM public.editais_leilao;

-- Amostra dos próximos 10 leilões
SELECT '=== PRÓXIMOS 10 LEILÕES (dashboard) ===' AS info;

SELECT
    id_interno,
    SUBSTRING(orgao FROM 1 FOR 35) AS orgao,
    uf,
    data_leilao::DATE AS data,
    modalidade_leilao AS modalidade,
    CASE WHEN link_leiloeiro IS NOT NULL AND link_leiloeiro != '' AND link_leiloeiro != 'N/D' THEN '✓' ELSE '❌' END AS link
FROM pub.v_auction_discovery
ORDER BY data_leilao ASC
LIMIT 10;

-- ============================================================================
-- FIM DO SCRIPT
-- ============================================================================

DO $$
BEGIN
    RAISE NOTICE '========================================';
    RAISE NOTICE 'CORREÇÃO DEFINITIVA CONSENSO - CONCLUÍDA';
    RAISE NOTICE '========================================';
    RAISE NOTICE 'Leilões passados: PRESERVADOS no banco';
    RAISE NOTICE 'View: filtra apenas futuros';
    RAISE NOTICE 'Tags lixo: REMOVIDAS';
    RAISE NOTICE 'Modalidades: NORMALIZADAS';
    RAISE NOTICE '========================================';
    RAISE NOTICE 'PRÓXIMO PASSO: cd frontend && npm run dev';
    RAISE NOTICE 'Depois atualize o dashboard (F5)';
    RAISE NOTICE '========================================';
END $$;
