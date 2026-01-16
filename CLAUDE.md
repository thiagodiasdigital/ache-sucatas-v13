# CLAUDE.md - Contexto do Projeto ACHE SUCATAS

> **Última atualização:** 16/01/2026 21:25 UTC
> **Versão atual:** V11 (Cloud-Native)
> **Status:** 100% Operacional na Nuvem

---

## Visão Geral

**ACHE SUCATAS DaaS** - Sistema de coleta e análise de editais de leilão público do Brasil.
- Coleta dados da API PNCP (Portal Nacional de Contratações Públicas)
- Faz download e parsing de PDFs de editais
- Extrai informações estruturadas (título, data, valores, itens, etc.)
- Persiste no Supabase PostgreSQL
- **PDFs armazenados no Supabase Storage (cloud)**
- **Execução automatizada via GitHub Actions**

---

## Escopo do Projeto

### Objetivo de Negócio
Criar um banco de dados estruturado de **leilões públicos municipais** do Brasil, focando em:
- Veículos e máquinas inservíveis
- Sucatas e materiais recicláveis
- Bens móveis de prefeituras

### Público-Alvo
- Empresas de reciclagem e sucata
- Compradores de leilões públicos
- Analistas de mercado de leilões

### Fontes de Dados
1. **API PNCP** - Metadados dos editais (título, órgão, datas, links)
2. **PDFs dos Editais** - Detalhes extraídos (itens, valores, leiloeiro)

### Fora do Escopo (por enquanto)
- Leilões federais e estaduais
- Leilões de imóveis
- Integração com sistemas de leiloeiros
- Interface web/dashboard

---

## Roadmap

### Fase 1 - Coleta (CONCLUÍDA)
- [x] Miner V9 coletando da API PNCP
- [x] Download automático de PDFs
- [x] 198 editais coletados inicialmente

### Fase 2 - Extração (CONCLUÍDA)
- [x] Auditor V13 extraindo dados dos PDFs
- [x] 14 campos estruturados
- [x] Score de qualidade calculado

### Fase 3 - Persistência (CONCLUÍDA)
- [x] Supabase configurado
- [x] Freios de segurança ativos
- [x] Miner V10 com integração Supabase (16/01/2026)

### Fase 4 - Cloud Native (CONCLUÍDA - 16/01/2026)
- [x] **Miner V11** - Upload de PDFs para Supabase Storage
- [x] **Auditor V14** - Lê PDFs do Storage (não mais local)
- [x] **supabase_storage.py** - Repositório Storage
- [x] **GitHub Actions** - Automação 3x/dia (cron)
- [x] **GitHub Secrets** - Configurados (SUPABASE_URL, SUPABASE_SERVICE_KEY)
- [x] **Primeiro workflow executado com sucesso** (16/01/2026 21:23 UTC)

### Fase 5 - Expansão (FUTURO)
- [ ] Dashboard de visualização
- [ ] API REST para consultas
- [ ] Alertas de novos editais (email/webhook)
- [ ] Migração dos 198 editais locais para Storage

---

## Arquitetura

### Arquitetura V11 - 100% Cloud (ATUAL)

```
┌─────────────────────────────────────────────────────────┐
│                   GITHUB ACTIONS                        │
│              (Cron: 00:00, 08:00, 16:00 UTC)           │
│              (21:00, 05:00, 13:00 BRT)                 │
├─────────────────────────────────────────────────────────┤
│                                                         │
│   ┌─────────────┐         ┌─────────────┐              │
│   │  Miner V11  │────────▶│ Auditor V14 │              │
│   │  (coleta)   │         │  (extração) │              │
│   │   ~55s      │         │    ~33s     │              │
│   └──────┬──────┘         └──────┬──────┘              │
│          │                       │                      │
│   ┌──────┴──────┐         ┌──────┴──────┐              │
│   │ Verificação │         │  Notificar  │              │
│   │   Final     │         │   Falha     │              │
│   │   ~29s      │         │ (se erro)   │              │
│   └─────────────┘         └─────────────┘              │
│                                                         │
└──────────┬───────────────────────┬──────────────────────┘
           │                       │
           ▼                       ▼
    ┌─────────────────────────────────────┐
    │           SUPABASE                   │
    │  ┌─────────────┐  ┌──────────────┐  │
    │  │   Storage   │  │  PostgreSQL  │  │
    │  │   (PDFs)    │  │  (metadados) │  │
    │  │ editais-pdfs│  │editais_leilao│  │
    │  └─────────────┘  └──────────────┘  │
    └─────────────────────────────────────┘
```

