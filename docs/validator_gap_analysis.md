# Análise de Gap do Validador - Contrato vs Implementação

**Data:** 2026-01-29
**Autor:** Claude (Auditoria Forense L8)

---

## 1. Resumo das Divergências

| Campo | Contrato | Validador (REQUIRED) | Validador (SELLABLE) | Status |
|-------|----------|---------------------|----------------------|--------|
| id_interno | SIM | ✓ | ✓ | OK |
| municipio | SIM | ✓ | ✓ | OK |
| uf | SIM | ✓ | ✓ | OK |
| data_leilao | SIM | ✓ | ✓ | OK |
| pncp_url | SIM | ✓ | ✓ | OK |
| data_atualizacao | SIM | ✓ | - | OK |
| titulo | SIM | ✓ | ✓ | OK |
| descricao | SIM | ✓ | ✓ | OK |
| orgao | SIM | ✓ | ✓ | OK |
| **n_edital** | **NÃO** | ✓ | ✓ | **DIVERGÊNCIA** |
| objeto_resumido | SIM | ✓ | - | OK |
| tags | SIM | ✓ | ✓ | OK |
| valor_estimado | SIM | ✓ | ✓ | OK |
| tipo_leilao | SIM | ✓ | - | OK |
| data_publicacao | - | - | ✓ | OK (vendabilidade) |
| leiloeiro_url | NÃO | - | - | OK |

---

## 2. Divergência Crítica: `n_edital`

### 2.1 O que diz o contrato

**Arquivo:** `contracts/dataset_contract_v1.md`

```markdown
| n_edital | identificação do documento | NÃO | Edital nº 0800100/0001/2026... | PDF |
```

O campo `n_edital` é marcado como **"NÃO"** obrigatório no contrato.

### 2.2 O que faz o validador

**Arquivo:** `validators/dataset_validator.py:16-31, 38-51`

```python
REQUIRED_FIELDS: Tuple[str, ...] = (
    "id_interno",
    "municipio",
    "uf",
    "data_leilao",
    "pncp_url",
    "data_atualizacao",
    "titulo",
    "descricao",
    "orgao",
    "n_edital",        # ← INCLUÍDO INCORRETAMENTE
    "objeto_resumido",
    "tags",
    "valor_estimado",
    "tipo_leilao",
)

SELLABLE_REQUIRED_FIELDS: Tuple[str, ...] = (
    "data_leilao",
    "pncp_url",
    "municipio",
    "uf",
    "id_interno",
    "titulo",
    "descricao",
    "orgao",
    "n_edital",        # ← INCLUÍDO INCORRETAMENTE
    "tags",
    "valor_estimado",
    "data_publicacao",
)
```

### 2.3 Impacto

- **162 registros** quarentenados por `n_edital` faltante (32% da amostra global)
- 5 dos 7 registros quarentenados no run alvo tinham `n_edital` = None

### 2.4 Correção Proposta

```python
# ANTES (incorreto):
REQUIRED_FIELDS: Tuple[str, ...] = (
    ...
    "n_edital",  # REMOVER
    ...
)

SELLABLE_REQUIRED_FIELDS: Tuple[str, ...] = (
    ...
    "n_edital",  # REMOVER
    ...
)

# DEPOIS (correto):
REQUIRED_FIELDS: Tuple[str, ...] = (
    "id_interno",
    "municipio",
    "uf",
    "data_leilao",
    "pncp_url",
    "data_atualizacao",
    "titulo",
    "descricao",
    "orgao",
    # "n_edital",      # REMOVIDO - NÃO obrigatório conforme contrato
    "objeto_resumido",
    "tags",
    "valor_estimado",
    "tipo_leilao",
)
```

---

## 3. Regras de Validação e Falhas

### 3.1 Regra: `tipo_leilao` obrigatório

**Expectativa:** Campo preenchido com "Presencial", "Eletronico" ou "Hibrido"
**Realidade:** 100% dos registros quarentenados nos runs alvo tinham `tipo_leilao` = None

**Causa Raiz:** Bug na função `extrair_tipo_leilao_pdf()` - regex sendo tratado como string literal.

**Registros derrubados:** 146 (29% da amostra global)

