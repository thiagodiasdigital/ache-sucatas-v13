# CHANGELOG - Minerador V12 + Auditor V15

> **Data:** 2026-01-19
> **Autor:** Claude Code (CRAUDIO)
> **Versoes:** Miner V12, Auditor V15

---

## RESUMO EXECUTIVO

Este documento descreve as mudancas implementadas para resolver o problema critico de `data_leilao` ausente em 91% dos editais.

### Problema Identificado

```
┌─────────────────────────────────────────────────────────────────────┐
│                    PROBLEMA (V11 + V14)                             │
├─────────────────────────────────────────────────────────────────────┤
│                                                                     │
│   API de SEARCH do PNCP (usada pelo V11)                           │
│   NAO RETORNA o campo dataAberturaProposta!                         │
│                                                                     │
│   Resultado:                                                        │
│   - 294 editais no banco                                            │
│   - Apenas ~25 com data_leilao (os que o Auditor V14 conseguiu     │
│     extrair do PDF)                                                 │
│   - VIEW filtra com data_leilao IS NOT NULL                         │
│   - Dashboard mostra apenas 25 registros                            │
│                                                                     │
└─────────────────────────────────────────────────────────────────────┘
```

### Solucao Implementada

```
┌─────────────────────────────────────────────────────────────────────┐
│                    SOLUCAO (V12 + V15)                              │
├─────────────────────────────────────────────────────────────────────┤
│                                                                     │
│   MINERADOR V12:                                                    │
│   - Apos buscar na API de SEARCH, faz chamada adicional            │
│   - API CONSULTA: /api/consulta/v1/orgaos/{cnpj}/compras/{ano}/{seq}│
│   - Extrai dataAberturaProposta (campo correto!)                    │
│                                                                     │
│   AUDITOR V15:                                                      │
│   - Cascata de fontes: PDF -> API PNCP -> Descricao                │
│   - Se PDF nao tiver data, busca na API como fallback              │
│                                                                     │
│   SCRIPT DE ATUALIZACAO:                                           │
│   - Atualiza os 294 editais existentes                              │
│   - Busca data_leilao da API para cada um                           │
│                                                                     │
└─────────────────────────────────────────────────────────────────────┘
```

---

## ARQUIVOS CRIADOS

### 1. Minerador V12

**Arquivo:** `src/core/ache_sucatas_miner_v12.py`

**Novidades:**
- DUAS chamadas de API: Search (lista) + Consulta (detalhes)
- Campo `data_leilao` preenchido da API Consulta
- Campo `valor_estimado` tambem extraido da API Consulta
- Metricas detalhadas de data_leilao por fonte
- Rate limiting configuravel para API Consulta
- Retry automatico em caso de falha

**Configuracoes novas (env vars):**
```bash
API_CONSULTA_DELAY_MS=100      # Delay entre chamadas (ms)
API_CONSULTA_MAX_RETRIES=2     # Tentativas em caso de falha
```

**Uso:**
```bash
# Executar minerador V12
PYTHONPATH=src/core python src/core/ache_sucatas_miner_v12.py
```

---

### 2. Auditor V15

**Arquivo:** `src/core/cloud_auditor_v15.py`

**Novidades:**
- CASCATA de fontes para data_leilao: PDF -> API -> Descricao
- Fallback para API PNCP quando PDF falhar
- Metricas detalhadas por fonte de extracao
- Modo `--only-missing-data` para processar so editais sem data
- Cliente de API PNCP integrado

**Configuracoes novas (env vars):**
```bash
ENABLE_API_FALLBACK=true       # Habilita fallback para API
API_CONSULTA_DELAY_MS=200      # Delay entre chamadas (ms)
API_CONSULTA_TIMEOUT=10        # Timeout em segundos
API_CONSULTA_MAX_RETRIES=2     # Tentativas em caso de falha
```

**Uso:**
```bash
# Processar editais pendentes (normal)
PYTHONPATH=src/core python src/core/cloud_auditor_v15.py

# Processar APENAS editais sem data_leilao (recomendado)
PYTHONPATH=src/core python src/core/cloud_auditor_v15.py --only-missing-data

# Reprocessar todos
PYTHONPATH=src/core python src/core/cloud_auditor_v15.py --reprocess-all

# Modo teste (5 editais)
PYTHONPATH=src/core python src/core/cloud_auditor_v15.py --test-mode
```

---

### 3. Script de Atualizacao

**Arquivo:** `src/scripts/atualizar_datas_294_editais.py`

**Funcao:** Atualiza data_leilao de TODOS os editais existentes que nao possuem essa informacao.

