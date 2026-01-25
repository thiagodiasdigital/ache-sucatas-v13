-- ============================================================
-- SETUP: Bucket de Reports no Supabase Storage
-- Brief 1.3 - Relatório de Qualidade
-- Data: 2026-01-26
-- ============================================================
-- IMPORTANTE: Este SQL deve ser executado no Supabase SQL Editor
-- apenas se o bucket "reports" não existir.
--
-- ALTERNATIVA: Criar via Dashboard:
-- 1. Supabase Dashboard > Storage
-- 2. Create Bucket > Nome: "reports"
-- 3. Public: No (privado, apenas service_key)
-- ============================================================

-- Verificar se o bucket existe (executar primeiro)
-- SELECT * FROM storage.buckets WHERE name = 'reports';

-- Criar bucket de reports (se não existir)
INSERT INTO storage.buckets (id, name, public, file_size_limit, allowed_mime_types)
VALUES (
    'reports',
    'reports',
    false,  -- Privado (apenas service_key pode acessar)
    5242880,  -- 5MB max por arquivo
    ARRAY['application/json']::text[]
)
ON CONFLICT (id) DO NOTHING;

-- Política de acesso: apenas service_role pode inserir
CREATE POLICY "Service role can upload reports" ON storage.objects
    FOR INSERT
    TO service_role
    WITH CHECK (bucket_id = 'reports');

-- Política de acesso: apenas service_role pode ler
CREATE POLICY "Service role can read reports" ON storage.objects
    FOR SELECT
    TO service_role
    USING (bucket_id = 'reports');

-- ============================================================
-- VERIFICAÇÃO (executar após criar):
-- SELECT * FROM storage.buckets WHERE name = 'reports';
-- ============================================================