**Fluxo do Miner V11 (Cloud):**
1. Coleta editais da API PNCP (janela temporal: 24h)
2. Calcula score de relevância (MIN_SCORE: 30)
3. Download do PDF em memória (bytes)
4. Upload PDF para Supabase Storage (`editais-pdfs/{pncp_id}/`)
5. Upload metadados.json para Storage
6. Insere metadados no PostgreSQL (com validação de UF)
7. Registra execução em `execucoes_miner`
8. Checkpoint para deduplicação

**Fluxo do Auditor V14 (Cloud):**
1. Query editais pendentes no PostgreSQL (`processado_auditor = false`)
2. Download PDF do Storage → BytesIO
3. `pdfplumber.open(BytesIO)` → extrai texto
4. Processa com funções de extração V13
5. Update no PostgreSQL com dados extraídos
6. Marca `processado_auditor = true`

### Arquitetura Legada (V10 - Local)

```
┌─────────────┐     ┌─────────────┐     ┌─────────────┐
│ Miner V10   │────▶│   Local     │────▶│ Auditor V13 │
│  (coleta)   │     │  (PDFs)     │     │  (parsing)  │
└──────┬──────┘     └─────────────┘     └──────┬──────┘
       │                                       │
       ▼                                       ▼
  ┌─────────────────────────────────────────────┐
  │              Supabase PostgreSQL             │
  └─────────────────────────────────────────────┘
```

---

## Arquivos Principais

### Scripts de Produção (V11 - Cloud) - ATUAIS

| Arquivo | Função | Criado em |
|---------|--------|-----------|
| `ache_sucatas_miner_v11.py` | **Miner V11** - coleta 100% cloud (Storage) | 16/01/2026 |
| `cloud_auditor_v14.py` | **Auditor V14** - extrai PDFs do Storage | 16/01/2026 |
| `supabase_storage.py` | Repositório Supabase Storage (upload/download) | 16/01/2026 |
| `supabase_repository.py` | Repositório Supabase PostgreSQL | 15/01/2026 |
| `.github/workflows/ache-sucatas.yml` | GitHub Actions (cron 3x/dia) | 16/01/2026 |

### Scripts Legados (V10 - Local)

| Arquivo | Função | Status |
|---------|--------|--------|
| `ache_sucatas_miner_v10.py` | Miner V10 - coleta + Supabase (local backup) | Legado |
| `local_auditor_v13.py` | Auditor V13 - lê PDFs locais | Legado |
| `migrar_v13_robusto.py` | Script de migração em lote | Legado |
| `ache_sucatas_miner_v9_cron.py` | Miner V9 (sem Supabase) | Descontinuado |

### Scripts de Segurança

| Arquivo | Função |
|---------|--------|
| `desligar_supabase.py` | KILL SWITCH - desativa Supabase imediatamente |
| `reativar_supabase.py` | Reativa Supabase após desligamento |
| `monitorar_uso_supabase.py` | Monitor de uso com alertas |
| `testar_freio_seguranca.py` | Testa limite de 10.000 editais |

### Configuração

| Arquivo | Função |
|---------|--------|
| `.env` | Credenciais locais (NUNCA versionar!) |
| `.env.example` | Template de credenciais |
| `schemas_v13_supabase.sql` | Schema das tabelas Supabase |
| `.gitignore` | Proteções de arquivos sensíveis |
| `requirements.txt` | Dependências Python |

---

## Estrutura de Pastas

```
testes-12-01-17h/
├── .github/
│   └── workflows/
│       └── ache-sucatas.yml      # GitHub Actions workflow
├── ACHE_SUCATAS_DB/              # PDFs locais (legado, não versionado)
│   ├── AL_MACEIO/
│   └── ...
├── logs/                          # Logs de execução
├── .env                           # CREDENCIAIS (não versionado)
├── .env.example                   # Template de credenciais
├── ache_sucatas_miner_v11.py     # Miner cloud-native
├── cloud_auditor_v14.py          # Auditor cloud-native
├── supabase_storage.py           # Storage repository
├── supabase_repository.py        # PostgreSQL repository
└── *.py                          # Outros scripts
```

