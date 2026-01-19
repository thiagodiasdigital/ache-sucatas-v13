-- ============================================================================
-- REMOVE ANON GRANTS - Security Hardening
-- ============================================================================
-- Data: 2026-01-19
-- Motivo: Defesa em profundidade - frontend ja exige autenticacao
-- Impacto: Nenhum (usuarios anonimos ja sao bloqueados pelo ProtectedRoute)
-- Referencia: SECURITY_AUDIT_CONSOLIDATED.json - PERM-001, PERM-002
-- ============================================================================

-- ============================================================================
-- FASE 1: Revogar grants das RPC functions
-- ============================================================================

-- Revogar acesso anonimo as funcoes RPC
REVOKE EXECUTE ON FUNCTION public.fetch_auctions_audit(JSONB) FROM anon;
REVOKE EXECUTE ON FUNCTION public.get_available_ufs() FROM anon;
REVOKE EXECUTE ON FUNCTION public.get_cities_by_uf(CHAR) FROM anon;
REVOKE EXECUTE ON FUNCTION public.get_dashboard_stats() FROM anon;

-- Verificar que authenticated ainda tem acesso
-- (Nao precisa fazer nada, grants existentes permanecem)

-- ============================================================================
-- FASE 2: Remover policies de acesso anonimo (se existirem)
-- ============================================================================

-- Remover policy de leitura publica em editais_leilao (se existir)
DROP POLICY IF EXISTS "anon_read_access" ON editais_leilao;
DROP POLICY IF EXISTS "Permitir leitura pública" ON editais_leilao;
DROP POLICY IF EXISTS "Permitir leitura publica" ON editais_leilao;

-- ============================================================================
-- FASE 3: Verificacao
-- ============================================================================

-- Listar grants atuais nas funcoes (para confirmar)
SELECT
    routine_name,
    grantee,
    privilege_type
FROM information_schema.routine_privileges
WHERE routine_schema = 'public'
  AND routine_name IN (
    'fetch_auctions_audit',
    'get_available_ufs',
    'get_cities_by_uf',
    'get_dashboard_stats'
  )
ORDER BY routine_name, grantee;

-- Listar policies em editais_leilao
SELECT
    schemaname,
    tablename,
    policyname,
    permissive,
    roles,
    cmd
FROM pg_policies
WHERE tablename = 'editais_leilao';

-- ============================================================================
-- ROLLBACK (caso necessario no futuro)
-- ============================================================================
/*
-- Para restaurar acesso anonimo:
GRANT EXECUTE ON FUNCTION public.fetch_auctions_audit(JSONB) TO anon;
GRANT EXECUTE ON FUNCTION public.get_available_ufs() TO anon;
GRANT EXECUTE ON FUNCTION public.get_cities_by_uf(CHAR) TO anon;
GRANT EXECUTE ON FUNCTION public.get_dashboard_stats() TO anon;
*/

-- ============================================================================
-- FIM
-- ============================================================================
