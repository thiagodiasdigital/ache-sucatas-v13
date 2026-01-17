# CLAUDE.md - ACHE SUCATAS (Quick Start)

> **Status:** 100% Operacional | **Versao:** V11 + Auditor V14.1 + CI
> **Documento completo:** [CLAUDE_FULL.md](./CLAUDE_FULL.md) (consultar se precisar de detalhes)

---

## O Que Este Sistema Faz

Sistema automatizado de coleta de **editais de leilao publico** do Brasil via API PNCP.
- Coleta 3x/dia via GitHub Actions (00:00, 08:00, 16:00 UTC)
- Armazena PDFs no Supabase Storage + metadados no PostgreSQL
- Extrai dados dos PDFs (data, valor, leiloeiro, itens)
- Envia email se workflow falhar

---

## Metricas Atuais

| Metrica | Valor |
|---------|-------|
| Editais no banco | 26 |
| PDFs no Storage | 20 |
| Testes unitarios | 98 (100% pass) |
| Custo mensal | $0 (free tier) |

---

## Arquivos de Producao (usar estes)

| Arquivo | Funcao |
|---------|--------|
| `ache_sucatas_miner_v11.py` | Coleta editais da API PNCP |
| `cloud_auditor_v14.py` | Extrai dados dos PDFs |
| `supabase_repository.py` | CRUD PostgreSQL |
| `supabase_storage.py` | Upload/download Storage |

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

# Executar testes localmente
pytest tests/ -v --tb=short

# Executar linting
ruff check .
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

## Quando Consultar CLAUDE_FULL.md

- Detalhes de arquitetura e fluxos
- Schema completo do banco de dados
- Configuracao de variaveis de ambiente
- Troubleshooting detalhado
- Historico de commits
- Configuracao de seguranca
- API PNCP (endpoints, parametros)

---

## Estrutura Resumida

```
testes-12-01-17h/
|-- .github/workflows/     # ache-sucatas.yml, ci.yml
|-- tests/                 # 98 testes unitarios
|-- ache_sucatas_miner_v11.py
|-- cloud_auditor_v14.py
|-- supabase_repository.py
|-- supabase_storage.py
|-- CLAUDE.md              # Este arquivo (leve)
|-- CLAUDE_FULL.md         # Documentacao completa
+-- .env                   # Credenciais (gitignore)
```

---

> Ao finalizar trabalho: atualizar CLAUDE_FULL.md com mudancas realizadas