### Estrutura no Supabase Storage

```
editais-pdfs/                      # Bucket principal
├── 18188243000160-1-000161-2025/  # Pasta por pncp_id
│   ├── metadados.json
│   ├── edital_a1b2c3d4.pdf
│   └── anexo_e5f6g7h8.xlsx
├── 00394460005887-1-000072-2025/
│   └── ...
└── [outros editais]/
```

---

## Variáveis de Ambiente

### .env (Local - NÃO VERSIONAR)

```env
# ============================================
# SUPABASE (CONFIDENCIAL)
# ============================================
SUPABASE_URL=https://SEU_PROJECT_ID.supabase.co
SUPABASE_SERVICE_KEY=sua_service_key_aqui
SUPABASE_DB_PASSWORD=sua_senha_do_banco_aqui

# ============================================
# PNCP API (PÚBLICO)
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

### GitHub Secrets (Configurados em 16/01/2026)

| Secret | Descrição | Configurado |
|--------|-----------|-------------|
| `SUPABASE_URL` | URL do projeto Supabase | 16/01/2026 21:21:31Z |
| `SUPABASE_SERVICE_KEY` | Service role key | 16/01/2026 21:21:39Z |

**Como configurar secrets (se necessário):**
```bash
# Via GitHub CLI (já autenticado)
echo "https://xxx.supabase.co" | gh secret set SUPABASE_URL
echo "sb_secret_xxx" | gh secret set SUPABASE_SERVICE_KEY

# Verificar secrets configurados
gh secret list
```

---

## Supabase - Tabelas

### 1. editais_leilao

| Campo | Tipo | Descrição |
|-------|------|-----------|
| id | SERIAL | PK auto-incremento |
| pncp_id | TEXT UNIQUE | ID único do PNCP |
| titulo | TEXT | Título do edital |
| orgao | TEXT | Órgão responsável |
| municipio | TEXT | Cidade |
| uf | CHAR(2) | Estado (CHECK constraint) |
| data_publicacao | TIMESTAMP | Data de publicação |
| data_leilao | TIMESTAMP | Data do leilão |
| valor_estimado | DECIMAL | Valor estimado |
| link_pncp | TEXT | Link no PNCP |
| link_leiloeiro | TEXT | Link do leiloeiro |
| nome_leiloeiro | TEXT | Nome do leiloeiro |
| quantidade_itens | INTEGER | Qtd de itens |
| descricao | TEXT | Descrição extraída |
| score | INTEGER | Score de qualidade |
| **storage_path** | TEXT | Caminho no Storage |
| **pdf_storage_url** | TEXT | URL pública do PDF |
| processado_auditor | BOOLEAN | Flag de processamento |
| created_at | TIMESTAMP | Data de criação |
| updated_at | TIMESTAMP | Data de atualização |

### 2. execucoes_miner

| Campo | Tipo | Descrição |
|-------|------|-----------|
| id | SERIAL | PK |
| versao_miner | TEXT | Versão do miner (V11) |
| execution_start | TIMESTAMP | Início da execução |
| execution_end | TIMESTAMP | Fim da execução |
| status | TEXT | RUNNING/SUCCESS/FAILED |
| editais_novos | INTEGER | Novos coletados |
| downloads | INTEGER | Downloads realizados |
| storage_uploads | INTEGER | Uploads no Storage |
| supabase_inserts | INTEGER | Inserts no banco |

### 3. metricas_diarias

| Campo | Tipo | Descrição |
|-------|------|-----------|
| id | SERIAL | PK |
| data | DATE UNIQUE | Data da métrica |
| total_editais | INTEGER | Total acumulado |
| novos_editais | INTEGER | Novos no dia |
| execucoes | INTEGER | Qtd de execuções |

---

## Comandos Úteis

### Execução Cloud (V11 - Recomendado)

```bash
# Disparar workflow manualmente
gh workflow run ache-sucatas.yml

# Verificar status do workflow
gh run list --workflow=ache-sucatas.yml --limit 3

