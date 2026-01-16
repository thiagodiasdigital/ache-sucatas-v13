# PROPOSTA DE INTEGRAÇÃO - SUPABASE + GITHUB
## ACHE SUCATAS DaaS V13

**Data**: 2026-01-16
**Stack Atual**: Python 3.9+ | File-based | API PNCP
**Objetivo**: Integrar Supabase (PostgreSQL) + GitHub (versionamento)

---

## 📊 STACK ATUAL (V12)

### Backend / Processamento
- **Python 3.9+**
  - pandas 2.3.3 - Manipulação de dados
  - pdfplumber 0.11.8 - Extração de PDFs
  - requests 2.32.5 - HTTP requests (API PNCP)
  - aiohttp 3.13.3 - Async HTTP (miner)
  - pydantic 2.12.5 - Validação de schemas
  - **supabase 2.27.0** - ✅ INSTALADO (não integrado)

### Storage Atual
- **File System Local**
  - 198 editais em `ACHE_SUCATAS_DB/`
  - Checkpoint: `.ache_sucatas_checkpoint.json`
  - Métricas: `ache_sucatas_metrics.jsonl`
  - Output: `analise_editais_v12.csv` + `RESULTADO_FINAL.xlsx`

### Pipeline Atual
```
API PNCP → Miner V9 → ACHE_SUCATAS_DB/ → Auditor V12 → CSV/XLSX
```

---

## 🎯 OBJETIVOS DA INTEGRAÇÃO

### 1. **Supabase (PostgreSQL Cloud)**
**Por quê?**
- ✅ Dados centralizados e seguros
- ✅ API REST automática
- ✅ Dashboard de visualização
- ✅ Queries SQL avançadas
- ✅ Backup automático
- ✅ Colaboração em tempo real

**O que integrar:**
- Tabela `editais_leilao` (19 colunas)
- Tabela `execucoes_miner` (log de execuções)
- Tabela `metricas_diarias` (analytics)

### 2. **GitHub (Versionamento)**
**Por quê?**
- ✅ Controle de versão do código
- ✅ Colaboração com equipe
- ✅ CI/CD automatizado
- ✅ Backup do código
- ✅ Issues e documentação

**O que versionar:**
- Scripts Python (miner, auditor)
- Schemas (SQL, JSON)
- Documentação (MD)
- Configurações (cron, .env.example)

---

## 🏗️ ARQUITETURA PROPOSTA (V13)

### Arquitetura de Dados
```
┌─────────────────────────────────────────────────────┐
│                  API PNCP (Source)                  │
│       https://pncp.gov.br/api/consulta/v1/          │
└──────────────────────┬──────────────────────────────┘
                       │
                       ▼
        ┌──────────────────────────────┐
        │   Miner V9 (Async Crawler)   │
        │   - aiohttp (async requests) │
        │   - Checkpoint local         │
        │   - Cron 3x/dia              │
        └──────────────┬───────────────┘
                       │
                       ▼
        ┌──────────────────────────────┐
        │   ACHE_SUCATAS_DB/ (Cache)   │
        │   - PDFs (opcional*)         │
        │   - metadados_pncp.json      │
        └──────────────┬───────────────┘
                       │
                       ▼
        ┌──────────────────────────────┐
        │   Auditor V13 (Processor)    │
        │   - pdfplumber               │
        │   - API PNCP (FONTE 0)       │
        │   - Cascata de extração      │
        │   - Supabase Client ✨ NOVO  │
        └──────────────┬───────────────┘
                       │
                       ├─────────────────┐
                       ▼                 ▼
        ┌──────────────────┐  ┌───────────────────┐
        │  Supabase DB ✨  │  │  CSV/XLSX (Backup)│
        │  - editais_leilao│  │  - Compatibilidade│
        │  - execucoes     │  │  - Analytics local│
        │  - metricas      │  └───────────────────┘
        └──────────────────┘
                 │
                 ▼
        ┌──────────────────────────────┐
        │   Supabase Dashboard         │
        │   - Visualização de dados    │
        │   - API REST automática      │
        │   - Auth (futuro)            │
        └──────────────────────────────┘
```