**Uso:**
```bash
# Modo teste (10 editais)
python src/scripts/atualizar_datas_294_editais.py --test

# Processar todos os editais sem data_leilao
python src/scripts/atualizar_datas_294_editais.py

# Processar com limite especifico
python src/scripts/atualizar_datas_294_editais.py --limit 50

# Dry-run (sem atualizar banco)
python src/scripts/atualizar_datas_294_editais.py --dry-run

# Modo verbose
python src/scripts/atualizar_datas_294_editais.py --verbose
```

---

## ARQUIVOS PRESERVADOS (NAO MODIFICADOS)

| Arquivo | Versao | Status |
|---------|--------|--------|
| `src/core/ache_sucatas_miner_v11.py` | V11 | INTACTO |
| `src/core/cloud_auditor_v14.py` | V14 | INTACTO |

---

## FLUXO DE DADOS (ANTES vs DEPOIS)

### ANTES (V11 + V14)

```
API Search ──► Miner V11 ──► Banco (sem data_leilao)
                                │
                                ▼
                        Auditor V14 ──► Tenta extrair do PDF
                                        (falha em ~91%)
                                │
                                ▼
                        VIEW filtra ──► 25 editais no Dashboard
```

### DEPOIS (V12 + V15)

```
API Search ──► Miner V12 ──► API Consulta ──► Banco (COM data_leilao!)
                                                │
                                                ▼
                                        VIEW ──► 294 editais no Dashboard

OU (para editais existentes):

Script de Atualizacao ──► API Consulta ──► UPDATE Banco ──► 294 editais
```

---

## ORDEM DE EXECUCAO RECOMENDADA

Para corrigir os dados existentes e garantir que novos editais venham corretos:

### 1. Atualizar editais existentes (URGENTE)

```bash
# Primeiro, testar com 10 editais
python src/scripts/atualizar_datas_294_editais.py --test

# Se OK, rodar para todos
python src/scripts/atualizar_datas_294_editais.py
```

### 2. Configurar GitHub Actions para usar V12

Editar `.github/workflows/ache-sucatas.yml`:
```yaml
# Trocar de:
- run: PYTHONPATH=src/core python src/core/ache_sucatas_miner_v11.py

# Para:
- run: PYTHONPATH=src/core python src/core/ache_sucatas_miner_v12.py
```

### 3. (Opcional) Rodar Auditor V15 para enriquecer dados

```bash
PYTHONPATH=src/core python src/core/cloud_auditor_v15.py --only-missing-data
```

---

## API DO PNCP - REFERENCIA

### API de Search (lista editais)

**URL:** `https://pncp.gov.br/api/search/`

**Campos retornados:**
- `numero_controle_pncp` (pncp_id)
- `titulo_objeto`
- `descricao_objeto`
- `data_publicacao`
- `orgao_nome`, `orgao_cnpj`
- `uf_nome`, `municipio_nome`
- ❌ `data_inicio_propostas` (geralmente NULL)
- ❌ `dataAberturaProposta` (NAO EXISTE)

### API de Consulta (detalhes completos)

**URL:** `https://pncp.gov.br/api/consulta/v1/orgaos/{cnpj}/compras/{ano}/{sequencial}`

**Campos retornados:**
- ✅ `dataAberturaProposta` (DATA DO LEILAO!)
- ✅ `valorTotalEstimado`
- `modalidadeNome`
- `situacaoNome`
- `objetoCompra`
- E muitos outros...

---

## METRICAS ESPERADAS

Apos executar o script de atualizacao:

| Metrica | Antes | Depois |
|---------|-------|--------|
| Editais no banco | 294 | 294 |
| Com data_leilao | ~25 | ~280+ |
| Taxa de sucesso | 8.5% | 95%+ |
| Visiveis na VIEW | 25 | 280+ |

*Nota: Alguns editais podem nao ter dataAberturaProposta na API (leiloes sem data definida ainda).*

---

## TROUBLESHOOTING

### "API retorna 404"

O edital pode ter sido removido do PNCP ou o pncp_id esta mal formatado.

### "Timeout na API"

Aumentar `API_CONSULTA_TIMEOUT` ou `API_CONSULTA_DELAY_MS`.

### "Muitos editais sem dataAberturaProposta"

Alguns orgaos publicam o edital antes de definir a data do leilao. Nesses casos, o Auditor V15 tentara extrair do PDF.

---

## HISTORICO DE VERSOES

| Versao | Data | Descricao |
|--------|------|-----------|
| Miner V11 | 2026-01 | Cloud-native, sem data_leilao |
| Miner V12 | 2026-01-19 | Fix: busca dataAberturaProposta da API Consulta |
| Auditor V14 | 2026-01 | Cloud-native, extrai do PDF |
| Auditor V15 | 2026-01-19 | Fallback para API PNCP |

---

*Documento gerado por Claude Code (CRAUDIO) em 2026-01-19*