# Acompanhar execução em tempo real
gh run watch <RUN_ID>

# Ver logs de uma execução
gh run view <RUN_ID> --log
```

### Execução Local (Debug/Testes)

```bash
# Miner V11 (cloud storage)
python ache_sucatas_miner_v11.py

# Auditor V14 (cloud storage)
python cloud_auditor_v14.py

# Testar conexão Storage
python -c "
from supabase_storage import SupabaseStorageRepository
s = SupabaseStorageRepository()
print(s.testar_conexao())
"
```

### Verificação de Status

```bash
# Contar editais no banco
python -c "from supabase_repository import SupabaseRepository; r = SupabaseRepository(); print(f'Editais: {r.contar_editais()}')"

# Listar últimas execuções
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

### EMERGÊNCIA

```bash
# Desligar Supabase
python desligar_supabase.py

# Reativar Supabase
python reativar_supabase.py
```

---

## Freios de Segurança

| Proteção | Limite | Status |
|----------|--------|--------|
| MAX_EDITAIS_SUPABASE | 10.000 registros | Ativo |
| Custo máximo aprovado | $50 USD | Ativo |
| Feature flag ENABLE_SUPABASE | true/false | Ativo |
| Feature flag ENABLE_SUPABASE_STORAGE | true/false | Ativo |
| Kill switch | `desligar_supabase.py` | Disponível |
| MIN_SCORE_TO_DOWNLOAD | 30 (editais relevantes) | Ativo |

### Estimativa de Custos (Free Tier)

| Serviço | Free Tier | Uso Atual | Status |
|---------|-----------|-----------|--------|
| Supabase DB | 500MB | ~5MB | OK |
| Supabase Storage | 1GB | ~50MB | OK |
| GitHub Actions | 2000 min/mês | ~6 min/dia (~180 min/mês) | OK |
| **TOTAL** | - | - | **$0/mês** |

---

## Status Atual (16/01/2026)

### Sistema 100% Operacional

| Componente | Status | Última Execução |
|------------|--------|-----------------|
| Miner V11 | ✓ Funcionando | 16/01/2026 21:23 UTC |
| Auditor V14 | ✓ Funcionando | 16/01/2026 21:24 UTC |
| Supabase Storage | ✓ Conectado | Bucket: editais-pdfs |
| Supabase PostgreSQL | ✓ Conectado | 6 editais |
| GitHub Actions | ✓ Configurado | Cron ativo 3x/dia |
| GitHub Secrets | ✓ Configurados | 2 secrets |

### Métricas do Último Teste (16/01/2026)

```
Editais analisados: 20
Editais novos: 20
Downloads: 59 (100% sucesso)
Storage uploads: 79 (0 erros)
Supabase inserts: 20 (0 erros)
Tempo total: ~71 segundos
```

### Workflow GitHub Actions (Primeiro Teste)

| Job | Status | Tempo |
|-----|--------|-------|
| Miner V11 - Coleta | ✓ Sucesso | 55s |
| Auditor V14 - Processamento | ✓ Sucesso | 33s |
| Verificação Final | ✓ Sucesso | 29s |
| Notificar Falha | - Pulado | N/A |
| **Total** | ✓ **Sucesso** | **~2 min** |

---

## Implementações Realizadas (16/01/2026)

### 1. supabase_storage.py (NOVO)

**Propósito:** Gerenciar uploads/downloads no Supabase Storage

**Métodos implementados:**
```python
class SupabaseStorageRepository:
    def __init__(self, bucket_name: str = "editais-pdfs")

    # Upload
    def upload_file(path: str, file_data: bytes, content_type: str) -> str
    def upload_pdf(pncp_id: str, filename: str, pdf_bytes: bytes) -> str
    def upload_json(pncp_id: str, data: dict) -> str

    # Download
    def download_file(path: str) -> bytes
    def download_pdf(path: str) -> BytesIO
    def download_json(path: str) -> dict

    # Listagem
    def listar_editais() -> List[str]
    def listar_arquivos(pncp_id: str) -> List[str]
    def arquivo_existe(path: str) -> bool

    # Utilitários
    def get_public_url(path: str) -> str
    def testar_conexao() -> dict
```

