# RELATÓRIO FORENSE — ACHE SUCATAS DaaS
## Campos Faltantes no Dashboard: Investigação Completa

**Data:** 2026-01-20
**Modelo:** Claude Code Opus 4.5
**Idioma:** Português (Brasil)

---

## (A) Sumário Executivo

**PROBLEMA IDENTIFICADO:** Campos obrigatórios do dashboard (`data_leilao`, `link_pncp`, `valor_estimado`, `tipo_leilao`) estão ausentes ou NULL nos registros exibidos.

**EVIDÊNCIAS QUANTITATIVAS:**
- Checkpoint V12 (`.ache_sucatas_checkpoint_v12.json:549-552`):
  - `data_leilao_encontrada: 0`
  - `valor_estimado_encontrado: 0`
  - `supabase_inserts: 0`

**PERÍODO DA REGRESSÃO:** Desde a criação do Miner V12 (commit `ae44dc0` de 2026-01-19), porém o problema de raiz é anterior — o `supabase_repository.py` nunca foi atualizado para o V12.

**CAUSA RAIZ PRINCIPAL:**
Bug de mapeamento no `supabase_repository.py:909` que lê `data_inicio_propostas` em vez de `data_leilao`, causando perda de 100% dos dados desse campo.

---

## (B) Definição do "Contrato de Dados do Dashboard"

### 17 Campos Obrigatórios (Canônicos):

| # | Campo | Descrição |
|---|-------|-----------|
| 01 | id_interno | Identificador único interno |
| 02 | orgao | Nome do órgão responsável |
| 03 | uf | Unidade Federativa |
| 04 | cidade | Município |
| 05 | n_edital | Número do edital |
| 06 | n_pncp | Número no PNCP |
| 07 | data_publicacao | Data de publicação |
| 08 | data_atualizacao | Data de atualização |
| 09 | **data_leilao** | Data do leilão (CRÍTICO) |
| 10 | titulo | Título do edital |
| 11 | descricao | Descrição completa |
| 12 | objeto_resumido | Resumo do objeto |
| 13 | tags | Tags categorizadas |
| 14 | **link_pncp** | Link oficial PNCP (CRÍTICO) |
| 15 | link_leiloeiro | Link do leiloeiro |
| 16 | **valor_estimado** | Valor estimado (CRÍTICO) |
| 17 | tipo_leilao | Tipo/modalidade do leilão |

### Entidade Canônica do Dashboard:
- **View:** `pub.v_auction_discovery`
- **Tabela Base:** `raw.leiloes`
- **Tabela de Escrita do Miner:** `public.editais_leilao`

---

## (C) Matriz de Cobertura dos Campos

| Campo | Fonte Primária | Transformação | Persistência | Exposição | Frontend | Status | Evidência |
|-------|---------------|---------------|--------------|-----------|----------|--------|-----------|
| id_interno | Miner | `_mapear_edital_model_para_v13:884` | editais_leilao | v_auction_discovery | AuctionCard | OK | `supabase_repository.py:931` |
| orgao | API Search | `EditalModel.orgao_nome` | editais_leilao.orgao | v_auction_discovery.orgao | AuctionCard | OK | `miner_v12.py:737` |
| uf | API Search | `EditalModel.uf` | editais_leilao.uf | v_auction_discovery.uf | TopFilterBar | OK | `miner_v12.py:739` |
| cidade | API Search | `EditalModel.municipio` | editais_leilao.cidade | v_auction_discovery.cidade | TopFilterBar | OK | `miner_v12.py:740` |
| n_edital | Derivado | `_mapear_edital_model_para_v13:923` | editais_leilao.n_edital | v_auction_discovery.n_edital | AuctionCard | OK | - |
| n_pncp | Derivado | `_mapear_edital_model_para_v13:924` | editais_leilao.n_pncp | Não exposto | - | OK | - |
| data_publicacao | API Search | `EditalModel.data_publicacao` | editais_leilao | v_auction_discovery | CalendarView | OK | `miner_v12.py:744` |
| data_atualizacao | API Search | `EditalModel.data_atualizacao` | editais_leilao | v_auction_discovery | - | OK | - |
| **data_leilao** | **API Consulta** | **BUG: lê campo errado** | **NULL** | **Filtrado pela VIEW** | **CalendarView** | **FALHA** | **`repository.py:909` lê `data_inicio_propostas` em vez de `data_leilao`** |
| titulo | API Search | `EditalModel.titulo` | editais_leilao.titulo | v_auction_discovery.titulo | AuctionCard | OK | - |
| descricao | API Search | `EditalModel.descricao` | editais_leilao.descricao | v_auction_discovery.descricao | AuctionCard | OK | - |
| objeto_resumido | API Search | `EditalModel.objeto` | editais_leilao.objeto_resumido | v_auction_discovery | - | OK | - |
| tags | Hardcoded | `["miner_v10"]` | editais_leilao.tags | v_auction_discovery.tags | - | PARCIAL | `repository.py:949` |
| **link_pncp** | Derivado | `gerar_link_pncp_correto()` | editais_leilao.link_pncp | **Filtrado pela VIEW** | AuctionCard | **PARCIAL** | Corrigido em runtime por `repository.py:951` |
| link_leiloeiro | Auditor | Não implementado Miner | NULL | v_auction_discovery | - | NULL | `repository.py:952` |
| **valor_estimado** | **API Consulta** | **Não mapeado!** | **NULL** | v_auction_discovery | - | **FALHA** | **`repository.py:955` define como NULL fixo** |
| tipo_leilao | API Consulta | `EditalModel.modalidade` | editais_leilao.modalidade_leilao | v_auction_discovery | - | PARCIAL | `repository.py:954` |

