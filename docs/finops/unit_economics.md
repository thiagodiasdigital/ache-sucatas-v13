# Unit Economics - Ache Sucatas FinOps

> **Versao:** 1.0
> **Data:** 2026-01-19
> **Responsavel:** CRAUDIO (Auditoria Automatizada)

---

## Resumo Executivo

| Metrica | Valor Atual | Target |
|---------|-------------|--------|
| **Custo mensal total** | $0 | < $10/mes |
| **Custo por execucao** | $0 | < $0.01 |
| **Custo por edital** | $0 | < $0.001 |

**Status:** Operando dentro do Free Tier do Supabase e GitHub.

---

## Custos Detalhados

### Supabase (Free Tier)

| Recurso | Limite Free | Uso Atual | % Utilizado |
|---------|-------------|-----------|-------------|
| Database | 500 MB | ~50 MB | 10% |
| Storage | 1 GB | ~200 MB | 20% |
| Bandwidth | 2 GB/mes | ~100 MB/mes | 5% |
| Edge Functions | 500K invocacoes | 0 | 0% |
| Auth Users | 50K MAU | 1 | <1% |

**Custo Supabase:** $0/mes (Free Tier)

### GitHub Actions

| Recurso | Limite Free | Uso Atual | % Utilizado |
|---------|-------------|-----------|-------------|
| Minutes (Ubuntu) | 2000 min/mes | ~90 min/mes | 4.5% |
| Storage Artifacts | 500 MB | ~10 MB | 2% |

**Calculo:**
- 3 execucoes/dia x 30 dias = 90 execucoes/mes
- ~1 min por execucao = 90 minutos/mes
- Limite: 2000 min/mes
- Uso: 4.5%

**Custo GitHub:** $0/mes (Free Tier)

### Outros Custos

| Item | Custo |
|------|-------|
| Dominio | N/A (nao configurado) |
| CDN | N/A (usando Supabase CDN) |
| Email (Gmail SMTP) | $0 |
| Monitoramento | $0 (nao configurado) |

---

## Metricas de Custo Unitario

### Custo por Execucao do Pipeline

```
custo_por_execucao = custo_mensal_total / execucoes_mensais

Calculo atual:
= $0 / 90 execucoes
= $0.00 por execucao
```

### Custo por Edital Publicado

```
custo_por_edital = custo_mensal_total / editais_novos_mes

Calculo atual (estimativa):
= $0 / ~360 editais novos/mes
= $0.00 por edital
```

### Custo por MB de Storage

```
custo_por_mb_storage = custo_storage_mensal / mb_armazenados

Calculo atual:
= $0 / 200 MB
= $0.00 por MB
```

---

## Projecoes de Escala

### Cenario 1: 10x Editais (3,000/mes)

| Recurso | Uso Projetado | Limite Free | Status |
|---------|---------------|-------------|--------|
| Database | ~500 MB | 500 MB | RISCO |
| Storage | ~2 GB | 1 GB | EXCEDE |
| Bandwidth | ~1 GB/mes | 2 GB/mes | OK |

**Custo projetado:** ~$25/mes (Pro tier necessario)

### Cenario 2: 100x Editais (30,000/mes)

| Recurso | Uso Projetado | Limite Pro | Status |
|---------|---------------|------------|--------|
| Database | ~5 GB | 8 GB | OK |
| Storage | ~20 GB | 100 GB | OK |
| Bandwidth | ~10 GB/mes | 50 GB/mes | OK |

**Custo projetado:** ~$50/mes (Pro tier)

---

## Script de Calculo

Execute localmente para recalcular metricas:

```bash
PYTHONPATH=src/core python src/scripts/calculate_unit_economics.py
```

Output esperado:

```
=== UNIT ECONOMICS - ACHE SUCATAS ===
Data: 2026-01-19

CUSTOS:
  Supabase: $0.00 (free tier)
  GitHub Actions: $0.00 (free tier)
  Total Mensal: $0.00

METRICAS:
  Execucoes/mes: 90
  Editais novos/mes: ~360
  Storage usado: 200 MB

UNIT COSTS:
  Por execucao: $0.0000
  Por edital: $0.0000
  Por MB storage: $0.0000

STATUS: Dentro do Free Tier
```

---

## Alertas de Custo

| Trigger | Acao |
|---------|------|
| Storage > 800 MB | Avaliar limpeza ou upgrade |
| Database > 400 MB | Avaliar arquivamento |
| GitHub minutes > 1500/mes | Otimizar workflows |
| Bandwidth > 1.5 GB/mes | Verificar uso anormal |

---

## Recomendacoes

1. **Curto prazo (atual):** Manter no Free Tier
2. **Medio prazo (>1000 editais):** Avaliar Supabase Pro ($25/mes)
3. **Longo prazo (>10000 editais):** Considerar self-hosted PostgreSQL

---

## Historico de Alteracoes

| Data | Versao | Descricao |
|------|--------|-----------|
| 2026-01-19 | 1.0 | Versao inicial - definicao de unit economics |

---

*Documento criado pela auditoria CRAUDIO em 2026-01-19*