### 2. ache_sucatas_miner_v11.py (NOVO)

**Propósito:** Miner 100% cloud-native

**Diferenças do V10:**
| Aspecto | V10 | V11 |
|---------|-----|-----|
| Storage de PDFs | Local (ACHE_SUCATAS_DB/) | Supabase Storage |
| Metadados | JSON local | JSON no Storage |
| Backup local | Obrigatório | Opcional (flag) |
| Execução | PC local | GitHub Actions |

**Fluxo principal:**
```python
async def _download_and_upload_files(self, files, pncp_id):
    for file in files:
        # 1. Download em memória
        pdf_bytes = await self._download_file_bytes(url)

        # 2. Upload para Storage
        storage_url = self.storage.upload_pdf(pncp_id, filename, pdf_bytes)

        # 3. Registra URL no edital
        edital.pdf_storage_url = storage_url
```

### 3. cloud_auditor_v14.py (NOVO)

**Propósito:** Auditor que lê PDFs do Storage

**Diferenças do V13:**
| Aspecto | V13 | V14 |
|---------|-----|-----|
| Leitura de PDFs | `pdfplumber.open(Path)` | `pdfplumber.open(BytesIO)` |
| Listagem editais | `Path.glob()` | `storage.listar_editais()` |
| Metadados | `open(json_file)` | `storage.download_json()` |
| Excel/DOCX | `pd.read_excel(Path)` | `pd.read_excel(BytesIO)` |

**Fluxo principal:**
```python
def processar_edital(self, pncp_id: str):
    # 1. Download do Storage
    pdf_bytes = self.storage.download_pdf(path)

    # 2. Processar com pdfplumber
    with pdfplumber.open(BytesIO(pdf_bytes)) as pdf:
        texto = extract_text(pdf)

    # 3. Extrair dados
    dados = self.extrair_campos(texto)

    # 4. Atualizar no PostgreSQL
    self.repository.atualizar_edital(pncp_id, dados)
```

### 4. .github/workflows/ache-sucatas.yml (NOVO)

**Propósito:** Automação via GitHub Actions

**Estrutura:**
```yaml
name: ACHE SUCATAS - Coleta e Processamento

on:
  schedule:
    - cron: '0 0,8,16 * * *'  # 00:00, 08:00, 16:00 UTC
  workflow_dispatch:           # Execução manual

jobs:
  miner:                       # Job 1: Coleta
  auditor:                     # Job 2: Processamento (needs: miner)
  verify:                      # Job 3: Verificação (needs: auditor)
  notify-failure:              # Job 4: Notificação (if: failure)
```

### 5. schemas_v13_supabase.sql (ATUALIZADO)

**Novos campos adicionados:**
```sql
ALTER TABLE editais_leilao ADD COLUMN storage_path TEXT;
ALTER TABLE editais_leilao ADD COLUMN pdf_storage_url TEXT;
CREATE INDEX idx_editais_storage_path ON editais_leilao(storage_path);
```

### 6. supabase_repository.py (ATUALIZADO)

**Fix crítico: Validação de UF**

**Problema:** API PNCP retornava UF vazia/inválida, violando `check_uf` constraint

**Solução implementada:**
```python
def _mapear_edital_model_para_v13(self, edital: dict) -> dict:
    # Extrair dados básicos
    uf_raw = str(edital.get("uf", "") or "").strip().upper()

    # Validar UF: deve ter exatamente 2 letras
    if len(uf_raw) == 2 and uf_raw.isalpha():
        uf = uf_raw
    else:
        # Fallback para UF desconhecida
        uf = "XX"

    return {
        "uf": uf,
        # ... outros campos
    }
```

---

## Decisões Lógicas Tomadas

### Arquitetura

| Decisão | Motivo | Alternativa Rejeitada |
|---------|--------|----------------------|
| Supabase Storage | Free tier 1GB, integrado ao Supabase | AWS S3 (custo), Google Cloud (complexidade) |
| GitHub Actions | Free tier 2000 min, integração Git | AWS Lambda (custo), cron local (não cloud) |
| BytesIO para PDFs | Processa em memória, não precisa disco | Temp files (mais lento, cleanup) |
| Bucket único | Simplicidade, todos editais juntos | Múltiplos buckets (complexidade) |
| Pasta por pncp_id | Organização clara, fácil navegação | Flat structure (difícil manutenção) |

