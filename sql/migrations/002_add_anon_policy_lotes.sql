-- =============================================================================
-- MIGRAÇÃO: Adicionar política RLS para leitura pública de lotes
-- Versão: 1.0
-- Data: 2026-01-26
-- Problema: Frontend usa anon key e não consegue acessar lotes_leilao
-- =============================================================================

-- Política para permitir SELECT público (anon) na tabela lotes_leilao
CREATE POLICY "Leitura publica lotes_leilao"
ON public.lotes_leilao FOR SELECT TO anon
USING (true);

-- Também permitir para authenticated (usuários logados)
CREATE POLICY "Leitura authenticated lotes_leilao"
ON public.lotes_leilao FOR SELECT TO authenticated
USING (true);

-- =============================================================================
-- FIM DA MIGRAÇÃO
-- =============================================================================
