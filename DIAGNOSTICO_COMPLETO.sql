-- ============================================================================
-- DIAGNOSTICO COMPLETO: Tags SYNC, Datas 2024, Links Faltando
-- Execute no SQL Editor do Supabase (https://supabase.com/dashboard)
-- ============================================================================

-- ============================================================================
-- PARTE 1: Contagem Geral
-- ============================================================================

SELECT '=== CONTAGEM GERAL ===' AS info;

SELECT 'public.editais_leilao' AS tabela, COUNT(*) AS total FROM public.editais_leilao
UNION ALL
SELECT 'raw.leiloes' AS tabela, COUNT(*) AS total FROM raw.leiloes
UNION ALL
SELECT 'pub.v_auction_discovery (view frontend)' AS tabela, COUNT(*) AS total FROM pub.v_auction_discovery;

-- ============================================================================
-- PARTE 2: Analise de TAGS (procurando SYNC, LEILAO)
-- ============================================================================

SELECT '=== LEILOES COM TAG SYNC/LEILAO ===' AS info;

-- Em editais_leilao (tags é array, usar array_to_string)
SELECT 'editais_leilao com tag SYNC' AS origem, COUNT(*) AS quantidade
FROM public.editais_leilao
WHERE array_to_string(tags, ',') ILIKE '%sync%'
   OR array_to_string(tags, ',') ILIKE '%leilao%'
   OR array_to_string(tags, ',') ILIKE '%leilão%';

-- Em raw.leiloes
SELECT 'raw.leiloes com tag SYNC' AS origem, COUNT(*) AS quantidade
FROM raw.leiloes
WHERE 'SYNC' = ANY(tags) OR 'sync' = ANY(tags) OR 'LEILAO' = ANY(tags) OR 'leilao' = ANY(tags);

-- Mostrar exemplos
SELECT '=== EXEMPLOS COM TAG SYNC (raw.leiloes) ===' AS info;
SELECT id_interno, orgao, tags
FROM raw.leiloes
WHERE 'SYNC' = ANY(tags) OR 'sync' = ANY(tags)
LIMIT 10;

-- ============================================================================
-- PARTE 3: Analise de DATAS (2024 e passadas)
-- ============================================================================

SELECT '=== LEILOES POR DATA ===' AS info;

-- Em editais_leilao
SELECT
    'editais_leilao' AS tabela,
    COUNT(*) AS total,
    COUNT(*) FILTER (WHERE EXTRACT(YEAR FROM data_leilao) = 2024) AS "ano_2024",
    COUNT(*) FILTER (WHERE data_leilao < CURRENT_DATE) AS "data_passada",
    COUNT(*) FILTER (WHERE data_leilao >= CURRENT_DATE) AS "data_futura",
    COUNT(*) FILTER (WHERE data_leilao IS NULL) AS "sem_data"
FROM public.editais_leilao;

-- Em raw.leiloes
SELECT
    'raw.leiloes' AS tabela,
    COUNT(*) AS total,
    COUNT(*) FILTER (WHERE EXTRACT(YEAR FROM data_leilao) = 2024) AS "ano_2024",
    COUNT(*) FILTER (WHERE data_leilao::date < CURRENT_DATE) AS "data_passada",
    COUNT(*) FILTER (WHERE data_leilao::date >= CURRENT_DATE) AS "data_futura",
    COUNT(*) FILTER (WHERE data_leilao IS NULL) AS "sem_data"
FROM raw.leiloes;

-- Mostrar leiloes de 2024
SELECT '=== EXEMPLOS DE 2024 (raw.leiloes) ===' AS info;
SELECT id_interno, orgao, data_leilao, titulo
FROM raw.leiloes
WHERE EXTRACT(YEAR FROM data_leilao) = 2024
ORDER BY data_leilao DESC
LIMIT 10;

-- ============================================================================
-- PARTE 4: Analise de LINK_LEILOEIRO
-- ============================================================================

SELECT '=== LEILOES SEM LINK_LEILOEIRO ===' AS info;

-- Em editais_leilao
SELECT
    'editais_leilao' AS tabela,
    COUNT(*) AS total,
    COUNT(*) FILTER (WHERE link_leiloeiro IS NULL OR link_leiloeiro = '' OR link_leiloeiro = 'N/D') AS "sem_link",
    COUNT(*) FILTER (WHERE link_leiloeiro IS NOT NULL AND link_leiloeiro != '' AND link_leiloeiro != 'N/D') AS "com_link"
FROM public.editais_leilao;

-- Em raw.leiloes
SELECT
    'raw.leiloes' AS tabela,
    COUNT(*) AS total,
    COUNT(*) FILTER (WHERE link_leiloeiro IS NULL OR link_leiloeiro = '' OR link_leiloeiro = 'N/D') AS "sem_link",
    COUNT(*) FILTER (WHERE link_leiloeiro IS NOT NULL AND link_leiloeiro != '' AND link_leiloeiro != 'N/D') AS "com_link"
FROM raw.leiloes;

-- Leiloes sem link MAS com URL na descricao (recuperaveis)
SELECT '=== SEM LINK MAS COM URL NA DESCRICAO (recuperaveis) ===' AS info;

SELECT
    'editais_leilao' AS tabela,
    COUNT(*) AS quantidade
FROM public.editais_leilao
WHERE (link_leiloeiro IS NULL OR link_leiloeiro = '' OR link_leiloeiro = 'N/D')
  AND (descricao ILIKE '%http%' OR descricao ILIKE '%www.%');

SELECT
    'raw.leiloes' AS tabela,
    COUNT(*) AS quantidade
FROM raw.leiloes
WHERE (link_leiloeiro IS NULL OR link_leiloeiro = '' OR link_leiloeiro = 'N/D')
  AND (descricao ILIKE '%http%' OR descricao ILIKE '%www.%');

-- Exemplos de URLs na descricao
SELECT '=== EXEMPLOS COM URL NA DESCRICAO ===' AS info;
SELECT
    id_interno,
    orgao,
    SUBSTRING(descricao FROM 'https?://[^\s<>"'')\]]+') AS url_encontrada
FROM raw.leiloes
WHERE (link_leiloeiro IS NULL OR link_leiloeiro = '' OR link_leiloeiro = 'N/D')
  AND (descricao ILIKE '%http%' OR descricao ILIKE '%www.%')
LIMIT 10;

-- ============================================================================
-- PARTE 5: Resumo Executivo
-- ============================================================================

SELECT '=== RESUMO EXECUTIVO ===' AS info;

WITH stats AS (
    SELECT
        -- Tags
        (SELECT COUNT(*) FROM raw.leiloes WHERE 'SYNC' = ANY(tags) OR 'sync' = ANY(tags)) AS com_tag_sync,
        -- Datas
        (SELECT COUNT(*) FROM raw.leiloes WHERE EXTRACT(YEAR FROM data_leilao) = 2024) AS data_2024,
        (SELECT COUNT(*) FROM raw.leiloes WHERE data_leilao::date < CURRENT_DATE) AS data_passada,
        -- Links
        (SELECT COUNT(*) FROM raw.leiloes WHERE link_leiloeiro IS NULL OR link_leiloeiro = '' OR link_leiloeiro = 'N/D') AS sem_link,
        (SELECT COUNT(*) FROM raw.leiloes WHERE (link_leiloeiro IS NULL OR link_leiloeiro = '' OR link_leiloeiro = 'N/D') AND (descricao ILIKE '%http%' OR descricao ILIKE '%www.%')) AS url_recuperavel
)
SELECT
    com_tag_sync AS "Leiloes com tag SYNC",
    data_2024 AS "Leiloes de 2024",
    data_passada AS "Leiloes com data passada",
    sem_link AS "Leiloes sem link_leiloeiro",
    url_recuperavel AS "URLs recuperaveis da descricao"
FROM stats;

-- ============================================================================
-- FIM DO DIAGNOSTICO
-- ============================================================================
