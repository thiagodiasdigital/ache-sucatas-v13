# CLAUDE.md - Contexto do Projeto ACHE SUCATAS

> **Ultima atualizacao:** 2026-01-17 13:05 UTC
> **Versao atual:** V11 (Cloud-Native) + Auditor V14.1 + CI
> **Status:** 100% Operacional na Nuvem com CI/CD
> **Seguranca:** Auditada e Corrigida (16/01/2026)

---

## Indice

1. [Visao Geral](#visao-geral)
2. [Escopo do Projeto](#escopo-do-projeto)
3. [Arquitetura](#arquitetura)
4. [Arquivos do Projeto](#arquivos-do-projeto)
5. [Estrutura de Pastas](#estrutura-de-pastas)
6. [Variaveis de Ambiente](#variaveis-de-ambiente)
7. [Seguranca](#seguranca)
8. [Banco de Dados (Supabase)](#banco-de-dados-supabase)
9. [GitHub Actions](#github-actions)
10. [CI - Integracao Continua](#ci---integracao-continua)
11. [Testes Unitarios](#testes-unitarios)
12. [Sistema de Notificacoes](#sistema-de-notificacoes)
13. [API PNCP](#api-pncp)
14. [Comandos Uteis](#comandos-uteis)
15. [Troubleshooting](#troubleshooting)
16. [Roadmap](#roadmap)
17. [Historico de Commits](#historico-de-commits)
18. [Checklist para Nova Sessao](#checklist-para-nova-sessao)

---

## Visao Geral

**ACHE SUCATAS DaaS** (Data as a Service) - Sistema automatizado de coleta e analise de editais de leilao publico do Brasil.

### O que o sistema faz

1. **Coleta** - Busca editais de leilao na API PNCP (Portal Nacional de Contratacoes Publicas)
2. **Download** - Baixa PDFs dos editais para Supabase Storage (nuvem)
3. **Extracao** - Extrai informacoes estruturadas dos PDFs (titulo, data, valores, itens, leiloeiro)
4. **Persistencia** - Armazena metadados no Supabase PostgreSQL
5. **Automacao** - Executa 3x/dia via GitHub Actions (sem necessidade de PC local)
6. **Notificacao** - Envia email automatico quando o workflow falha
7. **Validacao** - CI automatico com lint e testes em cada push/PR

### Metricas Atuais

| Metrica | Valor |
|---------|-------|
| Editais no banco (PostgreSQL) | 26 |
| Editais no Storage (PDFs) | 20 |
| Workflows de coleta executados | 3 (100% sucesso) |
| Workflows de CI executados | 4 (100% sucesso) |
| Ultima execucao coleta | 2026-01-17 08:17 UTC |
| Ultima execucao CI | 2026-01-17 12:59 UTC |
| Tempo medio coleta | ~2 minutos |
| Tempo medio CI | ~30 segundos |
| Testes unitarios | 98 (100% passando) |
| Notificacoes configuradas | Email (Gmail SMTP) |

### Funcionalidades Implementadas

| Funcionalidade | Status | Data |
|----------------|--------|------|
| Coleta automatica de editais | Operacional | 2026-01-16 |
| Upload para Supabase Storage | Operacional | 2026-01-16 |
| Persistencia no PostgreSQL | Operacional | 2026-01-16 |
| Extracao de dados dos PDFs | Operacional | 2026-01-16 |
| Execucao agendada 3x/dia | Operacional | 2026-01-16 |
| Notificacao de falha por email | Operacional | 2026-01-17 |
| Pre-commit hook de seguranca | Operacional | 2026-01-16 |
| CI com ruff (linting) | Operacional | 2026-01-17 |
| CI com pytest (98 testes) | Operacional | 2026-01-17 |
| Sincronizacao Storage-Banco | Operacional | 2026-01-17 |
| Auditor com storage_path | Operacional | 2026-01-17 |

---

## Escopo do Projeto

### Objetivo de Negocio

Criar um banco de dados estruturado de **leiloes publicos** do Brasil, focando em:
- Veiculos e maquinas agricolas inserviveis
- Sucatas de veiculos
- Bens moveis de orgaos publicos

### Publico-Alvo

- Centro de desmanche automotivo
- Compradores de leiloes publicos
- Auto pecas usadas

### Fontes de Dados

| Fonte | Tipo | Uso |
|-------|------|-----|
| API PNCP | REST API | Metadados dos editais (titulo, orgao, datas, links) |
| PDFs dos Editais | Documentos | Detalhes extraidos (itens, valores, leiloeiro) |

### Filtros de Coleta

- **Modalidade:** Leilao (modalidadeId=8)
- **Janela temporal:** Ultimas 24 horas
- **Score minimo:** 30 pontos (relevancia)

### Fora do Escopo (por enquanto)

- Leiloes de imoveis
- Integracao com sistemas de leiloeiros

---

## Arquitetura

### Arquitetura V11 - 100% Cloud + CI (ATUAL)

```
+-----------------------------------------------------------+
|                    GITHUB ACTIONS                          |
+-----------------------------------------------------------+
|                                                           |
|  WORKFLOW 1: ache-sucatas.yml (Coleta - 3x/dia)          |
|  +---------+    +----------+    +--------+    +--------+ |
|  | Miner   |--->| Auditor  |--->| Verify |--->| Notify | |
|  | V11     |    | V14      |    |        |    |(falha) | |
|  +---------+    +----------+    +--------+    +--------+ |
|       |              |                                    |
|       v              v                                    |
|  +---------------------------+                            |
|  |        SUPABASE           |                            |
|  |  +----------+ +--------+  |                            |
|  |  | Storage  | |PostgreSQL| |                            |
|  |  | (PDFs)   | |(metadata)| |                            |
|  |  +----------+ +--------+  |                            |
|  +---------------------------+                            |
|                                                           |
|  WORKFLOW 2: ci.yml (CI - Push/PR)                       |
|  +--------+    +--------+                                 |
|  | Lint   |    | Test   |                                 |
|  | (ruff) |    |(pytest)|                                 |
|  | ~8s    |    | ~32s   |                                 |
|  +--------+    +--------+                                 |
|                                                           |
+-----------------------------------------------------------+
```

### Fluxo Completo de Execucao (Coleta)

```
TRIGGER (Cron 3x/dia ou Manual)
           |
           v
+----------------------+
| Job 1: MINER V11     |
| - Conecta Supabase   |
| - Busca API PNCP     |
| - Filtra editais     |
| - Download PDFs      |
| - Upload Storage     |
| - Insert PostgreSQL  |
+----------+-----------+
           |
           | (needs: miner)
           v
+----------------------+
| Job 2: AUDITOR V14   |
| - Query pendentes    |
| - Download do Storage|
| - Extrai com         |
|   pdfplumber         |
| - Update PostgreSQL  |
+----------+-----------+
           |
           | (needs: miner, auditor)
           v
+----------------------+
| Job 3: VERIFY        |
| - Conta editais      |
| - Gera summary       |
+----------+-----------+
           |
           | (if: failure())
           v
+----------------------+
| Job 4: NOTIFY        |
| - Envia email Gmail  |
| - SMTP porta 465     |
| - SSL/TLS            |
+----------------------+
```

### Fluxo de CI (Validacao)

```
TRIGGER (Push ou PR para master)
           |
           v
+----------------------+     +----------------------+
| Job 1: LINT          |     | Job 2: TEST          |
| - Checkout           |     | - Checkout           |
| - Setup Python 3.11  |     | - Setup Python 3.11  |
| - Install ruff       |     | - Install deps       |
| - ruff check .       |     | - pytest tests/ -v   |
| Tempo: ~8s           |     | Tempo: ~32s          |
+----------------------+     +----------------------+
           |                           |
           +-------------+-------------+
                         |
                         v
                   [CI PASSOU]
```

### Fluxo Detalhado do Miner V11

```
1. Inicializacao
   |-- Carrega variaveis de ambiente (.env ou GitHub Secrets)
   |-- Conecta ao Supabase (PostgreSQL + Storage)
   |-- Carrega checkpoint de deduplicacao

2. Coleta de Editais
   |-- Define janela temporal (JANELA_TEMPORAL_HORAS=24)
   |-- Busca na API PNCP com filtros:
   |   |-- modalidadeId=8 (leilao)
   |   |-- dataPublicacaoInicio/Fim (janela 24h)
   |   |-- tamanhoPagina=500
   |-- Para cada edital encontrado:
       |-- Calcula score de relevancia
       |-- Se score >= MIN_SCORE (30):
           |-- Busca arquivos do edital na API
           |-- Download do PDF em memoria (bytes)
           |-- Upload para Supabase Storage
           |-- Upload metadados.json para Storage
           |-- Insert no PostgreSQL (com validacao UF)
           |-- Atualiza checkpoint

3. Finalizacao
   |-- Registra execucao em `execucoes_miner`
   |-- Salva checkpoint local
   |-- Gera metricas (ache_sucatas_metrics.jsonl)
```

### Fluxo Detalhado do Auditor V14

```
1. Inicializacao
   |-- Conecta ao Supabase (PostgreSQL + Storage)
   |-- Query editais pendentes (processado_auditor = false)

2. Processamento
   |-- Para cada edital pendente:
       |-- Download PDF do Storage -> BytesIO
       |-- pdfplumber.open(BytesIO) -> extrai texto
       |-- Aplica funcoes de extracao V13:
           |-- extrair_data_leilao()
           |-- extrair_valor_estimado()
           |-- extrair_quantidade_itens()
           |-- extrair_nome_leiloeiro()
           |-- extrair_link_leiloeiro()
           |-- extrair_descricao()
       |-- Calcula score de qualidade
       |-- Update no PostgreSQL com dados extraidos
       |-- Marca processado_auditor = true

3. Finalizacao
   |-- Gera CSV de resultados (analise_editais_v14.csv)
   |-- Log de estatisticas
```

### Fluxo de Notificacao de Falha

```
1. Condicao de Disparo
   |-- Job miner falhou (result == 'failure')
   |-- OU Job auditor falhou (result == 'failure')

2. Envio de Email
   |-- Servidor: smtp.gmail.com
   |-- Porta: 465 (SSL/TLS)
   |-- Autenticacao: EMAIL_ADDRESS + EMAIL_APP_PASSWORD
   |-- Destinatario: thiagodias180986@gmail.com

3. Conteudo do Email
   |-- Assunto: "ACHE SUCATAS - Workflow Falhou"
   |-- Corpo:
       |-- Status de cada job (miner, auditor)
       |-- Link direto para os logs no GitHub
       |-- Repositorio e branch
       |-- Data/hora da falha
```

### Diagrama de Dependencias (Scripts)

```
ache_sucatas_miner_v11.py
    |-- supabase_repository.py (PostgreSQL)
    |-- supabase_storage.py (Storage)
    |-- python-dotenv (variaveis)
    |-- requests (API PNCP)
    |-- pydantic (validacao)

cloud_auditor_v14.py
    |-- supabase_repository.py (PostgreSQL)
    |-- supabase_storage.py (Storage)
    |-- pdfplumber (parsing PDF)
    |-- funcoes de extracao (inline)

supabase_repository.py
    |-- supabase-py (cliente oficial)
    |-- python-dotenv

supabase_storage.py
    |-- supabase-py (cliente oficial)
    |-- python-dotenv

tests/
    |-- test_auditor_extraction.py
    |   |-- cloud_auditor_v14.py (funcoes puras)
    |-- test_miner_scoring.py
    |   |-- ache_sucatas_miner_v11.py (ScoringEngine, FileTypeDetector)
    |-- test_repository_parsing.py
        |-- supabase_repository.py (metodos _parse_*)

.github/workflows/ache-sucatas.yml
    |-- dawidd6/action-send-mail@v3 (envio email)
    |-- actions/checkout@v4
    |-- actions/setup-python@v5
    |-- actions/upload-artifact@v4

.github/workflows/ci.yml
    |-- actions/checkout@v4
    |-- actions/setup-python@v5
    |-- ruff (linting)
    |-- pytest (testes)
```

---

## Arquivos do Projeto

### Scripts de Producao (V11/V14 - Cloud) - ATIVOS

| Arquivo | Linhas | Funcao | Dependencias |
|---------|--------|--------|--------------|
| `ache_sucatas_miner_v11.py` | ~800 | Coleta editais, upload Storage, insert PostgreSQL | supabase, requests, pydantic |
| `cloud_auditor_v14.py` | ~650 | Processa PDFs do Storage, extrai dados (V14.1 com storage_path) | supabase, pdfplumber |
| `supabase_repository.py` | ~300 | Repositorio PostgreSQL (CRUD editais) | supabase |
| `supabase_storage.py` | ~240 | Repositorio Storage (upload/download PDFs, listar_pdfs_por_storage_path) | supabase |
| `sincronizar_storage_banco.py` | ~280 | Sincroniza PDFs do Storage com registros no banco | supabase, requests |

### Scripts de Migracao

| Arquivo | Funcao |
|---------|--------|
| `migrar_schema_v11_storage.sql` | SQL para adicionar colunas storage_path, processado_auditor, score |
| `schemas_v13_supabase.sql` | Schema completo das tabelas PostgreSQL |

### Testes Unitarios

| Arquivo | Testes | Funcao | Cobertura |
|---------|--------|--------|-----------|
| `tests/test_auditor_extraction.py` | 53 | Testa funcoes de extracao do cloud_auditor_v14 | corrigir_encoding, limpar_texto, formatar_data_br, formatar_valor_br, extrair_urls_de_texto, normalizar_url, extrair_valor_estimado, extrair_quantidade_itens, extrair_nome_leiloeiro, extrair_data_leilao_cascata |
| `tests/test_miner_scoring.py` | 19 | Testa ScoringEngine e FileTypeDetector | calculate_score, detect_by_content_type, detect_by_magic_bytes |
| `tests/test_repository_parsing.py` | 26 | Testa metodos de parsing do supabase_repository | _parse_valor, _parse_int, _parse_data, _parse_datetime |
| `tests/conftest.py` | - | Configuracao e fixtures do pytest | sys.path setup |
| `tests/__init__.py` | - | Inicializacao do pacote de testes | - |

### Configuracao de CI/Linting

| Arquivo | Linhas | Funcao |
|---------|--------|--------|
| `ruff.toml` | 60 | Configuracao do linter ruff (Python 3.11, regras E/F/W, exclusoes) |
| `pytest.ini` | 8 | Configuracao do pytest (testpaths, addopts) |
| `.github/workflows/ci.yml` | 75 | Workflow de CI (lint + test) |

### Scripts de Seguranca

| Arquivo | Funcao | Quando usar |
|---------|--------|-------------|
| `rotacionar_credenciais.py` | Guia interativo para rotacionar credenciais | Apos vazamento ou periodicamente |
| `instalar_hooks_seguranca.py` | Instala pre-commit hook | Uma vez por clone |
| `.githooks/pre-commit` | Bloqueia commits com secrets | Automatico |
| `desligar_supabase.py` | KILL SWITCH - desativa Supabase | EMERGENCIA |
| `reativar_supabase.py` | Reativa Supabase | Apos emergencia resolvida |
| `monitorar_uso_supabase.py` | Monitor de uso com alertas | Debug/monitoramento |

### Scripts de Configuracao

| Arquivo | Funcao |
|---------|--------|
| `.env` | Credenciais locais (NUNCA versionar!) |
| `.env.example` | Template de credenciais (82 linhas, documentado) |
| `requirements.txt` | Dependencias Python (9 pacotes) |
| `schemas_v13_supabase.sql` | Schema das tabelas PostgreSQL |
| `.gitignore` | Protecoes (96 linhas, reforcado com pytest/ruff) |

### GitHub Actions

| Arquivo | Linhas | Funcao | Trigger |
|---------|--------|--------|---------|
| `.github/workflows/ache-sucatas.yml` | 247 | Workflow principal de coleta (4 jobs) | Cron 3x/dia, manual |
| `.github/workflows/ci.yml` | 75 | Workflow de CI (lint + test) | Push/PR para master |

### Scripts Legados (NAO USAR em producao)

| Arquivo | Versao | Status |
|---------|--------|--------|
| `ache_sucatas_miner_v10.py` | V10 | Legado (backup local) |
| `ache_sucatas_miner_v9_cron.py` | V9 | Descontinuado |
| `local_auditor_v13.py` | V13 | Legado (le PDFs locais) |
| `local_auditor_v12*.py` | V12 | Descontinuado |
| `migrar_v13_robusto.py` | - | Migracao em lote (nao usado) |

### Arvore de Arquivos (Raiz)

```
testes-12-01-17h/
|
|-- .github/
|   +-- workflows/
|       |-- ache-sucatas.yml           # Workflow de coleta (247 linhas)
|       +-- ci.yml                     # Workflow de CI (75 linhas)
|
|-- .githooks/
|   +-- pre-commit                     # Hook de seguranca
|
|-- tests/                             # NOVO - Testes unitarios
|   |-- __init__.py                    # Pacote de testes
|   |-- conftest.py                    # Configuracao pytest
|   |-- test_auditor_extraction.py     # 53 testes - funcoes de extracao
|   |-- test_miner_scoring.py          # 19 testes - scoring e deteccao
|   +-- test_repository_parsing.py     # 26 testes - parsing de dados
|
|-- ache_sucatas_miner_v11.py          # PRODUCAO - Miner cloud
|-- cloud_auditor_v14.py               # PRODUCAO - Auditor cloud
|-- supabase_repository.py             # PRODUCAO - Repo PostgreSQL
|-- supabase_storage.py                # PRODUCAO - Repo Storage
|
|-- ruff.toml                          # NOVO - Config linter
|-- pytest.ini                         # NOVO - Config pytest
|
|-- rotacionar_credenciais.py          # Seguranca
|-- instalar_hooks_seguranca.py        # Seguranca
|-- desligar_supabase.py               # Emergencia
|-- reativar_supabase.py               # Emergencia
|-- monitorar_uso_supabase.py          # Monitoramento
|
|-- .env                               # CREDENCIAIS (gitignore)
|-- .env.example                       # Template documentado
|-- .gitignore                         # 96 linhas de protecao
|-- CLAUDE.md                          # Este arquivo
|-- requirements.txt                   # Dependencias Python
|-- schemas_v13_supabase.sql           # Schema SQL
|
|-- ache_sucatas_miner_v10.py          # Legado
|-- local_auditor_v13.py               # Legado
+-- [outros scripts legados...]
```

---

## Estrutura de Pastas

### Estrutura Local

```
testes-12-01-17h/
|
|-- .github/
|   +-- workflows/
|       |-- ache-sucatas.yml           # Workflow de coleta
|       +-- ci.yml                     # Workflow de CI
|
|-- .githooks/
|   +-- pre-commit                     # Hook de seguranca
|
|-- tests/                             # Testes unitarios (98 testes)
|   |-- __init__.py
|   |-- conftest.py
|   |-- test_auditor_extraction.py
|   |-- test_miner_scoring.py
|   +-- test_repository_parsing.py
|
|-- antes-dia-15-01-26/                # Backup de versoes antigas (gitignore)
|   |-- mineradores_com_resultados/
|   |-- backups/
|   +-- THIAGO_V6/
|
|-- ACHE_SUCATAS_DB/                   # PDFs locais legados (gitignore)
|   |-- AL_MACEIO/
|   |-- BA_SALVADOR/
|   +-- [outras UFs]/
|
|-- logs/                              # Logs de execucao (gitignore)
|
|-- .env                               # CREDENCIAIS (gitignore)
|-- .env.example                       # Template documentado
|-- .gitignore                         # 96 linhas de protecao
|-- CLAUDE.md                          # Este arquivo
|-- requirements.txt                   # Dependencias Python
|-- schemas_v13_supabase.sql           # Schema SQL
|-- ruff.toml                          # Config linter
|-- pytest.ini                         # Config pytest
|
|-- [scripts *.py]                     # Scripts do projeto
+-- [arquivos gerados *.csv, *.xlsx]   # Outputs (gitignore)
```

### Estrutura no Supabase Storage

```
Bucket: editais-pdfs (privado)
|
|-- 18188243000160-1-000161-2025/      # Pasta por pncp_id
|   |-- metadados.json                 # Metadados do edital
|   |-- edital_a1b2c3d4.pdf            # PDF principal
|   +-- anexo_e5f6g7h8.xlsx            # Anexos (se houver)
|
|-- 00394460005887-1-000072-2025/
|   +-- ...
|
+-- [20 editais armazenados]
```

### Estrutura no Supabase PostgreSQL

```
Schema: public
|
|-- editais_leilao                     # Tabela principal (26 registros)
|-- execucoes_miner                    # Log de execucoes
+-- metricas_diarias                   # Metricas agregadas
```

---

## Variaveis de Ambiente

### Arquivo .env (Local - NUNCA COMMITAR)

```env
# ============================================
# SUPABASE (OBRIGATORIO - CONFIDENCIAL)
# ============================================
SUPABASE_URL=https://SEU_PROJETO.supabase.co
SUPABASE_SERVICE_KEY=sua_service_key_aqui
SUPABASE_DB_PASSWORD=sua_senha_do_banco_aqui

# ============================================
# PNCP API (PUBLICO - nao precisa alterar)
# ============================================
PNCP_BASE_URL=https://pncp.gov.br/api/consulta/v1
PNCP_ARQUIVOS_URL=https://pncp.gov.br/pncp-api/v1

# ============================================
# DIRETORIOS LOCAIS
# ============================================
DOWNLOAD_DIR=./ACHE_SUCATAS_DB
LOG_DIR=./logs
BACKUP_DIR=./backups

# ============================================
# LIMITES
# ============================================
MAX_PAGES_PDF=50
MAX_RESULTS_PER_PAGE=500
REQUEST_TIMEOUT=30

# ============================================
# FEATURE FLAGS
# ============================================
ENABLE_SUPABASE=true
ENABLE_SUPABASE_STORAGE=true
SUPABASE_STORAGE_BUCKET=editais-pdfs
MAX_EDITAIS_SUPABASE=10000
ENABLE_LOCAL_BACKUP=false
ENABLE_PDF_CACHE=false
DEBUG=false

# ============================================
# CRON (MINER V11)
# ============================================
CRON_MODE=true
JANELA_TEMPORAL_HORAS=24
PAGE_LIMIT=3
MAX_DOWNLOADS=200

# ============================================
# SEGURANCA
# ============================================
ENABLE_AUDIT_LOG=true
ENABLE_FILE_VERIFICATION=true
```

### GitHub Secrets (Configurados)

| Secret | Descricao | Ultima Atualizacao |
|--------|-----------|-------------------|
| `SUPABASE_URL` | URL do projeto Supabase | 2026-01-16 21:21 UTC |
| `SUPABASE_SERVICE_KEY` | Service role key (ROTACIONADA) | 2026-01-16 22:41 UTC |
| `EMAIL_ADDRESS` | Email Gmail para notificacoes | 2026-01-16 23:41 UTC |
| `EMAIL_APP_PASSWORD` | App Password do Gmail (16 chars) | 2026-01-16 23:43 UTC |

### Como Verificar Secrets Configurados

```bash
# Listar todos os secrets
gh secret list

# Resultado esperado (4 secrets):
# EMAIL_ADDRESS         2026-01-16T23:41:58Z
# EMAIL_APP_PASSWORD    2026-01-16T23:43:24Z
# SUPABASE_SERVICE_KEY  2026-01-16T22:41:56Z
# SUPABASE_URL          2026-01-16T21:21:31Z
```

### Como Configurar GitHub Secrets

```bash
# Via GitHub CLI (requer autenticacao)

# 1. Supabase URL
gh secret set SUPABASE_URL
# Cole: https://xxx.supabase.co

# 2. Supabase Service Key
gh secret set SUPABASE_SERVICE_KEY
# Cole: eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...

# 3. Email para notificacoes
gh secret set EMAIL_ADDRESS
# Cole: seu-email@gmail.com

# 4. App Password do Gmail
gh secret set EMAIL_APP_PASSWORD
# Cole: abcdefghijklmnop (16 caracteres, sem espacos)
```

**Se precisar criar nova App Password:**
- Acesse https://myaccount.google.com/apppasswords
- Delete a antiga (ACHE SUCATAS)
- Crie uma nova
- Atualize o secret no GitHub

---

## Seguranca

### Auditoria Realizada (2026-01-16)

Uma auditoria completa de seguranca foi realizada e todas vulnerabilidades foram corrigidas.

#### Vulnerabilidades Encontradas e Corrigidas

| Severidade | Vulnerabilidade | Arquivo | Status |
|------------|-----------------|---------|--------|
| CRITICA | Senha do banco hardcoded | `executar_schema_postgresql.py` | CORRIGIDA |
| CRITICA | Service key exposta | `CLAUDE.md` (versao antiga) | CORRIGIDA |
| CRITICA | URL do projeto exposta | 7 arquivos | CORRIGIDA |
| ALTA | Credenciais no historico Git | Historico | MITIGADA (rotacao) |

#### Acoes Tomadas

1. **Remocao de credenciais** - 9 arquivos corrigidos manualmente
2. **Rotacao de credenciais** - Service key e senha do banco regeneradas no Supabase
3. **Pre-commit hook** - Bloqueia automaticamente commits com secrets
4. **Scripts de seguranca** - Ferramentas para rotacao e instalacao de hooks
5. **.gitignore reforcado** - 96 linhas com padroes de seguranca

### Pre-commit Hook

O hook `.githooks/pre-commit` bloqueia commits contendo:

| Padrao | Regex | Exemplo Bloqueado |
|--------|-------|-------------------|
| Supabase service key | `SUPABASE_SERVICE_KEY=.+` | SUPABASE_SERVICE_KEY=eyJ... |
| Supabase DB password | `SUPABASE_DB_PASSWORD=.+` | SUPABASE_DB_PASSWORD=senha123 |
| Supabase secret prefix | `sb_secret_[a-zA-Z0-9_-]+` | sb_secret_abc123 |
| PostgreSQL URL com senha | `postgresql://.*:.*@.*supabase` | postgresql://user:pass@xxx.supabase.co |
| JWT tokens | `eyJ[a-zA-Z0-9_-]{20,}` | eyJhbGciOiJIUzI1NiIsInR5... |
| Senhas em strings | `password.*=.*['\"][^'\"]{4,}['\"]` | password = "minhasenha" |
| Secrets em strings | `secret.*=.*['\"][^'\"]{4,}['\"]` | secret_key = "abc123" |
| API keys em strings | `api_key.*=.*['\"][^'\"]{4,}['\"]` | api_key = "xyz789" |

**Arquivos ignorados pelo hook:**
- `.env.example` (usa placeholders)
- `rotacionar_credenciais.py` (documentacao)
- `.githooks/pre-commit` (auto-referencia)

### Protecoes Ativas

| Protecao | Descricao | Status |
|----------|-----------|--------|
| Pre-commit hook | Detecta secrets antes do commit | ATIVO |
| .gitignore | Bloqueia .env, *.key, *.pem, etc | ATIVO |
| GitHub Secrets | Credenciais em secrets, nao no codigo | ATIVO |
| Service role key | Rotacionada em 2026-01-16 22:41 UTC | ATIVO |
| RLS (Row Level Security) | Ativo em todas as tabelas Supabase | ATIVO |
| Feature flags | ENABLE_SUPABASE pode desativar integracao | ATIVO |
| Kill switch | `desligar_supabase.py` disponivel | DISPONIVEL |
| Notificacao de falha | Email quando workflow falha | ATIVO |
| CI automatico | Valida codigo em cada push/PR | ATIVO |

### Como Rotacionar Credenciais

```bash
# 1. Gere novas credenciais no Dashboard do Supabase
#    - Settings -> API -> Regenerate service_role key
#    - Settings -> Database -> Reset database password

# 2. Execute o script de rotacao (guia interativo)
python rotacionar_credenciais.py

# 3. Atualize os GitHub Secrets
gh secret set SUPABASE_SERVICE_KEY
# Cole a nova chave e pressione Enter

# 4. Atualize o .env local
# Edite manualmente o arquivo .env
```

### Como Instalar Hooks de Seguranca

```bash
# Executar uma vez apos clonar o repositorio
python instalar_hooks_seguranca.py

# Verificar se foi instalado
git config core.hooksPath
# Deve retornar: .githooks
```

### Freios de Seguranca (Custos)

| Protecao | Limite | Proposito |
|----------|--------|-----------|
| MAX_EDITAIS_SUPABASE | 10.000 registros | Evitar estouro do free tier |
| Custo maximo aprovado | $50 USD | Budget definido |
| ENABLE_SUPABASE | true/false | Desativar integracao |
| ENABLE_SUPABASE_STORAGE | true/false | Desativar Storage |
| MIN_SCORE_TO_DOWNLOAD | 30 | So baixa editais relevantes |
| Kill switch | `desligar_supabase.py` | Desliga tudo imediatamente |

### Estimativa de Custos Atual

| Servico | Free Tier | Uso Atual | % Usado |
|---------|-----------|-----------|---------|
| Supabase DB | 500 MB | ~5 MB | 1% |
| Supabase Storage | 1 GB | ~50 MB | 5% |
| GitHub Actions | 2000 min/mes | ~180 min/mes | 9% |
| Gmail SMTP | Ilimitado | ~0 emails/mes | 0% |
| **TOTAL** | - | - | **$0/mes** |

---

## Banco de Dados (Supabase)

### Tabela: editais_leilao

Tabela principal com os editais coletados.

| Campo | Tipo | Constraints | Descricao |
|-------|------|-------------|-----------|
| id | SERIAL | PK, AUTO | ID auto-incremento |
| pncp_id | TEXT | UNIQUE, NOT NULL | ID unico do PNCP (ex: 18188243000160-1-000161-2025) |
| titulo | TEXT | | Titulo do edital |
| orgao | TEXT | | Orgao responsavel (prefeitura) |
| municipio | TEXT | | Nome da cidade |
| uf | CHAR(2) | CHECK (lista UFs) | Estado (XX = invalido) |
| data_publicacao | TIMESTAMP | | Data de publicacao no PNCP |
| data_leilao | TIMESTAMP | | Data do leilao (extraida do PDF) |
| valor_estimado | DECIMAL(15,2) | | Valor estimado total |
| link_pncp | TEXT | | URL do edital no PNCP |
| link_leiloeiro | TEXT | | URL do site do leiloeiro |
| nome_leiloeiro | TEXT | | Nome do leiloeiro oficial |
| quantidade_itens | INTEGER | | Quantidade de itens/lotes |
| descricao | TEXT | | Descricao resumida dos itens |
| score | INTEGER | | Score de qualidade (0-100) |
| storage_path | TEXT | | Caminho no Supabase Storage |
| pdf_storage_url | TEXT | | URL publica do PDF (se habilitado) |
| processado_auditor | BOOLEAN | DEFAULT false | Flag de processamento |
| created_at | TIMESTAMP | DEFAULT now() | Data de criacao |
| updated_at | TIMESTAMP | | Data de ultima atualizacao |

**Indices:**
- `idx_editais_pncp_id` (pncp_id)
- `idx_editais_processado` (processado_auditor)
- `idx_editais_uf` (uf)
- `idx_editais_data_publicacao` (data_publicacao)

**Constraint check_uf:**
```sql
CHECK (uf IN ('AC','AL','AP','AM','BA','CE','DF','ES','GO','MA',
              'MT','MS','MG','PA','PB','PR','PE','PI','RJ','RN',
              'RS','RO','RR','SC','SP','SE','TO','XX'))
```

### Tabela: execucoes_miner

Log de todas as execucoes do Miner.

| Campo | Tipo | Descricao |
|-------|------|-----------|
| id | SERIAL | PK |
| versao_miner | TEXT | Versao (V11_CLOUD) |
| execution_start | TIMESTAMP | Inicio da execucao |
| execution_end | TIMESTAMP | Fim da execucao |
| status | TEXT | RUNNING, SUCCESS, FAILED |
| editais_novos | INTEGER | Novos encontrados |
| downloads | INTEGER | Downloads realizados |
| storage_uploads | INTEGER | Uploads no Storage |
| supabase_inserts | INTEGER | Inserts no banco |
| error_message | TEXT | Mensagem de erro (se falhou) |

### Tabela: metricas_diarias

Metricas agregadas por dia.

| Campo | Tipo | Descricao |
|-------|------|-----------|
| id | SERIAL | PK |
| data | DATE | UNIQUE - Data da metrica |
| total_editais | INTEGER | Total acumulado |
| novos_editais | INTEGER | Novos no dia |
| execucoes | INTEGER | Quantidade de execucoes |

### Bucket: editais-pdfs

Configuracao do Supabase Storage.

| Propriedade | Valor |
|-------------|-------|
| Nome | editais-pdfs |
| Visibilidade | Privado |
| Tamanho maximo arquivo | 50 MB |
| Tipos permitidos | PDF, JSON, XLSX, DOC, DOCX |
| Editais armazenados | 20 |

---

## GitHub Actions

### Visao Geral dos Workflows

| Workflow | Arquivo | Trigger | Jobs | Tempo |
|----------|---------|---------|------|-------|
| Coleta e Processamento | `ache-sucatas.yml` | Cron 3x/dia, manual | 4 (miner, auditor, verify, notify) | ~2 min |
| CI - Lint & Test | `ci.yml` | Push/PR para master | 2 (lint, test) | ~40s |

### Workflow: ache-sucatas.yml (Coleta)

Configuracao completa do workflow de automacao.

**Arquivo:** `.github/workflows/ache-sucatas.yml`
**Linhas:** 247

#### Triggers

| Trigger | Configuracao | Descricao |
|---------|--------------|-----------|
| schedule | `0 0,8,16 * * *` | 3x/dia: 00:00, 08:00, 16:00 UTC |
| workflow_dispatch | manual | Execucao manual com parametros |

**Horarios em BRT (Brasil):**
- 00:00 UTC = 21:00 BRT (dia anterior)
- 08:00 UTC = 05:00 BRT
- 16:00 UTC = 13:00 BRT

#### Inputs (workflow_dispatch)

| Input | Tipo | Default | Descricao |
|-------|------|---------|-----------|
| run_miner | boolean | true | Executar Miner V11 |
| run_auditor | boolean | true | Executar Auditor V14 |
| auditor_limit | number | 0 | Limite de editais (0 = sem limite) |

#### Jobs

| Job | Nome | Depende de | Timeout | Condicao |
|-----|------|------------|---------|----------|
| miner | Miner V11 - Coleta | - | 30 min | Sempre (schedule ou manual) |
| auditor | Auditor V14 - Processamento | miner | 60 min | Miner sucesso ou pulado |
| verify | Verificacao Final | miner, auditor | - | Sempre |
| notify-failure | Notificar Falha por Email | miner, auditor | - | Se algum job falhou |

#### Variaveis de Ambiente (workflow)

```yaml
env:
  SUPABASE_URL: ${{ secrets.SUPABASE_URL }}
  SUPABASE_SERVICE_KEY: ${{ secrets.SUPABASE_SERVICE_KEY }}
  ENABLE_SUPABASE: 'true'
  ENABLE_SUPABASE_STORAGE: 'true'
  ENABLE_LOCAL_BACKUP: 'false'
  PYTHON_VERSION: '3.11'
```

#### Artifacts Gerados

| Artifact | Arquivos | Retencao |
|----------|----------|----------|
| miner-metrics-{N} | ache_sucatas_metrics.jsonl, .ache_sucatas_checkpoint.json | 30 dias |
| auditor-results-{N} | analise_editais_v14.csv | 30 dias |

#### Tempos de Execucao

| Job | Tempo Medio |
|-----|-------------|
| Miner V11 | 41s |
| Auditor V14 | 29s |
| Verificacao | 30s |
| Notificacao | 8s (se falhar) |
| **Total** | ~2 min |

---

## CI - Integracao Continua

### Visao Geral

O CI (Continuous Integration) valida automaticamente o codigo em cada push ou pull request para a branch master.

| Propriedade | Valor |
|-------------|-------|
| Workflow | `.github/workflows/ci.yml` |
| Trigger | Push/PR para master |
| Jobs | 2 (lint, test) |
| Tempo total | ~40 segundos |
| Linter | ruff (Python) |
| Framework de testes | pytest |
| Testes | 98 (100% passando) |

### Workflow: ci.yml

**Arquivo:** `.github/workflows/ci.yml`
**Linhas:** 75

```yaml
name: CI - Lint & Test

on:
  push:
    branches: [master]
  pull_request:
    branches: [master]

env:
  PYTHON_VERSION: '3.11'

jobs:
  lint:
    name: Lint with Ruff
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: ${{ env.PYTHON_VERSION }}
      - run: pip install ruff
      - run: ruff check .

  test:
    name: Unit Tests
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: ${{ env.PYTHON_VERSION }}
          cache: 'pip'
      - run: |
          pip install pytest
          pip install -r requirements.txt
      - run: pytest tests/ -v --tb=short
        env:
          ENABLE_SUPABASE: 'false'
          ENABLE_SUPABASE_STORAGE: 'false'
```

### Jobs do CI

| Job | Nome | Tempo | O que faz |
|-----|------|-------|-----------|
| lint | Lint with Ruff | ~8s | Verifica erros de codigo com ruff |
| test | Unit Tests | ~32s | Executa 98 testes unitarios com pytest |

### Configuracao do Ruff (ruff.toml)

```toml
# Target Python 3.11
target-version = "py311"

# Line length
line-length = 120

# Exclude legacy files
exclude = [
    ".git", ".venv", "venv", "__pycache__",
    "antes-dia-*", "ACHE_SUCATAS_DB", "logs"
]

[lint]
# Rules enabled
select = ["E", "F", "W"]  # pycodestyle, Pyflakes, warnings

# Rules ignored (existing code patterns)
ignore = [
    "E402",  # Import not at top
    "E501",  # Line too long
    "E701",  # Multiple statements on one line
    "E722",  # Bare except
    "E731",  # Lambda assignment
    "F401",  # Import unused
    "F541",  # f-string without placeholders
    "F841",  # Variable unused
    "W291",  # Trailing whitespace
    "W292",  # No newline at end
    "W293",  # Blank line whitespace
    "W605",  # Invalid escape sequence
]

# Per-file ignores for legacy code
[lint.per-file-ignores]
"ache_sucatas_miner_v10.py" = ["E", "F", "W"]
"ache_sucatas_miner_v9*.py" = ["E", "F", "W"]
"ache_sucatas_miner_v8*.py" = ["E", "F", "W"]
"local_auditor_v*.py" = ["E", "F", "W"]
"migrar_*.py" = ["E", "F", "W"]
# ... outros arquivos legados
```

### Configuracao do Pytest (pytest.ini)

```ini
[pytest]
testpaths = tests
python_files = test_*.py
python_classes = Test*
python_functions = test_*
addopts = -v --tb=short
filterwarnings =
    ignore::DeprecationWarning
    ignore::PendingDeprecationWarning
```

### Como Executar CI Localmente

```bash
# Instalar ferramentas
pip install ruff pytest

# Executar linting
ruff check .

# Executar testes
ENABLE_SUPABASE=false pytest tests/ -v

# Verificar formato (desabilitado no CI por enquanto)
ruff format --check .

# Formatar codigo automaticamente
ruff format .
```

---

## Testes Unitarios

### Visao Geral

| Metrica | Valor |
|---------|-------|
| Total de testes | 98 |
| Passando | 98 (100%) |
| Falhando | 0 |
| Tempo de execucao | ~3 segundos |
| Framework | pytest |
| Cobertura | Funcoes puras (sem Supabase) |

### Estrutura de Testes

```
tests/
|-- __init__.py                    # Pacote de testes
|-- conftest.py                    # Configuracao e fixtures
|-- test_auditor_extraction.py     # 53 testes
|-- test_miner_scoring.py          # 19 testes
+-- test_repository_parsing.py     # 26 testes
```

### test_auditor_extraction.py (53 testes)

Testa funcoes de extracao do `cloud_auditor_v14.py`.

| Classe de Teste | Testes | Funcao Testada |
|-----------------|--------|----------------|
| TestCorrigirEncoding | 4 | `corrigir_encoding()` |
| TestLimparTexto | 7 | `limpar_texto()` |
| TestFormatarDataBr | 8 | `formatar_data_br()` |
| TestFormatarValorBr | 6 | `formatar_valor_br()` |
| TestExtrairUrlsDeTexto | 5 | `extrair_urls_de_texto()` |
| TestNormalizarUrl | 6 | `normalizar_url()` |
| TestExtrairValorEstimado | 4 | `extrair_valor_estimado()` |
| TestExtrairQuantidadeItens | 4 | `extrair_quantidade_itens()` |
| TestExtrairNomeLeiloeiro | 3 | `extrair_nome_leiloeiro()` |
| TestExtrairDataLeilaoCascata | 6 | `extrair_data_leilao_cascata()` |

**Exemplo de teste:**
```python
class TestFormatarDataBr:
    def test_iso_format(self):
        assert formatar_data_br("2026-01-15") == "15/01/2026"

    def test_none_returns_nd(self):
        assert formatar_data_br(None) == "N/D"
```

### test_miner_scoring.py (19 testes)

Testa `ScoringEngine` e `FileTypeDetector` do `ache_sucatas_miner_v11.py`.

| Classe de Teste | Testes | Classe/Funcao Testada |
|-----------------|--------|----------------------|
| TestScoringEngine | 8 | `ScoringEngine.calculate_score()` |
| TestFileTypeDetector | 11 | `FileTypeDetector.detect_by_content_type()`, `detect_by_magic_bytes()` |

**Exemplo de teste:**
```python
class TestScoringEngine:
    def test_base_score(self):
        """Empty text should return base score of 50"""
        score = ScoringEngine.calculate_score("", "", "")
        assert score == 50

    def test_positive_keywords_increase_score(self):
        score = ScoringEngine.calculate_score(
            "leilão de veículos",
            "sucata inservível",
            ""
        )
        assert score > 50
```

### test_repository_parsing.py (26 testes)

Testa metodos de parsing do `supabase_repository.py`.

| Classe de Teste | Testes | Metodo Testado |
|-----------------|--------|----------------|
| TestParseValor | 7 | `_parse_valor()` |
| TestParseInt | 6 | `_parse_int()` |
| TestParseData | 6 | `_parse_data()` |
| TestParseDatetime | 5 | `_parse_datetime()` |

**Exemplo de teste:**
```python
class TestParseValor:
    @pytest.fixture
    def repo(self):
        return SupabaseRepository(enable_supabase=False)

    def test_with_currency_symbol(self, repo):
        assert repo._parse_valor("R$ 1.234,56") == 1234.56
```

### Funcoes Testadas (Resumo)

| Arquivo Fonte | Funcoes Testadas | Tipo |
|---------------|------------------|------|
| `cloud_auditor_v14.py` | corrigir_encoding, limpar_texto, formatar_data_br, formatar_valor_br, extrair_urls_de_texto, normalizar_url, extrair_valor_estimado, extrair_quantidade_itens, extrair_nome_leiloeiro, extrair_data_leilao_cascata | Funcoes puras |
| `ache_sucatas_miner_v11.py` | ScoringEngine.calculate_score, FileTypeDetector.detect_by_content_type, FileTypeDetector.detect_by_magic_bytes | Metodos estaticos |
| `supabase_repository.py` | _parse_valor, _parse_int, _parse_data, _parse_datetime | Metodos internos |

### Adicionar Novos Testes

Para adicionar novos testes:

1. Crie um arquivo `tests/test_<modulo>.py`
2. Use a convenção `Test<Classe>` para classes de teste
3. Use a convenção `test_<funcionalidade>` para metodos
4. Execute localmente: `pytest tests/ -v`
5. Push para validar no CI

---

## Sistema de Notificacoes

### Visao Geral

O sistema envia email automaticamente quando qualquer job do workflow falha.

| Propriedade | Valor |
|-------------|-------|
| Tipo | Email via Gmail SMTP |
| Servidor | smtp.gmail.com |
| Porta | 465 (SSL/TLS) |
| Autenticacao | App Password |
| Destinatario | thiagodias180986@gmail.com |
| Trigger | Quando miner OU auditor falha |

### Configuracao Tecnica

```yaml
# Job de notificacao no workflow
notify-failure:
  name: Notificar Falha por Email
  runs-on: ubuntu-latest
  needs: [miner, auditor]
  if: failure()

  steps:
    - name: Send email notification
      uses: dawidd6/action-send-mail@v3
      with:
        server_address: smtp.gmail.com
        server_port: 465
        secure: true
        username: ${{ secrets.EMAIL_ADDRESS }}
        password: ${{ secrets.EMAIL_APP_PASSWORD }}
        subject: "ACHE SUCATAS - Workflow Falhou"
        to: ${{ secrets.EMAIL_ADDRESS }}
        from: ACHE SUCATAS <${{ secrets.EMAIL_ADDRESS }}>
        body: |
          O workflow ACHE SUCATAS falhou!

          Miner V11:   ${{ needs.miner.result }}
          Auditor V14: ${{ needs.auditor.result }}

          Verifique os logs em:
          https://github.com/${{ github.repository }}/actions/runs/${{ github.run_id }}
```

### Formato do Email

**Assunto:**
```
ACHE SUCATAS - Workflow Falhou
```

**Corpo:**
```
O workflow ACHE SUCATAS falhou!

----------------------------------------
DETALHES DA EXECUCAO
----------------------------------------

Repositorio: thiagodiasdigital/ache-sucatas-v13
Branch: master
Commit: abc123...
Evento: schedule

----------------------------------------
STATUS DOS JOBS
----------------------------------------

Miner V11:   failure
Auditor V14: skipped

----------------------------------------
ACAO NECESSARIA
----------------------------------------

Verifique os logs em:
https://github.com/thiagodiasdigital/ache-sucatas-v13/actions/runs/123456789

----------------------------------------
Enviado automaticamente pelo GitHub Actions
```

### Secrets Necessarios

| Secret | Descricao | Como Obter |
|--------|-----------|------------|
| `EMAIL_ADDRESS` | Email Gmail completo | Seu email @gmail.com |
| `EMAIL_APP_PASSWORD` | Senha de app de 16 caracteres | myaccount.google.com/apppasswords |


---

## API PNCP

### Informacoes Gerais

| Propriedade | Valor |
|-------------|-------|
| Base URL (consulta) | https://pncp.gov.br/api/consulta/v1 |
| Base URL (arquivos) | https://pncp.gov.br/pncp-api/v1 |
| Documentacao | https://pncp.gov.br/api/consulta/swagger-ui/index.html |
| Autenticacao | Nenhuma (API publica) |
| Rate Limit | ~100 req/min (estimado, nao documentado) |

### Endpoints Utilizados

#### 1. Listar Editais

```
GET /contratacoes/publicacao
```

| Parametro | Tipo | Exemplo | Descricao |
|-----------|------|---------|-----------|
| modalidadeId | int | 8 | 8 = Leilao |
| dataPublicacaoInicio | date | 2026-01-15 | Data inicio |
| dataPublicacaoFim | date | 2026-01-16 | Data fim |
| pagina | int | 1 | Numero da pagina |
| tamanhoPagina | int | 500 | Itens por pagina (max 500) |

**Resposta:**
```json
{
  "data": [
    {
      "orgaoEntidade": {
        "cnpj": "18188243000160",
        "razaoSocial": "PREFEITURA MUNICIPAL DE ...",
        "uf": "RS"
      },
      "numeroControlePNCP": "18188243000160-1-000161/2025",
      "titulo": "Leilao de veiculos inserviveis",
      "dataPublicacao": "2026-01-16T10:00:00",
      ...
    }
  ],
  "paginacao": {
    "pagina": 1,
    "totalPaginas": 5,
    "totalRegistros": 2345
  }
}
```

#### 2. Listar Arquivos do Edital

```
GET /orgaos/{cnpj}/compras/{ano}/{sequencial}/arquivos
```

**Exemplo:**
```
GET /orgaos/18188243000160/compras/2025/000161/arquivos
```

**Resposta:**
```json
[
  {
    "sequencialDocumento": 1,
    "titulo": "Edital de Leilao",
    "url": "https://pncp.gov.br/pncp-api/v1/orgaos/.../arquivos/1"
  }
]
```

### Rate Limiting

- **Comportamento:** HTTP 429 Too Many Requests
- **Quando ocorre:** Apos ~9 termos de busca consecutivos
- **Mitigacao:** Janela temporal de 24h reduz requisicoes repetidas
- **Tratamento:** Nao e erro critico, sistema continua na proxima execucao

---

## Comandos Uteis

### Execucao Cloud (RECOMENDADO)

```bash
# Disparar workflow de coleta manualmente (todos os jobs)
gh workflow run ache-sucatas.yml

# Disparar apenas Miner
gh workflow run ache-sucatas.yml -f run_auditor=false

# Disparar apenas Auditor (limitar a 5 editais)
gh workflow run ache-sucatas.yml -f run_miner=false -f auditor_limit=5

# Verificar status dos ultimos workflows de coleta
gh run list --workflow=ache-sucatas.yml --limit 5

# Verificar status dos ultimos workflows de CI
gh run list --workflow=ci.yml --limit 5

# Acompanhar execucao em tempo real
gh run watch <RUN_ID>

# Ver logs de uma execucao
gh run view <RUN_ID> --log

# Ver logs de um job especifico
gh run view <RUN_ID> --log --job=<JOB_ID>
```

### CI e Testes

```bash
# Instalar ferramentas de CI
pip install ruff pytest

# Executar linting
ruff check .

# Executar linting com correcao automatica
ruff check . --fix

# Verificar formato
ruff format --check .

# Formatar codigo automaticamente
ruff format .

# Executar testes (sem Supabase)
ENABLE_SUPABASE=false pytest tests/ -v

# Executar testes com saida curta
pytest tests/ --tb=short

# Executar apenas um arquivo de teste
pytest tests/test_auditor_extraction.py -v

# Executar apenas uma classe de teste
pytest tests/test_auditor_extraction.py::TestFormatarDataBr -v

# Executar apenas um teste especifico
pytest tests/test_auditor_extraction.py::TestFormatarDataBr::test_iso_format -v
```

### Execucao Local (Debug/Testes)

```bash
# Miner V11 (requer .env configurado)
python ache_sucatas_miner_v11.py

# Auditor V14 (requer .env configurado)
python cloud_auditor_v14.py

# Auditor com limite
python cloud_auditor_v14.py --limit 5
```

### Verificacao de Status

```bash
# Contar editais no banco
python -c "from supabase_repository import SupabaseRepository; r = SupabaseRepository(); print(f'Editais: {r.contar_editais()}')"

# Contar editais no Storage
python -c "from supabase_storage import SupabaseStorageRepository; s = SupabaseStorageRepository(); print(f'Storage: {len(s.listar_editais())}')"

# Listar ultimas execucoes
python -c "
from supabase_repository import SupabaseRepository
r = SupabaseRepository()
resp = r.client.table('execucoes_miner').select('*').order('execution_start', desc=True).limit(5).execute()
for e in resp.data:
    print(f\"[{e['status']}] {e['versao_miner']} - novos:{e.get('editais_novos', 0)}\")
"

# Testar conexao com Supabase
python -c "from supabase_repository import SupabaseRepository; r = SupabaseRepository(); print('OK' if r.enable_supabase else 'FALHOU')"

# Testar conexao com Storage
python -c "from supabase_storage import SupabaseStorageRepository; s = SupabaseStorageRepository(); print('OK')"
```

### Seguranca

```bash
# Instalar hooks de seguranca (uma vez)
python instalar_hooks_seguranca.py

# Rotacionar credenciais (interativo)
python rotacionar_credenciais.py

# Verificar GitHub Secrets (deve mostrar 4)
gh secret list

# Testar hook manualmente
echo "SUPABASE_SERVICE_KEY=sb_secret_teste" > teste.txt
git add teste.txt
git commit -m "teste"  # Deve ser bloqueado!
rm teste.txt
```

### Git

```bash
# Status
git status

# Ultimos commits
git log --oneline -10

# Push
git push

# Verificar se hook esta ativo
git config core.hooksPath
```

### Notificacoes

```bash
# Verificar se secrets de email estao configurados
gh secret list | grep EMAIL

# Deve mostrar:
# EMAIL_ADDRESS         (data)
# EMAIL_APP_PASSWORD    (data)
```

### EMERGENCIA

```bash
# DESLIGAR TUDO IMEDIATAMENTE
python desligar_supabase.py

# Reativar apos resolver problema
python reativar_supabase.py
```

---

## Troubleshooting

### Problema: Workflow nao executa no horario

```
Sintoma: Cron nao disparou as 00:00 UTC
Causa: GitHub Actions tem delay de ate 15 minutos
Solucao: Normal, aguardar ou disparar manualmente
Comando: gh workflow run ache-sucatas.yml
```

### Problema: Erro de autenticacao no Storage

```
Sintoma: "Invalid API key" no upload
Causa: SUPABASE_SERVICE_KEY incorreta ou expirada
Solucao:
  1. Verificar secret: gh secret list
  2. Rotacionar: python rotacionar_credenciais.py
  3. Atualizar: gh secret set SUPABASE_SERVICE_KEY
```

### Problema: Pre-commit bloqueou meu commit

```
Sintoma: "COMMIT BLOQUEADO: Secrets detectados!"
Causa: Arquivo contem credenciais
Solucao:
  1. Remova as credenciais do arquivo
  2. Use variaveis de ambiente (.env)
  3. Tente commitar novamente
NUNCA: git commit --no-verify (exceto emergencia)
```

### Problema: Miner retorna 0 editais novos

```
Sintoma: "Editais novos: 0" no log
Causa: Todos editais ja estao no checkpoint
Verificar: cat .ache_sucatas_checkpoint.json
Solucao (teste): Deletar checkpoint e re-executar
Solucao (prod): Normal se nao ha editais novos
```

### Problema: Auditor nao processa editais

```
Sintoma: "Nenhum edital pendente"
Causa: Todos editais ja tem processado_auditor=true
Verificar: SELECT COUNT(*) FROM editais_leilao WHERE processado_auditor = false
Solucao: UPDATE editais_leilao SET processado_auditor = false WHERE ...
```

### Problema: Violacao de constraint check_uf

```
Sintoma: new row violates check constraint "check_uf"
Causa: API PNCP retornando UF vazia ou invalida
Solucao: Ja tratado - UF invalida vira "XX"
Commit: 4deadc2 fix: Handle empty/invalid UF values
```

### Problema: Rate limiting da API PNCP

```
Sintoma: API returned status 429 (Too Many Requests)
Causa: Muitas requisicoes em sequencia
Solucao: Nao e critico, sistema continua na proxima execucao
Mitigacao: JANELA_TEMPORAL_HORAS=24 reduz requisicoes
```

### Problema: Bucket nao encontrado no Storage

```
Sintoma: {'statusCode': 404, 'error': 'Bucket not found'}
Causa: Bucket editais-pdfs nao existe
Solucao:
  1. Supabase Dashboard -> Storage -> New bucket
  2. Nome: editais-pdfs
  3. Public: No (privado)
  4. File size limit: 50MB
```


### Problema: Erro SSL ao enviar email

```
Sintoma: ssl3_get_record:wrong version number
Causa: Porta errada (587 em vez de 465)
Solucao: Ja corrigido - workflow usa porta 465 com SSL
Commit: 75548f1 fix: Use SSL port 465 instead of STARTTLS port 587
```

### Problema: CI falhou no lint

```
Sintoma: ruff check . falhou
Causa: Codigo com erros de estilo/sintaxe
Solucao:
  1. Executar localmente: ruff check .
  2. Corrigir erros ou adicionar ao ignore em ruff.toml
  3. Para correcao automatica: ruff check . --fix
```

### Problema: CI falhou nos testes

```
Sintoma: pytest tests/ falhou
Causa: Teste quebrado ou funcao alterada
Solucao:
  1. Executar localmente: pytest tests/ -v
  2. Ver qual teste falhou
  3. Corrigir o teste ou a funcao
  4. Re-executar para validar
```

---

## Roadmap

### Fases Concluidas

| Fase | Descricao | Status | Data |
|------|-----------|--------|------|
| 1 - Coleta | Miner V9 coletando da API PNCP | CONCLUIDA | 2026-01-16 |
| 2 - Extracao | Auditor V13 extraindo dados dos PDFs | CONCLUIDA | 2026-01-16 |
| 3 - Persistencia | Supabase PostgreSQL configurado | CONCLUIDA | 2026-01-16 |
| 4 - Cloud Native | V11 + V14 100% na nuvem | CONCLUIDA | 2026-01-16 |
| 5 - Seguranca | Auditoria e correcoes | CONCLUIDA | 2026-01-16 |
| 6 - Notificacoes | Email de falha via Gmail | CONCLUIDA | 2026-01-17 |
| 7 - CI | Linting (ruff) + Testes (pytest) | CONCLUIDA | 2026-01-17 |

### Fase 8 - Expansao (FUTURO)

| Item | Descricao | Prioridade |
|------|-----------|------------|
| Dashboard | Interface web para visualizar dados | Alta |
| API REST | Endpoint para consultas externas | Alta |
| Alertas de novos editais | Notificacao quando novos editais sao coletados | Media |
| Retry backoff | Retry exponencial para API PNCP | Media |

### Dividas Tecnicas

| Item | Descricao | Esforco | Status |
|------|-----------|---------|--------|
| Notificacao de falha | Email quando workflow falha | Baixo | CONCLUIDO |
| Testes unitarios | Cobertura para funcoes puras | Medio | CONCLUIDO (98 testes) |
| CI/CD | Lint e testes automaticos | Medio | CONCLUIDO |
| Format check | Verificacao de formatacao | Baixo | Pendente (67 arquivos) |
| Monitoramento custos | Alerta quando Storage > 500MB | Baixo | Pendente |
| Limpeza editais antigos | Remover editais > 1 ano | Baixo | Pendente |

---

## Historico de Commits

### Commits Recentes (Mais Novos Primeiro)

| Hash | Data | Descricao |
|------|------|-----------|
| `06b615c` | 2026-01-17 | fix: Auditor now sets processado_auditor=True after processing |
| `1af9e55` | 2026-01-17 | docs: Update CLAUDE.md with new commit history and metrics |
| `df67098` | 2026-01-17 | fix: Auditor now correctly uses storage_path to download PDFs |
| `c9b813c` | 2026-01-17 | feat: Add CI workflow with ruff linting and pytest |
| `80ae043` | 2026-01-17 | docs: Ultra-detailed CLAUDE.md update with notifications system |
| `e566fd0` | 2026-01-17 | chore: Remove email test workflow |
| `75548f1` | 2026-01-17 | fix: Use SSL port 465 instead of STARTTLS port 587 for Gmail |
| `09bc949` | 2026-01-17 | test: Add email notification test workflow |
| `c3a9817` | 2026-01-17 | feat: Add email notification on workflow failure |
| `cf6cc99` | 2026-01-16 | docs: Comprehensive CLAUDE.md rewrite with ultra-detailed documentation |
| `f687f46` | 2026-01-16 | fix: Relax pre-commit hook regex to catch smaller secrets |
| `f437982` | 2026-01-16 | docs: Update CLAUDE.md with security audit and credential rotation |
| `dd57120` | 2026-01-16 | security: Remove exposed credentials and add protection mechanisms |
| `6642d33` | 2026-01-16 | docs: Comprehensive CLAUDE.md update with V11 cloud architecture |
| `4deadc2` | 2026-01-16 | fix: Handle empty/invalid UF values in edital mapping |
| `11ac508` | 2026-01-16 | feat: Add 100% cloud architecture with Supabase Storage and GitHub Actions |
| `a639ebd` | 2026-01-16 | feat: Add Miner V10 with Supabase integration |
| `ac0a52f` | 2026-01-16 | docs: Add .env.example and resolve documentation gaps |
| `aeb193a` | 2026-01-16 | docs: Add Quick Start, Troubleshooting and Architecture Decisions |
| `36c0595` | 2026-01-16 | docs: Add project scope, roadmap and next steps to CLAUDE.md |

### Commits por Categoria

#### Funcionalidades (feat)
| Hash | Descricao |
|------|-----------|
| `c9b813c` | CI workflow com ruff linting e pytest (98 testes) |
| `c3a9817` | Notificacao por email quando workflow falha |
| `11ac508` | Arquitetura 100% cloud com Supabase Storage |
| `a639ebd` | Miner V10 com integracao Supabase |

#### Correcoes (fix)
| Hash | Descricao |
|------|-----------|
| `06b615c` | Auditor seta processado_auditor=True |
| `df67098` | Auditor usa storage_path para baixar PDFs |
| `75548f1` | Porta SSL 465 para Gmail SMTP |
| `f687f46` | Regex do hook para secrets menores |
| `4deadc2` | Tratamento de UF invalida |

#### Seguranca (security)
| Hash | Descricao |
|------|-----------|
| `dd57120` | Remocao de credenciais expostas |

#### Documentacao (docs)
| Hash | Descricao |
|------|-----------|
| `80ae043` | CLAUDE.md com sistema de notificacoes |
| `cf6cc99` | Reescrita completa do CLAUDE.md |
| `f437982` | Auditoria de seguranca |
| `6642d33` | Arquitetura V11 cloud |

---

## Checklist para Nova Sessao

Execute estes comandos no inicio de cada sessao Claude:

```bash
# 1. Verificar status do ultimo workflow de coleta
gh run list --workflow=ache-sucatas.yml --limit 3

# 2. Verificar status do ultimo CI
gh run list --workflow=ci.yml --limit 3

# 3. Verificar editais no banco
python -c "from supabase_repository import SupabaseRepository; r = SupabaseRepository(); print(f'Editais no banco: {r.contar_editais()}')"

# 4. Verificar editais no Storage
python -c "from supabase_storage import SupabaseStorageRepository; s = SupabaseStorageRepository(); print(f'Editais no Storage: {len(s.listar_editais())}')"

# 5. Verificar secrets configurados (deve mostrar 4)
gh secret list

# 6. Executar testes localmente
pytest tests/ -v --tb=short
```

### Resultados Esperados

```
# Workflow de coleta
completed  success  ACHE SUCATAS - Coleta e Processamento  master  ...

# Workflow de CI
completed  success  CI - Lint & Test  master  ...

# Banco
Editais no banco: 26

# Storage
Editais no Storage: 20

# Secrets (4 secrets)
EMAIL_ADDRESS         2026-01-16T23:41:58Z
EMAIL_APP_PASSWORD    2026-01-16T23:43:24Z
SUPABASE_SERVICE_KEY  2026-01-16T22:41:56Z
SUPABASE_URL          2026-01-16T21:21:31Z

# Testes
98 passed in 3.00s
```

### Se Algum Falhar

| Problema | Acao |
|----------|------|
| Workflow de coleta falhou | `gh run view <ID> --log` para ver erro |
| CI falhou | `ruff check .` e `pytest tests/ -v` localmente |
| Supabase nao conecta | Verificar .env ou GitHub Secrets |
| Storage nao conecta | Verificar se bucket existe no Dashboard |
| Secrets nao listados | Configurar via `gh secret set` |
| Menos de 4 secrets | Configurar EMAIL_ADDRESS e EMAIL_APP_PASSWORD |
| Testes falharam | Ver output e corrigir teste ou funcao |

---

## Informacoes do Repositorio

| Propriedade | Valor |
|-------------|-------|
| URL | https://github.com/thiagodiasdigital/ache-sucatas-v13 |
| Visibilidade | Privado |
| Branch principal | master |
| Actions | https://github.com/thiagodiasdigital/ache-sucatas-v13/actions |
| Secrets configurados | 4 (SUPABASE_URL, SUPABASE_SERVICE_KEY, EMAIL_ADDRESS, EMAIL_APP_PASSWORD) |
| Email de notificacao | thiagodias180986@gmail.com |
| Workflows | 2 (ache-sucatas.yml, ci.yml) |
| Testes unitarios | 98 (100% passando) |

---

## Dependencias Python

Instalar com: `pip install -r requirements.txt`

| Pacote | Versao | Uso |
|--------|--------|-----|
| pdfplumber | >=0.10.0 | Parsing de PDFs |
| pandas | >=2.0.0 | Manipulacao de dados |
| openpyxl | >=3.1.0 | Exportacao Excel |
| supabase | >=2.0.0 | Cliente Supabase (PostgreSQL + Storage) |
| pydantic | >=2.0.0 | Validacao de dados (Miner V11) |
| python-dotenv | >=1.0.0 | Variaveis de ambiente |
| requests | >=2.31.0 | HTTP requests |
| aiohttp | >=3.9.0 | HTTP async |
| aiofiles | >=23.0.0 | I/O async |
| python-docx | >=1.0.0 | Parsing de DOCX (opcional) |

### Dependencias de Desenvolvimento

| Pacote | Versao | Uso |
|--------|--------|-----|
| ruff | >=0.1.0 | Linting Python |
| pytest | >=7.0.0 | Testes unitarios |

---

## Notas Importantes

1. **NUNCA commitar `.env`** - contem credenciais Supabase
2. **Pre-commit hook ativo** - bloqueia commits com secrets (regex atualizado)
3. **Credenciais rotacionadas** - em 2026-01-16 22:41 UTC
4. **ACHE_SUCATAS_DB/** esta no .gitignore (PDFs locais legados)
5. **Limite de $50 USD** aprovado para Supabase
6. **Sistema 100% cloud** - nao precisa mais de PC local ligado
7. **Execucao automatica 3x/dia** - 00:00, 08:00, 16:00 UTC
8. **4 GitHub Secrets configurados** - SUPABASE_URL, SUPABASE_SERVICE_KEY, EMAIL_ADDRESS, EMAIL_APP_PASSWORD
9. **Bucket `editais-pdfs`** ja criado e funcionando
10. **UF invalida vira "XX"** - nao bloqueia por dados ruins da API
11. **Notificacao por email** - envia automaticamente quando workflow falha
12. **Gmail SMTP porta 465** - SSL/TLS, nao usar porta 587
13. **CI automatico** - roda em cada push/PR para master
14. **98 testes unitarios** - cobrindo funcoes puras (sem Supabase)
15. **ruff.toml configurado** - regras relaxadas para codigo existente

---

> Documento gerado e mantido pelo Claude Code
> Ultima atualizacao: 2026-01-17 13:05 UTC
