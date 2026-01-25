-- ============================================================
-- MIGRATION: Whitelist de Dominios de Leiloeiros
-- ============================================================
-- Data: 2026-01-24
-- Descricao: Migra a whitelist hardcoded do miner para o Supabase,
--            permitindo gerenciamento sem alterar codigo.
-- ============================================================

-- 1. Adicionar coluna whitelist_oficial na tabela existente
ALTER TABLE leiloeiros_urls
ADD COLUMN IF NOT EXISTS whitelist_oficial BOOLEAN DEFAULT FALSE;

-- 2. Indice para consulta rapida (filtra apenas TRUE)
CREATE INDEX IF NOT EXISTS idx_leiloeiros_whitelist
ON leiloeiros_urls(whitelist_oficial)
WHERE whitelist_oficial = TRUE;

-- 3. Inserir os 51 dominios com UPSERT
-- Se o dominio ja existir, apenas atualiza para whitelist_oficial = TRUE
INSERT INTO leiloeiros_urls (dominio, fonte, whitelist_oficial, validado)
VALUES
    ('lfranca.com.br', 'whitelist_v18', TRUE, TRUE),
    ('bidgo.com.br', 'whitelist_v18', TRUE, TRUE),
    ('sodresantoro.com.br', 'whitelist_v18', TRUE, TRUE),
    ('superbid.net', 'whitelist_v18', TRUE, TRUE),
    ('superbid.com.br', 'whitelist_v18', TRUE, TRUE),
    ('vipleiloes.com.br', 'whitelist_v18', TRUE, TRUE),
    ('frfranca.com.br', 'whitelist_v18', TRUE, TRUE),
    ('lancenoleilao.com.br', 'whitelist_v18', TRUE, TRUE),
    ('leilomaster.com.br', 'whitelist_v18', TRUE, TRUE),
    ('lut.com.br', 'whitelist_v18', TRUE, TRUE),
    ('zfrancaleiloes.com.br', 'whitelist_v18', TRUE, TRUE),
    ('amaralleiloes.com.br', 'whitelist_v18', TRUE, TRUE),
    ('bfranca.com.br', 'whitelist_v18', TRUE, TRUE),
    ('cronos.com.br', 'whitelist_v18', TRUE, TRUE),
    ('confederacaoleiloes.com.br', 'whitelist_v18', TRUE, TRUE),
    ('megaleiloes.com.br', 'whitelist_v18', TRUE, TRUE),
    ('leilaoseg.com.br', 'whitelist_v18', TRUE, TRUE),
    ('cfrancaleiloes.com.br', 'whitelist_v18', TRUE, TRUE),
    ('estreladaleiloes.com.br', 'whitelist_v18', TRUE, TRUE),
    ('sold.com.br', 'whitelist_v18', TRUE, TRUE),
    ('mitroleiloes.com.br', 'whitelist_v18', TRUE, TRUE),
    ('alifrancaleiloes.com.br', 'whitelist_v18', TRUE, TRUE),
    ('hastavip.com.br', 'whitelist_v18', TRUE, TRUE),
    ('klfrancaleiloes.com.br', 'whitelist_v18', TRUE, TRUE),
    ('centraldosleiloes.com.br', 'whitelist_v18', TRUE, TRUE),
    ('dfranca.com.br', 'whitelist_v18', TRUE, TRUE),
    ('rfrancaleiloes.com.br', 'whitelist_v18', TRUE, TRUE),
    ('sfranca.com.br', 'whitelist_v18', TRUE, TRUE),
    ('clickleiloes.com.br', 'whitelist_v18', TRUE, TRUE),
    ('petroleiloes.com.br', 'whitelist_v18', TRUE, TRUE),
    ('pfranca.com.br', 'whitelist_v18', TRUE, TRUE),
    ('clfranca.com.br', 'whitelist_v18', TRUE, TRUE),
    ('tfleiloes.com.br', 'whitelist_v18', TRUE, TRUE),
    ('kfranca.com.br', 'whitelist_v18', TRUE, TRUE),
    ('lanceja.com.br', 'whitelist_v18', TRUE, TRUE),
    ('portalleiloes.com.br', 'whitelist_v18', TRUE, TRUE),
    ('wfrancaleiloes.com.br', 'whitelist_v18', TRUE, TRUE),
    ('rafaelfrancaleiloes.com.br', 'whitelist_v18', TRUE, TRUE),
    ('alfrancaleiloes.com.br', 'whitelist_v18', TRUE, TRUE),
    ('jfrancaleiloes.com.br', 'whitelist_v18', TRUE, TRUE),
    ('mfranca.com.br', 'whitelist_v18', TRUE, TRUE),
    ('msfranca.com.br', 'whitelist_v18', TRUE, TRUE),
    ('stfrancaleiloes.com.br', 'whitelist_v18', TRUE, TRUE),
    ('ofrancaleiloes.com.br', 'whitelist_v18', TRUE, TRUE),
    ('hmfrancaleiloes.com.br', 'whitelist_v18', TRUE, TRUE),
    ('abataleiloes.com.br', 'whitelist_v18', TRUE, TRUE),
    ('webleilao.com.br', 'whitelist_v18', TRUE, TRUE),
    ('gfrancaleiloes.com.br', 'whitelist_v18', TRUE, TRUE),
    ('lleiloes.com.br', 'whitelist_v18', TRUE, TRUE),
    ('lanceleiloes.com.br', 'whitelist_v18', TRUE, TRUE),
    ('lopesleiloes.net.br', 'whitelist_v18', TRUE, TRUE),
    ('lopesleiloes.com.br', 'whitelist_v18', TRUE, TRUE),
    ('eckertleiloes.com.br', 'whitelist_v18', TRUE, TRUE),
    ('giordanoleiloes.com.br', 'whitelist_v18', TRUE, TRUE)
ON CONFLICT (dominio) DO UPDATE SET
    whitelist_oficial = TRUE,
    validado = TRUE;

-- 4. Verificar resultado
-- SELECT COUNT(*) as total_whitelist FROM leiloeiros_urls WHERE whitelist_oficial = TRUE;
