# Metricas de Observabilidade - Ache Sucatas

> **Versao:** 1.0
> **Data:** 2026-01-19
> **Responsavel:** CRAUDIO (Auditoria Automatizada)

---

## Metricas Coletadas

### Metricas do Miner V11

| Metrica | Tipo | Descricao | Fonte |
|---------|------|-----------|-------|
| `execution_start` | timestamp | Inicio da execucao | MetricsTracker |
| `execution_end` | timestamp | Fim da execucao | MetricsTracker |
| `duration_seconds` | float | Duracao total em segundos | MetricsTracker |
| `janela_temporal_horas` | int | Janela de busca (default 24h) | Settings |
| `editais_analisados` | int | Total de editais retornados pela API | MetricsTracker |
| `editais_novos` | int | Editais inseridos nesta execucao | MetricsTracker |
| `editais_duplicados` | int | Editais ja existentes (deduplicados) | MetricsTracker |
| `downloads` | int | Total de downloads tentados | MetricsTracker |
| `downloads_sucesso` | int | Downloads bem-sucedidos | MetricsTracker |
| `downloads_falha` | int | Downloads com falha | MetricsTracker |
| `taxa_deduplicacao` | float | % de duplicados vs analisados | MetricsTracker |
| `storage_uploads` | int | Uploads para Supabase Storage | MetricsTracker |
| `storage_errors` | int | Erros de upload | MetricsTracker |
| `supabase_inserts` | int | Inserts no PostgreSQL | MetricsTracker |
| `supabase_errors` | int | Erros de insert | MetricsTracker |
| `mode` | string | "CLOUD" ou "LOCAL" | Settings |

### Metricas do Auditor V14

| Metrica | Tipo | Descricao | Fonte |
|---------|------|-----------|-------|
| `editais_processados` | int | PDFs analisados | Logs |
| `extracao_sucesso` | int | Extracoes bem-sucedidas | Logs |
| `extracao_falha` | int | Extracoes com falha | Logs |
| `campos_extraidos` | dict | Campos por edital | CSV output |

---

## Persistencia de Metricas

### Arquivo Local

```
ache_sucatas_metrics.jsonl
```

Formato: JSON Lines (uma linha por execucao)

```json
{
  "execution_start": "2026-01-19T08:00:00",
  "execution_end": "2026-01-19T08:15:32",
  "duration_seconds": 932.5,
  "editais_analisados": 150,
  "editais_novos": 12,
  "editais_duplicados": 138,
  "downloads": 12,
  "downloads_sucesso": 11,
  "downloads_falha": 1,
  "storage_uploads": 22,
  "supabase_inserts": 12,
  "mode": "CLOUD"
}
```

### Banco de Dados

Tabela: `execucoes_miner`

```sql
CREATE TABLE execucoes_miner (
  id SERIAL PRIMARY KEY,
  execution_start TIMESTAMP NOT NULL,
  execution_end TIMESTAMP,
  versao_miner TEXT,
  janela_temporal_horas INT,
  termos_buscados INT,
  paginas_por_termo INT,
  editais_analisados INT DEFAULT 0,
  editais_novos INT DEFAULT 0,
  editais_duplicados INT DEFAULT 0,
  downloads INT DEFAULT 0,
  downloads_sucesso INT DEFAULT 0,
  downloads_falha INT DEFAULT 0,
  storage_uploads INT DEFAULT 0,
  supabase_inserts INT DEFAULT 0,
  status TEXT DEFAULT 'RUNNING',
  error_message TEXT,
  metrics JSONB
);
```

---

## Queries de Analise

### Metricas dos Ultimos 7 Dias

```sql
SELECT
  DATE(execution_start) as dia,
  COUNT(*) as execucoes,
  SUM(editais_novos) as total_novos,
  AVG(duration_seconds)::int as duracao_media_seg,
  SUM(CASE WHEN status = 'SUCCESS' THEN 1 ELSE 0 END) * 100.0 / COUNT(*) as taxa_sucesso
FROM execucoes_miner
WHERE execution_start >= NOW() - INTERVAL '7 days'
GROUP BY DATE(execution_start)
ORDER BY dia DESC;
```

### Taxa de Downloads com Sucesso

```sql
SELECT
  SUM(downloads_sucesso) * 100.0 / NULLIF(SUM(downloads), 0) as taxa_download_sucesso
FROM execucoes_miner
WHERE execution_start >= NOW() - INTERVAL '30 days';
```

### Editais por UF (Ultimos 30 Dias)

```sql
SELECT
  uf,
  COUNT(*) as total_editais
FROM editais
WHERE created_at >= NOW() - INTERVAL '30 days'
GROUP BY uf
ORDER BY total_editais DESC;
```

---

## Dashboard de Metricas

### Streamlit (Local)

```bash
PYTHONPATH=src/core streamlit run src/core/streamlit_app.py
```

### Queries para Dashboard

```sql
-- Card: Total de editais
SELECT COUNT(*) FROM editais;

-- Card: Editais hoje
SELECT COUNT(*) FROM editais WHERE DATE(created_at) = CURRENT_DATE;

-- Card: Ultima execucao
SELECT
  execution_start,
  status,
  editais_novos,
  duration_seconds
FROM execucoes_miner
ORDER BY execution_start DESC
LIMIT 1;
```

---

## Alertas Baseados em Metricas

| Condicao | Alerta | Acao |
|----------|--------|------|
| `status = 'FAILED'` | Pipeline falhou | Email automatico |
| `editais_novos = 0` por 3 execucoes | Sem novos editais | Verificar API PNCP |
| `downloads_falha > downloads_sucesso` | Alta taxa de falha | Verificar conectividade |
| `duration_seconds > 1800` | Execucao lenta | Verificar timeout/rate limiting |

---

## Historico de Alteracoes

| Data | Versao | Descricao |
|------|--------|-----------|
| 2026-01-19 | 1.0 | Versao inicial - definicao de metricas |

---

*Documento criado pela auditoria CRAUDIO em 2026-01-19*