### Segurança

| Decisão | Motivo |
|---------|--------|
| Service role key em secrets | Nunca expor no código |
| ENABLE_SUPABASE_STORAGE flag | Permite desligar rapidamente |
| UF fallback "XX" | Não bloquear por dados inválidos da API |
| MIN_SCORE_TO_DOWNLOAD=30 | Filtrar editais irrelevantes (economia) |

### Performance

| Decisão | Motivo |
|---------|--------|
| Async downloads | Paralelismo, mais rápido |
| Checkpoint de deduplicação | Evitar reprocessar mesmos editais |
| Jobs sequenciais no workflow | Miner deve terminar antes do Auditor |

---

## Erros Encontrados e Correções

### Erro 1: Bucket não encontrado

**Quando:** Primeiro teste do Storage
**Erro:**
```
{'statusCode': 404, 'error': 'Bucket not found'}
```
**Causa:** Bucket `editais-pdfs` não existia no Supabase
**Solução:** Criar bucket manualmente no Dashboard:
1. Supabase Dashboard → Storage → New bucket
2. Nome: `editais-pdfs`
3. Public: No (privado)
4. File size limit: 50MB

### Erro 2: Violação de constraint check_uf

**Quando:** Inserção de editais no PostgreSQL
**Erro:**
```
new row for relation "editais_leilao" violates check constraint "check_uf"
```
**Causa:** API PNCP retornando UF vazia ou com espaços ("  " ao invés de "RS")
**Solução:** Validação em `supabase_repository.py`:
```python
uf_raw = str(edital.get("uf", "") or "").strip().upper()
if len(uf_raw) == 2 and uf_raw.isalpha():
    uf = uf_raw
else:
    uf = "XX"  # Fallback
```
**Commit:** `4deadc2 fix: Handle empty/invalid UF values in edital mapping`

### Erro 3: Rate limiting da API PNCP

**Quando:** Após ~9 termos de busca
**Erro:**
```
API returned status 429 (Too Many Requests)
```
**Causa:** Limite de requisições da API PNCP
**Solução:** Não é erro crítico, sistema continua na próxima execução
**Mitigação:** `JANELA_TEMPORAL_HORAS=24` reduz requisições repetidas

### Erro 4: 100% duplicados no checkpoint

**Quando:** Re-execução do Miner após teste
**Erro:**
```
Taxa de deduplicação: 100% (todos duplicados)
```
**Causa:** Checkpoint tinha IDs do teste anterior
**Solução:** Limpar checkpoint para teste limpo:
```bash
del .ache_sucatas_checkpoint.json
```

---

## Acertos e Boas Práticas

### 1. Fail-safe no Miner

O Miner V11 não trava se Supabase/Storage falhar:
- Try/except em cada operação
- Log de erros mas continua processando
- Métricas finais mostram sucesso/falha

### 2. Validação Robusta de Dados

Antes de inserir no banco:
- Validação de UF (2 letras alpha)
- Fallback para valores inválidos
- Não bloqueia por dados ruins da API

### 3. Deduplicação Eficiente

Checkpoint em JSON local/GitHub:
- Lista de pncp_ids já processados
- Evita downloads repetidos
- Mantido entre execuções

### 4. Métricas Completas

Cada execução registra:
- Duração total
- Editais analisados/novos/duplicados
- Downloads sucesso/falha
- Storage uploads/erros
- Supabase inserts/erros

### 5. Workflow Resiliente

GitHub Actions com:
- Jobs sequenciais (dependências)
- Verificação final
- Notificação de falha
- Artifacts para debug

---

## Dívidas Técnicas

### Alta Prioridade

| Item | Descrição | Esforço |
|------|-----------|---------|
| Migrar 198 editais locais | Upload dos editais já baixados para Storage | Médio |
| Notificação de falha | Implementar email/webhook quando workflow falha | Baixo |
| Retry com backoff | Implementar retry exponencial para API PNCP | Médio |

### Média Prioridade

