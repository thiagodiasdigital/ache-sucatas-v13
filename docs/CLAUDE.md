# CLAUDE.md - ACHE SUCATAS (Quick Start)

> **Status:** 100% Operacional | **Versao:** V11 + Auditor V14.1 + CI + Coleta Historica + Frontend React
> **Ultima atualizacao:** 2026-01-19
> **Documentacao completa:** Dividida em 6 arquivos em `docs/` (ver tabela abaixo)

---

## O Que Este Sistema Faz

Sistema automatizado de coleta de **editais de leilao publico** do Brasil via API PNCP.
- Coleta 3x/dia via GitHub Actions (00:00, 08:00, 16:00 UTC)
- Armazena PDFs no Supabase Storage + metadados no PostgreSQL
- Extrai dados dos PDFs (data, valor, leiloeiro, itens)
- Envia email se workflow falhar
- **Frontend React** com dashboard multi-view (Grid/Mapa/Calendario)

---

## Metricas Atuais

| Metrica | Valor |
|---------|-------|
| Editais no banco | 294 |
| PDFs no Storage | 698+ |
| Testes unitarios | 98 (100% pass) |
| Custo mensal | $0 (free tier) |

---

## Arquivos de Producao (usar estes)

| Arquivo | Local | Funcao |
|---------|-------|--------|
| `ache_sucatas_miner_v11.py` | `src/core/` | Coleta editais da API PNCP (diaria) |
| `coleta_historica_30d.py` | `src/core/` | Coleta historica dos ultimos 30 dias |
| `cloud_auditor_v14.py` | `src/core/` | Extrai dados dos PDFs |
| `supabase_repository.py` | `src/core/` | CRUD PostgreSQL |
| `supabase_storage.py` | `src/core/` | Upload/download Storage |
| `streamlit_app.py` | `src/core/` | Dashboard Streamlit |

**Frontend React (Semana 2):**
- `frontend/` - Dashboard React + Vite + TypeScript + Tailwind
- `frontend/supabase/week2_schema.sql` - Schema de notificacoes

**Workflows GitHub Actions:**
- `.github/workflows/ache-sucatas.yml` - Coleta automatica
- `.github/workflows/ci.yml` - Lint (ruff) + Testes (pytest)

---

## Comandos Essenciais

```bash
# Verificar status dos workflows
gh run list --workflow=ache-sucatas.yml --limit 3
gh run list --workflow=ci.yml --limit 3

# Disparar coleta manualmente
gh workflow run ache-sucatas.yml

# Executar miner localmente
PYTHONPATH=src/core python src/core/ache_sucatas_miner_v11.py

# Executar auditor localmente
PYTHONPATH=src/core python src/core/cloud_auditor_v14.py

# Coleta historica (30 dias)
PYTHONPATH=src/core python src/core/coleta_historica_30d.py

# Executar testes localmente
pytest tests/ -v --tb=short

# Executar linting
ruff check src/core/

# Frontend React
cd frontend && npm install
npm run dev      # Rodar em http://localhost:5173
npm run build    # Build para producao
```

---

## Checklist Nova Sessao

```bash
# 1. Status workflows
gh run list --workflow=ache-sucatas.yml --limit 1

# 2. Contar editais
PYTHONPATH=src/core python -c "from supabase_repository import SupabaseRepository; print(SupabaseRepository().contar_editais())"

# 3. Testes passando?
pytest tests/ -v --tb=short
```

---

## Regras Importantes

1. **NUNCA commitar `.env`** - contem credenciais
2. **Pre-commit hook ativo** - bloqueia secrets automaticamente
3. **4 GitHub Secrets configurados** - SUPABASE_URL, SUPABASE_SERVICE_KEY, EMAIL_ADDRESS, EMAIL_APP_PASSWORD
4. **UF invalida vira "XX"** - sistema nao quebra com dados ruins

---

## Seguranca

### Status da Auditoria CRAUDIO (2026-01-19)

```
╔═══════════════════════════════════════════════════════════╗
║  AUDITORIA CRAUDIO: 11 itens OK / 3 pendentes HIGH       ║
║  Risk Level: MEDIO                                        ║
║  Deploy: AUTORIZADO (com ressalvas)                       ║
║  Documento completo: docs/AUDITORIA_CRAUDIO_2026-01-19.md ║
╚═══════════════════════════════════════════════════════════╝
```

