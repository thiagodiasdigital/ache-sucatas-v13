-- ============================================================================
-- SCRIPT CONSOLIDADO - EXECUTAR NO SQL EDITOR DO SUPABASE
-- ============================================================================
-- Este script:
-- 1. Cria schemas (raw, pub, audit)
-- 2. Cria tabelas (raw.leiloes, pub.ref_municipios)
-- 3. Cria VIEW (pub.v_auction_discovery)
-- 4. Migra dados de editais_leilao para raw.leiloes
-- 5. Cria RPCs que o frontend precisa
-- ============================================================================

-- ============================================================================
-- PARTE 1: CRIAR SCHEMAS
-- ============================================================================

CREATE SCHEMA IF NOT EXISTS raw;
CREATE SCHEMA IF NOT EXISTS pub;
CREATE SCHEMA IF NOT EXISTS audit;

-- ============================================================================
-- PARTE 2: TABELA DE REFERENCIA DE MUNICIPIOS
-- ============================================================================

CREATE TABLE IF NOT EXISTS pub.ref_municipios (
    codigo_ibge INTEGER PRIMARY KEY,
    nome_municipio VARCHAR(100) NOT NULL,
    uf CHAR(2) NOT NULL,
    latitude DECIMAL(10, 6),
    longitude DECIMAL(10, 6),
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_ref_municipios_uf ON pub.ref_municipios(uf);
CREATE INDEX IF NOT EXISTS idx_ref_municipios_nome ON pub.ref_municipios(nome_municipio);

-- ============================================================================
-- PARTE 3: TABELA raw.leiloes
-- ============================================================================

CREATE TABLE IF NOT EXISTS raw.leiloes (
    id BIGSERIAL PRIMARY KEY,
    id_interno VARCHAR(255) UNIQUE NOT NULL,
    pncp_id VARCHAR(100) NOT NULL,
    orgao VARCHAR(500),
    uf CHAR(2),
    cidade VARCHAR(100),
    n_edital VARCHAR(100),
    n_pncp VARCHAR(150),
    data_publicacao DATE,
    data_atualizacao DATE,
    data_leilao TIMESTAMPTZ,
    titulo VARCHAR(1000),
    descricao TEXT,
    objeto_resumido VARCHAR(1000),
    tags TEXT[],
    link_pncp VARCHAR(500),
    link_leiloeiro VARCHAR(500),
    modalidade_leilao VARCHAR(50),
    valor_estimado DECIMAL(15, 2),
    quantidade_itens INTEGER,
    nome_leiloeiro VARCHAR(200),
    arquivo_origem VARCHAR(500),
    storage_path VARCHAR(500),
    pdf_storage_url VARCHAR(1000),
    pdf_hash VARCHAR(64),
    versao_auditor VARCHAR(50),
    publication_status VARCHAR(20) DEFAULT 'published',
    score INTEGER DEFAULT 0,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_raw_leiloes_uf ON raw.leiloes(uf);
CREATE INDEX IF NOT EXISTS idx_raw_leiloes_cidade ON raw.leiloes(cidade);
CREATE INDEX IF NOT EXISTS idx_raw_leiloes_data_leilao ON raw.leiloes(data_leilao);
CREATE INDEX IF NOT EXISTS idx_raw_leiloes_data_publicacao ON raw.leiloes(data_publicacao);
CREATE INDEX IF NOT EXISTS idx_raw_leiloes_pncp_id ON raw.leiloes(pncp_id);
CREATE INDEX IF NOT EXISTS idx_raw_leiloes_valor_estimado ON raw.leiloes(valor_estimado);

-- RLS para raw.leiloes
ALTER TABLE raw.leiloes ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS "Anon can view leiloes" ON raw.leiloes;
CREATE POLICY "Anon can view leiloes"
    ON raw.leiloes FOR SELECT TO anon USING (true);

DROP POLICY IF EXISTS "Authenticated can view leiloes" ON raw.leiloes;
CREATE POLICY "Authenticated can view leiloes"
    ON raw.leiloes FOR SELECT TO authenticated USING (true);

DROP POLICY IF EXISTS "Service role full access leiloes" ON raw.leiloes;
CREATE POLICY "Service role full access leiloes"
    ON raw.leiloes FOR ALL TO service_role
    USING (true) WITH CHECK (true);

-- ============================================================================
-- PARTE 4: VIEW DE PRODUCAO
-- ============================================================================

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
WHERE
    l.publication_status = 'published'
    AND l.data_leilao IS NOT NULL
    AND l.link_pncp IS NOT NULL
    AND l.link_pncp != ''
ORDER BY l.data_leilao DESC;

-- ============================================================================
-- PARTE 5: MIGRAR DADOS DE editais_leilao PARA raw.leiloes
-- ============================================================================

INSERT INTO raw.leiloes (
    id_interno, pncp_id, orgao, uf, cidade, n_edital, n_pncp,
    data_publicacao, data_atualizacao, data_leilao,
    titulo, descricao, objeto_resumido, tags,
    link_pncp, link_leiloeiro,
    modalidade_leilao, valor_estimado, quantidade_itens, nome_leiloeiro,
    arquivo_origem, storage_path, pdf_hash,
    versao_auditor, score, created_at, updated_at
)
SELECT
    id_interno, pncp_id, orgao, uf, cidade, n_edital, n_pncp,
    data_publicacao, data_atualizacao, data_leilao,
    titulo, descricao, objeto_resumido, tags,
    link_pncp, link_leiloeiro,
    modalidade_leilao, valor_estimado, quantidade_itens, nome_leiloeiro,
    arquivo_origem, storage_path, pdf_hash,
    versao_auditor, COALESCE(score, 0), created_at, updated_at
FROM public.editais_leilao
ON CONFLICT (id_interno) DO UPDATE SET
    data_leilao = EXCLUDED.data_leilao,
    link_pncp = EXCLUDED.link_pncp,
    link_leiloeiro = EXCLUDED.link_leiloeiro,
    valor_estimado = EXCLUDED.valor_estimado,
    updated_at = NOW();

-- ============================================================================
-- PARTE 6: RPC FETCH_AUCTIONS_PAGINATED (usado pelo frontend)
-- ============================================================================

DROP FUNCTION IF EXISTS public.fetch_auctions_paginated;

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
    v_offset := (p_page - 1) * p_page_size;

    -- Contar total
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

    -- Buscar dados
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

    RETURN json_build_object(
        'data', COALESCE(v_data, '[]'::json),
        'total', v_total,
        'page', p_page,
        'pageSize', p_page_size,
        'totalPages', CEIL(v_total::NUMERIC / p_page_size)
    );
END;
$$;

GRANT EXECUTE ON FUNCTION public.fetch_auctions_paginated TO anon, authenticated;

-- ============================================================================
-- PARTE 7: RPCs AUXILIARES
-- ============================================================================

-- get_available_ufs
DROP FUNCTION IF EXISTS public.get_available_ufs();

CREATE OR REPLACE FUNCTION public.get_available_ufs()
RETURNS TABLE(uf CHAR(2), count BIGINT)
LANGUAGE sql
STABLE
AS $$
    SELECT v.uf, COUNT(*) as count
    FROM pub.v_auction_discovery v
    WHERE v.uf IS NOT NULL
    GROUP BY v.uf
    ORDER BY count DESC;
$$;

GRANT EXECUTE ON FUNCTION public.get_available_ufs() TO anon, authenticated;

-- get_cities_by_uf
DROP FUNCTION IF EXISTS public.get_cities_by_uf(CHAR);

CREATE OR REPLACE FUNCTION public.get_cities_by_uf(p_uf CHAR(2))
RETURNS TABLE(cidade VARCHAR, count BIGINT)
LANGUAGE sql
STABLE
AS $$
    SELECT v.cidade, COUNT(*) as count
    FROM pub.v_auction_discovery v
    WHERE v.uf = p_uf AND v.cidade IS NOT NULL
    GROUP BY v.cidade
    ORDER BY count DESC;
$$;

GRANT EXECUTE ON FUNCTION public.get_cities_by_uf(CHAR) TO anon, authenticated;

-- get_dashboard_stats
DROP FUNCTION IF EXISTS public.get_dashboard_stats();

CREATE OR REPLACE FUNCTION public.get_dashboard_stats()
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
        COUNT(DISTINCT v.uf) as total_ufs,
        COUNT(DISTINCT v.cidade) as total_cidades,
        COALESCE(SUM(v.valor_estimado), 0) as valor_total_estimado,
        COUNT(*) FILTER (WHERE v.data_leilao BETWEEN NOW() AND NOW() + INTERVAL '7 days') as leiloes_proximos_7_dias
    FROM pub.v_auction_discovery v;
$$;

GRANT EXECUTE ON FUNCTION public.get_dashboard_stats() TO anon, authenticated;

-- ============================================================================
-- VERIFICACAO FINAL
-- ============================================================================

DO $$
DECLARE
    v_count INTEGER;
BEGIN
    SELECT COUNT(*) INTO v_count FROM pub.v_auction_discovery;
    RAISE NOTICE '========================================';
    RAISE NOTICE 'INFRAESTRUTURA CRIADA COM SUCESSO!';
    RAISE NOTICE '========================================';
    RAISE NOTICE 'VIEW pub.v_auction_discovery: % registros', v_count;
    RAISE NOTICE '========================================';
END $$;