---

## (D) Rastreamento Ponta-a-Ponta (Data Lineage)

### Campo: `data_leilao` — FALHA CRÍTICA

**1. Extração (Miner V12):**
- **Arquivo:** `src/core/ache_sucatas_miner_v12.py:700-706`
- **Campo da API:** `dataAberturaProposta` (API Consulta PNCP)
- **Código:**
```python
data_abertura_str = detalhes.get("dataAberturaProposta")
if data_abertura_str:
    data_leilao = self._parse_date(data_abertura_str)
```
- **Status:** ✅ Extração CORRETA

**2. Modelo de Dados (Miner V12):**
- **Arquivo:** `src/core/ache_sucatas_miner_v12.py:357`
- **Campo:** `data_leilao: Optional[datetime] = None`
- **Status:** ✅ Campo EXISTE no modelo

**3. Serialização (Miner V12):**
- **Arquivo:** `src/core/ache_sucatas_miner_v12.py:917-919`
- **Código:**
```python
if edital_dict.get("data_leilao"):
    edital_dict["data_leilao"] = edital.data_leilao.isoformat()
```
- **Status:** ✅ Serialização CORRETA

**4. Persistência — PONTO DE FALHA:**
- **Arquivo:** `src/core/supabase_repository.py:908-909`
- **BUG CRÍTICO:**
```python
# Formatar data_leilao (data_inicio_propostas)
data_leilao = edital.get("data_inicio_propostas")  # ← CAMPO ERRADO!
```
- **O Miner envia:** `edital["data_leilao"]`
- **O Repository lê:** `edital.get("data_inicio_propostas")` (que é NULL)
- **Status:** ❌ **FALHA AQUI** — Campo perdido

**5. VIEW — FILTRO EXCLUDENTE:**
- **Arquivo:** `frontend/supabase/supabase_infrastructure.sql:182-185`
- **Cláusula:**
```sql
WHERE l.publication_status = 'published'
  AND l.data_leilao IS NOT NULL    -- ← Exclui registros sem data_leilao!
  AND l.link_pncp IS NOT NULL
```
- **Status:** ❌ Registros com NULL são EXCLUÍDOS da view

---

### Campo: `valor_estimado` — FALHA CRÍTICA

**1. Extração (Miner V12):**
- **Arquivo:** `src/core/ache_sucatas_miner_v12.py:712-718`
- **Campo da API:** `valorTotalEstimado` (API Consulta PNCP)
- **Status:** ✅ Extração CORRETA

**2. Modelo de Dados:**
- **Arquivo:** `src/core/ache_sucatas_miner_v12.py:372`
- **Campo:** `valor_estimado: Optional[float] = None`
- **Status:** ✅ Campo EXISTE no modelo

**3. Persistência — PONTO DE FALHA:**
- **Arquivo:** `src/core/supabase_repository.py:955`
- **BUG:**
```python
"valor_estimado": None,  # Auditor extrai
```
- **O Miner envia:** `edital["valor_estimado"]` com valor real
- **O Repository define:** `None` (ignora o valor enviado)
- **Status:** ❌ **FALHA AQUI** — Valor descartado

---

### Campo: `link_pncp` — PARCIALMENTE FUNCIONAL

**1. Geração:**
- **Arquivo:** `src/core/supabase_repository.py:951`
- **Código:**
```python
"link_pncp": gerar_link_pncp_correto(cnpj, ano, seq) or edital.get("link_pncp", ""),
```
- **Status:** ✅ Corrigido, porém alguns registros antigos podem ter link inválido

**2. VIEW Filtro:**
- **Cláusula:** `AND l.link_pncp IS NOT NULL`
- **Status:** ⚠️ Registros sem link são excluídos

---

## (E) Investigação de Regressão via Git

### Commits Relevantes:

