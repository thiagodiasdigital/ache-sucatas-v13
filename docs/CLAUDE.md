# CLAUDE.md - ACHE SUCATAS (Quick Start)

> **Status:** 100% Operacional | **Versao:** V11 + Auditor V14.1 + CI + Coleta Historica + Frontend React
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

### Ativar Pre-commit Hooks (Obrigatorio para Desenvolvedores)

```bash
# Ativar hooks de seguranca que bloqueiam commits com secrets
git config core.hooksPath .githooks
```

### Arquivos de Seguranca

| Arquivo | Descricao |
|---------|-----------|
| `SECURITY.md` | Politica de vulnerabilidades |
| `SECURITY_AUDIT_CONSOLIDATED.json` | Resultado da auditoria |
| `SECURITY_REMEDIATION_CHECKLIST.md` | Checklist de correcoes |
| `.github/dependabot.yml` | Monitoramento de vulnerabilidades |
| `.github/workflows/codeql-analysis.yml` | Analise estatica (SAST) |
| `.githooks/pre-commit` | Hook que bloqueia secrets |

### Ultima Auditoria: 2026-01-19

- **Risk Level:** LOW
- **Deploy:** AUTORIZADO
- **Proxima auditoria:** 2026-01-26

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

> Ao finalizar trabalho: atualizar o arquivo `docs/CLAUDE_FULL_*.md` correspondente com mudancas realizadas
