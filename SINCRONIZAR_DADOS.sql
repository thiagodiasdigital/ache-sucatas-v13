-- ============================================================================
-- SCRIPT: Sincronizar dados de public.editais_leilao para raw.leiloes
-- ============================================================================
-- VERSAO CORRIGIDA - Removida coluna pdf_storage_url que nao existe na origem
-- ============================================================================
--
-- COMO EXECUTAR:
-- 1. Acesse o Supabase Dashboard
-- 2. Va em "SQL Editor" (menu lateral)
-- 3. Cole este script inteiro
-- 4. Clique em "Run" (ou Ctrl+Enter)
-- ============================================================================

-- ============================================================================
-- PASSO 1: Verificar situacao atual (ANTES)
-- ============================================================================

DO $$
DECLARE
    v_count_editais INTEGER;
    v_count_raw INTEGER;
    v_count_view INTEGER;
BEGIN
    -- Contar em public.editais_leilao
    SELECT COUNT(*) INTO v_count_editais FROM public.editais_leilao;

    -- Contar em raw.leiloes
    SELECT COUNT(*) INTO v_count_raw FROM raw.leiloes;

    -- Contar na view (com filtros)
    SELECT COUNT(*) INTO v_count_view FROM pub.v_auction_discovery;

    RAISE NOTICE '========================================';
    RAISE NOTICE 'SITUACAO ATUAL (ANTES DA SINCRONIZACAO)';
    RAISE NOTICE '========================================';
    RAISE NOTICE 'public.editais_leilao: % registros', v_count_editais;
    RAISE NOTICE 'raw.leiloes: % registros', v_count_raw;
    RAISE NOTICE 'pub.v_auction_discovery (view): % registros', v_count_view;
    RAISE NOTICE '========================================';
END $$;

-- ============================================================================
-- PASSO 2: Sincronizar dados
-- ============================================================================

INSERT INTO raw.leiloes (
    id_interno,
    pncp_id,
    orgao,
    uf,
    cidade,
    n_edital,
    n_pncp,
    data_publicacao,
    data_atualizacao,
    data_leilao,
    titulo,
    descricao,
    objeto_resumido,
    tags,
    link_pncp,
    link_leiloeiro,
    modalidade_leilao,
    valor_estimado,
    quantidade_itens,
    nome_leiloeiro,
    arquivo_origem,
    storage_path,
    pdf_hash,
    versao_auditor,
    publication_status,
    created_at,
    updated_at
)
SELECT
    id_interno,
    pncp_id,
    orgao,
    uf,
    cidade,
    n_edital,
    n_pncp,
    data_publicacao,
    data_atualizacao,
    data_leilao,
    titulo,
    descricao,
    objeto_resumido,
    tags,
    link_pncp,
    link_leiloeiro,
    modalidade_leilao,
    valor_estimado,
    quantidade_itens,
    nome_leiloeiro,
    arquivo_origem,
    storage_path,
    pdf_hash,
    versao_auditor,
    'published',  -- Marca todos como publicados
    created_at,
    updated_at
FROM public.editais_leilao
ON CONFLICT (id_interno) DO UPDATE SET
    pncp_id = EXCLUDED.pncp_id,
    orgao = EXCLUDED.orgao,
    uf = EXCLUDED.uf,
    cidade = EXCLUDED.cidade,
    n_edital = EXCLUDED.n_edital,
    n_pncp = EXCLUDED.n_pncp,
    data_publicacao = EXCLUDED.data_publicacao,
    data_atualizacao = EXCLUDED.data_atualizacao,
    data_leilao = EXCLUDED.data_leilao,
    titulo = EXCLUDED.titulo,
    descricao = EXCLUDED.descricao,
    objeto_resumido = EXCLUDED.objeto_resumido,
    tags = EXCLUDED.tags,
    link_pncp = EXCLUDED.link_pncp,
    link_leiloeiro = EXCLUDED.link_leiloeiro,
    modalidade_leilao = EXCLUDED.modalidade_leilao,
    valor_estimado = EXCLUDED.valor_estimado,
    quantidade_itens = EXCLUDED.quantidade_itens,
    nome_leiloeiro = EXCLUDED.nome_leiloeiro,
    arquivo_origem = EXCLUDED.arquivo_origem,
    storage_path = EXCLUDED.storage_path,
    pdf_hash = EXCLUDED.pdf_hash,
    versao_auditor = EXCLUDED.versao_auditor,
    publication_status = 'published',
    updated_at = NOW();

-- ============================================================================
-- PASSO 3: Verificar situacao apos sincronizacao
-- ============================================================================

DO $$
DECLARE
    v_count_editais INTEGER;
    v_count_raw INTEGER;
    v_count_view INTEGER;
    v_sem_data_leilao INTEGER;
    v_sem_link_pncp INTEGER;
BEGIN
    -- Contar em public.editais_leilao
    SELECT COUNT(*) INTO v_count_editais FROM public.editais_leilao;

    -- Contar em raw.leiloes
    SELECT COUNT(*) INTO v_count_raw FROM raw.leiloes;

    -- Contar na view (com filtros)
    SELECT COUNT(*) INTO v_count_view FROM pub.v_auction_discovery;

    -- Contar quantos NAO tem data_leilao
    SELECT COUNT(*) INTO v_sem_data_leilao
    FROM raw.leiloes
    WHERE data_leilao IS NULL;

    -- Contar quantos NAO tem link_pncp
    SELECT COUNT(*) INTO v_sem_link_pncp
    FROM raw.leiloes
    WHERE link_pncp IS NULL OR link_pncp = '';

    RAISE NOTICE '========================================';
    RAISE NOTICE 'SITUACAO APOS SINCRONIZACAO';
    RAISE NOTICE '========================================';
    RAISE NOTICE 'public.editais_leilao: % registros', v_count_editais;
    RAISE NOTICE 'raw.leiloes: % registros', v_count_raw;
    RAISE NOTICE 'pub.v_auction_discovery (view): % registros', v_count_view;
    RAISE NOTICE '----------------------------------------';
    RAISE NOTICE 'Registros SEM data_leilao: %', v_sem_data_leilao;
    RAISE NOTICE 'Registros SEM link_pncp: %', v_sem_link_pncp;
    RAISE NOTICE '========================================';

    IF v_count_view < v_count_raw THEN
        RAISE NOTICE 'ATENCAO: A view exclui registros sem data_leilao ou link_pncp';
        RAISE NOTICE 'Se quiser ver TODOS os registros, execute o PASSO 4 abaixo';
    END IF;
END $$;

-- ============================================================================
-- PASSO 4 (OPCIONAL): Remover filtros da view para mostrar TODOS os registros
-- ============================================================================
-- Descomente as linhas abaixo se quiser que a view mostre TODOS os leiloes,
-- mesmo os que nao tem data_leilao ou link_pncp

/*
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
  -- Removido: AND l.data_leilao IS NOT NULL
  -- Removido: AND l.link_pncp IS NOT NULL
ORDER BY l.data_leilao DESC NULLS LAST;
*/

-- ============================================================================
-- FIM DO SCRIPT
-- ============================================================================
