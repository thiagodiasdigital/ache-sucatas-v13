-- =============================================================================
-- MIGRAÇÃO: Criar RPC para buscar lotes por id_interno do edital
-- Versão: 1.0
-- Data: 2026-01-26
-- Problema: Frontend usa raw.leiloes.id mas lotes referenciam editais_leilao.id
-- Solução: Função que faz o lookup transparente via id_interno
-- =============================================================================

-- -----------------------------------------------------------------------------
-- FUNÇÃO: get_lotes_by_id_interno
-- Propósito: Buscar lotes de um edital usando id_interno (campo único compartilhado)
-- -----------------------------------------------------------------------------

CREATE OR REPLACE FUNCTION public.get_lotes_by_id_interno(p_id_interno TEXT)
RETURNS TABLE (
    id BIGINT,
    id_interno TEXT,
    edital_id BIGINT,
    numero_lote TEXT,
    numero_lote_raw TEXT,
    descricao_completa TEXT,
    descricao_raw TEXT,
    valor_raw TEXT,
    avaliacao_valor NUMERIC,
    texto_fonte_completo TEXT,
    placa TEXT,
    chassi TEXT,
    renavam TEXT,
    marca TEXT,
    modelo TEXT,
    ano_fabricacao INTEGER,
    categoria_id TEXT,
    tipo_venda TEXT,
    confidence_score NUMERIC,
    fonte_tipo TEXT,
    fonte_arquivo TEXT,
    fonte_pagina INTEGER,
    versao_extrator TEXT,
    familia_pdf TEXT,
    data_extracao TIMESTAMPTZ,
    created_at TIMESTAMPTZ
)
LANGUAGE plpgsql
SECURITY DEFINER
STABLE
AS $$
DECLARE
    v_edital_id BIGINT;
BEGIN
    -- Buscar o ID do edital pelo id_interno
    SELECT e.id INTO v_edital_id
    FROM public.editais_leilao e
    WHERE e.id_interno = p_id_interno
    LIMIT 1;

    -- Se não encontrou, retorna vazio
    IF v_edital_id IS NULL THEN
        RETURN;
    END IF;

    -- Retornar lotes do edital encontrado
    RETURN QUERY
    SELECT
        l.id,
        l.id_interno,
        l.edital_id,
        l.numero_lote,
        l.numero_lote_raw,
        l.descricao_completa,
        l.descricao_raw,
        l.valor_raw,
        l.avaliacao_valor,
        l.texto_fonte_completo,
        l.placa,
        l.chassi,
        l.renavam,
        l.marca,
        l.modelo,
        l.ano_fabricacao,
        l.categoria_id,
        l.tipo_venda,
        l.confidence_score,
        l.fonte_tipo,
        l.fonte_arquivo,
        l.fonte_pagina,
        l.versao_extrator,
        l.familia_pdf,
        l.data_extracao,
        l.created_at
    FROM public.lotes_leilao l
    WHERE l.edital_id = v_edital_id
    ORDER BY l.numero_lote ASC;
END;
$$;

-- Permissões: permitir acesso público (anon e authenticated)
GRANT EXECUTE ON FUNCTION public.get_lotes_by_id_interno(TEXT) TO anon;
GRANT EXECUTE ON FUNCTION public.get_lotes_by_id_interno(TEXT) TO authenticated;

-- Comentário
COMMENT ON FUNCTION public.get_lotes_by_id_interno IS
'Busca lotes de um edital usando id_interno como chave de lookup.
Resolve incompatibilidade entre raw.leiloes.id e editais_leilao.id.
Retorna lista vazia se edital não encontrado.';

-- =============================================================================
-- VERIFICAÇÃO
-- =============================================================================

DO $$
BEGIN
    RAISE NOTICE '========================================';
    RAISE NOTICE 'RPC get_lotes_by_id_interno CRIADA!';
    RAISE NOTICE '========================================';
    RAISE NOTICE 'Uso: SELECT * FROM get_lotes_by_id_interno(''id_interno_aqui'')';
    RAISE NOTICE 'Permissões: anon, authenticated';
    RAISE NOTICE '========================================';
END $$;