| Item | Descrição | Esforço |
|------|-----------|---------|
| Dashboard de métricas | Visualizar status do sistema | Alto |
| API REST | Endpoint para consultar editais | Alto |
| Testes unitários | Cobertura para Storage e Repository | Médio |
| Monitoramento de custos | Alerta quando Storage > 500MB | Baixo |

### Baixa Prioridade

| Item | Descrição | Esforço |
|------|-----------|---------|
| Limpeza de editais antigos | Remover editais > 1 ano | Baixo |
| Compressão de PDFs | Reduzir tamanho no Storage | Médio |
| Multi-região | Backup em região diferente | Alto |

---

## Próximos Passos Esperados

### Imediato (Próximas 24h)

1. **Monitorar primeira execução automática** (00:00 UTC)
   ```bash
   gh run list --workflow=ache-sucatas.yml --limit 1
   ```

2. **Verificar dados no banco após execução**
   ```bash
   python -c "from supabase_repository import SupabaseRepository; r = SupabaseRepository(); print(f'Editais: {r.contar_editais()}')"
   ```

### Curto Prazo (Próxima semana)

1. **Migrar editais locais para Storage**
   - Criar script `migrar_local_para_storage.py`
   - Upload dos 198 editais existentes

2. **Configurar notificação de falha**
   - Email ou webhook quando workflow falha
   - Integrar com Slack/Discord (opcional)

### Médio Prazo (Próximo mês)

1. **Implementar retry com backoff**
   - Para rate limiting da API PNCP
   - Para falhas temporárias do Supabase

2. **Dashboard simples**
   - Usando Supabase Realtime + Next.js
   - Ou Streamlit (mais simples)

---

## API PNCP

### Endpoints Utilizados

| Endpoint | Método | Uso |
|----------|--------|-----|
| `/contratacoes/publicacao` | GET | Lista editais |
| `/pncp-api/v1/orgaos/{cnpj}/compras/{ano}/{seq}/arquivos` | GET | Lista arquivos |

### Filtros Usados

```
modalidadeId=8         # Leilão
dataPublicacaoFim      # Data limite
dataPublicacaoInicio   # Data início
pagina                 # Paginação
tamanhoPagina=500      # Máximo por página
```

### Rate Limiting

- **Limite:** Não documentado (~100 req/min estimado)
- **Erro:** HTTP 429 Too Many Requests
- **Mitigação:** Janela temporal de 24h reduz requisições

### Documentação

- Swagger: https://pncp.gov.br/api/consulta/swagger-ui/index.html

---

## Campos Extraídos dos Editais

| Campo | Fonte | Descrição | Validação |
|-------|-------|-----------|-----------|
| titulo | PDF/JSON | Título do edital | - |
| n_edital | PDF/JSON | Número do edital | - |
| orgao | JSON | Órgão responsável | - |
| municipio | JSON | Cidade do leilão | - |
| uf | JSON | Estado | 2 letras alpha ou "XX" |
| data_publicacao | JSON | Data de publicação | ISO 8601 |
| data_leilao | PDF | Data do leilão | Regex extraction |
| valor_estimado | PDF/API | Valor estimado total | Decimal |
| link_pncp | JSON | Link no PNCP | URL válida |
| link_leiloeiro | PDF | Link do leiloeiro | Regex extraction |
| nome_leiloeiro | PDF | Nome do leiloeiro | Regex extraction |
| quantidade_itens | PDF | Qtd de itens/lotes | Integer |
| descricao | PDF | Descrição extraída | Truncado 1000 chars |
| score | Calculado | Score de qualidade | 0-100 |
| storage_path | Sistema | Caminho no Storage | {pncp_id}/ |
| pdf_storage_url | Sistema | URL do PDF | Supabase URL |

---

## Troubleshooting

### Workflow não executa no horário

```
Problema: Cron não disparou às 00:00 UTC
Causa: GitHub Actions tem delay de até 15 minutos
Solução: Normal, aguardar ou disparar manualmente
```

### Erro de autenticação no Storage

```
Problema: "Invalid API key" no upload
Causa: SUPABASE_SERVICE_KEY incorreta ou expirada
Solução:
  1. Verificar secret no GitHub: gh secret list
  2. Atualizar se necessário: echo "nova_key" | gh secret set SUPABASE_SERVICE_KEY
```

### Miner retorna 0 editais novos