*PDFs opcionais: Podemos mover para Supabase Storage (economia de disco local)

---

## 📋 SCHEMA DO BANCO DE DADOS

### Tabela 1: `editais_leilao` (Principal)

```sql
CREATE TABLE editais_leilao (
  -- Identificação
  id BIGSERIAL PRIMARY KEY,
  id_interno TEXT UNIQUE NOT NULL,  -- UF_CIDADE_PNCP_ID
  pncp_id TEXT UNIQUE NOT NULL,     -- CNPJ-ANO-SEQUENCIAL

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
  tags TEXT[] NOT NULL,              -- Array de tags

  -- Links
  link_pncp TEXT NOT NULL,
  link_leiloeiro TEXT,

  -- Comercial (V12)
  modalidade_leilao TEXT,            -- ONLINE | PRESENCIAL | HÍBRIDO
  valor_estimado DECIMAL(12,2),      -- Em reais
  quantidade_itens INTEGER,
  nome_leiloeiro TEXT,

  -- Metadata
  arquivo_origem TEXT NOT NULL,      -- Path no file system
  pdf_hash TEXT,                     -- SHA256 do PDF

  -- Controle
  created_at TIMESTAMPTZ DEFAULT NOW(),
  updated_at TIMESTAMPTZ DEFAULT NOW(),
  versao_auditor TEXT DEFAULT 'V13', -- Rastreabilidade

  -- Índices
  CONSTRAINT check_uf CHECK (length(uf) = 2),
  CONSTRAINT check_valor CHECK (valor_estimado IS NULL OR valor_estimado >= 0)
);

-- Índices para performance
CREATE INDEX idx_editais_uf_cidade ON editais_leilao(uf, cidade);
CREATE INDEX idx_editais_data_leilao ON editais_leilao(data_leilao);
CREATE INDEX idx_editais_pncp_id ON editais_leilao(pncp_id);
CREATE INDEX idx_editais_tags ON editais_leilao USING GIN(tags);
CREATE INDEX idx_editais_created_at ON editais_leilao(created_at);
```

### Tabela 2: `execucoes_miner` (Log de Execuções)

```sql
CREATE TABLE execucoes_miner (
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
  editais_analisados INTEGER NOT NULL,
  editais_novos INTEGER NOT NULL,
  editais_duplicados INTEGER NOT NULL,
  taxa_deduplicacao DECIMAL(5,2),

  -- Downloads
  downloads INTEGER DEFAULT 0,
  downloads_sucesso INTEGER DEFAULT 0,
  downloads_falha INTEGER DEFAULT 0,

  -- Status
  status TEXT NOT NULL,              -- RUNNING | SUCCESS | FAILED
  erro TEXT,                         -- Mensagem de erro (se houver)

  -- Metadata
  versao_miner TEXT NOT NULL,        -- V9_CRON
  checkpoint_snapshot JSONB,         -- Snapshot do checkpoint

  created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_execucoes_start ON execucoes_miner(execution_start DESC);
CREATE INDEX idx_execucoes_status ON execucoes_miner(status);
```

### Tabela 3: `metricas_diarias` (Analytics Agregadas)

```sql
CREATE TABLE metricas_diarias (
  id BIGSERIAL PRIMARY KEY,

  data DATE UNIQUE NOT NULL,

  -- Editais
  total_editais INTEGER NOT NULL,
  novos_editais INTEGER NOT NULL,
  editais_por_uf JSONB,              -- {"SP": 45, "RJ": 32, ...}

  -- Valores
  valor_total_estimado DECIMAL(15,2),
  valor_medio_edital DECIMAL(12,2),

  -- Modalidades
  modalidades_count JSONB,           -- {"ONLINE": 120, "PRESENCIAL": 30, ...}

  -- Qualidade
  taxa_preenchimento_valor DECIMAL(5,2),
  taxa_preenchimento_leiloeiro DECIMAL(5,2),

  created_at TIMESTAMPTZ DEFAULT NOW(),
  updated_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_metricas_data ON metricas_diarias(data DESC);
```

---

## 🚀 IMPLEMENTAÇÃO V13

