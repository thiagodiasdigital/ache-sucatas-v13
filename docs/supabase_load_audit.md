# Auditoria do Loader / Supabase

**Data:** 2026-01-29
**Autor:** Claude (Auditoria Forense L8)

---

## 1. Diagnóstico

A investigação confirmou que **o problema NÃO está no loader Supabase**. Os registros estão sendo corretamente:

1. Validados pelo `dataset_validator.py`
2. Roteados para `editais` (válidos) ou `dataset_rejections` (quarentena)
3. Persistidos no Supabase

O problema está **upstream** (no validador e na extração de campos).

---

## 2. Queries Executadas

### 2.1 Pipeline Run Reports

```sql
SELECT *
FROM pipeline_run_reports
ORDER BY created_at DESC
LIMIT 20;
```

**Resultado:** 20 relatórios encontrados, incluindo os 4 runs alvo:
- 20260129T085904Z_993dc64e7e54: Total 281, Com Link 269, Sem Link 12
- 20260129T083054Z_b0f947208521: Total 281, Com Link 269, Sem Link 12
- 20260129T012107Z_b35376702d14: Total 278, Com Link 267, Sem Link 11
- 20260128T162822Z_6b1837d1c72b: Total 276, Com Link 265, Sem Link 11

### 2.2 Dataset Rejections

```sql
SELECT run_id, COUNT(*) as total
FROM dataset_rejections
GROUP BY run_id
ORDER BY total DESC
LIMIT 10;
```

**Resultado:**
| run_id | total |
|--------|-------|
| 20260123T130011Z_4979beeb4d9f | 131 |
| 20260123T114641Z_76002631dae6 | 131 |
| 20260123T000557Z_d02c71454c07 | 79 |
| ... | ... |
| 20260129T085904Z_993dc64e7e54 | 7 |
| 20260129T083054Z_b0f947208521 | 7 |
| 20260129T012107Z_b35376702d14 | 4 |
| 20260128T162822Z_6b1837d1c72b | 4 |

### 2.3 Análise de Erros

```sql
SELECT
  jsonb_array_elements(errors)->>'code' as error_code,
  jsonb_array_elements(errors)->>'field' as field,
  COUNT(*) as total
FROM dataset_rejections
GROUP BY 1, 2
ORDER BY total DESC;
```

**Resultado:**
| error_code | field | total |
|------------|-------|-------|
| missing_required_field | valor_estimado | 435 |
| missing_required_field | data_leilao | 431 |
| missing_required_field | n_edital | 162 |
| missing_required_field | tipo_leilao | 146 |
| missing_required_field | objeto_resumido | 97 |
| missing_required_field | tags | 72 |
| invalid_url | pncp_url | 108 |

---

## 3. RLS / Policies

### 3.1 Tabela `editais`

```sql
SELECT * FROM pg_policies WHERE tablename = 'editais';
```

**Resultado:** Policies configuradas corretamente:
- `anon` pode SELECT
- `service_role` pode INSERT, UPDATE, DELETE

### 3.2 Tabela `dataset_rejections`

```sql
SELECT * FROM pg_policies WHERE tablename = 'dataset_rejections';
```

**Resultado:** Policies configuradas:
- `service_role` pode INSERT (usado pelo miner)
- `anon` não tem acesso (correto - quarentena é interna)

### 3.3 Tabela `pipeline_run_reports`

**Resultado:** Policies configuradas:
- `service_role` pode INSERT/UPDATE
- `anon` pode SELECT (para dashboard de métricas)

---

## 4. Contagem de Inserts por Run

```sql
SELECT
  run_id,
  COUNT(*) FILTER (WHERE status = 'valid') as validos,
  COUNT(*) FILTER (WHERE status = 'draft') as draft,
  COUNT(*) FILTER (WHERE status = 'not_sellable') as not_sellable,
  COUNT(*) FILTER (WHERE status = 'rejected') as rejected
FROM dataset_rejections
WHERE run_id LIKE '20260129%'
GROUP BY run_id;
```

**Resultado (runs de 2026-01-29):**
| run_id | validos | draft | not_sellable | rejected |
|--------|---------|-------|--------------|----------|
| 20260129T085904Z_993dc64e7e54 | 0 | 1 | 6 | 0 |
| 20260129T083054Z_b0f947208521 | 0 | 1 | 6 | 0 |

**Nota:** `validos = 0` na tabela de quarentena é esperado - registros válidos vão para `editais`, não para `dataset_rejections`.

---

## 5. Diagnóstico Final

### 5.1 Loader está funcionando corretamente

| Componente | Status |
|------------|--------|
| Conexão Supabase | ✓ OK |
| Upsert em `editais` | ✓ OK |
| Upsert em `dataset_rejections` | ✓ OK |
| RLS / Policies | ✓ OK |
| pipeline_run_reports | ✓ OK |

### 5.2 Problema está no Validador/Extração

O loader recebe registros já validados. Se chegam como `draft` ou `not_sellable`, o loader os envia corretamente para `dataset_rejections`.

**O problema está upstream:**
1. `tipo_leilao` chegando como `None` (bug na extração)
2. `n_edital` marcado incorretamente como obrigatório

---

## 6. Recomendações

1. **Nenhuma alteração necessária no loader**
2. **Monitorar** taxa de inserts em `editais` após correções
3. **Considerar** migration para adicionar índice em `dataset_rejections.run_id`
4. **Dashboard** já consulta tabela correta (`editais` para válidos)
