# CLAUDE.md - Contexto do Projeto ACHE SUCATAS

> **Ultima atualizacao:** 16/01/2026 22:48 UTC
> **Versao atual:** V11 (Cloud-Native)
> **Status:** 100% Operacional na Nuvem
> **Seguranca:** Auditada e Corrigida (16/01/2026)

---

## Visao Geral

**ACHE SUCATAS DaaS** - Sistema de coleta e analise de editais de leilao publico do Brasil.
- Coleta dados da API PNCP (Portal Nacional de Contratacoes Publicas)
- Faz download e parsing de PDFs de editais
- Extrai informacoes estruturadas (titulo, data, valores, itens, etc.)
- Persiste no Supabase PostgreSQL
- **PDFs armazenados no Supabase Storage (cloud)**
- **Execucao automatizada via GitHub Actions**
- **Seguranca: Pre-commit hooks e rotacao de credenciais**

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
1. **API PNCP** - Metadados dos editais (titulo, orgao, datas, links)
2. **PDFs dos Editais** - Detalhes extraidos (itens, valores, leiloeiro)

### Fora do Escopo (por enquanto)
- Leiloes federais e estaduais
- Leiloes de imoveis
- Integracao com sistemas de leiloeiros
- Interface web/dashboard

---

## Roadmap

### Fase 1 - Coleta (CONCLUIDA)
- [x] Miner V9 coletando da API PNCP
- [x] Download automatico de PDFs
- [x] 198 editais coletados inicialmente

### Fase 2 - Extracao (CONCLUIDA)
- [x] Auditor V13 extraindo dados dos PDFs
- [x] 14 campos estruturados
- [x] Score de qualidade calculado

### Fase 3 - Persistencia (CONCLUIDA)
- [x] Supabase configurado
- [x] Freios de seguranca ativos
- [x] Miner V10 com integracao Supabase (16/01/2026)

### Fase 4 - Cloud Native (CONCLUIDA - 16/01/2026)
- [x] **Miner V11** - Upload de PDFs para Supabase Storage
- [x] **Auditor V14** - Le PDFs do Storage (nao mais local)
- [x] **supabase_storage.py** - Repositorio Storage
- [x] **GitHub Actions** - Automacao 3x/dia (cron)
- [x] **GitHub Secrets** - Configurados (SUPABASE_URL, SUPABASE_SERVICE_KEY)
- [x] **Primeiro workflow executado com sucesso** (16/01/2026 21:23 UTC)

### Fase 5 - Seguranca (CONCLUIDA - 16/01/2026)
- [x] **Auditoria completa de seguranca** - Identificadas 3 vulnerabilidades criticas
- [x] **Remocao de credenciais expostas** - 9 arquivos corrigidos
- [x] **Pre-commit hook** - Bloqueia commits com secrets
- [x] **Rotacao de credenciais** - Service key e senha do banco rotacionadas
- [x] **Scripts de seguranca** - rotacionar_credenciais.py, instalar_hooks_seguranca.py
- [x] **.gitignore reforçado** - Padroes adicionais de seguranca

### Fase 6 - Expansao (FUTURO)
- [ ] Dashboard de visualizacao
- [ ] API REST para consultas
- [ ] Alertas de novos editais (email/webhook)
- [ ] Migracao dos 198 editais locais para Storage

---

## Arquitetura

### Arquitetura V11 - 100% Cloud (ATUAL)

```
+-----------------------------------------------------------+
|                    GITHUB ACTIONS                          |
|              (Cron: 00:00, 08:00, 16:00 UTC)               |
|              (21:00, 05:00, 13:00 BRT)                     |
+-----------------------------------------------------------+
|                                                            |
|   +--------------+         +--------------+                |
|   |  Miner V11   |-------->| Auditor V14  |                |
|   |  (coleta)    |         |  (extracao)  |                |
|   |   ~41s       |         |    ~29s      |                |
|   +------+-------+         +------+-------+                |
|          |                        |                        |
|   +------+-------+         +------+-------+                |
|   | Verificacao  |         |  Notificar   |                |
|   |   Final      |         |   Falha      |                |
|   |   ~30s       |         | (se erro)    |                |
|   +--------------+         +--------------+                |
|                                                            |
+-----------+---------------------------+--------------------+
            |                           |
            v                           v
    +---------------------------------------+
    |            SUPABASE                    |
    |  +--------------+  +---------------+  |
    |  |   Storage    |  |  PostgreSQL   |  |
    |  |   (PDFs)     |  |  (metadados)  |  |
    |  | editais-pdfs |  |editais_leilao |  |
    |  +--------------+  +---------------+  |
    +---------------------------------------+
```

