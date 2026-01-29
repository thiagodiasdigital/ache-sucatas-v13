# Relatório Forense de Quarentena - Ache Sucatas

**Data:** 2026-01-29
**Autor:** Claude (Auditoria Forense L8)
**Run IDs Investigados:**
- 20260129T085904Z_993dc64e7e54
- 20260129T083054Z_b0f947208521
- 20260129T012107Z_b35376702d14
- 20260128T162822Z_6b1837d1c72b

---

## 1. Resumo Executivo

| Métrica | Valor |
|---------|-------|
| Runs investigados | 4 |
| Total registros quarentenados | 22 |
| Principal causa | `tipo_leilao` = None (100%) |
| Segunda causa | `n_edital` = None (~70%) |
| Bug identificado | Regex tratado como string literal |

---

## 2. Contagens por Run

| Run ID | Processados | Válidos | Quarentena | Taxa Quarentena |
|--------|-------------|---------|------------|-----------------|
| 20260129T085904Z_993dc64e7e54 | 7 | 0 | 7 | 100% |
| 20260129T083054Z_b0f947208521 | 7 | 0 | 7 | 100% |
| 20260129T012107Z_b35376702d14 | 4 | 0 | 4 | 100% |
| 20260128T162822Z_6b1837d1c72b | 4 | 0 | 4 | 100% |

**Nota:** Os números acima são relativos à tabela `dataset_rejections`. Os pipeline_run_reports mostram totais diferentes (281, 278, 276) porque a maioria dos registros foi processada com sucesso.

---

## 3. Top-5 Motivos de Quarentena por Run

### Run: 20260129T085904Z_993dc64e7e54 (7 registros)

| Campo Faltante | Contagem | % do Run |
|----------------|----------|----------|
| tipo_leilao | 7 | 100% |
| n_edital | 5 | 71% |
| objeto_resumido | 2 | 29% |
| tags | 2 | 29% |
| valor_estimado | 1 | 14% |

### Run: 20260129T083054Z_b0f947208521 (7 registros)

| Campo Faltante | Contagem | % do Run |
|----------------|----------|----------|
| tipo_leilao | 7 | 100% |
| n_edital | 5 | 71% |
| objeto_resumido | 2 | 29% |
| tags | 2 | 29% |
| valor_estimado | 1 | 14% |

### Run: 20260129T012107Z_b35376702d14 (4 registros)

| Campo Faltante | Contagem | % do Run |
|----------------|----------|----------|
| tipo_leilao | 4 | 100% |
| n_edital | 3 | 75% |
| objeto_resumido | 2 | 50% |
| tags | 2 | 50% |

### Run: 20260128T162822Z_6b1837d1c72b (4 registros)

| Campo Faltante | Contagem | % do Run |
|----------------|----------|----------|
| tipo_leilao | 4 | 100% |
| n_edital | 3 | 75% |
| objeto_resumido | 2 | 50% |
| tags | 2 | 50% |

---

## 4. Análise Global (500 registros mais recentes)

| Campo Faltante | Total | % Global |
|----------------|-------|----------|
| valor_estimado | 435 | 87% |
| data_leilao | 431 | 86% |
| n_edital | 162 | 32% |
| tipo_leilao | 146 | 29% |
| objeto_resumido | 97 | 19% |
| tags | 72 | 14% |

| Código de Erro | Total |
|----------------|-------|
| missing_required_field | 1343 |
| invalid_url | 108 |

---

## 5. Amostras de Registros Quarentenados

### Amostra 1: ID 76247329000113-1-000006/2026

**Status:** not_sellable
**Run:** 20260129T085904Z_993dc64e7e54
**Campos faltantes:** `n_edital`, `tipo_leilao`

| Campo | Valor |
|-------|-------|
| uf | PR |
| tags | CAMINHAO, VEICULO |
| orgao | MUNICIPIO DE TUNEIRAS DO OESTE |
| titulo | Edital nº 000006-/2026/2026 |
| n_edital | **None** |
| tipo_leilao | **None** |
| pncp_url | https://pncp.gov.br/app/editais/76247329000113-1-000006/2026 |
| municipio | Tuneiras do Oeste |
| data_leilao | 30-01-2026 |
| valor_estimado | 276518.45 |

