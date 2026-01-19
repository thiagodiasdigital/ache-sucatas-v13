# SLA/SLO - Ache Sucatas Pipeline

> **Versao:** 1.0
> **Data:** 2026-01-19
> **Responsavel:** CRAUDIO (Auditoria Automatizada)

---

## Definicoes

| Termo | Significado |
|-------|-------------|
| **SLA** | Service Level Agreement - compromisso contratual |
| **SLO** | Service Level Objective - meta interna |
| **SLI** | Service Level Indicator - metrica medida |

---

## SLOs Definidos

### SLO-001: Taxa de Sucesso do Pipeline

| Atributo | Valor |
|----------|-------|
| **Descricao** | Percentual de execucoes do pipeline (Miner + Auditor) concluidas sem erro |
| **SLI** | `execucoes_sucesso / execucoes_total * 100` |
| **Target** | >= 95% |
| **Janela** | Rolling 7 dias |
| **Fonte de dados** | Tabela `execucoes_miner` no Supabase |
| **Query de verificacao** | Ver abaixo |

```sql
-- SLI: Taxa de sucesso (ultimos 7 dias)
SELECT
  COUNT(*) FILTER (WHERE status = 'SUCCESS') * 100.0 / NULLIF(COUNT(*), 0) as taxa_sucesso
FROM execucoes_miner
WHERE execution_start >= NOW() - INTERVAL '7 days';
```

**Rollback Plan:** Se SLO < 95%, investigar logs de erro. Causas comuns: timeout API PNCP, erro de conexao Supabase.

---

### SLO-002: Frescor dos Dados (Data Freshness)

| Atributo | Valor |
|----------|-------|
| **Descricao** | Tempo maximo entre publicacao de edital no PNCP e entrada no banco |
| **SLI** | `MAX(timestamp_insert - data_publicacao_pncp)` |
| **Target** | <= 24 horas |
| **Janela** | Por execucao |
| **Fonte de dados** | Tabela `editais` + `execucoes_miner` |
| **Justificativa** | Pipeline roda 3x/dia (8h, 16h, 00h UTC). Janela temporal = 24h. |

```sql
-- SLI: Frescor medio (editais inseridos hoje)
SELECT
  AVG(EXTRACT(EPOCH FROM (created_at - data_publicacao)) / 3600) as horas_atraso_medio
FROM editais
WHERE created_at >= CURRENT_DATE;
```

**Rollback Plan:** Se SLO violado, considerar aumentar frequencia do cron ou reduzir janela temporal.

---

### SLO-003: Integridade dos Dados

| Atributo | Valor |
|----------|-------|
| **Descricao** | Percentual de registros validos vs descartados por qualidade |
| **SLI** | `editais_inseridos / (editais_inseridos + editais_descartados) * 100` |
| **Target** | >= 90% |
| **Janela** | Por execucao |
| **Fonte de dados** | Metricas da execucao (`editais_novos`, `editais_descartados`) |

```sql
-- SLI: Taxa de integridade (ultima execucao)
SELECT
  editais_novos * 100.0 / NULLIF(editais_novos + COALESCE((metrics->>'editais_descartados')::int, 0), 0) as taxa_integridade
FROM execucoes_miner
ORDER BY execution_start DESC
LIMIT 1;
```

**Rollback Plan:** Se SLO violado, revisar regex de extracao e score minimo (atualmente 60).

---

### SLO-004: Disponibilidade do Frontend

| Atributo | Valor |
|----------|-------|
| **Descricao** | Percentual de tempo que o dashboard esta acessivel |
| **SLI** | `uptime / periodo_total * 100` |
| **Target** | >= 99% |
| **Janela** | Mensal |
| **Fonte de dados** | Monitoramento externo (se configurado) ou logs Vercel/Cloudflare |

**Rollback Plan:** Se SLO violado, verificar status do Supabase e CDN.

---

## Alertas e Notificacoes

| Alerta | Trigger | Canal |
|--------|---------|-------|
| Pipeline falhou | `status = 'FAILED'` | Email (configurado em `ache-sucatas.yml`) |
| SLO-001 violado | Taxa < 95% em 7d | Manual (auditoria semanal) |
| Supabase indisponivel | Erro de conexao | Email automatico |

---

## Calendario de Revisao

| Acao | Frequencia | Responsavel |
|------|------------|-------------|
| Verificar SLO-001 | Semanal | Automatico (auditoria) |
| Verificar SLO-002/003 | Por execucao | Metricas automaticas |
| Revisar targets | Trimestral | Equipe |
| Atualizar SLOs | Conforme necessario | Equipe |

---

## Historico de Alteracoes

| Data | Versao | Descricao |
|------|--------|-----------|
| 2026-01-19 | 1.0 | Versao inicial - 4 SLOs definidos |

---

*Documento criado pela auditoria CRAUDIO em 2026-01-19*