**Fluxo do Miner V11 (Cloud):**
1. Coleta editais da API PNCP (janela temporal: 24h)
2. Calcula score de relevancia (MIN_SCORE: 30)
3. Download do PDF em memoria (bytes)
4. Upload PDF para Supabase Storage (`editais-pdfs/{pncp_id}/`)
5. Upload metadados.json para Storage
6. Insere metadados no PostgreSQL (com validacao de UF)
7. Registra execucao em `execucoes_miner`
8. Checkpoint para deduplicacao

**Fluxo do Auditor V14 (Cloud):**
1. Query editais pendentes no PostgreSQL (`processado_auditor = false`)
2. Download PDF do Storage -> BytesIO
3. `pdfplumber.open(BytesIO)` -> extrai texto
4. Processa com funcoes de extracao V13
5. Update no PostgreSQL com dados extraidos
6. Marca `processado_auditor = true`

### Arquitetura Legada (V10 - Local)

```
+--------------+     +--------------+     +--------------+
| Miner V10    |---->|   Local      |---->| Auditor V13  |
|  (coleta)    |     |  (PDFs)      |     |  (parsing)   |
+------+-------+     +--------------+     +------+-------+
       |                                         |
       v                                         v
  +----------------------------------------------+
  |              Supabase PostgreSQL              |
  +----------------------------------------------+
```

---

## Arquivos Principais

### Scripts de Producao (V11 - Cloud) - ATUAIS

| Arquivo | Funcao | Criado em |
|---------|--------|-----------|
| `ache_sucatas_miner_v11.py` | **Miner V11** - coleta 100% cloud (Storage) | 16/01/2026 |
| `cloud_auditor_v14.py` | **Auditor V14** - extrai PDFs do Storage | 16/01/2026 |
| `supabase_storage.py` | Repositorio Supabase Storage (upload/download) | 16/01/2026 |
| `supabase_repository.py` | Repositorio Supabase PostgreSQL | 15/01/2026 |
| `.github/workflows/ache-sucatas.yml` | GitHub Actions (cron 3x/dia) | 16/01/2026 |

### Scripts de Seguranca

| Arquivo | Funcao | Criado em |
|---------|--------|-----------|
| `rotacionar_credenciais.py` | **NOVO** - Script interativo para rotacionar credenciais | 16/01/2026 |
| `instalar_hooks_seguranca.py` | **NOVO** - Instala pre-commit hook para detectar secrets | 16/01/2026 |
| `.githooks/pre-commit` | **NOVO** - Hook que bloqueia commits com credenciais | 16/01/2026 |
| `desligar_supabase.py` | KILL SWITCH - desativa Supabase imediatamente | 16/01/2026 |
| `reativar_supabase.py` | Reativa Supabase apos desligamento | 16/01/2026 |
| `monitorar_uso_supabase.py` | Monitor de uso com alertas | 16/01/2026 |

### Scripts Legados (V10 - Local)

| Arquivo | Funcao | Status |
|---------|--------|--------|
| `ache_sucatas_miner_v10.py` | Miner V10 - coleta + Supabase (local backup) | Legado |
| `local_auditor_v13.py` | Auditor V13 - le PDFs locais | Legado |
| `migrar_v13_robusto.py` | Script de migracao em lote | Legado |
| `ache_sucatas_miner_v9_cron.py` | Miner V9 (sem Supabase) | Descontinuado |

### Configuracao

| Arquivo | Funcao |
|---------|--------|
| `.env` | Credenciais locais (NUNCA versionar!) |
| `.env.example` | Template de credenciais |
| `schemas_v13_supabase.sql` | Schema das tabelas Supabase |
| `.gitignore` | Protecoes de arquivos sensiveis (reforçado) |
| `requirements.txt` | Dependencias Python |

---

## Estrutura de Pastas

