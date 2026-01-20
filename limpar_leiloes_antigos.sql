-- ============================================================================
-- SCRIPT: Limpar/Arquivar Leiloes com Data Passada
-- ============================================================================
-- Este script remove leiloes com data_leilao anterior a hoje do banco.
-- Leiloes antigos nao sao mais relevantes pois ja aconteceram.
--
-- COMO EXECUTAR:
-- 1. Acesse o Supabase Dashboard (https://supabase.com/dashboard)
-- 2. Va em "SQL Editor" (menu lateral)
-- 3. Cole este script inteiro
-- 4. Clique em "Run" (ou Ctrl+Enter)
-- ============================================================================

-- ============================================================================
-- PASSO 1: Diagnostico - Ver quantos leiloes estao com data passada
-- ============================================================================

DO $$
DECLARE
    v_total INTEGER;
    v_data_passada INTEGER;
    v_data_2024 INTEGER;
    v_data_futura INTEGER;
    v_sem_data INTEGER;
BEGIN
    -- Total de leiloes
    SELECT COUNT(*) INTO v_total FROM raw.leiloes;

    -- Com data passada (antes de hoje)
    SELECT COUNT(*) INTO v_data_passada
    FROM raw.leiloes
    WHERE data_leilao < CURRENT_DATE;

    -- Especificamente de 2024
    SELECT COUNT(*) INTO v_data_2024
    FROM raw.leiloes
    WHERE EXTRACT(YEAR FROM data_leilao) = 2024;

    -- Com data futura (hoje ou depois)
    SELECT COUNT(*) INTO v_data_futura
    FROM raw.leiloes
    WHERE data_leilao >= CURRENT_DATE;

    -- Sem data
    SELECT COUNT(*) INTO v_sem_data
    FROM raw.leiloes
    WHERE data_leilao IS NULL;

    RAISE NOTICE '================================================';
    RAISE NOTICE 'DIAGNOSTICO DE LEILOES POR DATA';
    RAISE NOTICE '================================================';
    RAISE NOTICE 'Total de leiloes no banco: %', v_total;
    RAISE NOTICE '------------------------------------------------';
    RAISE NOTICE 'Com data PASSADA (antes de hoje): % (SERAO REMOVIDOS)', v_data_passada;
    RAISE NOTICE '  - Especificamente de 2024: %', v_data_2024;
    RAISE NOTICE 'Com data FUTURA (hoje ou depois): % (SERAO MANTIDOS)', v_data_futura;
    RAISE NOTICE 'Sem data (NULL): % (SERAO MANTIDOS)', v_sem_data;
    RAISE NOTICE '================================================';
END $$;

-- ============================================================================
-- PASSO 2: Ver amostra dos leiloes que serao removidos
-- ============================================================================

SELECT
    id_interno,
    orgao,
    uf,
    data_leilao,
    titulo
FROM raw.leiloes
WHERE data_leilao < CURRENT_DATE
ORDER BY data_leilao DESC
LIMIT 10;

-- ============================================================================
-- PASSO 3: REMOVER leiloes com data passada
-- ============================================================================
-- ATENCAO: Esta operacao é IRREVERSIVEL!
-- Se quiser apenas ARQUIVAR (mover para outra tabela), use o PASSO 3B

-- Descomente a linha abaixo para DELETAR os leiloes antigos:

-- DELETE FROM raw.leiloes WHERE data_leilao < CURRENT_DATE;

-- ============================================================================
-- PASSO 3B (ALTERNATIVA): ARQUIVAR em vez de deletar
-- ============================================================================
-- Esta opcao move os leiloes antigos para uma tabela de arquivo
-- Assim voce pode recuperar se precisar

-- Primeiro, criar tabela de arquivo (execute apenas uma vez):
/*
CREATE TABLE IF NOT EXISTS raw.leiloes_arquivados (
    LIKE raw.leiloes INCLUDING ALL,
    arquivado_em TIMESTAMP DEFAULT NOW(),
    motivo_arquivo TEXT DEFAULT 'data_leilao_passada'
);
*/

-- Depois, mover os leiloes antigos:
/*
INSERT INTO raw.leiloes_arquivados (
    id, id_interno, pncp_id, orgao, uf, cidade, n_edital, n_pncp,
    data_publicacao, data_atualizacao, data_leilao, titulo, descricao,
    objeto_resumido, tags, link_pncp, link_leiloeiro, modalidade_leilao,
    valor_estimado, quantidade_itens, nome_leiloeiro, arquivo_origem,
    storage_path, pdf_hash, versao_auditor, publication_status,
    score, created_at, updated_at
)
SELECT
    id, id_interno, pncp_id, orgao, uf, cidade, n_edital, n_pncp,
    data_publicacao, data_atualizacao, data_leilao, titulo, descricao,
    objeto_resumido, tags, link_pncp, link_leiloeiro, modalidade_leilao,
    valor_estimado, quantidade_itens, nome_leiloeiro, arquivo_origem,
    storage_path, pdf_hash, versao_auditor, publication_status,
    score, created_at, updated_at
FROM raw.leiloes
WHERE data_leilao < CURRENT_DATE;

-- Apos arquivar, deletar da tabela principal:
DELETE FROM raw.leiloes WHERE data_leilao < CURRENT_DATE;
*/

-- ============================================================================
-- PASSO 4: Verificar resultado apos limpeza
-- ============================================================================

DO $$
DECLARE
    v_total INTEGER;
    v_na_view INTEGER;
BEGIN
    SELECT COUNT(*) INTO v_total FROM raw.leiloes;
    SELECT COUNT(*) INTO v_na_view FROM pub.v_auction_discovery;

    RAISE NOTICE '================================================';
    RAISE NOTICE 'RESULTADO APOS LIMPEZA';
    RAISE NOTICE '================================================';
    RAISE NOTICE 'Total em raw.leiloes: %', v_total;
    RAISE NOTICE 'Total na view (frontend): %', v_na_view;
    RAISE NOTICE '================================================';
    RAISE NOTICE 'Atualize a pagina do dashboard (F5) para ver as mudancas';
END $$;

-- ============================================================================
-- FIM DO SCRIPT
-- ============================================================================
