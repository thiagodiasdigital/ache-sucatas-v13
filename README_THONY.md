# README_THONY.md - Estrutura Reorganizada

> **Gerado por:** THONY (Technical Hygiene & Organized Network Yield)
> **Data:** 2026-01-19 06:52:48
> **Modo:** EXECUCAO REAL

---

## Nova Estrutura do Projeto

```
testes-12-01-17h/
|
|-- src/                          # Codigo fonte
|   |-- core/                     # Arquivos de producao
|   |   |-- ache_sucatas_miner_v11.py    # Miner principal
|   |   |-- cloud_auditor_v14.py         # Auditor principal
|   |   |-- supabase_repository.py       # CRUD PostgreSQL
|   |   |-- supabase_storage.py          # Storage operations
|   |   |-- coleta_historica_30d.py      # Coleta historica
|   |   +-- streamlit_app.py             # Dashboard Streamlit
|   |
|   |-- scripts/                  # Scripts utilitarios
|   |   |-- instalar_hooks_seguranca.py
|   |   |-- rotacionar_credenciais.py
|   |   |-- gerar_excel_final.py
|   |   |-- monitorar_*.py
|   |   +-- [outros scripts ativos]
|   |
|   +-- migrations/               # Scripts de migracao
|       |-- migrar_v13_robusto.py
|       +-- executar_schema_*.py
|
|-- docs/                         # Documentacao
|   |-- CLAUDE.md                 # Quick start
|   |-- CLAUDE_FULL_*.md          # Documentacao completa
|   |-- GUIA_SEGURANCA_MAXIMA.md
|   +-- reports/                  # Relatorios historicos
|       |-- RELATORIO_*.md
|       +-- RESULTADO_*.md
|
|-- config/                       # Configuracoes
|   |-- .env.example
|   |-- pytest.ini
|   |-- ruff.toml
|   +-- .ache_sucatas_checkpoint.json
|
|-- data/                         # Dados
|   +-- sql/                      # Scripts SQL
|       |-- insert_municipios.sql
|       |-- migrar_schema_v11_storage.sql
|       +-- schemas_v13_supabase.sql
|
|-- tests/                        # Testes unitarios (98 testes)
|   |-- conftest.py
|   |-- test_auditor_extraction.py
|   |-- test_miner_scoring.py
|   +-- test_repository_parsing.py
|
|-- frontend/                     # Dashboard React + Vite
|   |-- src/
|   |-- supabase/
|   +-- [estrutura padrao React]
|
|-- .github/workflows/            # CI/CD
|   |-- ache-sucatas.yml
|   +-- ci.yml
|
|-- _DESCARTE_AUDITORIA/          # LIXEIRA LOGICA (revisar antes de deletar)
|   |-- versoes_antigas/          # Scripts v8-v13
|   |-- logs_antigos/             # Logs historicos
|   |-- backups/                  # Diretorios de backup
|   |-- analises_antigas/         # CSVs de versoes anteriores
|   +-- artifacts/                # Arquivos de sistema
|
|-- ACHE_SUCATAS_DB/              # Database local (1.3 GB - nao movido)
|
+-- [arquivos de dados atuais]    # CSVs e XLSX atuais
    |-- analise_editais_v12.csv
    |-- analise_editais_v14.csv
    |-- ache_sucatas_relatorio_final.csv
    +-- RESULTADO_FINAL.xlsx
```

---

## Arquivos de Producao (ATIVOS)

| Arquivo | Local | Funcao |
|---------|-------|--------|
| `ache_sucatas_miner_v11.py` | src/core/ | Coleta editais PNCP |
| `cloud_auditor_v14.py` | src/core/ | Extrai dados dos PDFs |
| `supabase_repository.py` | src/core/ | CRUD PostgreSQL |
| `supabase_storage.py` | src/core/ | Upload/download Storage |
| `coleta_historica_30d.py` | src/core/ | Coleta historica |

---

## Pasta _DESCARTE_AUDITORIA

Esta pasta contem arquivos que foram identificados como:
- **Duplicados** ou versoes anteriores
- **Temporarios** ou logs antigos
- **Backups** consolidados
- **Scripts de teste** avulsos

### ACAO REQUERIDA
1. Revise os arquivos marcados com `REVIEW_NEEDED_`
2. Verifique se algum arquivo ainda eh necessario
3. Apos revisao, delete a pasta inteira: `rm -rf _DESCARTE_AUDITORIA`

---

## Comandos Atualizados

```bash
# Executar miner (novo caminho)
python src/core/ache_sucatas_miner_v11.py

# Executar auditor (novo caminho)
python src/core/cloud_auditor_v14.py

# Testes (sem alteracao)
pytest tests/ -v

# Frontend (sem alteracao)
cd frontend && npm run dev
```

---

## Estatisticas da Reorganizacao

- **Operacoes realizadas:** 40
- **Modo:** Execucao real
- **Log completo:** `thony_reorganizar.log`

---

## Proximos Passos

1. [ ] Revisar pasta `_DESCARTE_AUDITORIA`
2. [ ] Atualizar imports nos workflows (`.github/workflows/`)
3. [ ] Verificar se todos os testes passam: `pytest tests/ -v`
4. [ ] Deletar `_DESCARTE_AUDITORIA` apos revisao
5. [ ] Commitar nova estrutura

---

> *"Ordem eh o primeiro passo para a maestria."* - THONY