```
testes-12-01-17h/
|-- .github/
|   +-- workflows/
|       +-- ache-sucatas.yml       # GitHub Actions workflow
|-- .githooks/
|   +-- pre-commit                 # Hook de seguranca (NOVO)
|-- ACHE_SUCATAS_DB/               # PDFs locais (legado, nao versionado)
|   |-- AL_MACEIO/
|   +-- ...
|-- logs/                          # Logs de execucao
|-- .env                           # CREDENCIAIS (nao versionado)
|-- .env.example                   # Template de credenciais
|-- ache_sucatas_miner_v11.py      # Miner cloud-native
|-- cloud_auditor_v14.py           # Auditor cloud-native
|-- supabase_storage.py            # Storage repository
|-- supabase_repository.py         # PostgreSQL repository
|-- rotacionar_credenciais.py      # Script de rotacao (NOVO)
|-- instalar_hooks_seguranca.py    # Instalador de hooks (NOVO)
+-- *.py                           # Outros scripts
```

### Estrutura no Supabase Storage

```
editais-pdfs/                      # Bucket principal
|-- 18188243000160-1-000161-2025/  # Pasta por pncp_id
|   |-- metadados.json
|   |-- edital_a1b2c3d4.pdf
|   +-- anexo_e5f6g7h8.xlsx
|-- 00394460005887-1-000072-2025/
|   +-- ...
+-- [outros editais]/
```

---

## Variaveis de Ambiente

### .env (Local - NAO VERSIONAR)

```env
# ============================================
# SUPABASE (CONFIDENCIAL)
# ============================================
SUPABASE_URL=https://SEU_PROJECT_ID.supabase.co
SUPABASE_SERVICE_KEY=sua_service_key_aqui
SUPABASE_DB_PASSWORD=sua_senha_do_banco_aqui

# ============================================
# PNCP API (PUBLICO)
# ============================================
PNCP_BASE_URL=https://pncp.gov.br/api/consulta/v1
PNCP_ARQUIVOS_URL=https://pncp.gov.br/pncp-api/v1

# ============================================
# FEATURES FLAGS
# ============================================
ENABLE_SUPABASE=true
ENABLE_SUPABASE_STORAGE=true
SUPABASE_STORAGE_BUCKET=editais-pdfs
MAX_EDITAIS_SUPABASE=10000
ENABLE_LOCAL_BACKUP=false

# ============================================
# CRON (V11 MINER)
# ============================================
CRON_MODE=true
JANELA_TEMPORAL_HORAS=24
PAGE_LIMIT=3
MAX_DOWNLOADS=200
```

### GitHub Secrets

| Secret | Descricao | Ultima Atualizacao |
|--------|-----------|-------------------|
| `SUPABASE_URL` | URL do projeto Supabase | 16/01/2026 21:21 UTC |
| `SUPABASE_SERVICE_KEY` | Service role key (ROTACIONADA) | 16/01/2026 22:41 UTC |

**Como configurar/atualizar secrets:**
```bash
# Via GitHub CLI (ja autenticado)
echo "https://xxx.supabase.co" | gh secret set SUPABASE_URL
echo "sb_secret_xxx" | gh secret set SUPABASE_SERVICE_KEY

# Verificar secrets configurados
gh secret list
```

---

## Seguranca

### Auditoria Realizada (16/01/2026)

Uma auditoria completa de seguranca foi realizada e corrigida:

#### Vulnerabilidades Encontradas e Corrigidas

| Severidade | Vulnerabilidade | Status |
|------------|-----------------|--------|
| CRITICA | Senha do banco hardcoded em `executar_schema_postgresql.py` | CORRIGIDA |
| CRITICA | Service key exposta no `CLAUDE.md` | CORRIGIDA |
| CRITICA | URL do projeto exposta em 7 arquivos | CORRIGIDA |
| ALTA | Credenciais no historico Git | MITIGADA (rotacao) |

#### Acoes Tomadas

1. **Remocao de credenciais** - 9 arquivos corrigidos
2. **Rotacao de credenciais** - Service key e senha do banco regeneradas no Supabase
3. **Pre-commit hook** - Bloqueia automaticamente commits com secrets
4. **Scripts de seguranca** - Ferramentas para rotacao e instalacao de hooks
5. **.gitignore reforçado** - Padroes adicionais para arquivos sensiveis

