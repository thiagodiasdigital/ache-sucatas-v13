# CLAUDE_FULL_2.md - Arquitetura e Fluxos

> **Versao:** V11 (Cloud-Native) + Auditor V14.2

---

## Navegacao da Documentacao

| # | Arquivo | Conteudo |
|---|---------|----------|
| 1 | [CLAUDE_FULL_1.md](./CLAUDE_FULL_1.md) | Estado atual, Frontend React, Hotfixes |
| **2** | **CLAUDE_FULL_2.md** (este) | Arquitetura e Fluxos |
| 3 | [CLAUDE_FULL_3.md](./CLAUDE_FULL_3.md) | CI/CD, Testes, Workflows |
| 4 | [CLAUDE_FULL_4.md](./CLAUDE_FULL_4.md) | Banco de Dados e API PNCP |
| 5 | [CLAUDE_FULL_5.md](./CLAUDE_FULL_5.md) | Seguranca e Configuracao |
| 6 | [CLAUDE_FULL_6.md](./CLAUDE_FULL_6.md) | Operacoes e Historico |

---

## Arquitetura V11 - 100% Cloud + CI

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

---

## Fluxo Completo de Execucao (Coleta)

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

---

## Fluxo de CI (Validacao)

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

---

## Fluxo Detalhado do Miner V11

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

---

## Fluxo Detalhado do Auditor V14

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

---

## Fluxo de Notificacao de Falha

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

---

## Diagrama de Dependencias (Scripts)

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

### Scripts de Producao (ATIVOS)

| Arquivo | Linhas | Funcao |
|---------|--------|--------|
| `ache_sucatas_miner_v11.py` | ~800 | Coleta editais, upload Storage, insert PostgreSQL |
| `cloud_auditor_v14.py` | ~650 | Processa PDFs do Storage, extrai dados |
| `supabase_repository.py` | ~300 | Repositorio PostgreSQL (CRUD editais) |
| `supabase_storage.py` | ~240 | Repositorio Storage (upload/download PDFs) |
| `sincronizar_storage_banco.py` | ~280 | Sincroniza PDFs do Storage com banco |
| `coleta_historica_30d.py` | ~350 | Coleta historica dos ultimos 30 dias |

### Scripts de Migracao

| Arquivo | Funcao |
|---------|--------|
| `migrar_schema_v11_storage.sql` | SQL para adicionar colunas storage_path, processado_auditor, score |
| `schemas_v13_supabase.sql` | Schema completo das tabelas PostgreSQL |

### Scripts Legados (NAO USAR)

| Arquivo | Status |
|---------|--------|
| `ache_sucatas_miner_v10.py` | Legado |
| `ache_sucatas_miner_v9_cron.py` | Descontinuado |
| `local_auditor_v13.py` | Legado (le PDFs locais) |
| `local_auditor_v12*.py` | Descontinuado |

---

## Arvore de Arquivos (Raiz)

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
|-- tests/                             # Testes unitarios (98 testes)
|   |-- __init__.py
|   |-- conftest.py
|   |-- test_auditor_extraction.py     # 53 testes
|   |-- test_miner_scoring.py          # 19 testes
|   +-- test_repository_parsing.py     # 26 testes
|
|-- frontend/                          # Dashboard React
|   |-- src/components/
|   |-- src/hooks/
|   +-- supabase/week2_schema.sql
|
|-- ache_sucatas_miner_v11.py          # PRODUCAO
|-- cloud_auditor_v14.py               # PRODUCAO
|-- supabase_repository.py             # PRODUCAO
|-- supabase_storage.py                # PRODUCAO
|-- coleta_historica_30d.py            # PRODUCAO
|
|-- ruff.toml                          # Config linter
|-- pytest.ini                         # Config pytest
|-- requirements.txt                   # Dependencias Python
|-- .env                               # CREDENCIAIS (gitignore)
|-- .env.example                       # Template
|-- .gitignore                         # 96 linhas
|-- CLAUDE.md                          # Resumo
|-- CLAUDE_FULL_*.md                   # Documentacao completa
+-- schemas_v13_supabase.sql           # Schema SQL
```

---

> Anterior: [CLAUDE_FULL_1.md](./CLAUDE_FULL_1.md) | Proximo: [CLAUDE_FULL_3.md](./CLAUDE_FULL_3.md)
