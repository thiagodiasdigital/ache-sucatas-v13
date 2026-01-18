-- ============================================================================
-- ACHE SUCATAS - INFRAESTRUTURA SUPABASE (SEMANA 1)
-- Versão: 1.0.0
-- Data: 2026-01-18
-- ============================================================================

-- ============================================================================
-- FASE 1: CRIAR SCHEMAS
-- ============================================================================

-- Schema para dados brutos (origem)
CREATE SCHEMA IF NOT EXISTS raw;
COMMENT ON SCHEMA raw IS 'Dados brutos vindos das APIs e mineradores';

-- Schema para dados de consumo (produção)
CREATE SCHEMA IF NOT EXISTS pub;
COMMENT ON SCHEMA pub IS 'Dados processados e prontos para consumo';

-- Schema para auditoria e logs
CREATE SCHEMA IF NOT EXISTS audit;
COMMENT ON SCHEMA audit IS 'Logs de auditoria e consumo DaaS';

-- ============================================================================
-- FASE 2: TABELA DE REFERÊNCIA DE MUNICÍPIOS (IBGE)
-- ============================================================================

CREATE TABLE IF NOT EXISTS pub.ref_municipios (
    codigo_ibge INTEGER PRIMARY KEY,
    nome_municipio VARCHAR(100) NOT NULL,
    uf CHAR(2) NOT NULL,
    latitude DECIMAL(10, 6),
    longitude DECIMAL(10, 6),
    created_at TIMESTAMPTZ DEFAULT NOW(),
    CONSTRAINT ref_municipios_uf_check CHECK (uf ~ '^[A-Z]{2}$')
);

-- Índices para performance
CREATE INDEX IF NOT EXISTS idx_ref_municipios_uf ON pub.ref_municipios(uf);
CREATE INDEX IF NOT EXISTS idx_ref_municipios_nome ON pub.ref_municipios(nome_municipio);
CREATE INDEX IF NOT EXISTS idx_ref_municipios_uf_nome ON pub.ref_municipios(uf, nome_municipio);

COMMENT ON TABLE pub.ref_municipios IS 'Tabela de referência dos municípios brasileiros (IBGE)';
COMMENT ON COLUMN pub.ref_municipios.codigo_ibge IS 'Código IBGE do município (7 dígitos)';
COMMENT ON COLUMN pub.ref_municipios.nome_municipio IS 'Nome oficial do município';
COMMENT ON COLUMN pub.ref_municipios.uf IS 'Unidade federativa (2 letras)';
COMMENT ON COLUMN pub.ref_municipios.latitude IS 'Latitude do centroide do município';
COMMENT ON COLUMN pub.ref_municipios.longitude IS 'Longitude do centroide do município';

-- ============================================================================
-- FASE 3: MIGRAR/CRIAR TABELA DE LEILÕES NO SCHEMA RAW
-- ============================================================================

-- Criar tabela raw.leiloes se não existir (baseada na editais_leilao existente)
CREATE TABLE IF NOT EXISTS raw.leiloes (
    id BIGSERIAL PRIMARY KEY,
    id_interno VARCHAR(255) UNIQUE NOT NULL,
    pncp_id VARCHAR(100) NOT NULL,

    -- Localização
    orgao VARCHAR(500),
    uf CHAR(2),
    cidade VARCHAR(100),

    -- Identificação do edital
    n_edital VARCHAR(100),
    n_pncp VARCHAR(150),

    -- Datas
    data_publicacao DATE,
    data_atualizacao DATE,
    data_leilao TIMESTAMPTZ,

    -- Conteúdo
    titulo VARCHAR(1000),
    descricao TEXT,
    objeto_resumido VARCHAR(1000),
    tags TEXT[],

    -- Links
    link_pncp VARCHAR(500),
    link_leiloeiro VARCHAR(500),

    -- Comercial
    modalidade_leilao VARCHAR(50),
    valor_estimado DECIMAL(15, 2),
    quantidade_itens INTEGER,
    nome_leiloeiro VARCHAR(200),

    -- Storage
    arquivo_origem VARCHAR(500),
    storage_path VARCHAR(500),
    pdf_storage_url VARCHAR(1000),
    pdf_hash VARCHAR(64),

    -- Metadata
    versao_auditor VARCHAR(50),
    publication_status VARCHAR(20) DEFAULT 'published',
    score INTEGER DEFAULT 0,

    -- Timestamps
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),

    CONSTRAINT leiloes_uf_check CHECK (uf IS NULL OR uf ~ '^[A-Z]{2}$'),
    CONSTRAINT leiloes_publication_status_check CHECK (publication_status IN ('draft', 'published', 'archived'))
);