#### Commit de Seguranca
```
dd57120 security: Remove exposed credentials and add protection mechanisms
```

### Protecoes Ativas

| Protecao | Descricao | Status |
|----------|-----------|--------|
| Pre-commit hook | Detecta secrets antes do commit | ATIVO |
| .gitignore | Bloqueia .env, *.key, *.pem, etc | ATIVO |
| GitHub Secrets | Credenciais em secrets, nao no codigo | ATIVO |
| Service role key | Rotacionada em 16/01/2026 22:41 UTC | ATIVO |
| RLS (Row Level Security) | Ativo em todas as tabelas | ATIVO |

### Como Rotacionar Credenciais

```bash
# 1. Gere novas credenciais no Dashboard do Supabase
#    - Settings -> API -> Regenerate service_role key
#    - Settings -> Database -> Reset database password

# 2. Execute o script de rotacao
python rotacionar_credenciais.py

# 3. Atualize os GitHub Secrets
gh secret set SUPABASE_SERVICE_KEY
```

### Como Instalar Hooks de Seguranca

```bash
python instalar_hooks_seguranca.py
```

---

## Freios de Seguranca (Custos)

| Protecao | Limite | Status |
|----------|--------|--------|
| MAX_EDITAIS_SUPABASE | 10.000 registros | Ativo |
| Custo maximo aprovado | $50 USD | Ativo |
| Feature flag ENABLE_SUPABASE | true/false | Ativo |
| Feature flag ENABLE_SUPABASE_STORAGE | true/false | Ativo |
| Kill switch | `desligar_supabase.py` | Disponivel |
| MIN_SCORE_TO_DOWNLOAD | 30 (editais relevantes) | Ativo |

### Estimativa de Custos (Free Tier)

| Servico | Free Tier | Uso Atual | Status |
|---------|-----------|-----------|--------|
| Supabase DB | 500MB | ~5MB | OK |
| Supabase Storage | 1GB | ~50MB | OK |
| GitHub Actions | 2000 min/mes | ~6 min/dia (~180 min/mes) | OK |
| **TOTAL** | - | - | **$0/mes** |

---

## Status Atual (16/01/2026 22:48 UTC)

### Sistema 100% Operacional e Seguro

| Componente | Status | Detalhes |
|------------|--------|----------|
| Miner V11 | OK | Ultima execucao: 22:43 UTC |
| Auditor V14 | OK | Ultima execucao: 22:44 UTC |
| Supabase Storage | OK | 20 editais armazenados |
| Supabase PostgreSQL | OK | 6 editais no banco |
| GitHub Actions | OK | Cron ativo 3x/dia |
| GitHub Secrets | OK | Rotacionados em 22:41 UTC |
| Pre-commit hook | OK | Instalado e funcionando |

### Metricas Atuais

```
Editais no banco: 6
Editais no Storage: 20
Workflows executados: 2 (100% sucesso)
Credenciais: Rotacionadas
Seguranca: Auditada e corrigida
```

### Ultimo Workflow (16/01/2026 22:43 UTC)

| Job | Status | Tempo |
|-----|--------|-------|
| Miner V11 - Coleta | Sucesso | 41s |
| Auditor V14 - Processamento | Sucesso | 29s |
| Verificacao Final | Sucesso | 30s |
| Notificar Falha | Pulado | N/A |
| **Total** | **Sucesso** | **~1m49s** |

---

## Supabase - Tabelas

### 1. editais_leilao

| Campo | Tipo | Descricao |
|-------|------|-----------|
| id | SERIAL | PK auto-incremento |
| pncp_id | TEXT UNIQUE | ID unico do PNCP |
| titulo | TEXT | Titulo do edital |
| orgao | TEXT | Orgao responsavel |
| municipio | TEXT | Cidade |
| uf | CHAR(2) | Estado (CHECK constraint) |
| data_publicacao | TIMESTAMP | Data de publicacao |
| data_leilao | TIMESTAMP | Data do leilao |
| valor_estimado | DECIMAL | Valor estimado |
| link_pncp | TEXT | Link no PNCP |
| link_leiloeiro | TEXT | Link do leiloeiro |
| nome_leiloeiro | TEXT | Nome do leiloeiro |
| quantidade_itens | INTEGER | Qtd de itens |
| descricao | TEXT | Descricao extraida |
| score | INTEGER | Score de qualidade |
| storage_path | TEXT | Caminho no Storage |
| pdf_storage_url | TEXT | URL publica do PDF |
| processado_auditor | BOOLEAN | Flag de processamento |
| created_at | TIMESTAMP | Data de criacao |
| updated_at | TIMESTAMP | Data de atualizacao |

