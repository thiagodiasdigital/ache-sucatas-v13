# Análise de Qualidade do Output do Miner

**Data:** 2026-01-29
**Autor:** Claude (Auditoria Forense L8)

---

## 1. Cadeia de Processamento

```
PNCP API ──> Miner V18 ──> PDF Parse ──> IA Enrichment ──> Normalização ──> Validador ──> Roteamento
     │           │            │               │                │               │            │
     │           │            │               │                │               │            ├─> editais (válidos)
     │           │            │               │                │               │            └─> dataset_rejections (quarentena)
     │           │            │               │                │               │
     │           │            │               │                │               └─> QualityReport
     │           │            │               │                │
     │           │            │               │                └─> registro_validacao dict
     │           │            │               │
     │           │            │               └─> titulo_comercial, resumo, url_leilao
     │           │            │
     │           │            └─> n_edital, tipo_leilao, objeto_resumido (do PDF)
     │           │
     │           └─> campos básicos (municipio, uf, data_leilao, pncp_url, etc.)
     │
     └─> búsqueda + API detalhes
```

---

## 2. Exemplo de Registro Emitido vs Contrato

### 2.1 Registro Emitido (raw_record)

```json
{
  "id_interno": "76247329000113-1-000006/2026",
  "municipio": "Tuneiras do Oeste",
  "uf": "PR",
  "data_leilao": "30-01-2026",
  "pncp_url": "https://pncp.gov.br/app/editais/76247329000113-1-000006/2026",
  "data_atualizacao": "29-01-2026",
  "titulo": "Edital nº 000006-/2026/2026",
  "descricao": "AQUISIÇÃO DE 01 UM VEÍCULO, TIPO CAMIONETE CABINE DUPLA...",
  "orgao": "MUNICIPIO DE TUNEIRAS DO OESTE",
  "n_edital": null,
  "objeto_resumido": "Edital nº 000006-/2026/2026 AQUISIÇÃO DE 01 UM VEÍCULO...",
  "tags": "CAMINHAO, VEICULO",
  "valor_estimado": 276518.45,
  "tipo_leilao": null,
  "leiloeiro_url": null,
  "data_publicacao": "28-01-2026"
}
```

### 2.2 Campos Esperados pelo Contrato

| Campo | Obrigatório | Valor Emitido | Status |
|-------|-------------|---------------|--------|
| id_interno | SIM | ✓ Preenchido | OK |
| municipio | SIM | ✓ Preenchido | OK |
| uf | SIM | ✓ Preenchido | OK |
| data_leilao | SIM | ✓ Preenchido | OK |
| pncp_url | SIM | ✓ Preenchido | OK |
| data_atualizacao | SIM | ✓ Preenchido | OK |
| titulo | SIM | ✓ Preenchido | OK |
| descricao | SIM | ✓ Preenchido | OK |
| orgao | SIM | ✓ Preenchido | OK |
| n_edital | **NÃO** | ✗ null | OK (opcional) |
| objeto_resumido | SIM | ✓ Preenchido | OK |
| tags | SIM | ✓ Preenchido | OK |
| valor_estimado | SIM | ✓ Preenchido | OK |
| tipo_leilao | SIM | ✗ null | **FALHA** |
| leiloeiro_url | NÃO | ✗ null | OK (opcional) |
| data_publicacao | SIM (vendabilidade) | ✓ Preenchido | OK |

---

## 3. Diff Contra Contrato

### 3.1 Campos Problemáticos Identificados

| Campo | Fonte | Problema | Causa |
|-------|-------|----------|-------|
| `tipo_leilao` | PDF | Sempre null | Bug na função de extração (regex como literal) |
| `n_edital` | PDF | Frequentemente null | Extração não encontra padrão; **contrato diz opcional** |
| `valor_estimado` | API | Às vezes null | API PNCP não retorna |
| `objeto_resumido` | PDF | Às vezes null | PDF sem texto extraível |
| `tags` | Taxonomia | Às vezes null | Edital sem termos automotivos |

### 3.2 Problemas Corrigidos (2026-01-29)

1. **`n_edital` removido de REQUIRED_FIELDS**
   - Alinha implementação com contrato
   - Impacto: ~162 registros deixarão de ser rejeitados por este campo

2. **`extrair_tipo_leilao_pdf()` corrigida**
   - Patterns regex agora usam `re.search()` corretamente
   - Impacto: Extração de "leilão eletrônico" funciona

3. **Fallback de `tipo_leilao` melhorado**
   - Mapeamento de modalidade PNCP → tipo esperado
   - Códigos "6" e "7" convertidos para "Eletronico" e "Presencial"

---

## 4. Pontos de Correção no Miner

### 4.1 Correção Aplicada: `extrair_tipo_leilao_pdf()`

**Arquivo:** `src/core/ache_sucatas_miner_v18.py:305-350`

**Antes:**
```python
tem_eletronico = any(p in texto_lower for p in [
    "leil[aã]o eletr[oô]nico", ...  # BUG: regex como literal
])
```

**Depois:**
```python
ELETRONICO_REGEX = [r"leil[aã]o\s*eletr[oô]nico", ...]
tem_eletronico = any(re.search(p, texto_lower) for p in ELETRONICO_REGEX)
```

### 4.2 Correção Aplicada: Fallback `tipo_leilao`

**Arquivo:** `src/core/ache_sucatas_miner_v18.py:2685-2700`

**Antes:**
```python
if not tipo_leilao and edital_db.get("modalidade"):
    tipo_leilao = edital_db.get("modalidade", "")  # Sem mapeamento
```

**Depois:**
```python
MODALIDADE_PARA_TIPO = {
    "6": "Eletronico",
    "7": "Presencial",
    ...
}
tipo_leilao = MODALIDADE_PARA_TIPO.get(str(modalidade_raw), modalidade_raw)
```

---

## 5. Métricas de Qualidade Esperadas Pós-Correção

| Métrica | Antes | Depois (Esperado) |
|---------|-------|-------------------|
| Taxa de quarentena | 100% | < 30% |
| `tipo_leilao` preenchido | 0% | > 70% |
| `n_edital` como erro | 32% | 0% |
| Registros válidos por run | 0 | > 50% |

---

## 6. Recomendações Adicionais

1. **Adicionar logging detalhado** para extração de campos do PDF
2. **Considerar fallback** para `valor_estimado` quando API não retorna
3. **Monitorar** taxa de quarentena nas próximas execuções
4. **Documentar** mapeamento de modalidades PNCP no contrato
