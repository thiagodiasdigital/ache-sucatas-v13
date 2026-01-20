-- ============================================================================
-- DIAGNOSTICO: Por que so aparecem 25 leiloes?
-- Execute no SQL Editor do Supabase
-- ============================================================================

-- 1. Quantos registros em cada lugar?
SELECT 'public.editais_leilao' AS tabela, COUNT(*) AS total FROM public.editais_leilao
UNION ALL
SELECT 'raw.leiloes' AS tabela, COUNT(*) AS total FROM raw.leiloes
UNION ALL
SELECT 'pub.v_auction_discovery (view)' AS tabela, COUNT(*) AS total FROM pub.v_auction_discovery;

-- 2. Quantos registros em raw.leiloes NAO passam pelos filtros da view?
SELECT
    COUNT(*) AS total_raw_leiloes,
    COUNT(*) FILTER (WHERE publication_status = 'published') AS com_status_published,
    COUNT(*) FILTER (WHERE data_leilao IS NOT NULL) AS com_data_leilao,
    COUNT(*) FILTER (WHERE link_pncp IS NOT NULL AND link_pncp != '') AS com_link_pncp,
    COUNT(*) FILTER (
        WHERE publication_status = 'published'
        AND data_leilao IS NOT NULL
        AND link_pncp IS NOT NULL
        AND link_pncp != ''
    ) AS passam_todos_filtros
FROM raw.leiloes;

-- 3. Quais sao os valores de publication_status?
SELECT publication_status, COUNT(*) AS quantidade
FROM raw.leiloes
GROUP BY publication_status;