### 2. execucoes_miner

| Campo | Tipo | Descricao |
|-------|------|-----------|
| id | SERIAL | PK |
| versao_miner | TEXT | Versao do miner (V11) |
| execution_start | TIMESTAMP | Inicio da execucao |
| execution_end | TIMESTAMP | Fim da execucao |
| status | TEXT | RUNNING/SUCCESS/FAILED |
| editais_novos | INTEGER | Novos coletados |
| downloads | INTEGER | Downloads realizados |
| storage_uploads | INTEGER | Uploads no Storage |
| supabase_inserts | INTEGER | Inserts no banco |

### 3. metricas_diarias

| Campo | Tipo | Descricao |
|-------|------|-----------|
| id | SERIAL | PK |
| data | DATE UNIQUE | Data da metrica |
| total_editais | INTEGER | Total acumulado |
| novos_editais | INTEGER | Novos no dia |
| execucoes | INTEGER | Qtd de execucoes |

---

## Comandos Uteis

### Execucao Cloud (V11 - Recomendado)

```bash
# Disparar workflow manualmente
gh workflow run ache-sucatas.yml

# Verificar status do workflow
gh run list --workflow=ache-sucatas.yml --limit 3

# Acompanhar execucao em tempo real
gh run watch <RUN_ID>

# Ver logs de uma execucao
gh run view <RUN_ID> --log
```

### Execucao Local (Debug/Testes)

```bash
# Miner V11 (cloud storage)
python ache_sucatas_miner_v11.py

# Auditor V14 (cloud storage)
python cloud_auditor_v14.py

# Testar conexao com Supabase
python -c "from supabase_repository import SupabaseRepository; r = SupabaseRepository(); print(f'OK: {r.contar_editais()} editais')"

# Testar conexao com Storage
python -c "from supabase_storage import SupabaseStorageRepository; s = SupabaseStorageRepository(); print(f'OK: {len(s.listar_editais())} editais')"
```

### Seguranca

```bash
# Instalar hooks de seguranca
python instalar_hooks_seguranca.py

# Rotacionar credenciais (interativo)
python rotacionar_credenciais.py

# Verificar GitHub Secrets
gh secret list
```

### Verificacao de Status

```bash
# Contar editais no banco
python -c "from supabase_repository import SupabaseRepository; r = SupabaseRepository(); print(f'Editais: {r.contar_editais()}')"

# Listar ultimas execucoes
python -c "
from supabase_repository import SupabaseRepository
r = SupabaseRepository()
resp = r.client.table('execucoes_miner').select('*').order('execution_start', desc=True).limit(5).execute()
for e in resp.data:
    print(f\"[{e['status']}] {e['versao_miner']} - {e.get('editais_novos', 0)} novos\")
"

# Listar arquivos no Storage
python -c "
from supabase_storage import SupabaseStorageRepository
s = SupabaseStorageRepository()
editais = s.listar_editais()
print(f'Editais no Storage: {len(editais)}')
"
```

### EMERGENCIA

```bash
# Desligar Supabase
python desligar_supabase.py

# Reativar Supabase
python reativar_supabase.py
```

---

## Erros Encontrados e Correcoes

### Erro 1: Bucket nao encontrado

**Quando:** Primeiro teste do Storage
**Erro:**
```
{'statusCode': 404, 'error': 'Bucket not found'}
```
**Causa:** Bucket `editais-pdfs` nao existia no Supabase
**Solucao:** Criar bucket manualmente no Dashboard:
1. Supabase Dashboard -> Storage -> New bucket
2. Nome: `editais-pdfs`
3. Public: No (privado)
4. File size limit: 50MB

### Erro 2: Violacao de constraint check_uf

