-- ============================================
-- ACHE SUCATAS DaaS V13 - Schemas Supabase
-- Data: 2026-01-16
-- Descrição: Schemas otimizados para o projeto atual
-- ============================================

-- ============================================
-- TABELA 1: editais_leilao (Principal)
-- Armazena todos os editais processados
-- ============================================

CREATE TABLE IF NOT EXISTS editais_leilao (
  -- Identificação
  id BIGSERIAL PRIMARY KEY,
  id_interno TEXT UNIQUE NOT NULL,           -- UF_CIDADE_PNCP_ID (ex: "SP_CAMPINAS_12345678000199-1-000001-2025")
  pncp_id TEXT UNIQUE NOT NULL,              -- CNPJ-SEQUENCIAL-ANO (ex: "12345678000199-1-000001-2025")

  -- Órgão
  orgao TEXT NOT NULL,
  uf CHAR(2) NOT NULL,
  cidade TEXT NOT NULL,

  -- Edital
  n_edital TEXT NOT NULL,
  n_pncp TEXT,

  -- Datas
  data_publicacao DATE NOT NULL,
  data_atualizacao DATE,
  data_leilao TIMESTAMP,

  -- Conteúdo
  titulo TEXT NOT NULL,
  descricao TEXT NOT NULL,
  objeto_resumido TEXT,
  tags TEXT[] NOT NULL,                      -- Array de tags (sucata, documentado, etc.)

  -- Links
  link_pncp TEXT NOT NULL,
  link_leiloeiro TEXT,

  -- Campos Comerciais (V12/V13)
  modalidade_leilao TEXT,                    -- ONLINE | PRESENCIAL | HÍBRIDO | N/D
  valor_estimado DECIMAL(12,2),              -- Em reais
  quantidade_itens INTEGER,
  nome_leiloeiro TEXT,

  -- Metadata
  arquivo_origem TEXT NOT NULL,              -- Path no file system local
  pdf_hash TEXT,                             -- SHA256 do PDF

  -- Controle
  created_at TIMESTAMPTZ DEFAULT NOW(),
  updated_at TIMESTAMPTZ DEFAULT NOW(),
  versao_auditor TEXT DEFAULT 'V13',         -- Rastreabilidade

  -- Constraints
  CONSTRAINT check_uf CHECK (length(uf) = 2),
  CONSTRAINT check_valor CHECK (valor_estimado IS NULL OR valor_estimado >= 0),
  CONSTRAINT check_quantidade CHECK (quantidade_itens IS NULL OR quantidade_itens >= 0)
);

-- Índices para performance
CREATE INDEX IF NOT EXISTS idx_editais_uf_cidade ON editais_leilao(uf, cidade);
CREATE INDEX IF NOT EXISTS idx_editais_data_leilao ON editais_leilao(data_leilao);
CREATE INDEX IF NOT EXISTS idx_editais_pncp_id ON editais_leilao(pncp_id);
CREATE INDEX IF NOT EXISTS idx_editais_tags ON editais_leilao USING GIN(tags);
CREATE INDEX IF NOT EXISTS idx_editais_created_at ON editais_leilao(created_at DESC);
CREATE INDEX IF NOT EXISTS idx_editais_modalidade ON editais_leilao(modalidade_leilao);

-- ============================================
-- TABELA 2: execucoes_miner (Log de Execuções)
-- Rastreia todas as execuções do miner
-- ============================================

CREATE TABLE IF NOT EXISTS execucoes_miner (
  id BIGSERIAL PRIMARY KEY,

  -- Execução
  execution_start TIMESTAMPTZ NOT NULL,
  execution_end TIMESTAMPTZ,
  duration_seconds DECIMAL(10,2),

  -- Configuração
  janela_temporal_horas INTEGER NOT NULL,
  termos_buscados INTEGER,
  paginas_por_termo INTEGER,

  -- Resultados
  editais_analisados INTEGER NOT NULL DEFAULT 0,
  editais_novos INTEGER NOT NULL DEFAULT 0,
  editais_duplicados INTEGER NOT NULL DEFAULT 0,
  taxa_deduplicacao DECIMAL(5,2),

  -- Downloads
  downloads INTEGER DEFAULT 0,
  downloads_sucesso INTEGER DEFAULT 0,
  downloads_falha INTEGER DEFAULT 0,

  -- Status
  status TEXT NOT NULL DEFAULT 'RUNNING',    -- RUNNING | SUCCESS | FAILED
  erro TEXT,                                 -- Mensagem de erro (se houver)

  -- Metadata
  versao_miner TEXT NOT NULL,                -- V9_CRON, V10, etc.
  checkpoint_snapshot JSONB,                 -- Snapshot do checkpoint

  created_at TIMESTAMPTZ DEFAULT NOW(),

  -- Constraints
  CONSTRAINT check_status CHECK (status IN ('RUNNING', 'SUCCESS', 'FAILED'))
);

CREATE INDEX IF NOT EXISTS idx_execucoes_start ON execucoes_miner(execution_start DESC);
CREATE INDEX IF NOT EXISTS idx_execucoes_status ON execucoes_miner(status);
CREATE INDEX IF NOT EXISTS idx_execucoes_versao ON execucoes_miner(versao_miner);

-- ============================================
-- TABELA 3: metricas_diarias (Analytics)
-- Métricas agregadas por dia
-- ============================================