| SHA | Data | Mensagem | Impacto |
|-----|------|----------|---------|
| `ae44dc0` | 2026-01-19 | fix: Add Miner V12 + Auditor V15 to fetch data_leilao | Criou V12 mas NÃO atualizou supabase_repository.py |
| `c9370b1` | 2026-01-19 | chore: Update GitHub Actions workflow | Passou a usar V12 em produção |
| `ea3cde1` | 2026-01-20 | fix: Add rate limiting delays | Ajustes de rate limit, sem fix no mapping |

### Evidência Git Blame:
- **Arquivo:** `src/core/supabase_repository.py:909`
- **Commit:** `a639ebd2` (2026-01-16)
- **Autor:** thiagodiasdigital
- **Conclusão:** A função `_mapear_edital_model_para_v13` foi criada ANTES do V12 e nunca foi atualizada.

### Comentário TODO não implementado:
- **Arquivo:** `src/core/ache_sucatas_miner_v12.py:904-905`
```python
IMPORTANTE: O método inserir_edital_miner do supabase_repository
precisa ser atualizado para mapear data_leilao corretamente.
```
- **Evidência:** O método `inserir_edital_miner_v12` **NÃO EXISTE** no repository.

---

## (F) Supabase Forensics

### Arquitetura de Tabelas:

```
┌─────────────────────────┐     ┌─────────────────────┐
│ public.editais_leilao   │     │     raw.leiloes     │
│ (Miner escreve aqui)    │ --> │ (Dashboard lê aqui) │
└─────────────────────────┘     └──────────┬──────────┘
                                           │
                        LEFT JOIN pub.ref_municipios
                                           │
                                           v
                               ┌───────────────────────┐
                               │ pub.v_auction_discovery│
                               │  (VIEW com filtros)   │
                               └───────────────────────┘
                                           │
                                           v
                               ┌───────────────────────┐
                               │ fetch_auctions_paginated│
                               │       (RPC)           │
                               └───────────────────────┘
```

### Schema da Tabela `raw.leiloes`:
- **Evidência:** `frontend/supabase/supabase_infrastructure.sql:54-106`
- **Colunas relevantes:**
  - `data_leilao TIMESTAMPTZ` (linha 71)
  - `link_pncp VARCHAR(500)` (linha 79)
  - `valor_estimado DECIMAL(15, 2)` (linha 85)

### VIEW `pub.v_auction_discovery`:
- **Evidência:** `frontend/supabase/supabase_infrastructure.sql:148-187`
- **Filtros Excludentes:**
```sql
WHERE
    l.publication_status = 'published'
    AND l.data_leilao IS NOT NULL
    AND l.link_pncp IS NOT NULL
```

### SQL Diagnóstico:
```sql
-- Quantificar NULLs por campo
SELECT
    COUNT(*) AS total,
    COUNT(*) FILTER (WHERE data_leilao IS NULL) AS sem_data_leilao,
    COUNT(*) FILTER (WHERE link_pncp IS NULL OR link_pncp = '') AS sem_link_pncp,
    COUNT(*) FILTER (WHERE valor_estimado IS NULL) AS sem_valor_estimado
FROM raw.leiloes;
```

---

## (G) Frontend/API Forensics

### Query do Dashboard:
- **Arquivo:** `frontend/src/hooks/useAuctions.ts:40-54`
- **RPC:** `fetch_auctions_paginated`
- **View consumida:** `pub.v_auction_discovery`

### Campos Esperados pelo Frontend:
- **Arquivo:** `frontend/src/types/database.ts:40-68`
- **Type:** `Database["pub"]["Views"]["v_auction_discovery"]["Row"]`
- **Campos:** `data_leilao: string | null`, `link_pncp: string | null`, `valor_estimado: number | null`

### Mapeamento:
- O frontend ESPERA esses campos
- A API RETORNA esses campos (se não forem NULL)
- A VIEW EXCLUI registros onde `data_leilao IS NULL` ou `link_pncp IS NULL`

---

## (H) Causas Raiz (Ordenadas por Impacto)

### 1. **BUG CRÍTICO: Mapeamento de `data_leilao`** (Impacto: 100% dos novos registros)
- **Evidência:** `src/core/supabase_repository.py:909`
- **Problema:** Lê `data_inicio_propostas` em vez de `data_leilao`
- **Resultado:** 100% dos registros inseridos pelo Miner V12 têm `data_leilao = NULL`

### 2. **BUG CRÍTICO: `valor_estimado` ignorado** (Impacto: 100% dos novos registros)
- **Evidência:** `src/core/supabase_repository.py:955`
- **Problema:** Campo definido como `None` fixo, ignorando valor do Miner
- **Resultado:** 100% dos registros têm `valor_estimado = NULL`