### Fase 1: Setup Supabase (2h)
1. ✅ Criar projeto no Supabase
2. ✅ Executar SQL schemas acima
3. ✅ Configurar RLS (Row Level Security) - opcional
4. ✅ Criar `.env` local com credenciais

### Fase 2: Modificar Auditor V12 → V13 (4h)
1. ✅ Adicionar `SupabaseRepository` class
2. ✅ Modificar `processar_edital()` para persist no Supabase
3. ✅ Manter CSV/XLSX como backup
4. ✅ Adicionar try/except para falhas no Supabase
5. ✅ Adicionar campo `versao_auditor = 'V13'`

### Fase 3: Migração de Dados (1h)
1. ✅ Script `migrar_csv_para_supabase.py`
2. ✅ Importar 198 editais existentes
3. ✅ Validar integridade (checksums)

### Fase 4: Modificar Miner V9 → V10 (2h)
1. ✅ Adicionar logging de execuções no Supabase
2. ✅ Salvar métricas em `execucoes_miner`
3. ✅ Manter checkpoint local + snapshot no DB

### Fase 5: GitHub Setup (1h)
1. ✅ Criar repositório privado
2. ✅ Adicionar `.gitignore` (PDFs, .env, checkpoints)
3. ✅ Commit inicial com código V13
4. ✅ Criar `README.md` principal
5. ✅ Configurar GitHub Actions (opcional - CI/CD)

### Fase 6: Dashboard Supabase (2h - OPCIONAL)
1. ✅ Criar views no Supabase
2. ✅ Configurar API pública (somente leitura)
3. ✅ Criar dashboard básico (Supabase UI)

---

## 📁 ESTRUTURA DO PROJETO (Após Integração)

```
ache-sucatas-daas/
├── .git/                           # Git (versionamento)
├── .github/
│   └── workflows/
│       └── ci.yml                  # GitHub Actions (CI/CD)
├── src/
│   ├── miner/
│   │   └── ache_sucatas_miner_v10.py
│   ├── auditor/
│   │   └── local_auditor_v13.py
│   ├── database/
│   │   ├── schemas.sql
│   │   ├── supabase_client.py
│   │   └── migrations/
│   └── utils/
│       ├── checkpoint.py
│       └── metrics.py
├── scripts/
│   ├── migrar_csv_para_supabase.py
│   ├── backup_db.py
│   └── reprocessar_editais.py
├── data/                           # Cache local (opcional)
│   ├── ACHE_SUCATAS_DB/           # PDFs + JSON
│   ├── .ache_sucatas_checkpoint.json
│   └── backups/
├── docs/
│   ├── README.md
│   ├── ARQUITETURA.md
│   ├── API_REFERENCE.md
│   └── DEPLOYMENT.md
├── tests/
│   ├── test_miner.py
│   ├── test_auditor.py
│   └── test_supabase.py
├── .env.example                    # Template de configuração
├── .gitignore
├── requirements.txt
└── README.md
```

---

## 🔐 VARIÁVEIS DE AMBIENTE (.env)

```bash
# Supabase
SUPABASE_URL=https://seu-projeto.supabase.co
SUPABASE_KEY=sua-service-key-aqui
SUPABASE_SERVICE_KEY=sua-service-key-aqui  # Admin key

# PNCP API
PNCP_BASE_URL=https://pncp.gov.br/api/consulta/v1
PNCP_ARQUIVOS_URL=https://pncp.gov.br/pncp-api/v1

# Diretórios
DOWNLOAD_DIR=./data/ACHE_SUCATAS_DB
LOG_DIR=./logs

# Limites
MAX_PAGES_PDF=50
MAX_RESULTS_PER_PAGE=500
REQUEST_TIMEOUT=30

# Features
ENABLE_SUPABASE=true               # Feature flag
ENABLE_LOCAL_BACKUP=true           # Manter CSV/XLSX
ENABLE_PDF_CACHE=true              # Cache de PDFs local

# Cron (V10 Miner)
CRON_MODE=true
JANELA_TEMPORAL_HORAS=24
PAGE_LIMIT=3
MAX_DOWNLOADS=200
```

---

