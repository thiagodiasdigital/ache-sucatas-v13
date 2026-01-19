# CLAUDE.md - ACHE SUCATAS (Quick Start)

> **Status:** 100% Operacional | **Versao:** V11 + Auditor V14.1 + CI + Coleta Historica + Frontend React
> **Documentacao completa:** Dividida em 6 arquivos (ver tabela abaixo)

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

| Arquivo | Funcao |
|---------|--------|
| `ache_sucatas_miner_v11.py` | Coleta editais da API PNCP (diaria) |
| `coleta_historica_30d.py` | Coleta historica dos ultimos 30 dias |
| `cloud_auditor_v14.py` | Extrai dados dos PDFs |
| `supabase_repository.py` | CRUD PostgreSQL |
| `supabase_storage.py` | Upload/download Storage |

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

# Coleta historica (30 dias) - script standalone
python coleta_historica_30d.py

# Executar testes localmente
pytest tests/ -v --tb=short

# Executar linting
ruff check .

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
python -c "from supabase_repository import SupabaseRepository; print(SupabaseRepository().contar_editais())"

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

## Estrutura Resumida

```
testes-12-01-17h/
|-- .github/workflows/     # ache-sucatas.yml, ci.yml
|-- frontend/              # Dashboard React + Vite + TypeScript
|   |-- src/components/    # NotificationBell, MapView, CalendarView, etc
|   |-- src/hooks/         # useNotifications, useUserFilters, useViewMode
|   +-- supabase/          # week2_schema.sql (notificacoes)
|-- tests/                 # 98 testes unitarios
|-- ache_sucatas_miner_v11.py
|-- coleta_historica_30d.py   # Script coleta historica
|-- cloud_auditor_v14.py
|-- supabase_repository.py
|-- supabase_storage.py
|-- CLAUDE.md              # Este arquivo (resumo)
|-- CLAUDE_FULL_1.md       # Estado atual, Frontend React
|-- CLAUDE_FULL_2.md       # Arquitetura e Fluxos
|-- CLAUDE_FULL_3.md       # CI/CD, Testes, Workflows
|-- CLAUDE_FULL_4.md       # Banco de Dados e API
|-- CLAUDE_FULL_5.md       # Seguranca e Configuracao
|-- CLAUDE_FULL_6.md       # Operacoes e Historico
+-- .env                   # Credenciais (gitignore)
```

---

> Ao finalizar trabalho: atualizar o arquivo CLAUDE_FULL_*.md correspondente com mudancas realizadas
