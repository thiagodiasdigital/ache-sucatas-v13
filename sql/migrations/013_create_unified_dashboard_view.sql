-- ============================================================================
-- MIGRACAO 013: Criar view unificada para dashboard
-- Data: 2026-01-30
-- Autor: Claude Code
-- Descricao: View que combina dados PNCP (raw.leiloes) e Leiloeiro (leiloeiro_lotes)
--            usando UNION ALL. Schema identico para ambas as fontes.
-- ============================================================================

-- ============================================================================
-- FASE 1: CRIAR VIEW UNIFICADA
-- ============================================================================

CREATE OR REPLACE VIEW pub.v_dashboard_lotes_unificado AS

-- =====================
-- FONTE 1: PNCP (raw.leiloes)
-- =====================
SELECT
    l.id,
    l.id_interno,
    l.pncp_id,
    l.orgao,
    l.uf,
    l.cidade,
    l.n_edital,
    l.data_publicacao,
    l.data_leilao,
    l.titulo,
    l.descricao,
    l.objeto_resumido,
    l.tags,
    -- link_edital: prioriza storage interno, fallback para link_pncp
    CASE
        WHEN l.storage_path IS NOT NULL AND l.storage_path <> ''
        THEN l.storage_path  -- Frontend vai montar URL completa
        ELSE l.link_pncp
    END AS link_edital,
    l.link_leiloeiro,
    l.modalidade_leilao,
    l.valor_estimado,
    l.quantidade_itens,
    l.nome_leiloeiro,
    l.storage_path,
    l.score,
    l.created_at,
    -- Origem
    COALESCE(l.source_type, 'pncp')::TEXT AS source_type,
    COALESCE(l.source_name, 'Portal Nacional de Contratacoes Publicas')::TEXT AS source_name,
    COALESCE(l.metadata, '{}'::JSONB) AS metadata,
    -- Dados do municipio
    m.codigo_ibge,
    m.latitude,
    m.longitude,
    m.nome_municipio AS municipio_oficial,
    -- Status temporal calculado
    CASE
        WHEN l.data_leilao >= CURRENT_DATE THEN 'futuro'
        ELSE 'passado'
    END AS status_temporal
FROM raw.leiloes l
LEFT JOIN pub.ref_municipios m
    ON UPPER(TRIM(l.cidade)) = UPPER(TRIM(m.nome_municipio))
    AND l.uf = m.uf
WHERE
    l.publication_status = 'published'
    AND l.data_leilao IS NOT NULL
    AND (
        l.link_pncp IS NOT NULL
        OR (l.source_type = 'leiloeiro' AND l.link_leiloeiro IS NOT NULL)
    )

UNION ALL

-- =====================
-- FONTE 2: LEILOEIRO (leiloeiro_lotes)
-- =====================
SELECT
    ll.id,
    ll.id_interno,
    NULL::TEXT AS pncp_id,  -- Leiloeiros nao tem PNCP ID
    ll.orgao,
    ll.uf,
    ll.cidade,
    ll.n_edital,
    ll.data_publicacao,
    ll.data_leilao,
    ll.titulo,
    ll.descricao,
    ll.objeto_resumido,
    ll.tags,
    -- link_edital: do leiloeiro
    ll.link_edital,
    ll.link_leiloeiro,
    ll.tipo_leilao AS modalidade_leilao,
    ll.valor_avaliacao AS valor_estimado,
    1 AS quantidade_itens,  -- Cada registro e 1 lote
    ll.nome_leiloeiro,
    NULL::TEXT AS storage_path,  -- Leiloeiros nao tem storage interno
    ll.confidence_score AS score,
    ll.created_at,
    -- Origem
    ll.source_type,
    ll.source_name,
    ll.metadata,
    -- Dados do municipio
    m.codigo_ibge,
    m.latitude,
    m.longitude,
    m.nome_municipio AS municipio_oficial,
    -- Status temporal calculado
    CASE
        WHEN ll.data_leilao >= CURRENT_DATE THEN 'futuro'
        ELSE 'passado'
    END AS status_temporal
FROM public.leiloeiro_lotes ll
LEFT JOIN pub.ref_municipios m
    ON UPPER(TRIM(ll.cidade)) = UPPER(TRIM(m.nome_municipio))
    AND ll.uf = m.uf
