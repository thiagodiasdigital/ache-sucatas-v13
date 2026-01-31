-- ============================================================
-- Discovery Veiculos - Tabela para armazenar veiculos de leilao
-- ============================================================
-- Criado em: 2026-01-31
-- Fonte: Discovery Pipeline (scrapers de DETRANs, PRF, etc.)
-- ============================================================

-- Criar tabela principal
CREATE TABLE IF NOT EXISTS discovery_veiculos (
    -- Identificacao
    id_fonte TEXT PRIMARY KEY,              -- Hash unico: fonte + edital + lote
    fonte TEXT NOT NULL,                     -- Ex: DETRAN-MG, DETRAN-SP, PRF

    -- Leilao
    edital TEXT,
    cidade TEXT,
    data_encerramento TEXT,
    status_leilao TEXT,                      -- Publicado, Em Andamento, Finalizado

    -- Veiculo
    lote INTEGER,
    categoria TEXT,                          -- Sucata, Conservado
    marca_modelo TEXT,
    ano INTEGER,
    placa TEXT,
    valor_inicial NUMERIC(12,2),

    -- Metadados
    url_lote TEXT,
    url_imagem TEXT,
    coletado_em TIMESTAMPTZ NOT NULL,

    -- Campos de controle
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- Indices para consultas frequentes
CREATE INDEX IF NOT EXISTS idx_discovery_veiculos_fonte
    ON discovery_veiculos(fonte);

CREATE INDEX IF NOT EXISTS idx_discovery_veiculos_categoria
    ON discovery_veiculos(categoria);

CREATE INDEX IF NOT EXISTS idx_discovery_veiculos_status
    ON discovery_veiculos(status_leilao);

CREATE INDEX IF NOT EXISTS idx_discovery_veiculos_coletado
    ON discovery_veiculos(coletado_em DESC);

CREATE INDEX IF NOT EXISTS idx_discovery_veiculos_valor
    ON discovery_veiculos(valor_inicial);

-- Indice full-text para busca por marca/modelo
CREATE INDEX IF NOT EXISTS idx_discovery_veiculos_marca_modelo
    ON discovery_veiculos USING gin(to_tsvector('portuguese', marca_modelo));

-- Trigger para updated_at
CREATE OR REPLACE FUNCTION update_discovery_veiculos_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trigger_discovery_veiculos_updated_at ON discovery_veiculos;
CREATE TRIGGER trigger_discovery_veiculos_updated_at
    BEFORE UPDATE ON discovery_veiculos
    FOR EACH ROW
    EXECUTE FUNCTION update_discovery_veiculos_updated_at();

-- ============================================================
-- VIEWS
-- ============================================================

-- View: Veiculos ativos (leiloes nao finalizados)
CREATE OR REPLACE VIEW discovery_veiculos_ativos AS
SELECT *
FROM discovery_veiculos
WHERE status_leilao IN ('Publicado', 'Em Andamento')
  AND coletado_em > NOW() - INTERVAL '7 days'
ORDER BY valor_inicial ASC;

-- View: Estatisticas por fonte
CREATE OR REPLACE VIEW discovery_stats_por_fonte AS
SELECT
    fonte,
    COUNT(*) as total_veiculos,
    COUNT(DISTINCT edital) as total_leiloes,
    SUM(CASE WHEN categoria = 'Sucata' THEN 1 ELSE 0 END) as sucatas,
    SUM(CASE WHEN categoria = 'Conservado' THEN 1 ELSE 0 END) as conservados,
    MIN(valor_inicial) as menor_valor,
    MAX(valor_inicial) as maior_valor,
    AVG(valor_inicial)::NUMERIC(12,2) as valor_medio,
    MAX(coletado_em) as ultima_coleta
FROM discovery_veiculos
GROUP BY fonte;

-- ============================================================
-- RLS (Row Level Security) - Opcional
-- ============================================================

-- Habilitar RLS
ALTER TABLE discovery_veiculos ENABLE ROW LEVEL SECURITY;

-- Policy: Leitura publica (anon pode ler)
CREATE POLICY "discovery_veiculos_read_all"
    ON discovery_veiculos
    FOR SELECT
    USING (true);

-- Policy: Escrita apenas service_role
CREATE POLICY "discovery_veiculos_write_service"
    ON discovery_veiculos
    FOR ALL
    USING (auth.role() = 'service_role');

-- ============================================================
-- COMENTARIOS
-- ============================================================

COMMENT ON TABLE discovery_veiculos IS 'Veiculos coletados de leiloes governamentais (DETRANs, PRF, etc.)';
COMMENT ON COLUMN discovery_veiculos.id_fonte IS 'Hash MD5 de fonte+edital+lote para deduplicacao';
COMMENT ON COLUMN discovery_veiculos.fonte IS 'Origem: DETRAN-MG, DETRAN-SP, PRF, etc.';
COMMENT ON COLUMN discovery_veiculos.categoria IS 'Classificacao: Sucata ou Conservado';