**Quando:** Insercao de editais no PostgreSQL
**Erro:**
```
new row for relation "editais_leilao" violates check constraint "check_uf"
```
**Causa:** API PNCP retornando UF vazia ou com espacos ("  " ao inves de "RS")
**Solucao:** Validacao em `supabase_repository.py`:
```python
uf_raw = str(edital.get("uf", "") or "").strip().upper()
if len(uf_raw) == 2 and uf_raw.isalpha():
    uf = uf_raw
else:
    uf = "XX"  # Fallback
```
**Commit:** `4deadc2 fix: Handle empty/invalid UF values in edital mapping`

### Erro 3: Rate limiting da API PNCP

**Quando:** Apos ~9 termos de busca
**Erro:**
```
API returned status 429 (Too Many Requests)
```
**Causa:** Limite de requisicoes da API PNCP
**Solucao:** Nao e erro critico, sistema continua na proxima execucao
**Mitigacao:** `JANELA_TEMPORAL_HORAS=24` reduz requisicoes repetidas

### Erro 4: Credenciais expostas no Git

**Quando:** Auditoria de seguranca (16/01/2026)
**Erro:** Credenciais hardcoded em arquivos versionados
**Causa:** Senha do banco e service key commitadas por engano
**Solucao:**
1. Remover credenciais dos arquivos (9 arquivos corrigidos)
2. Rotacionar todas as credenciais no Supabase
3. Atualizar GitHub Secrets
4. Instalar pre-commit hook para prevenir futuros vazamentos
**Commit:** `dd57120 security: Remove exposed credentials and add protection mechanisms`

---

## Commits Importantes

| Hash | Data | Descricao |
|------|------|-----------|
| `dd57120` | 16/01/2026 | **security:** Remove exposed credentials and add protection mechanisms |
| `6642d33` | 16/01/2026 | docs: Comprehensive CLAUDE.md update with V11 cloud architecture |
| `4deadc2` | 16/01/2026 | fix: Handle empty/invalid UF values in edital mapping |
| `11ac508` | 16/01/2026 | feat: Add 100% cloud architecture with Supabase Storage and GitHub Actions |
| `a639ebd` | 16/01/2026 | feat: Add Miner V10 with Supabase integration |
| `ac0a52f` | 16/01/2026 | docs: Add .env.example and resolve documentation gaps |

---

## Checklist para Nova Sessao Claude

**SEMPRE execute no inicio de uma nova sessao:**

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

**Se algum falhar:**
- Workflow falhou -> `gh run view <ID> --log` para ver erro
- Supabase nao conecta -> Verificar .env ou secrets
- Storage nao conecta -> Verificar bucket existe no Dashboard

---

## Troubleshooting

### Workflow nao executa no horario

```
Problema: Cron nao disparou as 00:00 UTC
Causa: GitHub Actions tem delay de ate 15 minutos
Solucao: Normal, aguardar ou disparar manualmente
```

### Erro de autenticacao no Storage

```
Problema: "Invalid API key" no upload
Causa: SUPABASE_SERVICE_KEY incorreta ou expirada
Solucao:
  1. Verificar secret no GitHub: gh secret list
  2. Rotacionar credenciais: python rotacionar_credenciais.py
  3. Atualizar GitHub Secret: gh secret set SUPABASE_SERVICE_KEY
```

### Pre-commit bloqueou meu commit

```
Problema: "COMMIT BLOQUEADO: Secrets detectados!"
Causa: Voce tentou commitar um arquivo com credenciais
Solucao:
  1. Remova as credenciais do arquivo
  2. Use variaveis de ambiente (.env)
  3. Tente commitar novamente
  4. NUNCA use --no-verify para bypass
```

### Miner retorna 0 editais novos

```
Problema: "Editais novos: 0"
Causa: Todos editais ja estao no checkpoint
Solucao:
  1. Verificar checkpoint: cat .ache_sucatas_checkpoint.json
  2. Se teste: deletar checkpoint e re-executar
  3. Se producao: normal, nao ha editais novos
```

### Auditor nao processa editais

```
Problema: "Nenhum edital pendente"
Causa: Todos editais ja tem processado_auditor=true
Solucao:
  1. Verificar no banco: SELECT COUNT(*) FROM editais_leilao WHERE processado_auditor = false
  2. Se necessario resetar: UPDATE editais_leilao SET processado_auditor = false
```

---

## API PNCP

### Endpoints Utilizados