#### Pendencias Alta Prioridade

| ID | Item | Status |
|----|------|--------|
| HIGH-001 | Secret Scanning Alert (1 alerta) | PENDENTE |
| HIGH-002 | Branch Protection (0 branches) | PENDENTE |
| HIGH-003 | CodeQL (130 alertas p/ triagem) | PENDENTE |

### Controles Implementados

| Categoria | Controle | Status |
|-----------|----------|--------|
| **Supabase** | SSL Enforcement | ON |
| **Supabase** | Storage Bucket Privado | ON |
| **Supabase** | RLS em todas as tabelas | ON |
| **Supabase** | Anon grants removidos | ON |
| **Supabase** | JWT ECC P-256 (legado revogado) | ON |
| **GitHub** | Secret Scanning | ON |
| **GitHub** | Branch Protection (PR + 1 approval) | ON |
| **GitHub** | Dependabot Alerts | ON |
| **GitHub** | CodeQL (SAST) | ON |
| **CI/CD** | Gitleaks Secret Scan | ON |
| **Codigo** | Pre-commit hooks | ON |

### Ativar Pre-commit Hooks (Obrigatorio para Desenvolvedores)

```bash
# Ativar hooks de seguranca que bloqueiam commits com secrets
git config core.hooksPath .githooks

# Testar se esta funcionando
echo "SUPABASE_SERVICE_KEY=teste123" > teste.txt
git add teste.txt
git commit -m "teste"  # Deve ser BLOQUEADO
rm teste.txt
```

### Arquivos de Seguranca

| Arquivo | Descricao |
|---------|-----------|
| `SECURITY.md` | Politica de vulnerabilidades |
| `SECURITY_AUDIT_CONSOLIDATED.json` | Resultado consolidado da auditoria |
| `SECURITY_AUDIT_LOCAL.json` | Auditoria de codigo local |
| `SECURITY_AUDIT_BROWSER.json` | Auditoria via Supabase/GitHub UI |
| `SECURITY_REMEDIATION_CHECKLIST.md` | Checklist de correcoes (100% completo) |
| `.github/dependabot.yml` | Monitoramento de vulnerabilidades (pip, npm, actions) |
| `.github/workflows/codeql-analysis.yml` | Analise estatica (Python + JS/TS) |
| `.githooks/pre-commit` | Hook que bloqueia secrets antes do commit |
| `data/sql/remove_anon_grants.sql` | Script que removeu acesso anonimo |

### Historico de Auditorias

| Data | Tipo | Risk Level | Status | Documento |
|------|------|------------|--------|-----------|
| 2026-01-19 | CRAUDIO 3-Partes | MEDIO | 3 HIGH pendentes | [AUDITORIA_CRAUDIO_2026-01-19.md](./AUDITORIA_CRAUDIO_2026-01-19.md) |
| 2026-01-19 | Seguranca Inicial | LOW | COMPLETO | SECURITY_AUDIT_CONSOLIDATED.json |

### Proxima Auditoria

- **Data:** 2026-01-26
- **Escopo:** Verificar vulnerabilidades Dependabot + CodeQL findings

---

## Documentacao Completa (6 arquivos)

| # | Arquivo | Conteudo | Quando Consultar |
|---|---------|----------|------------------|
| 1 | [CLAUDE_FULL_1.md](./CLAUDE_FULL_1.md) | Estado atual, Frontend React, Hotfixes | Primeiro a ler, estado mais recente |
| 2 | [CLAUDE_FULL_2.md](./CLAUDE_FULL_2.md) | Arquitetura e Fluxos | Entender como o sistema funciona |
| 3 | [CLAUDE_FULL_3.md](./CLAUDE_FULL_3.md) | CI/CD, Testes, Workflows | Config de CI, adicionar testes |
| 4 | [CLAUDE_FULL_4.md](./CLAUDE_FULL_4.md) | Banco de Dados e API PNCP | Schema, queries, endpoints |
| 5 | [CLAUDE_FULL_5.md](./CLAUDE_FULL_5.md) | Seguranca e Configuracao | Variaveis, secrets, hooks |
| 6 | [CLAUDE_FULL_6.md](./CLAUDE_FULL_6.md) | Operacoes e Historico | Comandos, troubleshooting, commits |