-- Índices para performance
CREATE INDEX IF NOT EXISTS idx_raw_leiloes_uf ON raw.leiloes(uf);
CREATE INDEX IF NOT EXISTS idx_raw_leiloes_cidade ON raw.leiloes(cidade);
CREATE INDEX IF NOT EXISTS idx_raw_leiloes_data_leilao ON raw.leiloes(data_leilao);
CREATE INDEX IF NOT EXISTS idx_raw_leiloes_data_publicacao ON raw.leiloes(data_publicacao);
CREATE INDEX IF NOT EXISTS idx_raw_leiloes_publication_status ON raw.leiloes(publication_status);
CREATE INDEX IF NOT EXISTS idx_raw_leiloes_pncp_id ON raw.leiloes(pncp_id);
CREATE INDEX IF NOT EXISTS idx_raw_leiloes_valor_estimado ON raw.leiloes(valor_estimado);
CREATE INDEX IF NOT EXISTS idx_raw_leiloes_tags ON raw.leiloes USING GIN(tags);

COMMENT ON TABLE raw.leiloes IS 'Dados brutos de leilões coletados do PNCP';

-- ============================================================================
-- FASE 4: ATIVAR RLS (Row Level Security) NA TABELA raw.leiloes
-- ============================================================================

-- Ativar RLS
ALTER TABLE raw.leiloes ENABLE ROW LEVEL SECURITY;

-- Política: SELECT apenas para usuários autenticados
DROP POLICY IF EXISTS "Authenticated users can view leiloes" ON raw.leiloes;
CREATE POLICY "Authenticated users can view leiloes"
    ON raw.leiloes
    FOR SELECT
    TO authenticated
    USING (true);

-- Política: INSERT/UPDATE apenas para service_role (backend)
DROP POLICY IF EXISTS "Service role can manage leiloes" ON raw.leiloes;
CREATE POLICY "Service role can manage leiloes"
    ON raw.leiloes
    FOR ALL
    TO service_role
    USING (true)
    WITH CHECK (true);

-- ============================================================================
-- FASE 5: VIEW DE PRODUÇÃO (pub.v_auction_discovery)
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
    -- Dados geográficos do município (LEFT JOIN)
    m.codigo_ibge,
    m.latitude,
    m.longitude,
    m.nome_municipio AS municipio_oficial
FROM raw.leiloes l
LEFT JOIN pub.ref_municipios m
    ON UPPER(TRIM(l.cidade)) = UPPER(TRIM(m.nome_municipio))
    AND l.uf = m.uf
WHERE
    -- Filtros obrigatórios para qualidade dos dados
    l.publication_status = 'published'
    AND l.data_leilao IS NOT NULL
    AND l.link_pncp IS NOT NULL
ORDER BY l.data_leilao DESC;

COMMENT ON VIEW pub.v_auction_discovery IS 'View de produção para descoberta de leilões - filtros de qualidade aplicados';

-- ============================================================================
-- FASE 6: TABELA DE AUDITORIA (audit.consumption_logs)
-- ============================================================================