### 3. **VIEW com Filtros Excludentes** (Impacto: Registros sem data_leilao/link invisíveis)
- **Evidência:** `frontend/supabase/supabase_infrastructure.sql:182-185`
- **Problema:** `AND l.data_leilao IS NOT NULL AND l.link_pncp IS NOT NULL`
- **Resultado:** Registros com campos NULL não aparecem no dashboard

### 4. **Tabelas Desincronizadas** (Impacto: Dados existentes não migrados)
- **Miner escreve em:** `public.editais_leilao`
- **View lê de:** `raw.leiloes`
- **Script de sincronização:** `SINCRONIZAR_DADOS.sql` (deve ser executado manualmente)

### 5. **Método V12 Não Implementado**
- **Evidência:** `miner_v12.py:922-925` verifica `inserir_edital_miner_v12` que não existe
- **Fallback:** Usa `inserir_edital_miner` com mapeamento V10/V11

---

## (I) Remediações (Propostas, Sem Implementar)

### Correção 1: Atualizar Mapeamento de `data_leilao`
- **Arquivo:** `src/core/supabase_repository.py`
- **Linha:** 909
- **De:** `edital.get("data_inicio_propostas")`
- **Para:** `edital.get("data_leilao") or edital.get("data_inicio_propostas")`
- **Risco:** Baixo
- **Impacto:** Alto — restaura 100% da funcionalidade para novos registros

### Correção 2: Mapear `valor_estimado` do Miner
- **Arquivo:** `src/core/supabase_repository.py`
- **Linha:** 955
- **De:** `"valor_estimado": None`
- **Para:** `"valor_estimado": edital.get("valor_estimado")`
- **Risco:** Baixo
- **Impacto:** Alto — restaura valor estimado

### Correção 3: Remover Filtros Excludentes da VIEW
- **Executar SQL:** `CORRIGIR_VIEW.sql` (já existe no repositório)
- **Risco:** Médio — pode mostrar registros incompletos
- **Impacto:** Alto — exibe todos os registros imediatamente

### Correção 4: Sincronizar Dados entre Tabelas
- **Executar SQL:** `SINCRONIZAR_DADOS.sql` (já existe no repositório)
- **Risco:** Baixo
- **Impacto:** Médio — copia dados existentes

### Ordem de Execução Segura:
1. Corrigir `supabase_repository.py` (linhas 909 e 955)
2. Executar `SINCRONIZAR_DADOS.sql` no Supabase
3. Executar `CORRIGIR_VIEW.sql` no Supabase
4. Re-executar o Miner V12 para popular novos registros com dados corretos

---

## (J) Verificação (Definition of Done)

### Checklist SQL de Validação:
```sql
-- 1. Verificar que data_leilao não é mais NULL
SELECT
    COUNT(*) AS total,
    COUNT(data_leilao) AS com_data_leilao,
    ROUND(100.0 * COUNT(data_leilao) / COUNT(*), 2) AS percentual
FROM raw.leiloes
WHERE created_at > NOW() - INTERVAL '1 day';

-- 2. Verificar valor_estimado
SELECT
    COUNT(*) AS total,
    COUNT(valor_estimado) AS com_valor,
    ROUND(100.0 * COUNT(valor_estimado) / COUNT(*), 2) AS percentual
FROM raw.leiloes
WHERE created_at > NOW() - INTERVAL '1 day';

-- 3. Verificar que view retorna registros
SELECT COUNT(*) FROM pub.v_auction_discovery;

-- 4. Comparar tabelas
SELECT
    (SELECT COUNT(*) FROM public.editais_leilao) AS editais_leilao,
    (SELECT COUNT(*) FROM raw.leiloes) AS raw_leiloes,
    (SELECT COUNT(*) FROM pub.v_auction_discovery) AS view_discovery;
```

### Validação no Dashboard:
1. Acessar `http://localhost:5173` (ou URL de produção)
2. Verificar que cards de leilão exibem data do leilão
3. Verificar que filtro de data funciona
4. Verificar que mapa exibe pontos (requer coordenadas)

### Critérios de Sucesso:
- [ ] 100% dos novos registros têm `data_leilao` não-NULL
- [ ] VIEW `pub.v_auction_discovery` retorna registros
- [ ] Dashboard exibe cards com datas
- [ ] CalendarView funciona com filtros de data

---

## CONCLUSÃO FINAL

A regressão foi causada por **falta de atualização do `supabase_repository.py`** após a criação do Miner V12. O código do Miner está correto, mas o Repository ainda usa mapeamentos da versão anterior, ignorando os campos `data_leilao` e `valor_estimado` enviados pelo V12.

A correção requer **edição de 2 linhas** no `supabase_repository.py` e **execução de 2 scripts SQL** já existentes no repositório.

---

*Relatório gerado por Claude Code Opus 4.5 em 2026-01-20*
