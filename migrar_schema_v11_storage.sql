-- ============================================
-- MIGRACAO: Adicionar colunas de Storage V11
-- ============================================
-- Executar no Supabase Dashboard > SQL Editor
-- Data: 2026-01-17
-- Proposito: Linkar PDFs do Storage aos registros do banco
-- ============================================

-- ============================================
-- PARTE 1: ADICIONAR COLUNAS FALTANTES
-- ============================================

-- Coluna para caminho no Storage
ALTER TABLE editais_leilao
ADD COLUMN IF NOT EXISTS storage_path TEXT;

-- Coluna para URL publica do PDF
ALTER TABLE editais_leilao
ADD COLUMN IF NOT EXISTS pdf_storage_url TEXT;

-- Coluna de controle do Auditor
ALTER TABLE editais_leilao
ADD COLUMN IF NOT EXISTS processado_auditor BOOLEAN DEFAULT false;

-- Coluna para score de relevancia
ALTER TABLE editais_leilao
ADD COLUMN IF NOT EXISTS score INTEGER;

-- ============================================
-- PARTE 2: CRIAR INDICES
-- ============================================

-- Indice para busca por storage_path
CREATE INDEX IF NOT EXISTS idx_editais_storage_path
ON editais_leilao(storage_path);

-- Indice para busca por processado_auditor
CREATE INDEX IF NOT EXISTS idx_editais_processado_auditor
ON editais_leilao(processado_auditor);

-- Indice para busca por score
CREATE INDEX IF NOT EXISTS idx_editais_score
ON editais_leilao(score);

-- ============================================
-- PARTE 3: COMENTARIOS (DOCUMENTACAO)
-- ============================================

COMMENT ON COLUMN editais_leilao.storage_path IS
'Caminho no Supabase Storage (ex: pncp_id/arquivo.pdf) - Adicionado V11';

COMMENT ON COLUMN editais_leilao.pdf_storage_url IS
'URL publica do PDF no Supabase Storage - Adicionado V11';

COMMENT ON COLUMN editais_leilao.processado_auditor IS
'Flag indicando se o Auditor V14 ja processou este edital';

COMMENT ON COLUMN editais_leilao.score IS
'Score de relevancia calculado pelo Miner (0-100)';

-- ============================================
-- PARTE 4: VERIFICACAO
-- ============================================

-- Verificar se as colunas foram criadas
SELECT column_name, data_type, column_default
FROM information_schema.columns
WHERE table_name = 'editais_leilao'
  AND column_name IN ('storage_path', 'pdf_storage_url', 'processado_auditor', 'score')
ORDER BY column_name;

-- ============================================
-- NOTA IMPORTANTE
-- ============================================
--
-- Os PDFs no Storage (20) e os registros no Banco (6)
-- NAO correspondem - sao de coletas diferentes:
--
-- STORAGE (sem ano no ID):
--   00394460005887-1-000001
--   00394460005887-1-000071
--   ... (20 total)
--
-- BANCO (com ano no ID):
--   04302189000128-1-000019-2025
--   04312641000132-1-000097-2025
--   ... (6 total)
--
-- Apos executar esta migracao, as PROXIMAS coletas
-- do Miner V11 vao popular storage_path corretamente.
--
-- Para os dados existentes, seria necessario:
-- 1. Re-coletar os editais do Storage, OU
-- 2. Importar os 20 PDFs do Storage como novos registros
-- ============================================

-- ============================================
-- FIM DA MIGRACAO
-- ============================================
