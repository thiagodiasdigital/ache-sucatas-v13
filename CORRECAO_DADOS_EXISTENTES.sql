-- ============================================================================
-- CORREÇÃO DE DADOS EXISTENTES - ACHE SUCATAS
-- ============================================================================
-- Data: 2026-01-20
-- Objetivo: Corrigir dados faltando nos editais existentes
-- ============================================================================
--
-- EXECUTAR APÓS: CORRECAO_DEFINITIVA_VIEW.sql
--
-- COMO EXECUTAR:
-- 1. Acesse https://supabase.com/dashboard
-- 2. Selecione seu projeto
-- 3. Vá em "SQL Editor" (menu lateral esquerdo)
-- 4. Cole TODO este conteúdo
-- 5. Clique no botão "Run" (ou pressione Ctrl+Enter)
--
-- ============================================================================

-- ============================================================================
-- PASSO 1: DIAGNÓSTICO DETALHADO
-- ============================================================================

SELECT '=== DIAGNÓSTICO DE CAMPOS FALTANDO ===' AS info;

SELECT
    'Total de editais' AS campo,
    COUNT(*)::TEXT AS quantidade
FROM public.editais_leilao

UNION ALL

SELECT
    'Sem título',
    COUNT(*)::TEXT
FROM public.editais_leilao
WHERE titulo IS NULL OR titulo = ''

UNION ALL

SELECT
    'Sem descrição',
    COUNT(*)::TEXT
FROM public.editais_leilao
WHERE descricao IS NULL OR descricao = ''

UNION ALL

SELECT
    'Sem objeto_resumido',
    COUNT(*)::TEXT
FROM public.editais_leilao
WHERE objeto_resumido IS NULL OR objeto_resumido = ''

UNION ALL

SELECT
    'Sem tags',
    COUNT(*)::TEXT
FROM public.editais_leilao
WHERE tags IS NULL OR array_length(tags, 1) IS NULL

UNION ALL

SELECT
    'Sem link_leiloeiro',
    COUNT(*)::TEXT
FROM public.editais_leilao
WHERE link_leiloeiro IS NULL OR link_leiloeiro = '' OR link_leiloeiro = 'N/D'

UNION ALL

SELECT
    'Sem modalidade_leilao',
    COUNT(*)::TEXT
FROM public.editais_leilao
WHERE modalidade_leilao IS NULL OR modalidade_leilao = '' OR modalidade_leilao = 'N/D'

UNION ALL

SELECT
    'Com data passada',
    COUNT(*)::TEXT
FROM public.editais_leilao
WHERE data_leilao < CURRENT_DATE

UNION ALL

SELECT
    'Com data futura (válidos)',
    COUNT(*)::TEXT
FROM public.editais_leilao
WHERE data_leilao >= CURRENT_DATE;

-- ============================================================================
-- PASSO 2: REMOVER LEILÕES COM DATA PASSADA
-- ============================================================================

SELECT '=== REMOVENDO LEILÕES COM DATA PASSADA ===' AS info;

-- Criar tabela de backup primeiro
CREATE TABLE IF NOT EXISTS public.editais_leilao_arquivados AS
SELECT *, NOW() AS arquivado_em, 'data_passada' AS motivo
FROM public.editais_leilao
WHERE 1=0; -- Cria estrutura sem dados

-- Mover para backup
INSERT INTO public.editais_leilao_arquivados
SELECT *, NOW(), 'data_passada'
FROM public.editais_leilao
WHERE data_leilao < CURRENT_DATE;

-- Deletar da tabela principal
DELETE FROM public.editais_leilao
WHERE data_leilao < CURRENT_DATE;

-- ============================================================================
-- PASSO 3: REMOVER TAGS PROIBIDAS (SYNC, LEILAO)
-- ============================================================================

SELECT '=== REMOVENDO TAGS PROIBIDAS ===' AS info;

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
-- PASSO 4: NORMALIZAR MODALIDADES
-- ============================================================================

SELECT '=== NORMALIZANDO MODALIDADES ===' AS info;

-- Eletrônico
UPDATE public.editais_leilao
SET
    modalidade_leilao = 'Eletrônico',
    updated_at = NOW()
WHERE modalidade_leilao IN (
    'Leilão - Eletrônico',
    'Leil�o - Eletr�nico',
    'ELETRONICO',
    'Eletronico',
    'ELETRÔNICO',
    'Leilao - Eletronico'
);

-- Presencial
UPDATE public.editais_leilao
SET
    modalidade_leilao = 'Presencial',
    updated_at = NOW()
WHERE modalidade_leilao IN (
    'Leilão - Presencial',
    'Leil�o - Presencial',
    'PRESENCIAL',
    'Leilao - Presencial'
);

