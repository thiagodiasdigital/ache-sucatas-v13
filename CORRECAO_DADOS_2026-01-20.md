# Relatório de Correção de Dados - Ache Sucatas

**Data:** 2026-01-20
**Executado por:** Claude Code
**Solicitado por:** Thiago

---

## Resumo Executivo

Foi realizada uma correção em massa nos dados existentes no banco de dados Supabase para resolver inconsistências identificadas nos cards do dashboard.

| Métrica | Valor |
|---------|-------|
| **Total de editais antes** | 294 |
| **Total de editais após** | 288 |
| **Editais modificados** | 114 |
| **Editais removidos** | 6 |

---

## Problemas Identificados

### Problema 1: Modalidades Inconsistentes
**Descrição:** O banco tinha 7 variações diferentes para representar 3 modalidades.

| Valor no Banco | Ocorrências | Problema |
|----------------|-------------|----------|
| `Eletrônico` | OK | - |
| `Leilão - Eletrônico` | 12 | Prefixo desnecessário |
| `PRESENCIAL` | 2 | Caixa alta |
| `Presencial` | OK | - |
| `Leilão - Presencial` | 6 | Prefixo desnecessário |
| `HÍBRIDO` | 3 | Caixa alta |
| `Híbrido` | OK | - |

### Problema 2: Tags Inúteis
**Descrição:** Editais com tags que não agregam valor ao usuário.

| Tag | Problema |
|-----|----------|
| `sync` | Tag interna de sincronização |
| `leilao` | Redundante - todo edital é de leilão |

### Problema 3: Modalidade Incorreta
**Descrição:** Editais com título/descrição mencionando "Online" mas modalidade marcada como "Presencial".

| ID | Cidade | Título | Modalidade Errada |
|----|--------|--------|-------------------|
| 160 | Teresópolis/RJ | "Leilão Online, tendo como objeto sucata..." | Presencial |
| 170 | ? | "EDITAL DE LEILAO PRESENCIAL E ONLINE..." | Presencial |
| 172 | ? | "LEILÃO ONLINE/PRESENCIAL..." | Presencial |

### Problema 4: Leilões com Data Passada
**Descrição:** 6 editais com data de leilão em 2024 (já encerrados).

| ID | Cidade/UF | Data Leilão | Órgão |
|----|-----------|-------------|-------|
| 5 | Ubaitaba/BA | 16/08/2024 | Município de Ubaitaba |
| 4 | Dom Macedo Costa/BA | 05/12/2024 | Município de Dom Macedo Costa |
| 1316 | Ronda Alta/RS | 14/08/2024 | Município de Ronda Alta |
| 1382 | Uruguaiana/RS | 25/09/2024 | Município de Uruguaiana |
| 1443 | Bossoroca/RS | 10/05/2024 | Município de Bossoroca |
| 1526 | Porto Lucena/RS | 29/10/2024 | Município de Porto Lucena |

---

## Correções Aplicadas

### Correção 1: Normalização de Modalidades
**Ação:** Padronizar todas as modalidades para 3 valores únicos.

```
Mapeamento aplicado:
- "Leilão - Eletrônico" → "Eletrônico"
- "PRESENCIAL" → "Presencial"
- "Leilão - Presencial" → "Presencial"
- "HÍBRIDO" → "Híbrido"
```

**Resultado:** 25 editais atualizados

### Correção 2: Remoção de Tags Inúteis
**Ação:** Remover tags `sync` e `leilao` de todos os editais.

**Resultado:** 86 editais atualizados

### Correção 3: Correção de Modalidade por Contexto
**Ação:** Alterar modalidade para "Eletrônico" quando título/descrição contém "online".

**Resultado:** 3 editais corrigidos (IDs: 160, 170, 172)

### Correção 4: Remoção de Leilões Encerrados
**Ação:** Deletar editais com `data_leilao < 2025-01-01`.

**Resultado:** 6 editais removidos (IDs: 4, 5, 1316, 1382, 1443, 1526)

---

## Causa Raiz (PENDENTE DE CORREÇÃO)

Essas correções são **paliativas**. Os problemas vão se repetir se não corrigir a **origem dos dados**:

### Arquivos que precisam ser corrigidos:

| Arquivo | Problema | Correção Necessária |
|---------|----------|---------------------|
| `src/core/ache_sucatas_miner_v12.py` | Não filtra leilões com data passada | Adicionar filtro `data_leilao >= hoje` |
| `src/core/cloud_auditor_v15.py` | Extrai modalidade incorretamente | Detectar "online" no texto → Eletrônico |
| `src/core/cloud_auditor_v15.py` | Não normaliza modalidades | Padronizar para 3 valores |
| `src/core/cloud_auditor_v15.py` | Cria tags inúteis | Não criar tags "sync" e "leilao" |

---

## Próximos Passos

1. **[PENDENTE]** Corrigir Miner V12 para ignorar leilões com data passada
2. **[PENDENTE]** Corrigir Auditor V15 para:
   - Normalizar modalidades (3 valores apenas)
   - Detectar "Online" no texto e marcar como Eletrônico
   - Não criar tags "sync" e "leilao"
3. **[PENDENTE]** Adicionar validação no frontend para não exibir leilões passados

---

## Verificação Pós-Correção

```sql
-- Verificar modalidades únicas
SELECT DISTINCT modalidade_leilao, COUNT(*)
FROM editais_leilao
GROUP BY modalidade_leilao;

-- Verificar se ainda existem tags ruins
SELECT id, tags
FROM editais_leilao
WHERE 'sync' = ANY(tags) OR 'leilao' = ANY(tags);

-- Verificar leilões com data passada
SELECT * FROM editais_leilao
WHERE data_leilao < CURRENT_DATE;
```

---

## Assinaturas

- **Executado:** Claude Code (claude-opus-4-5-20251101)
- **Data/Hora:** 2026-01-20 10:30 UTC-3
- **Ambiente:** Produção (Supabase)