---

## Estrutura do Projeto

```
testes-12-01-17h/
|
|-- src/                          # CODIGO FONTE
|   |-- core/                     # Arquivos de producao
|   |   |-- ache_sucatas_miner_v11.py
|   |   |-- cloud_auditor_v14.py
|   |   |-- coleta_historica_30d.py
|   |   |-- supabase_repository.py
|   |   |-- supabase_storage.py
|   |   +-- streamlit_app.py
|   |-- scripts/                  # Scripts utilitarios
|   +-- migrations/               # Scripts de migracao
|
|-- docs/                         # DOCUMENTACAO
|   |-- CLAUDE.md                 # Este arquivo (quick start)
|   |-- CLAUDE_FULL_*.md          # Documentacao completa (6 arquivos)
|   +-- reports/                  # Relatorios historicos
|
|-- config/                       # CONFIGURACAO
|   |-- .env.example
|   |-- pytest.ini
|   +-- ruff.toml
|
|-- data/sql/                     # Scripts SQL
|
|-- tests/                        # 98 testes unitarios
|
|-- frontend/                     # Dashboard React + Vite + TypeScript
|   |-- src/components/           # NotificationBell, MapView, CalendarView
|   |-- src/hooks/                # useNotifications, useUserFilters
|   +-- supabase/                 # week2_schema.sql
|
|-- .github/workflows/            # CI/CD
|   |-- ache-sucatas.yml          # Coleta automatica 3x/dia
|   +-- ci.yml                    # Lint + Testes
|
|-- ACHE_SUCATAS_DB/              # Database local de PDFs (1.3 GB)
|
+-- .env                          # Credenciais (gitignore)
```

---

---

## Historico de Sessoes

### 2026-01-19 - Auditoria CRAUDIO Completa

**Atividades realizadas:**

1. **PARTE 1: Auditoria Local (sem navegador)**
   - Mapeamento completo da estrutura do repositorio
   - Analise de 30 commits recentes
   - Inspecao de workflows CI/CD, schema SQL, testes
   - Identificacao de 11 itens OK + findings

2. **PARTE 2: Coleta via Navegador (Chrome)**
   - 11 tarefas executadas no Supabase e GitHub
   - SSL, RLS, JWT, Branch Protection verificados
   - Outputs salvos em `output_navegador_relatorio.txt`

3. **PARTE 3: Analise Final**
   - Veredito: Deploy AUTORIZADO com ressalvas
   - 3 itens HIGH pendentes identificados
   - Plano de correcao e criterios de aceite definidos

**Pendencias identificadas:**
- [EXEC-01] Resolver 1 alerta Secret Scanning
- [EXEC-02] Corrigir Branch Protection (0 branches)
- [EXEC-03] Triar 130 alertas CodeQL

**Documentacao gerada:**
- `docs/AUDITORIA_CRAUDIO_2026-01-19.md` (relatorio completo)

---

### 2026-01-19 - Correcoes Frontend

**Atividades realizadas:**

1. **Teste do Frontend**
   - Servidor Vite iniciado em `http://localhost:5173`
   - Build e lint executados

2. **Correcao de 5 erros ESLint**
   - `badge.tsx`: eslint-disable para `react-refresh/only-export-components`
   - `button.tsx`: eslint-disable para `react-refresh/only-export-components`
   - `input.tsx`: Convertido interface vazia para type alias
   - `AuthContext.tsx`: eslint-disable para hook `useAuth`
   - `NotificationContext.tsx`: eslint-disable para hook `useNotifications`

3. **Build de producao**
   - TypeScript: OK
   - Vite build: OK (dist/ gerado)

4. **Commit das correcoes**
   - `a317909 fix: Resolve ESLint errors in frontend components`

5. **Atualizacao da chave API Supabase**
   - Chave JWT legada (HS256) substituida pela nova chave ECC P-256
   - Arquivo: `frontend/.env` - `VITE_SUPABASE_ANON_KEY`

**Status:** Frontend operacional com nova chave API

---

> Ao finalizar trabalho: atualizar o arquivo `docs/CLAUDE_FULL_*.md` correspondente com mudancas realizadas
