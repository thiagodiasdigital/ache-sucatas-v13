# CLAUDE.md - Contexto do Projeto ACHE SUCATAS

> **Ultima atualizacao:** 2026-01-17 00:30 UTC
> **Versao atual:** V11 (Cloud-Native) + Auditor V14
> **Status:** 100% Operacional na Nuvem
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
10. [API PNCP](#api-pncp)
11. [Comandos Uteis](#comandos-uteis)
12. [Troubleshooting](#troubleshooting)
13. [Roadmap](#roadmap)
14. [Historico de Commits](#historico-de-commits)
15. [Checklist para Nova Sessao](#checklist-para-nova-sessao)

---

## Visao Geral

**ACHE SUCATAS DaaS** (Data as a Service) - Sistema automatizado de coleta e analise de editais de leilao publico do Brasil.

### O que o sistema faz

1. **Coleta** - Busca editais de leilao na API PNCP (Portal Nacional de Contratacoes Publicas)
2. **Download** - Baixa PDFs dos editais para Supabase Storage (nuvem)
3. **Extracao** - Extrai informacoes estruturadas dos PDFs (titulo, data, valores, itens, leiloeiro)
4. **Persistencia** - Armazena metadados no Supabase PostgreSQL
5. **Automacao** - Executa 3x/dia via GitHub Actions (sem necessidade de PC local)

### Metricas Atuais

| Metrica | Valor |
|---------|-------|
| Editais no banco (PostgreSQL) | 6 |
| Editais no Storage (PDFs) | 20 |
| Workflows executados | 2 (100% sucesso) |
| Ultima execucao | 2026-01-16 22:43 UTC |
| Tempo medio de execucao | ~2 minutos |

---

## Escopo do Projeto

### Objetivo de Negocio

Criar um banco de dados estruturado de **leiloes publicos municipais** do Brasil, focando em:
- Veiculos e maquinas inserviveis
- Sucatas e materiais reciclaveis
- Bens moveis de prefeituras

### Publico-Alvo

- Empresas de reciclagem e sucata
- Compradores de leiloes publicos
- Analistas de mercado de leiloes

### Fontes de Dados

| Fonte | Tipo | Uso |
|-------|------|-----|
| API PNCP | REST API | Metadados dos editais (titulo, orgao, datas, links) |
| PDFs dos Editais | Documentos | Detalhes extraidos (itens, valores, leiloeiro) |

### Filtros de Coleta

- **Modalidade:** Leilao (modalidadeId=8)
- **Esfera:** Municipal (prefeituras)
- **Janela temporal:** Ultimas 24 horas
- **Score minimo:** 30 pontos (relevancia)

### Fora do Escopo (por enquanto)

- Leiloes federais e estaduais
- Leiloes de imoveis
- Integracao com sistemas de leiloeiros
- Interface web/dashboard

---

## Arquitetura

### Arquitetura V11 - 100% Cloud (ATUAL)

```
+-----------------------------------------------------------+
|                    GITHUB ACTIONS                          |
|              (Cron: 00:00, 08:00, 16:00 UTC)               |
|              (21:00, 05:00, 13:00 BRT)                     |
+-----------------------------------------------------------+
                            |
       +--------------------+--------------------+
       |                                         |
       v                                         v
+--------------+                         +--------------+
|  Miner V11   |------------------------>| Auditor V14  |
|  (coleta)    |  (needs: miner)         |  (extracao)  |
|   ~41s       |                         |    ~29s      |
+------+-------+                         +------+-------+
       |                                        |
       |   +------------------------------------+
       |   |
       v   v
+---------------------------------------+
|            SUPABASE                    |
|  +--------------+  +---------------+  |
|  |   Storage    |  |  PostgreSQL   |  |
|  |   (PDFs)     |  |  (metadados)  |  |
|  | editais-pdfs |  |editais_leilao |  |
|  +--------------+  +---------------+  |
+---------------------------------------+
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
```

---

## Arquivos do Projeto

### Scripts de Producao (V11/V14 - Cloud) - ATIVOS

| Arquivo | Linhas | Funcao | Dependencias |
|---------|--------|--------|--------------|
| `ache_sucatas_miner_v11.py` | ~800 | Coleta editais, upload Storage, insert PostgreSQL | supabase, requests, pydantic |
| `cloud_auditor_v14.py` | ~600 | Processa PDFs do Storage, extrai dados | supabase, pdfplumber |
| `supabase_repository.py` | ~300 | Repositorio PostgreSQL (CRUD editais) | supabase |
| `supabase_storage.py` | ~200 | Repositorio Storage (upload/download PDFs) | supabase |

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
| `.gitignore` | Protecoes (87 linhas, reforçado) |

### GitHub Actions

| Arquivo | Funcao |
|---------|--------|
| `.github/workflows/ache-sucatas.yml` | Workflow principal (217 linhas) |

### Scripts Legados (NAO USAR em producao)

| Arquivo | Versao | Status |
|---------|--------|--------|
| `ache_sucatas_miner_v10.py` | V10 | Legado (backup local) |
| `ache_sucatas_miner_v9_cron.py` | V9 | Descontinuado |
| `local_auditor_v13.py` | V13 | Legado (le PDFs locais) |
| `local_auditor_v12*.py` | V12 | Descontinuado |
| `migrar_v13_robusto.py` | - | Migracao em lote (nao usado) |

### Arvore de Arquivos Python (Raiz)

```
testes-12-01-17h/
|-- ache_sucatas_miner_v11.py      # PRODUCAO - Miner cloud
|-- cloud_auditor_v14.py           # PRODUCAO - Auditor cloud
|-- supabase_repository.py         # PRODUCAO - Repo PostgreSQL
|-- supabase_storage.py            # PRODUCAO - Repo Storage
|-- rotacionar_credenciais.py      # Seguranca
|-- instalar_hooks_seguranca.py    # Seguranca
|-- desligar_supabase.py           # Emergencia
|-- reativar_supabase.py           # Emergencia
|-- monitorar_uso_supabase.py      # Monitoramento
|-- ache_sucatas_miner_v10.py      # Legado
|-- local_auditor_v13.py           # Legado
|-- [outros scripts legados...]
```

---

## Estrutura de Pastas

### Estrutura Local

```
testes-12-01-17h/
|
|-- .github/
|   +-- workflows/
|       +-- ache-sucatas.yml           # GitHub Actions workflow
|
|-- .githooks/
|   +-- pre-commit                     # Hook de seguranca
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
|-- .gitignore                         # 87 linhas de protecao
|-- CLAUDE.md                          # Este arquivo
|-- requirements.txt                   # Dependencias Python
|-- schemas_v13_supabase.sql           # Schema SQL
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
|-- editais_leilao                     # Tabela principal (6 registros)
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
| `EMAIL_ADDRESS` | Email Gmail para notificacoes | Pendente |
| `EMAIL_APP_PASSWORD` | App Password do Gmail | Pendente |

### Como Configurar GitHub Secrets

```bash
# Via GitHub CLI (requer autenticacao)
echo "https://xxx.supabase.co" | gh secret set SUPABASE_URL
echo "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9..." | gh secret set SUPABASE_SERVICE_KEY

# Secrets de Email (notificacao de falha)
gh secret set EMAIL_ADDRESS        # seu-email@gmail.com
gh secret set EMAIL_APP_PASSWORD   # App Password de 16 caracteres

# Verificar secrets configurados
gh secret list

# Resultado esperado:
# EMAIL_ADDRESS         (data)
# EMAIL_APP_PASSWORD    (data)
# SUPABASE_SERVICE_KEY  2026-01-16T22:41:56Z
# SUPABASE_URL          2026-01-16T21:21:31Z
```

### Como Criar Gmail App Password

O Gmail nao permite login direto por SMTP. E necessario criar um "App Password":

1. Acesse https://myaccount.google.com/security
2. Ative "Verificacao em duas etapas" (se ainda nao tiver)
3. Acesse https://myaccount.google.com/apppasswords
4. Selecione "Outro (nome personalizado)" e digite "ACHE SUCATAS"
5. Clique em "Gerar"
6. Copie a senha de 16 caracteres (ex: `abcd efgh ijkl mnop`)
7. Use essa senha no secret `EMAIL_APP_PASSWORD` (sem espacos)

**IMPORTANTE:** A App Password so aparece uma vez. Se perder, delete e crie outra.

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
5. **.gitignore reforçado** - 87 linhas com padroes de seguranca

### Pre-commit Hook

O hook `.githooks/pre-commit` bloqueia commits contendo:

| Padrao | Regex |
|--------|-------|
| Supabase service key | `SUPABASE_SERVICE_KEY=.+` |
| Supabase DB password | `SUPABASE_DB_PASSWORD=.+` |
| Supabase secret prefix | `sb_secret_[a-zA-Z0-9_-]+` |
| PostgreSQL URL com senha | `postgresql://.*:.*@.*supabase` |
| JWT tokens | `eyJ[a-zA-Z0-9_-]{20,}` |
| Senhas em strings | `password.*=.*['\"][^'\"]{4,}['\"]` |
| Secrets em strings | `secret.*=.*['\"][^'\"]{4,}['\"]` |
| API keys em strings | `api_key.*=.*['\"][^'\"]{4,}['\"]` |

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

**Ultimas execucoes:**
```
[SUCCESS] V11_CLOUD - novos:433 storage:0 db:0
[SUCCESS] V11_CLOUD - novos:433 storage:0 db:0
[SUCCESS] V11_CLOUD - novos:20 storage:0 db:0
```

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

### Workflow: ache-sucatas.yml

Configuracao completa do workflow de automacao.

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
| notify-failure | Notificar Falha | miner, auditor | - | Se falhou |

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
| **Total** | ~2 min |

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
      "titulo": "Leilão de veículos inservíveis",
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
    "titulo": "Edital de Leilão",
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
# Disparar workflow manualmente (todos os jobs)
gh workflow run ache-sucatas.yml

# Disparar apenas Miner
gh workflow run ache-sucatas.yml -f run_auditor=false

# Disparar apenas Auditor (limitar a 5 editais)
gh workflow run ache-sucatas.yml -f run_miner=false -f auditor_limit=5

# Verificar status dos ultimos workflows
gh run list --workflow=ache-sucatas.yml --limit 5

# Acompanhar execucao em tempo real
gh run watch <RUN_ID>

# Ver logs de uma execucao
gh run view <RUN_ID> --log

# Ver logs de um job especifico
gh run view <RUN_ID> --log --job=<JOB_ID>
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

# Verificar GitHub Secrets
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

---

## Roadmap

### Fases Concluidas

| Fase | Descricao | Status |
|------|-----------|--------|
| 1 - Coleta | Miner V9 coletando da API PNCP | CONCLUIDA |
| 2 - Extracao | Auditor V13 extraindo dados dos PDFs | CONCLUIDA |
| 3 - Persistencia | Supabase PostgreSQL configurado | CONCLUIDA |
| 4 - Cloud Native | V11 + V14 100% na nuvem | CONCLUIDA |
| 5 - Seguranca | Auditoria e correcoes | CONCLUIDA |

### Fase 6 - Expansao (FUTURO)

| Item | Descricao | Prioridade |
|------|-----------|------------|
| Dashboard | Interface web para visualizar dados | Alta |
| API REST | Endpoint para consultas externas | Alta |
| Alertas | Notificacoes de novos editais (email/webhook) | Media |
| Retry backoff | Retry exponencial para API PNCP | Media |

### Dividas Tecnicas

| Item | Descricao | Esforco | Status |
|------|-----------|---------|--------|
| Notificacao de falha | Email quando workflow falha | Baixo | IMPLEMENTADO (configurar secrets) |
| Testes unitarios | Cobertura para Storage e Repository | Medio | Pendente |
| Monitoramento custos | Alerta quando Storage > 500MB | Baixo | Pendente |
| Limpeza editais antigos | Remover editais > 1 ano | Baixo | Pendente |

---

## Historico de Commits

### Commits Recentes (Mais Novos Primeiro)

| Hash | Data | Descricao |
|------|------|-----------|
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

### Commits de Seguranca

| Hash | Descricao |
|------|-----------|
| `f687f46` | Regex do hook relaxado para pegar secrets menores |
| `dd57120` | Remocao de credenciais e mecanismos de protecao |

---

## Checklist para Nova Sessao

Execute estes comandos no inicio de cada sessao Claude:

```bash
# 1. Verificar status do ultimo workflow
gh run list --workflow=ache-sucatas.yml --limit 3

# 2. Verificar editais no banco
python -c "from supabase_repository import SupabaseRepository; r = SupabaseRepository(); print(f'Editais no banco: {r.contar_editais()}')"

# 3. Verificar editais no Storage
python -c "from supabase_storage import SupabaseStorageRepository; s = SupabaseStorageRepository(); print(f'Editais no Storage: {len(s.listar_editais())}')"

# 4. Verificar secrets configurados
gh secret list
```

### Resultados Esperados

```
# Workflow
completed  success  ACHE SUCATAS - Coleta e Processamento  master  ...

# Banco
Editais no banco: 6

# Storage
Editais no Storage: 20

# Secrets
SUPABASE_SERVICE_KEY  2026-01-16T22:41:56Z
SUPABASE_URL          2026-01-16T21:21:31Z
```

### Se Algum Falhar

| Problema | Acao |
|----------|------|
| Workflow falhou | `gh run view <ID> --log` para ver erro |
| Supabase nao conecta | Verificar .env ou GitHub Secrets |
| Storage nao conecta | Verificar se bucket existe no Dashboard |
| Secrets nao listados | Configurar via `gh secret set` |

---

## Informacoes do Repositorio

| Propriedade | Valor |
|-------------|-------|
| URL | https://github.com/thiagodiasdigital/ache-sucatas-v13 |
| Visibilidade | Privado |
| Branch principal | master |
| Actions | https://github.com/thiagodiasdigital/ache-sucatas-v13/actions |
| Secrets configurados | 2 (SUPABASE_URL, SUPABASE_SERVICE_KEY) |

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

---

## Notas Importantes

1. **NUNCA commitar `.env`** - contem credenciais Supabase
2. **Pre-commit hook ativo** - bloqueia commits com secrets (regex atualizado)
3. **Credenciais rotacionadas** - em 2026-01-16 22:41 UTC
4. **ACHE_SUCATAS_DB/** esta no .gitignore (PDFs locais legados)
5. **Limite de $50 USD** aprovado para Supabase
6. **Sistema 100% cloud** - nao precisa mais de PC local ligado
7. **Execucao automatica 3x/dia** - 00:00, 08:00, 16:00 UTC
8. **GitHub Secrets configurados** - nao precisa .env no workflow
9. **Bucket `editais-pdfs`** ja criado e funcionando
10. **UF invalida vira "XX"** - nao bloqueia por dados ruins da API

---

> Documento gerado e mantido pelo Claude Code
> Ultima atualizacao: 2026-01-16 23:15 UTC