-- Híbrido
UPDATE public.editais_leilao
SET
    modalidade_leilao = 'Híbrido',
    updated_at = NOW()
WHERE modalidade_leilao IN (
    'HÍBRIDO',
    'H�BRIDO',
    'Hibrido',
    'H�brido'
);

-- ============================================================================
-- PASSO 5: CORRIGIR MODALIDADE BASEADO NO TÍTULO/DESCRIÇÃO
-- ============================================================================

-- Se título diz "Online" mas modalidade é "Presencial", corrigir
UPDATE public.editais_leilao
SET
    modalidade_leilao = 'Eletrônico',
    updated_at = NOW()
WHERE
    modalidade_leilao = 'Presencial'
    AND (
        LOWER(titulo) LIKE '%online%'
        OR LOWER(descricao) LIKE '%online%'
        OR LOWER(titulo) LIKE '%eletrônico%'
        OR LOWER(titulo) LIKE '%eletronico%'
    )
    AND LOWER(titulo) NOT LIKE '%presencial%';

-- Se menciona ambos, é Híbrido
UPDATE public.editais_leilao
SET
    modalidade_leilao = 'Híbrido',
    updated_at = NOW()
WHERE
    (
        LOWER(titulo) LIKE '%online%'
        OR LOWER(titulo) LIKE '%eletrônico%'
        OR LOWER(titulo) LIKE '%eletronico%'
    )
    AND LOWER(titulo) LIKE '%presencial%';

-- ============================================================================
-- PASSO 6: PREENCHER TÍTULO VAZIO COM OBJETO_RESUMIDO OU DESCRIÇÃO
-- ============================================================================

SELECT '=== PREENCHENDO TÍTULOS VAZIOS ===' AS info;

-- Usar objeto_resumido se disponível
UPDATE public.editais_leilao
SET
    titulo = COALESCE(objeto_resumido, SUBSTRING(descricao FROM 1 FOR 200)),
    updated_at = NOW()
WHERE
    (titulo IS NULL OR titulo = '')
    AND (objeto_resumido IS NOT NULL AND objeto_resumido != '')
    OR (descricao IS NOT NULL AND descricao != '');

-- ============================================================================
-- PASSO 7: EXTRAIR LINK_LEILOEIRO DA DESCRIÇÃO (se ainda não tem)
-- ============================================================================

SELECT '=== TENTANDO EXTRAIR LINKS DA DESCRIÇÃO ===' AS info;

-- Extrair URLs que parecem ser de leiloeiros
UPDATE public.editais_leilao
SET
    link_leiloeiro = (
        SELECT
            CASE
                WHEN descricao ~* 'https?://[^\s<>"'']+' THEN
                    (regexp_match(descricao, '(https?://[^\s<>"'']+)', 'i'))[1]
                WHEN descricao ~* 'www\.[^\s<>"'']+' THEN
                    'https://' || (regexp_match(descricao, '(www\.[^\s<>"'']+)', 'i'))[1]
                ELSE NULL
            END
    ),
    updated_at = NOW()
WHERE
    (link_leiloeiro IS NULL OR link_leiloeiro = '' OR link_leiloeiro = 'N/D')
    AND (
        descricao ~* 'https?://[^\s<>"'']+leilao'
        OR descricao ~* 'https?://[^\s<>"'']+leiloes'
        OR descricao ~* 'https?://[^\s<>"'']+lance'
        OR descricao ~* 'www\.[^\s<>"'']+leilao'
        OR descricao ~* 'www\.[^\s<>"'']+lance'
        OR descricao ~* 'superbid'
        OR descricao ~* 'sodresantoro'
        OR descricao ~* 'megaleiloes'
        OR descricao ~* 'jcacem'
        OR descricao ~* 'licitanet'
    );

-- ============================================================================
-- PASSO 8: ADICIONAR TAGS BASEADO NO CONTEÚDO (se não tem tags)
-- ============================================================================

SELECT '=== ADICIONANDO TAGS AUTOMÁTICAS ===' AS info;

-- Tag SUCATA
UPDATE public.editais_leilao
SET
    tags = ARRAY['SUCATA'],
    updated_at = NOW()
WHERE
    (tags IS NULL OR array_length(tags, 1) IS NULL OR tags = '{}')
    AND (
        LOWER(titulo || ' ' || COALESCE(descricao, '')) LIKE '%sucata%'
        OR LOWER(titulo || ' ' || COALESCE(descricao, '')) LIKE '%inservível%'
        OR LOWER(titulo || ' ' || COALESCE(descricao, '')) LIKE '%inservivel%'
    );

