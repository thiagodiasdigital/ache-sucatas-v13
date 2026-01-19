# CLAUDE_FULL_5.md - Seguranca e Configuracao

> **Auditoria:** Realizada em 2026-01-16 | **Pre-commit hook:** Ativo

---

## Navegacao da Documentacao

| # | Arquivo | Conteudo |
|---|---------|----------|
| 1 | [CLAUDE_FULL_1.md](./CLAUDE_FULL_1.md) | Estado atual, Frontend React, Hotfixes |
| 2 | [CLAUDE_FULL_2.md](./CLAUDE_FULL_2.md) | Arquitetura e Fluxos |
| 3 | [CLAUDE_FULL_3.md](./CLAUDE_FULL_3.md) | CI/CD, Testes, Workflows |
| 4 | [CLAUDE_FULL_4.md](./CLAUDE_FULL_4.md) | Banco de Dados e API PNCP |
| **5** | **CLAUDE_FULL_5.md** (este) | Seguranca e Configuracao |
| 6 | [CLAUDE_FULL_6.md](./CLAUDE_FULL_6.md) | Operacoes e Historico |

---

## Auditoria de Seguranca (2026-01-16)

Uma auditoria completa de seguranca foi realizada e todas vulnerabilidades foram corrigidas.

### Vulnerabilidades Encontradas e Corrigidas

| Severidade | Vulnerabilidade | Arquivo | Status |
|------------|-----------------|---------|--------|
| CRITICA | Senha do banco hardcoded | `executar_schema_postgresql.py` | CORRIGIDA |
| CRITICA | Service key exposta | `CLAUDE.md` (versao antiga) | CORRIGIDA |
| CRITICA | URL do projeto exposta | 7 arquivos | CORRIGIDA |
| ALTA | Credenciais no historico Git | Historico | MITIGADA (rotacao) |

### Acoes Tomadas

1. **Remocao de credenciais** - 9 arquivos corrigidos manualmente
2. **Rotacao de credenciais** - Service key e senha do banco regeneradas no Supabase
3. **Pre-commit hook** - Bloqueia automaticamente commits com secrets
4. **Scripts de seguranca** - Ferramentas para rotacao e instalacao de hooks
5. **.gitignore reforcado** - 96 linhas com padroes de seguranca

---

## Pre-commit Hook

O hook `.githooks/pre-commit` bloqueia commits contendo:

| Padrao Detectado | Descricao |
|------------------|-----------|
| Chaves Supabase | Variaveis SERVICE_KEY ou DB_PASSWORD com valores |
| Prefixos sb_secret | Tokens que iniciam com prefixo de secret Supabase |
| URLs PostgreSQL | Conexoes com usuario:senha no Supabase |
| Tokens JWT | Strings iniciando com eyJ seguido de 20+ caracteres |
| Credenciais em codigo | Atribuicoes de password, secret ou api_key em strings |

**Arquivos ignorados pelo hook:**
- `.env.example` (usa placeholders)
- `rotacionar_credenciais.py` (documentacao)
- `.githooks/pre-commit` (auto-referencia)

---

## Protecoes Ativas

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

---

## Como Rotacionar Credenciais

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

---

## Como Instalar Hooks de Seguranca

```bash
# Executar uma vez apos clonar o repositorio
python instalar_hooks_seguranca.py

# Verificar se foi instalado
git config core.hooksPath
# Deve retornar: .githooks
```

---

## Freios de Seguranca (Custos)

| Protecao | Limite | Proposito |
|----------|--------|-----------|
| MAX_EDITAIS_SUPABASE | 10.000 registros | Evitar estouro do free tier |
| Custo maximo aprovado | $50 USD | Budget definido |
| ENABLE_SUPABASE | true/false | Desativar integracao |
| ENABLE_SUPABASE_STORAGE | true/false | Desativar Storage |
| MIN_SCORE_TO_DOWNLOAD | 30 | So baixa editais relevantes |
| Kill switch | `desligar_supabase.py` | Desliga tudo imediatamente |