CREATE TABLE IF NOT EXISTS audit.consumption_logs (
    id BIGSERIAL PRIMARY KEY,
    user_id UUID REFERENCES auth.users(id),
    queried_at TIMESTAMPTZ DEFAULT NOW(),
    filter_applied JSONB NOT NULL DEFAULT '{}',
    results_count INTEGER DEFAULT 0,
    response_time_ms INTEGER,
    ip_address INET,
    user_agent TEXT,
    session_id UUID,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Índices para auditoria
CREATE INDEX IF NOT EXISTS idx_consumption_logs_user_id ON audit.consumption_logs(user_id);
CREATE INDEX IF NOT EXISTS idx_consumption_logs_queried_at ON audit.consumption_logs(queried_at);
CREATE INDEX IF NOT EXISTS idx_consumption_logs_filter ON audit.consumption_logs USING GIN(filter_applied);

-- RLS na tabela de auditoria
ALTER TABLE audit.consumption_logs ENABLE ROW LEVEL SECURITY;

-- Usuários autenticados podem ver seus próprios logs
DROP POLICY IF EXISTS "Users can view own logs" ON audit.consumption_logs;
CREATE POLICY "Users can view own logs"
    ON audit.consumption_logs
    FOR SELECT
    TO authenticated
    USING (auth.uid() = user_id);

-- Service role pode gerenciar todos os logs
DROP POLICY IF EXISTS "Service role can manage logs" ON audit.consumption_logs;
CREATE POLICY "Service role can manage logs"
    ON audit.consumption_logs
    FOR ALL
    TO service_role
    USING (true)
    WITH CHECK (true);

COMMENT ON TABLE audit.consumption_logs IS 'Logs de auditoria para consumo DaaS';

-- ============================================================================
-- FASE 7: RPC PARA FETCH COM AUDITORIA (pub.fetch_auctions_audit)
-- ============================================================================

CREATE OR REPLACE FUNCTION pub.fetch_auctions_audit(
    filter_params JSONB DEFAULT '{}'::JSONB
)
RETURNS SETOF pub.v_auction_discovery
LANGUAGE plpgsql
SECURITY DEFINER
AS $$
DECLARE
    v_user_id UUID;
    v_start_time TIMESTAMPTZ;
    v_results_count INTEGER;
    v_uf TEXT;
    v_cidade TEXT;
    v_valor_min DECIMAL;
    v_valor_max DECIMAL;
    v_data_inicio DATE;
    v_data_fim DATE;
    v_limit_val INTEGER;
    v_offset_val INTEGER;
BEGIN
    -- Capturar tempo de início
    v_start_time := clock_timestamp();

    -- Obter user_id do contexto (pode ser NULL se anônimo)
    v_user_id := auth.uid();

    -- Extrair parâmetros do JSONB
    v_uf := filter_params->>'uf';
    v_cidade := filter_params->>'cidade';
    v_valor_min := (filter_params->>'valor_min')::DECIMAL;
    v_valor_max := (filter_params->>'valor_max')::DECIMAL;
    v_data_inicio := (filter_params->>'data_inicio')::DATE;
    v_data_fim := (filter_params->>'data_fim')::DATE;
    v_limit_val := COALESCE((filter_params->>'limit')::INTEGER, 50);
    v_offset_val := COALESCE((filter_params->>'offset')::INTEGER, 0);

    -- Limitar para evitar abusos
    IF v_limit_val > 100 THEN
        v_limit_val := 100;
    END IF;

    -- Contar resultados (para auditoria)
    SELECT COUNT(*) INTO v_results_count
    FROM pub.v_auction_discovery v
    WHERE
        (v_uf IS NULL OR v.uf = v_uf)
        AND (v_cidade IS NULL OR UPPER(v.cidade) LIKE UPPER('%' || v_cidade || '%'))
        AND (v_valor_min IS NULL OR v.valor_estimado >= v_valor_min)
        AND (v_valor_max IS NULL OR v.valor_estimado <= v_valor_max)
        AND (v_data_inicio IS NULL OR v.data_leilao >= v_data_inicio)
        AND (v_data_fim IS NULL OR v.data_leilao <= v_data_fim);

    -- Inserir log de auditoria
    INSERT INTO audit.consumption_logs (
        user_id,
        queried_at,
        filter_applied,
        results_count,
        response_time_ms
    ) VALUES (
        v_user_id,
        NOW(),
        filter_params,
        v_results_count,
        EXTRACT(MILLISECONDS FROM (clock_timestamp() - v_start_time))::INTEGER
    );

    -- Retornar resultados filtrados
    RETURN QUERY
    SELECT *
    FROM pub.v_auction_discovery v
    WHERE
        (v_uf IS NULL OR v.uf = v_uf)
        AND (v_cidade IS NULL OR UPPER(v.cidade) LIKE UPPER('%' || v_cidade || '%'))
        AND (v_valor_min IS NULL OR v.valor_estimado >= v_valor_min)
        AND (v_valor_max IS NULL OR v.valor_estimado <= v_valor_max)
        AND (v_data_inicio IS NULL OR v.data_leilao >= v_data_inicio)
        AND (v_data_fim IS NULL OR v.data_leilao <= v_data_fim)
    ORDER BY v.data_leilao DESC
    LIMIT v_limit_val
    OFFSET v_offset_val;
END;
$$;

-- Permissões da função
GRANT EXECUTE ON FUNCTION pub.fetch_auctions_audit(JSONB) TO authenticated;
GRANT EXECUTE ON FUNCTION pub.fetch_auctions_audit(JSONB) TO anon;

COMMENT ON FUNCTION pub.fetch_auctions_audit IS 'Busca leilões com filtros e registra log de auditoria para DaaS';

-- ============================================================================
-- FASE 8: FUNÇÕES AUXILIARES
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

GRANT EXECUTE ON FUNCTION pub.get_available_ufs() TO authenticated;
GRANT EXECUTE ON FUNCTION pub.get_available_ufs() TO anon;

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

GRANT EXECUTE ON FUNCTION pub.get_cities_by_uf(CHAR) TO authenticated;
GRANT EXECUTE ON FUNCTION pub.get_cities_by_uf(CHAR) TO anon;

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

GRANT EXECUTE ON FUNCTION pub.get_dashboard_stats() TO authenticated;
GRANT EXECUTE ON FUNCTION pub.get_dashboard_stats() TO anon;

-- ============================================================================
-- FASE 9: MIGRAR DADOS DA TABELA EXISTENTE (SE HOUVER)
-- ============================================================================

-- Migrar dados de editais_leilao (public) para raw.leiloes (se a tabela existir)
-- Usa apenas colunas que existem na tabela origem, NULL para as demais
DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM information_schema.tables WHERE table_schema = 'public' AND table_name = 'editais_leilao') THEN
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
        ON CONFLICT (id_interno) DO NOTHING;

        RAISE NOTICE 'Dados migrados de public.editais_leilao para raw.leiloes';
    END IF;
END $$;

-- ============================================================================
-- FIM DA INFRAESTRUTURA
-- ============================================================================

-- Verificação final
DO $$
BEGIN
    RAISE NOTICE '========================================';
    RAISE NOTICE 'INFRAESTRUTURA ACHE SUCATAS CRIADA!';
    RAISE NOTICE '========================================';
    RAISE NOTICE 'Schemas: raw, pub, audit';
    RAISE NOTICE 'Tabelas: raw.leiloes, pub.ref_municipios, audit.consumption_logs';
    RAISE NOTICE 'Views: pub.v_auction_discovery';
    RAISE NOTICE 'RPCs: pub.fetch_auctions_audit, pub.get_available_ufs, pub.get_cities_by_uf, pub.get_dashboard_stats';
    RAISE NOTICE '========================================';
END $$;