-- Tag AUTOMOVEL
UPDATE public.editais_leilao
SET
    tags = array_cat(COALESCE(tags, '{}'), ARRAY['AUTOMOVEL']),
    updated_at = NOW()
WHERE
    NOT ('AUTOMOVEL' = ANY(COALESCE(tags, '{}')))
    AND (
        LOWER(titulo || ' ' || COALESCE(descricao, '')) LIKE '%automóvel%'
        OR LOWER(titulo || ' ' || COALESCE(descricao, '')) LIKE '%automovel%'
        OR LOWER(titulo || ' ' || COALESCE(descricao, '')) LIKE '%veículo%'
        OR LOWER(titulo || ' ' || COALESCE(descricao, '')) LIKE '%veiculo%'
        OR LOWER(titulo || ' ' || COALESCE(descricao, '')) LIKE '%carro%'
    );

-- Tag MOTOCICLETA
UPDATE public.editais_leilao
SET
    tags = array_cat(COALESCE(tags, '{}'), ARRAY['MOTOCICLETA']),
    updated_at = NOW()
WHERE
    NOT ('MOTOCICLETA' = ANY(COALESCE(tags, '{}')))
    AND (
        LOWER(titulo || ' ' || COALESCE(descricao, '')) LIKE '%motocicleta%'
        OR LOWER(titulo || ' ' || COALESCE(descricao, '')) LIKE '%moto%'
    );

-- Tag CAMINHAO
UPDATE public.editais_leilao
SET
    tags = array_cat(COALESCE(tags, '{}'), ARRAY['CAMINHAO']),
    updated_at = NOW()
WHERE
    NOT ('CAMINHAO' = ANY(COALESCE(tags, '{}')))
    AND (
        LOWER(titulo || ' ' || COALESCE(descricao, '')) LIKE '%caminhão%'
        OR LOWER(titulo || ' ' || COALESCE(descricao, '')) LIKE '%caminhao%'
    );

-- Tag UTILITARIO
UPDATE public.editais_leilao
SET
    tags = array_cat(COALESCE(tags, '{}'), ARRAY['UTILITARIO']),
    updated_at = NOW()
WHERE
    NOT ('UTILITARIO' = ANY(COALESCE(tags, '{}')))
    AND (
        LOWER(titulo || ' ' || COALESCE(descricao, '')) LIKE '%utilitário%'
        OR LOWER(titulo || ' ' || COALESCE(descricao, '')) LIKE '%utilitario%'
        OR LOWER(titulo || ' ' || COALESCE(descricao, '')) LIKE '%pick-up%'
        OR LOWER(titulo || ' ' || COALESCE(descricao, '')) LIKE '%van%'
    );

-- ============================================================================
-- PASSO 9: RESULTADO FINAL
-- ============================================================================

SELECT '=== RESULTADO FINAL ===' AS info;

SELECT
    COUNT(*) AS total_leiloes,
    COUNT(*) FILTER (WHERE titulo IS NOT NULL AND titulo != '') AS com_titulo,
    COUNT(*) FILTER (WHERE link_leiloeiro IS NOT NULL AND link_leiloeiro != '' AND link_leiloeiro != 'N/D') AS com_link_leiloeiro,
    COUNT(*) FILTER (WHERE modalidade_leilao IN ('Eletrônico', 'Presencial', 'Híbrido')) AS modalidade_normalizada,
    COUNT(*) FILTER (WHERE tags IS NOT NULL AND array_length(tags, 1) > 0) AS com_tags,
    COUNT(*) FILTER (WHERE data_leilao >= CURRENT_DATE) AS data_futura
FROM public.editais_leilao;

-- Amostra dos dados corrigidos
SELECT '=== AMOSTRA (10 próximos leilões) ===' AS info;

SELECT
    id_interno,
    SUBSTRING(orgao FROM 1 FOR 40) AS orgao,
    uf,
    cidade,
    data_leilao::DATE AS data,
    modalidade_leilao AS modalidade,
    CASE WHEN link_leiloeiro IS NOT NULL AND link_leiloeiro != '' AND link_leiloeiro != 'N/D' THEN '✓' ELSE '❌' END AS link,
    array_to_string(tags, ',') AS tags
FROM public.editais_leilao
WHERE data_leilao >= CURRENT_DATE
ORDER BY data_leilao ASC
LIMIT 10;

-- ============================================================================
-- FIM
-- ============================================================================

DO $$
BEGIN
    RAISE NOTICE '========================================';
    RAISE NOTICE 'CORREÇÃO DE DADOS CONCLUÍDA!';
    RAISE NOTICE '========================================';
    RAISE NOTICE 'Agora atualize o dashboard (F5)';
    RAISE NOTICE '========================================';
END $$;