---

## Estimativa de Custos Atual

| Servico | Free Tier | Uso Atual | % Usado |
|---------|-----------|-----------|---------|
| Supabase DB | 500 MB | ~5 MB | 1% |
| Supabase Storage | 1 GB | ~50 MB | 5% |
| GitHub Actions | 2000 min/mes | ~180 min/mes | 9% |
| Gmail SMTP | Ilimitado | ~0 emails/mes | 0% |
| **TOTAL** | - | - | **$0/mes** |

---

## Variaveis de Ambiente

### Arquivo .env (Local - NUNCA COMMITAR)

```env
# ============================================
# SUPABASE (OBRIGATORIO - CONFIDENCIAL)
# ============================================
SUPABASE_URL=https://SEU_PROJETO.supabase.co
SUPABASE_KEY=<sua_service_key_aqui>
SUPABASE_DBPASS=<sua_senha_do_banco_aqui>

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

---

## GitHub Secrets (Configurados)

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
# Cole: sua_service_key_jwt_aqui

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
|-- frontend/                          # Dashboard React
|   |-- src/
|   +-- supabase/week2_schema.sql
|
|-- antes-dia-15-01-26/                # Backup de versoes antigas (gitignore)
|
|-- ACHE_SUCATAS_DB/                   # PDFs locais legados (gitignore)
|
|-- logs/                              # Logs de execucao (gitignore)
|
|-- .env                               # CREDENCIAIS (gitignore)
|-- .env.example                       # Template documentado
|-- .gitignore                         # 96 linhas de protecao
|-- requirements.txt                   # Dependencias Python
|-- ruff.toml                          # Config linter
|-- pytest.ini                         # Config pytest
+-- [scripts *.py]                     # Scripts do projeto
```

---

## Scripts de Seguranca

| Arquivo | Funcao | Quando usar |
|---------|--------|-------------|
| `rotacionar_credenciais.py` | Guia interativo para rotacionar credenciais | Apos vazamento ou periodicamente |
| `instalar_hooks_seguranca.py` | Instala pre-commit hook | Uma vez por clone |
| `.githooks/pre-commit` | Bloqueia commits com secrets | Automatico |
| `desligar_supabase.py` | KILL SWITCH - desativa Supabase | EMERGENCIA |
| `reativar_supabase.py` | Reativa Supabase | Apos emergencia resolvida |
| `monitorar_uso_supabase.py` | Monitor de uso com alertas | Debug/monitoramento |

---

## Informacoes do Repositorio

| Propriedade | Valor |
|-------------|-------|
| URL | https://github.com/thiagodiasdigital/ache-sucatas-v13 |
| Visibilidade | Privado |
| Branch principal | master |
| Actions | https://github.com/thiagodiasdigital/ache-sucatas-v13/actions |
| Secrets configurados | 4 |
| Email de notificacao | thiagodias180986@gmail.com |

---

## Dependencias Python

Instalar com: `pip install -r requirements.txt`

| Pacote | Versao | Uso |
|--------|--------|-----|
| pdfplumber | >=0.10.0 | Parsing de PDFs |
| pandas | >=2.0.0 | Manipulacao de dados |
| openpyxl | >=3.1.0 | Exportacao Excel |
| supabase | >=2.0.0 | Cliente Supabase |
| pydantic | >=2.0.0 | Validacao de dados |
| python-dotenv | >=1.0.0 | Variaveis de ambiente |
| requests | >=2.31.0 | HTTP requests |
| aiohttp | >=3.9.0 | HTTP async |
| aiofiles | >=23.0.0 | I/O async |

### Dependencias de Desenvolvimento

| Pacote | Versao | Uso |
|--------|--------|-----|
| ruff | >=0.1.0 | Linting Python |
| pytest | >=7.0.0 | Testes unitarios |

---

> Anterior: [CLAUDE_FULL_4.md](./CLAUDE_FULL_4.md) | Proximo: [CLAUDE_FULL_6.md](./CLAUDE_FULL_6.md)
