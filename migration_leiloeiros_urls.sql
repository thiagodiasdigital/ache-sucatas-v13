-- ============================================================
-- Migration: Tabela de URLs de Leiloeiros Conhecidos
-- ============================================================
-- Data: 2026-01-21
-- Versão: V1_LEILOEIROS_URLS
--
-- Descrição:
--   Cria tabela para acumular domínios de leiloeiros encontrados
--   nos editais. Serve como whitelist dinâmica para validações
--   futuras e histórico de leiloeiros conhecidos.
-- ============================================================

-- Criar tabela principal
CREATE TABLE IF NOT EXISTS leiloeiros_urls (
    -- Domínio base como chave primária (ex: megaleiloes.com.br)
    dominio TEXT PRIMARY KEY,

    -- URL completa de exemplo (para referência)
    url_exemplo TEXT,

    -- Contagem de quantas vezes este domínio apareceu
    qtd_ocorrencias INT DEFAULT 1,

    -- Timestamps de rastreamento
    primeiro_visto TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    ultimo_visto TIMESTAMP WITH TIME ZONE DEFAULT NOW(),

    -- Fonte que encontrou o domínio (auditor, miner, manual)
    fonte TEXT DEFAULT 'auditor',

    -- Flag para validação manual (NULL = não revisado, true = válido, false = inválido)
    validado BOOLEAN DEFAULT NULL,

    -- Observações manuais
    notas TEXT
);

-- Comentários na tabela
COMMENT ON TABLE leiloeiros_urls IS
'Banco de dados de domínios de leiloeiros conhecidos, populado automaticamente pelo Auditor/Miner';

COMMENT ON COLUMN leiloeiros_urls.dominio IS
'Domínio base extraído da URL (ex: megaleiloes.com.br)';

COMMENT ON COLUMN leiloeiros_urls.url_exemplo IS
'Uma URL completa de exemplo onde este domínio foi encontrado';

COMMENT ON COLUMN leiloeiros_urls.qtd_ocorrencias IS
'Quantos editais diferentes usaram este domínio de leiloeiro';

COMMENT ON COLUMN leiloeiros_urls.fonte IS
'Origem do registro: auditor | miner | manual';

COMMENT ON COLUMN leiloeiros_urls.validado IS
'Validação manual: NULL=pendente, true=confirmado, false=inválido';


-- ============================================================
-- Função para registrar/atualizar domínio de leiloeiro
-- ============================================================
-- Uso: SELECT registrar_leiloeiro_url('megaleiloes.com.br', 'https://www.megaleiloes.com.br/leilao/123', 'auditor');

CREATE OR REPLACE FUNCTION registrar_leiloeiro_url(
    p_dominio TEXT,
    p_url_exemplo TEXT DEFAULT NULL,
    p_fonte TEXT DEFAULT 'auditor'
)
RETURNS void AS $$
BEGIN
    INSERT INTO leiloeiros_urls (dominio, url_exemplo, fonte, qtd_ocorrencias, primeiro_visto, ultimo_visto)
    VALUES (LOWER(p_dominio), p_url_exemplo, p_fonte, 1, NOW(), NOW())
    ON CONFLICT (dominio) DO UPDATE SET
        qtd_ocorrencias = leiloeiros_urls.qtd_ocorrencias + 1,
        ultimo_visto = NOW(),
        url_exemplo = COALESCE(EXCLUDED.url_exemplo, leiloeiros_urls.url_exemplo);
END;
$$ LANGUAGE plpgsql;

COMMENT ON FUNCTION registrar_leiloeiro_url IS
'Registra ou atualiza um domínio de leiloeiro. Se já existe, incrementa contagem.';


-- ============================================================
-- Índices para consultas
-- ============================================================

-- Índice para buscar por quantidade (mais usados primeiro)
CREATE INDEX IF NOT EXISTS idx_leiloeiros_qtd
ON leiloeiros_urls(qtd_ocorrencias DESC);

-- Índice para buscar pendentes de validação
CREATE INDEX IF NOT EXISTS idx_leiloeiros_validacao
ON leiloeiros_urls(validado)
WHERE validado IS NULL;

-- Índice para buscar por data
CREATE INDEX IF NOT EXISTS idx_leiloeiros_ultimo_visto
ON leiloeiros_urls(ultimo_visto DESC);


-- ============================================================
-- View para listar leiloeiros ordenados por uso
-- ============================================================

CREATE OR REPLACE VIEW v_leiloeiros_ranking AS
SELECT
    dominio,
    url_exemplo,
    qtd_ocorrencias,
    primeiro_visto,
    ultimo_visto,
    fonte,
    CASE
        WHEN validado IS NULL THEN 'pendente'
        WHEN validado = true THEN 'válido'
        ELSE 'inválido'
    END as status_validacao,
    notas
FROM leiloeiros_urls
ORDER BY qtd_ocorrencias DESC, ultimo_visto DESC;

COMMENT ON VIEW v_leiloeiros_ranking IS
'Ranking de leiloeiros por quantidade de ocorrências nos editais';


-- ============================================================
-- Função para verificar se domínio é conhecido
-- ============================================================

CREATE OR REPLACE FUNCTION is_leiloeiro_conhecido(p_url TEXT)
RETURNS BOOLEAN AS $$
DECLARE
    v_dominio TEXT;
BEGIN
    -- Extrair domínio da URL
    v_dominio := LOWER(
        REGEXP_REPLACE(
            REGEXP_REPLACE(p_url, '^https?://(www\.)?', ''),
            '/.*$', ''
        )
    );

    -- Verificar se existe na tabela
    RETURN EXISTS (
        SELECT 1 FROM leiloeiros_urls
        WHERE dominio = v_dominio
        AND (validado IS NULL OR validado = true)
    );
END;
$$ LANGUAGE plpgsql;

COMMENT ON FUNCTION is_leiloeiro_conhecido IS
'Verifica se uma URL pertence a um leiloeiro conhecido (não marcado como inválido)';


-- ============================================================
-- Popular com domínios já existentes nos editais
-- ============================================================

-- Extrair domínios únicos das URLs válidas já existentes
INSERT INTO leiloeiros_urls (dominio, url_exemplo, fonte, qtd_ocorrencias, primeiro_visto, ultimo_visto)
SELECT
    LOWER(
        REGEXP_REPLACE(
            REGEXP_REPLACE(link_leiloeiro, '^https?://(www\.)?', ''),
            '/.*$', ''
        )
    ) as dominio,
    MIN(link_leiloeiro) as url_exemplo,
    'historico' as fonte,
    COUNT(*) as qtd_ocorrencias,
    MIN(created_at) as primeiro_visto,
    MAX(updated_at) as ultimo_visto
FROM editais_leilao
WHERE
    link_leiloeiro IS NOT NULL
    AND link_leiloeiro != ''
    AND link_leiloeiro != 'N/D'
    AND (link_leiloeiro_valido IS NULL OR link_leiloeiro_valido = true)
GROUP BY LOWER(
    REGEXP_REPLACE(
        REGEXP_REPLACE(link_leiloeiro, '^https?://(www\.)?', ''),
        '/.*$', ''
    )
)
ON CONFLICT (dominio) DO UPDATE SET
    qtd_ocorrencias = EXCLUDED.qtd_ocorrencias,
    ultimo_visto = EXCLUDED.ultimo_visto;


-- ============================================================
-- Fim da migration
-- ============================================================

DO $$
BEGIN
    RAISE NOTICE 'Migration V1_LEILOEIROS_URLS aplicada com sucesso';
    RAISE NOTICE 'Tabela leiloeiros_urls criada e populada com domínios existentes';
END $$;
