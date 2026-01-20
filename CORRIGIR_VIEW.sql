-- ============================================================================
-- CORRIGIR VIEW: Remover filtros que excluem registros
-- Execute no SQL Editor do Supabase
-- ============================================================================

-- Recriar a view SEM os filtros restritivos de data_leilao e link_pncp
CREATE OR REPLACE VIEW pub.v_auction_discovery AS
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
    l.link_pncp,
    l.link_leiloeiro,
    l.modalidade_leilao,
    l.valor_estimado,
    l.quantidade_itens,
    l.nome_leiloeiro,
    l.storage_path,
    l.score,
    l.created_at,
    m.codigo_ibge,
    m.latitude,
    m.longitude,
    m.nome_municipio AS municipio_oficial
FROM raw.leiloes l
LEFT JOIN pub.ref_municipios m
    ON UPPER(TRIM(l.cidade)) = UPPER(TRIM(m.nome_municipio))
    AND l.uf = m.uf
WHERE l.publication_status = 'published'
-- REMOVIDO: AND l.data_leilao IS NOT NULL (excluia registros sem data)
-- REMOVIDO: AND l.link_pncp IS NOT NULL (excluia registros sem link)
ORDER BY l.data_leilao DESC NULLS LAST;

-- Verificar quantos registros agora aparecem na view
SELECT COUNT(*) AS total_na_view FROM pub.v_auction_discovery;

-- ============================================================================
-- PRONTO! Atualize a pagina do localhost (F5)
-- ============================================================================