**Exemplo real:**
```json
{
  "id_interno": "76247329000113-1-000006/2026",
  "tipo_leilao": null,
  "descricao": "AQUISIÇÃO DE 01 UM VEÍCULO..."
}
```

**Correção proposta:** Corrigir função de extração e/ou adicionar fallback para modalidade da API.

---

### 3.2 Regra: `n_edital` extraído do PDF

**Expectativa:** Número do edital extraído via regex do PDF
**Realidade:** Extração falha em ~70% dos casos problemáticos

**Causa Raiz:**
1. PDFs nem sempre contêm o padrão esperado
2. Campo marcado como obrigatório quando deveria ser opcional

**Registros derrubados:** 162 (32% da amostra global)

**Exemplo real:**
```json
{
  "id_interno": "27174143000176-1-000212/2025",
  "titulo": "Edital nº 000076/2025",
  "n_edital": null
}
```

**Correção proposta:** Remover de REQUIRED_FIELDS (alinhar com contrato).

---

### 3.3 Regra: `valor_estimado` obrigatório

**Expectativa:** Valor numérico > 0
**Realidade:** API PNCP nem sempre retorna `valorTotalEstimado`

**Registros derrubados:** 435 (87% da amostra global histórica)

**Exemplo real:**
```json
{
  "id_interno": "89161475000173-1-000001/2026",
  "valor_estimado": null
}
```

**Correção proposta:** Considerar fallback para valor mínimo ou marcar como "not_sellable" sem rejeitar completamente.

---

### 3.4 Regra: `tags` não vazias

**Expectativa:** Lista de tags automotivas
**Realidade:** Taxonomia automotiva não encontra termos em alguns editais

**Registros derrubados:** 72 (14% da amostra global)

**Exemplo real:**
```json
{
  "id_interno": "18299446000124-1-000001/2026",
  "tags": null,
  "descricao": "Bens moveis inserviveis antieconomicos ou irrecuperaveis..."
}
```

**Nota:** Este pode ser comportamento correto - editais sem veículos devem ser rejeitados pelo sistema Ache Sucatas (foco em veículos).

---

## 4. Tabela de Regras e Impacto

| Regra | Campo | Registros Derrubados | % Global | Correção |
|-------|-------|---------------------|----------|----------|
| missing_required_field | tipo_leilao | 146 | 29% | Corrigir extração |
| missing_required_field | n_edital | 162 | 32% | Remover de REQUIRED |
| missing_required_field | valor_estimado | 435 | 87% | Fallback/tolerância |
| missing_required_field | objeto_resumido | 97 | 19% | Melhorar extração |
| missing_required_field | tags | 72 | 14% | OK (fora do escopo) |
| invalid_url | pncp_url | 108 | 22% | Verificar normalização |

---

## 5. Priorização de Correções

### Alta Prioridade (Fix Imediato)

1. **Remover `n_edital` de REQUIRED_FIELDS e SELLABLE_REQUIRED_FIELDS**
   - Impacto: -162 quarentenas
   - Risco: Baixo (alinha com contrato)
   - Arquivo: `validators/dataset_validator.py`

2. **Corrigir `extrair_tipo_leilao_pdf()`**
   - Impacto: -146 quarentenas (potencial)
   - Risco: Médio (requer teste)
   - Arquivo: `src/core/ache_sucatas_miner_v18.py`

### Média Prioridade

3. **Adicionar fallback para `tipo_leilao` usando modalidade da API**
   - Impacto: Reduzir quarentenas quando PDF não tem info
   - Arquivo: `src/core/ache_sucatas_miner_v18.py`

4. **Melhorar extração de `objeto_resumido`**
   - Impacto: -97 quarentenas
   - Arquivo: `src/core/ache_sucatas_miner_v18.py`

### Baixa Prioridade

5. **Tolerância para `valor_estimado` = 0 ou None**
   - Análise: Verificar se faz sentido para o negócio
   - Risco: Alto (pode incluir editais inválidos)

---

## 6. Checklist de Verificação Pós-Correção

- [ ] Rodar pipeline com --force em modo teste (RUN_LIMIT=10)
- [ ] Verificar taxa de quarentena < 30%
- [ ] Confirmar que registros válidos aparecem no dashboard
- [ ] Verificar que nenhum campo obrigatório real foi removido
- [ ] Rodar testes unitários do validador