CREATE TABLE IF NOT EXISTS metricas_diarias (
  id BIGSERIAL PRIMARY KEY,

  data DATE UNIQUE NOT NULL,

  -- Editais
  total_editais INTEGER NOT NULL DEFAULT 0,
  novos_editais INTEGER NOT NULL DEFAULT 0,
  editais_por_uf JSONB,                      -- {"SP": 45, "RJ": 32, ...}

  -- Valores
  valor_total_estimado DECIMAL(15,2),
  valor_medio_edital DECIMAL(12,2),

  -- Modalidades
  modalidades_count JSONB,                   -- {"ONLINE": 120, "PRESENCIAL": 30, ...}

  -- Qualidade de Dados
  taxa_preenchimento_valor DECIMAL(5,2),
  taxa_preenchimento_leiloeiro DECIMAL(5,2),
  taxa_preenchimento_quantidade DECIMAL(5,2),

  created_at TIMESTAMPTZ DEFAULT NOW(),
  updated_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_metricas_data ON metricas_diarias(data DESC);

-- ============================================
-- FUNÇÕES E TRIGGERS
-- ============================================

-- Função para atualizar updated_at automaticamente
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ language 'plpgsql';

-- Trigger para editais_leilao
DROP TRIGGER IF EXISTS update_editais_leilao_updated_at ON editais_leilao;
CREATE TRIGGER update_editais_leilao_updated_at
    BEFORE UPDATE ON editais_leilao
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();

-- Trigger para metricas_diarias
DROP TRIGGER IF EXISTS update_metricas_diarias_updated_at ON metricas_diarias;
CREATE TRIGGER update_metricas_diarias_updated_at
    BEFORE UPDATE ON metricas_diarias
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();

-- ============================================
-- VIEWS ÚTEIS
-- ============================================

-- View: Resumo de editais com estatísticas
CREATE OR REPLACE VIEW vw_editais_resumo AS
SELECT
    id,
    id_interno,
    pncp_id,
    orgao,
    uf,
    cidade,
    n_edital,
    data_publicacao,
    data_leilao,
    titulo,
    modalidade_leilao,
    valor_estimado,
    quantidade_itens,
    tags,
    link_pncp,
    link_leiloeiro,
    versao_auditor,
    created_at
FROM editais_leilao
ORDER BY data_publicacao DESC;

-- View: Estatísticas por UF
CREATE OR REPLACE VIEW vw_estatisticas_uf AS
SELECT
    uf,
    COUNT(*) AS total_editais,
    COUNT(*) FILTER (WHERE valor_estimado IS NOT NULL) AS com_valor,
    COUNT(*) FILTER (WHERE link_leiloeiro IS NOT NULL) AS com_leiloeiro,
    COUNT(*) FILTER (WHERE quantidade_itens IS NOT NULL) AS com_quantidade,
    SUM(valor_estimado) AS valor_total,
    ROUND(AVG(valor_estimado)::numeric, 2) AS valor_medio,
    MAX(data_leilao) AS ultimo_leilao
FROM editais_leilao
GROUP BY uf
ORDER BY total_editais DESC;

-- View: Estatísticas por modalidade
CREATE OR REPLACE VIEW vw_estatisticas_modalidade AS
SELECT
    modalidade_leilao,
    COUNT(*) AS total_editais,
    ROUND(AVG(valor_estimado)::numeric, 2) AS valor_medio,
    SUM(valor_estimado) AS valor_total
FROM editais_leilao
WHERE modalidade_leilao IS NOT NULL
GROUP BY modalidade_leilao
ORDER BY total_editais DESC;

-- ============================================
-- ROW LEVEL SECURITY (RLS) - SEGURANÇA MÁXIMA
-- ============================================

-- Ativar RLS em TODAS as tabelas
ALTER TABLE editais_leilao ENABLE ROW LEVEL SECURITY;
ALTER TABLE execucoes_miner ENABLE ROW LEVEL SECURITY;
ALTER TABLE metricas_diarias ENABLE ROW LEVEL SECURITY;

-- Política 1: Service Key tem acesso TOTAL
-- (Backend Python usa service_role key)
CREATE POLICY "Service role tem acesso total a editais"
ON editais_leilao
FOR ALL
TO service_role
USING (true)
WITH CHECK (true);

CREATE POLICY "Service role tem acesso total a execucoes"
ON execucoes_miner
FOR ALL
TO service_role
USING (true)
WITH CHECK (true);

CREATE POLICY "Service role tem acesso total a metricas"
ON metricas_diarias
FOR ALL
TO service_role
USING (true)
WITH CHECK (true);

-- Política 2: BLOQUEIO TOTAL via API pública
-- (Nenhuma política para 'anon' = acesso negado)
-- Isso garante que mesmo se anon key vazar, ninguém acessa nada

-- ============================================
-- COMENTÁRIOS NAS TABELAS
-- ============================================

COMMENT ON TABLE editais_leilao IS 'Editais de leilão de alienação de bens públicos - V13';
COMMENT ON TABLE execucoes_miner IS 'Log de execuções do miner (cron 3x/dia)';
COMMENT ON TABLE metricas_diarias IS 'Métricas agregadas diárias para analytics';

COMMENT ON COLUMN editais_leilao.pncp_id IS 'Identificador único PNCP: CNPJ-SEQUENCIAL-ANO';
COMMENT ON COLUMN editais_leilao.tags IS 'Tags classificatórias: sucata, documentado, automovel, etc.';
COMMENT ON COLUMN editais_leilao.versao_auditor IS 'Versão do auditor que processou (V12, V13, etc.)';
COMMENT ON COLUMN execucoes_miner.checkpoint_snapshot IS 'Snapshot do checkpoint para rastreabilidade';

-- ============================================
-- FIM DO SCHEMA V13
-- ============================================
