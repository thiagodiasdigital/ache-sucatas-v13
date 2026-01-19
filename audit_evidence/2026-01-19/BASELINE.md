# BASELINE - AUDITORIA CRAUDIO 2026-01-19

## SNAPSHOT DO REPOSITORIO

| Metrica | Valor |
|---------|-------|
| **Branch** | master |
| **Ultimo commit** | 8cea887 |
| **Testes unitarios** | 104 |
| **Testes passando** | 104 (100%) |
| **Editais no banco** | 294 |
| **PDFs no Storage** | 698+ |

## ESTRUTURA DE PRODUCAO

```
src/core/
  ache_sucatas_miner_v11.py   # Miner 100% cloud-native
  cloud_auditor_v14.py        # Auditor de PDFs
  supabase_repository.py      # CRUD PostgreSQL
  supabase_storage.py         # Upload/download Storage
  coleta_historica_30d.py     # Coleta historica
  streamlit_app.py            # Dashboard Streamlit

tests/
  test_auditor_extraction.py  # 59 testes
  test_miner_scoring.py       # 31 testes
  test_repository_parsing.py  # 14 testes

.github/workflows/
  ache-sucatas.yml            # Coleta 3x/dia
  ci.yml                      # Lint + Test + Gitleaks
  codeql-analysis.yml         # SAST Python/JS
```

## CI/CD STATUS

| Job | Status |
|-----|--------|
| Gitleaks | OK (rodando) |
| Ruff Lint | OK |
| Pytest | OK (104 tests) |
| CodeQL | OK (130 alertas triados) |
| Bandit | NAO CONFIGURADO |

## BUGS E4 - STATUS

| Bug | Descricao | Status |
|-----|-----------|--------|
| #1 | `encontrar_pasta_dados` so pega primeira subpasta | N/A - Codigo legado em `_DESCARTE_AUDITORIA/`. Producao (V11) e 100% cloud-native. |
| #2 | Regex URL nao captura `www.` sem protocolo | CORRIGIDO - Testes existem e passam |
| #3 | Regex nao contempla `.net.br` | CORRIGIDO - Testes existem e passam |

## EVIDENCIA DE TESTES

```
============================= test session starts =============================
platform win32 -- Python 3.12.8, pytest-9.0.2
collected 104 items

tests/test_auditor_extraction.py    59 passed
tests/test_miner_scoring.py         31 passed
tests/test_repository_parsing.py    14 passed

============================= 104 passed =============================
```

## PENDENCIAS IDENTIFICADAS (PRE-IMPLEMENTACAO)

| Exigencia | Status |
|-----------|--------|
| E1: SLA/SLO | NAO EXISTE |
| E2: FinOps/Unit Economics | NAO EXISTE |
| E3: Bandit SAST | NAO CONFIGURADO |
| E4: Bugs Miner | RESOLVIDO (2/3 corrigidos, 1/3 N/A) |
| E5: Contrato de Dados v2 | EXISTE v1, PRECISA ATUALIZAR |

## CHECKLIST DE MUDANCAS A REALIZAR

- [ ] Criar `docs/observability/slo.md`
- [ ] Criar `docs/observability/metrics.md`
- [ ] Criar `docs/finops/unit_economics.md`
- [ ] Criar script `src/scripts/calculate_unit_economics.py`
- [ ] Adicionar Bandit ao `.github/workflows/ci.yml`
- [ ] Criar `bandit.baseline` (ignorar falsos positivos)
- [ ] Atualizar `schema.json` para v2
- [ ] Criar `docs/contracts/data_contract_v2.md`
- [ ] Criar `docs/contracts/changelog.md`

---

*Gerado automaticamente em 2026-01-19*