```
Problema: "Editais novos: 0"
Causa: Todos editais já estão no checkpoint
Solução:
  1. Verificar checkpoint: cat .ache_sucatas_checkpoint.json
  2. Se teste: deletar checkpoint e re-executar
  3. Se produção: normal, não há editais novos
```

### Auditor não processa editais

```
Problema: "Nenhum edital pendente"
Causa: Todos editais já têm processado_auditor=true
Solução:
  1. Verificar no banco: SELECT COUNT(*) FROM editais_leilao WHERE processado_auditor = false
  2. Se necessário resetar: UPDATE editais_leilao SET processado_auditor = false
```

### Storage cheio (>1GB)

```
Problema: "Storage quota exceeded"
Causa: Free tier tem limite de 1GB
Solução:
  1. Verificar uso no Dashboard Supabase
  2. Deletar editais antigos (>1 ano)
  3. Ou fazer upgrade do plano
```

---

## Checklist para Nova Sessão Claude

**SEMPRE execute no início de uma nova sessão:**

```bash
# 1. Verificar status do último workflow
gh run list --workflow=ache-sucatas.yml --limit 3

# 2. Verificar editais no banco
python -c "from supabase_repository import SupabaseRepository; r = SupabaseRepository(); print(f'Editais no banco: {r.contar_editais()}')"

# 3. Verificar conexão Storage
python -c "from supabase_storage import SupabaseStorageRepository; s = SupabaseStorageRepository(); print(s.testar_conexao())"

# 4. Verificar secrets configurados
gh secret list
```

**Se algum falhar:**
- Workflow falhou → `gh run view <ID> --log` para ver erro
- Supabase não conecta → Verificar .env ou secrets
- Storage não conecta → Verificar bucket existe no Dashboard

---

## Commits Importantes

| Hash | Data | Descrição |
|------|------|-----------|
| `a639ebd` | 16/01/2026 | feat: Add Miner V10 with Supabase integration |
| `xxxxxxx` | 16/01/2026 | feat: Add cloud-native V11 architecture |
| `4deadc2` | 16/01/2026 | fix: Handle empty/invalid UF values in edital mapping |

---

## GitHub

- **Repo:** https://github.com/thiagodiasdigital/ache-sucatas-v13
- **Visibilidade:** Privado
- **Branch principal:** master
- **Actions:** https://github.com/thiagodiasdigital/ache-sucatas-v13/actions
- **Secrets:** 2 configurados (SUPABASE_URL, SUPABASE_SERVICE_KEY)

---

## Dependências Python

Instalar com: `pip install -r requirements.txt`

| Pacote | Versão | Uso |
|--------|--------|-----|
| pdfplumber | >=0.9.0 | Parsing de PDFs |
| pandas | >=2.0.0 | Manipulação de dados |
| openpyxl | >=3.1.0 | Exportação Excel |
| supabase | >=2.0.0 | Cliente Supabase |
| python-dotenv | >=1.0.0 | Variáveis de ambiente |
| requests | >=2.31.0 | HTTP requests |
| aiohttp | >=3.9.0 | HTTP async |
| aiofiles | >=23.0.0 | I/O async |
| pydantic | >=2.0.0 | Validação de dados |
| python-docx | >=1.0.0 | Parsing de DOCX |

---

## Notas Importantes

1. **NUNCA commitar `.env`** - contém credenciais Supabase
2. **ACHE_SUCATAS_DB/** está no .gitignore (PDFs muito grandes, legado)
3. **Limite de $50 USD** aprovado para Supabase
4. **Sistema 100% cloud** - não precisa mais de PC local ligado
5. **Execução automática 3x/dia** - 00:00, 08:00, 16:00 UTC
6. **GitHub Secrets configurados** - não precisa .env no workflow
7. **Bucket `editais-pdfs`** já criado e funcionando
8. **UF inválida vira "XX"** - não bloqueia por dados ruins

---

## Contato

- **Repositório:** https://github.com/thiagodiasdigital/ache-sucatas-v13
- **Issues:** https://github.com/thiagodiasdigital/ache-sucatas-v13/issues

---

> Documento gerado e mantido pelo Claude Code
> Última atualização: 16/01/2026 21:25 UTC