WHERE
    ll.publication_status = 'published'
    AND ll.data_leilao IS NOT NULL;

-- ============================================================================
-- FASE 2: COMENTARIO DA VIEW
-- ============================================================================

COMMENT ON VIEW pub.v_dashboard_lotes_unificado IS
'View unificada que combina lotes de todas as fontes (PNCP + Leiloeiros).
Use esta view para o dashboard quando a feature flag SHOW_LEILOEIRO estiver ativa.
Schema identico para ambas as fontes, permitindo UNION ALL transparente.

Fontes:
- PNCP: raw.leiloes (dados existentes)
- Leiloeiro: public.leiloeiro_lotes (novos dados da API leiloesjudiciais)

Campos calculados:
- link_edital: prioriza storage_path para PNCP, link_edital para leiloeiros
- status_temporal: futuro se data_leilao >= hoje, passado caso contrario
- municipio_oficial: join com ref_municipios para geolocalizacao';

-- ============================================================================
-- FASE 3: GRANT PERMISSIONS
-- ============================================================================

GRANT SELECT ON pub.v_dashboard_lotes_unificado TO anon;
GRANT SELECT ON pub.v_dashboard_lotes_unificado TO authenticated;

-- ============================================================================
-- FASE 4: FUNCAO AUXILIAR PARA ESTATISTICAS
-- ============================================================================

CREATE OR REPLACE FUNCTION public.get_dashboard_stats_unified()
RETURNS TABLE (
    total_lotes BIGINT,
    total_pncp BIGINT,
    total_leiloeiro BIGINT,
    total_ufs BIGINT,
    total_cidades BIGINT,
    valor_total NUMERIC,
    lotes_futuros BIGINT,
    lotes_passados BIGINT
)
LANGUAGE plpgsql
SECURITY DEFINER
AS $$
BEGIN
    RETURN QUERY
    SELECT
        COUNT(*)::BIGINT AS total_lotes,
        COUNT(*) FILTER (WHERE source_type = 'pncp')::BIGINT AS total_pncp,
        COUNT(*) FILTER (WHERE source_type = 'leiloeiro')::BIGINT AS total_leiloeiro,
        COUNT(DISTINCT uf)::BIGINT AS total_ufs,
        COUNT(DISTINCT cidade)::BIGINT AS total_cidades,
        COALESCE(SUM(valor_estimado), 0)::NUMERIC AS valor_total,
        COUNT(*) FILTER (WHERE status_temporal = 'futuro')::BIGINT AS lotes_futuros,
        COUNT(*) FILTER (WHERE status_temporal = 'passado')::BIGINT AS lotes_passados
    FROM pub.v_dashboard_lotes_unificado;
END;
$$;

GRANT EXECUTE ON FUNCTION public.get_dashboard_stats_unified TO anon;
GRANT EXECUTE ON FUNCTION public.get_dashboard_stats_unified TO authenticated;

-- ============================================================================
-- VERIFICACAO FINAL
-- ============================================================================

DO $$
DECLARE
    v_pncp_count BIGINT;
    v_leiloeiro_count BIGINT;
BEGIN
    -- Conta registros de cada fonte na view
    SELECT
        COUNT(*) FILTER (WHERE source_type = 'pncp'),
        COUNT(*) FILTER (WHERE source_type = 'leiloeiro')
    INTO v_pncp_count, v_leiloeiro_count
    FROM pub.v_dashboard_lotes_unificado;

    RAISE NOTICE '========================================';
    RAISE NOTICE 'MIGRACAO 013 CONCLUIDA!';
    RAISE NOTICE '========================================';
    RAISE NOTICE 'View: pub.v_dashboard_lotes_unificado';
    RAISE NOTICE 'Proposito: UNION ALL de PNCP + Leiloeiro';
    RAISE NOTICE 'Registros PNCP: %', v_pncp_count;
    RAISE NOTICE 'Registros Leiloeiro: %', v_leiloeiro_count;
    RAISE NOTICE 'Total: %', v_pncp_count + v_leiloeiro_count;
    RAISE NOTICE 'Funcao: get_dashboard_stats_unified()';
    RAISE NOTICE 'Grants: anon, authenticated';
    RAISE NOTICE '========================================';
END $$;
