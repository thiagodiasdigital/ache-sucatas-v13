-- =============================================================================
-- MIGRAÇÃO: Padronizar id_interno para formato ID_XXXXXXXXXXXX
-- Versão: 1.0
-- Data: 2026-01-26
--
-- Problema: Existem dois formatos de id_interno:
--   - Formato CORRETO: ID_FFC584EA30FA (12 chars hex maiúsculo)
--   - Formato ERRADO: UF_CIDADE_CNPJ-... (formato antigo)
--
-- Solução: Criar função que gera novo ID e atualiza ambas as tabelas
-- =============================================================================

-- -----------------------------------------------------------------------------
-- FUNÇÃO: gerar_id_interno_padrao
-- Gera ID no formato ID_XXXXXXXXXXXX usando gen_random_uuid()
-- -----------------------------------------------------------------------------
CREATE OR REPLACE FUNCTION public.gerar_id_interno_padrao()
RETURNS TEXT
LANGUAGE sql
AS $$
    SELECT 'ID_' || UPPER(SUBSTRING(REPLACE(gen_random_uuid()::text, '-', ''), 1, 12));
$$;

COMMENT ON FUNCTION public.gerar_id_interno_padrao IS 'Gera id_interno no formato padrão ID_XXXXXXXXXXXX';

-- -----------------------------------------------------------------------------
-- FUNÇÃO: migrar_id_interno_formato
-- Migra todos os id_interno do formato antigo para o novo
-- Retorna quantidade de registros atualizados
-- -----------------------------------------------------------------------------
CREATE OR REPLACE FUNCTION public.migrar_id_interno_formato()
RETURNS TABLE (
    tabela TEXT,
    registros_atualizados INTEGER,
    registros_totais INTEGER
)
LANGUAGE plpgsql
SECURITY DEFINER
AS $$
DECLARE
    v_count_editais INTEGER := 0;
    v_count_raw INTEGER := 0;
    v_total_editais INTEGER := 0;
    v_total_raw INTEGER := 0;
    r RECORD;
    v_novo_id TEXT;
BEGIN
    -- Contar totais
    SELECT COUNT(*) INTO v_total_editais FROM public.editais_leilao;
    SELECT COUNT(*) INTO v_total_raw FROM raw.leiloes;

    -- Criar tabela temporária com mapeamento
    CREATE TEMP TABLE IF NOT EXISTS temp_id_mapping (
        old_id_interno TEXT PRIMARY KEY,
        new_id_interno TEXT NOT NULL
    );

    -- Limpar tabela temporária
    TRUNCATE temp_id_mapping;

    -- Popular mapeamento para editais_leilao
    FOR r IN
        SELECT id_interno
        FROM public.editais_leilao
        WHERE id_interno IS NOT NULL
          AND id_interno NOT LIKE 'ID_%'
    LOOP
        INSERT INTO temp_id_mapping (old_id_interno, new_id_interno)
        VALUES (r.id_interno, public.gerar_id_interno_padrao())
        ON CONFLICT (old_id_interno) DO NOTHING;
    END LOOP;

    -- Adicionar mapeamento para raw.leiloes que não estão em editais
    FOR r IN
        SELECT id_interno
        FROM raw.leiloes
        WHERE id_interno IS NOT NULL
          AND id_interno NOT LIKE 'ID_%'
          AND id_interno NOT IN (SELECT old_id_interno FROM temp_id_mapping)
    LOOP
        INSERT INTO temp_id_mapping (old_id_interno, new_id_interno)
        VALUES (r.id_interno, public.gerar_id_interno_padrao())
        ON CONFLICT (old_id_interno) DO NOTHING;
    END LOOP;

    -- Atualizar editais_leilao
    UPDATE public.editais_leilao e
    SET id_interno = m.new_id_interno
    FROM temp_id_mapping m
    WHERE e.id_interno = m.old_id_interno;

    GET DIAGNOSTICS v_count_editais = ROW_COUNT;

    -- Atualizar raw.leiloes
    UPDATE raw.leiloes r
    SET id_interno = m.new_id_interno
    FROM temp_id_mapping m
    WHERE r.id_interno = m.old_id_interno;

    GET DIAGNOSTICS v_count_raw = ROW_COUNT;

    -- Dropar tabela temporária
    DROP TABLE IF EXISTS temp_id_mapping;

    -- Retornar resultados
    RETURN QUERY SELECT 'editais_leilao'::TEXT, v_count_editais, v_total_editais;
    RETURN QUERY SELECT 'raw.leiloes'::TEXT, v_count_raw, v_total_raw;
END;
$$;

COMMENT ON FUNCTION public.migrar_id_interno_formato IS 'Migra id_interno do formato UF_CIDADE_... para ID_XXXX';

-- Permissões (apenas service_role pode executar)
REVOKE ALL ON FUNCTION public.migrar_id_interno_formato() FROM PUBLIC;
GRANT EXECUTE ON FUNCTION public.migrar_id_interno_formato() TO service_role;

-- -----------------------------------------------------------------------------
-- VERIFICAÇÃO PRÉ-MIGRAÇÃO
-- -----------------------------------------------------------------------------
DO $$
DECLARE
    v_editais_errados INTEGER;
    v_raw_errados INTEGER;
BEGIN
    SELECT COUNT(*) INTO v_editais_errados
    FROM public.editais_leilao
    WHERE id_interno IS NOT NULL AND id_interno NOT LIKE 'ID_%';

    SELECT COUNT(*) INTO v_raw_errados
    FROM raw.leiloes
    WHERE id_interno IS NOT NULL AND id_interno NOT LIKE 'ID_%';

    RAISE NOTICE '========================================';
    RAISE NOTICE 'PRÉ-MIGRAÇÃO - Registros a migrar:';
    RAISE NOTICE '  editais_leilao: % registros', v_editais_errados;
    RAISE NOTICE '  raw.leiloes: % registros', v_raw_errados;
    RAISE NOTICE '========================================';
    RAISE NOTICE '';
    RAISE NOTICE 'Para executar a migração, rode:';
    RAISE NOTICE '  SELECT * FROM public.migrar_id_interno_formato();';
    RAISE NOTICE '========================================';
END $$;

-- =============================================================================
-- PARA EXECUTAR A MIGRAÇÃO:
-- 1. Execute este arquivo no SQL Editor do Supabase
-- 2. Depois execute: SELECT * FROM public.migrar_id_interno_formato();
-- =============================================================================