| Endpoint | Metodo | Uso |
|----------|--------|-----|
| `/contratacoes/publicacao` | GET | Lista editais |
| `/pncp-api/v1/orgaos/{cnpj}/compras/{ano}/{seq}/arquivos` | GET | Lista arquivos |

### Filtros Usados

```
modalidadeId=8         # Leilao
dataPublicacaoFim      # Data limite
dataPublicacaoInicio   # Data inicio
pagina                 # Paginacao
tamanhoPagina=500      # Maximo por pagina
```

### Rate Limiting

- **Limite:** Nao documentado (~100 req/min estimado)
- **Erro:** HTTP 429 Too Many Requests
- **Mitigacao:** Janela temporal de 24h reduz requisicoes

### Documentacao

- Swagger: https://pncp.gov.br/api/consulta/swagger-ui/index.html

---

## Dividas Tecnicas

### Alta Prioridade

| Item | Descricao | Esforco |
|------|-----------|---------|
| Migrar 198 editais locais | Upload dos editais ja baixados para Storage | Medio |
| Notificacao de falha | Implementar email/webhook quando workflow falha | Baixo |
| Retry com backoff | Implementar retry exponencial para API PNCP | Medio |

### Media Prioridade

| Item | Descricao | Esforco |
|------|-----------|---------|
| Dashboard de metricas | Visualizar status do sistema | Alto |
| API REST | Endpoint para consultar editais | Alto |
| Testes unitarios | Cobertura para Storage e Repository | Medio |
| Monitoramento de custos | Alerta quando Storage > 500MB | Baixo |

### Baixa Prioridade

| Item | Descricao | Esforco |
|------|-----------|---------|
| Limpeza de editais antigos | Remover editais > 1 ano | Baixo |
| Compressao de PDFs | Reduzir tamanho no Storage | Medio |
| Multi-regiao | Backup em regiao diferente | Alto |

---

## GitHub

- **Repo:** https://github.com/thiagodiasdigital/ache-sucatas-v13
- **Visibilidade:** Privado
- **Branch principal:** master
- **Actions:** https://github.com/thiagodiasdigital/ache-sucatas-v13/actions
- **Secrets:** 2 configurados (SUPABASE_URL, SUPABASE_SERVICE_KEY)

---

## Dependencias Python

Instalar com: `pip install -r requirements.txt`

| Pacote | Versao | Uso |
|--------|--------|-----|
| pdfplumber | >=0.9.0 | Parsing de PDFs |
| pandas | >=2.0.0 | Manipulacao de dados |
| openpyxl | >=3.1.0 | Exportacao Excel |
| supabase | >=2.0.0 | Cliente Supabase |
| python-dotenv | >=1.0.0 | Variaveis de ambiente |
| requests | >=2.31.0 | HTTP requests |
| aiohttp | >=3.9.0 | HTTP async |
| aiofiles | >=23.0.0 | I/O async |
| pydantic | >=2.0.0 | Validacao de dados |
| python-docx | >=1.0.0 | Parsing de DOCX |

---

## Notas Importantes

1. **NUNCA commitar `.env`** - contem credenciais Supabase
2. **Pre-commit hook ativo** - bloqueia commits com secrets
3. **Credenciais rotacionadas** - em 16/01/2026 22:41 UTC
4. **ACHE_SUCATAS_DB/** esta no .gitignore (PDFs muito grandes, legado)
5. **Limite de $50 USD** aprovado para Supabase
6. **Sistema 100% cloud** - nao precisa mais de PC local ligado
7. **Execucao automatica 3x/dia** - 00:00, 08:00, 16:00 UTC
8. **GitHub Secrets configurados** - nao precisa .env no workflow
9. **Bucket `editais-pdfs`** ja criado e funcionando
10. **UF invalida vira "XX"** - nao bloqueia por dados ruins

---

## Historico de Auditorias de Seguranca

| Data | Tipo | Resultado | Acoes |
|------|------|-----------|-------|
| 16/01/2026 | Completa | 3 vulnerabilidades criticas | Credenciais rotacionadas, hooks instalados |

---

## Contato

- **Repositorio:** https://github.com/thiagodiasdigital/ache-sucatas-v13
- **Issues:** https://github.com/thiagodiasdigital/ache-sucatas-v13/issues

---

> Documento gerado e mantido pelo Claude Code
> Ultima atualizacao: 16/01/2026 22:48 UTC