## 🎯 BENEFÍCIOS DA INTEGRAÇÃO

### 1. **Centralização de Dados**
- ✅ Dados em PostgreSQL cloud (Supabase)
- ✅ API REST automática para consultas
- ✅ Backup automático diário

### 2. **Escalabilidade**
- ✅ Suporta milhares de editais
- ✅ Queries SQL otimizadas
- ✅ Índices para performance

### 3. **Colaboração**
- ✅ GitHub para versionamento
- ✅ Múltiplos desenvolvedores
- ✅ Code review via Pull Requests

### 4. **Observabilidade**
- ✅ Logs de execuções no DB
- ✅ Métricas agregadas diárias
- ✅ Dashboard Supabase

### 5. **Segurança**
- ✅ Credenciais via .env (não commitadas)
- ✅ RLS (Row Level Security) no Supabase
- ✅ Repositório privado no GitHub

---

## ⚠️ CONSIDERAÇÕES

### Custos
- **Supabase**: Gratuito até 500MB + 2GB bandwidth/mês
- **GitHub**: Gratuito (repositório privado)

### Backup Strategy
- **Dual Storage**: Supabase (primário) + CSV/XLSX (backup)
- **Checkpoint Local**: Mantido para recovery rápido
- **Git**: Código versionado

### Rollback Plan
- ✅ Manter CSV/XLSX funcionais (backward compatibility)
- ✅ Feature flag `ENABLE_SUPABASE` para desabilitar
- ✅ Código V12 preservado (antes da integração)

---

## 📊 CRONOGRAMA

| Fase | Atividade | Tempo | Status |
|------|-----------|-------|--------|
| 1 | Setup Supabase | 2h | 🟡 Aguardando autorização |
| 2 | Auditor V12 → V13 | 4h | 🟡 Aguardando |
| 3 | Migração de Dados | 1h | 🟡 Aguardando |
| 4 | Miner V9 → V10 | 2h | 🟡 Aguardando |
| 5 | GitHub Setup | 1h | 🟡 Aguardando |
| 6 | Dashboard (opcional) | 2h | 🟡 Aguardando |
| **TOTAL** | | **12h** | |

---

## ✅ PRÓXIMOS PASSOS

### Você Precisa:
1. ✅ **Criar projeto no Supabase** (5 min)
   - Ir para: https://supabase.com/dashboard
   - Clicar em "New Project"
   - Copiar URL + Service Key

2. ✅ **Criar repositório no GitHub** (5 min)
   - Ir para: https://github.com/new
   - Nome: `ache-sucatas-daas` (privado)
   - Copiar URL do repo

3. ✅ **Fornecer Credenciais**
   - `SUPABASE_URL`
   - `SUPABASE_SERVICE_KEY`
   - `GITHUB_REPO_URL` (opcional - posso inicializar localmente)

### Eu Farei:
1. ✅ Criar schemas SQL no Supabase
2. ✅ Modificar código V12 → V13
3. ✅ Migrar 198 editais para Supabase
4. ✅ Configurar GitHub
5. ✅ Testar integração completa
6. ✅ Documentar tudo

---

## 🎯 RESULTADO FINAL

### Sistema Integrado V13:
```
Miner V10 (Cron 3x/dia)
    ↓
ACHE_SUCATAS_DB/ (Cache)
    ↓
Auditor V13
    ↓
┌─────────────┬──────────────┐
│  Supabase   │  CSV/XLSX    │
│  (Primary)  │  (Backup)    │
└─────────────┴──────────────┘
    ↓
Dashboard + API REST
```

### Funcionalidades:
- ✅ Dados centralizados (Supabase)
- ✅ Backup local (CSV/XLSX)
- ✅ Versionamento (GitHub)
- ✅ API REST automática
- ✅ Dashboard de visualização
- ✅ Logs de execuções
- ✅ Métricas agregadas

---

**Posso começar assim que você fornecer as credenciais do Supabase!** 🚀

Quer que eu:
1. Espere você criar o projeto Supabase e fornecer credenciais?
2. Ou vamos direto para GitHub setup (sem Supabase por enquanto)?
3. Ou prefere manter a stack atual (file-based)?