**Observação:** Todos os campos principais estão presentes, exceto `n_edital` e `tipo_leilao` que são extraídos do PDF.

---

### Amostra 2: ID 89161475000173-1-000001/2026

**Status:** not_sellable
**Run:** 20260129T085904Z_993dc64e7e54
**Campos faltantes:** `valor_estimado`, `tipo_leilao`

| Campo | Valor |
|-------|-------|
| uf | RS |
| tags | CAMINHAO, CATERPILLAR, MASSEY_FERGUSON, NEW_HOLLAND, STRADA |
| orgao | ASSOC RIOGR DE EMPR DE ASSIST TEC E EXTENSAO RURAL |
| titulo | Edital nº 0004/2026 |
| n_edital | 3 |
| tipo_leilao | **None** |
| pncp_url | https://pncp.gov.br/app/editais/89161475000173-1-000001/2026 |
| municipio | Porto Alegre |
| data_leilao | 29-01-2026 |
| valor_estimado | **None** |

**Observação:** `n_edital` foi extraído com sucesso (= 3), mas `tipo_leilao` ainda é None.

---

### Amostra 3: ID 18299446000124-1-000001/2026

**Status:** not_sellable
**Run:** 20260129T085904Z_993dc64e7e54
**Campos faltantes:** `n_edital`, `objeto_resumido`, `tags`, `tipo_leilao`

| Campo | Valor |
|-------|-------|
| uf | MG |
| tags | **None** |
| orgao | MUNICIPIO DE ITABIRA |
| titulo | Edital nº 1 - Processo 1/2026 |
| n_edital | **None** |
| tipo_leilao | **None** |
| descricao | Bens moveis inserviveis antieconomicos ou irrecuperaveis... |
| municipio | Itabira |
| data_leilao | 09-02-2026 |
| valor_estimado | 382910.0 |
| objeto_resumido | **None** |

**Observação:** Este registro tem mais campos faltantes - incluindo `tags` e `objeto_resumido`. A taxonomia automotiva não encontrou termos veiculares no texto, e a extração do PDF falhou.

---

## 6. Causa Raiz Identificada

### Bug Principal: `extrair_tipo_leilao_pdf()`

**Arquivo:** `src/core/ache_sucatas_miner_v18.py:305-333`

```python
# CÓDIGO COM BUG (linha 312-315):
tem_eletronico = any(p in texto_lower for p in [
    "leil[aã]o eletr[oô]nico", "eletr[oô]nico", "online",  # ← REGEX como string literal!
    "modo eletronico", "forma eletronica", "virtual"
])
```

**Problema:** Os patterns `"leil[aã]o eletr[oô]nico"` contêm sintaxe regex (`[aã]`, `[oô]`), mas a função `any(p in texto_lower ...)` faz verificação de substring literal.

**Resultado:** A string literal `"leil[aã]o eletr[oô]nico"` NUNCA será encontrada no texto, porque o texto contém `"leilão eletrônico"` (com acentos reais), não `"leil[aã]o eletr[oô]nico"`.

### Problema Secundário: `n_edital` é obrigatório incorretamente

**Arquivo:** `validators/dataset_validator.py:16-31`

O contrato (`contracts/dataset_contract_v1.md`) define `n_edital` como "NÃO" obrigatório, mas o validador o inclui em `REQUIRED_FIELDS` e `SELLABLE_REQUIRED_FIELDS`.

---

## 7. Recomendações

1. **Corrigir `extrair_tipo_leilao_pdf()`** - Usar `re.search()` em vez de `p in texto_lower`
2. **Remover `n_edital` de REQUIRED_FIELDS** - Alinhar com contrato
3. **Adicionar fallback para `tipo_leilao`** - Usar modalidade da API PNCP
4. **Melhorar logging** - Adicionar contador por campo faltante no QualityReport

---

## 8. Anexo: JSON Completo

Ver arquivo: `docs/forensic_quarantine_analysis.json`
