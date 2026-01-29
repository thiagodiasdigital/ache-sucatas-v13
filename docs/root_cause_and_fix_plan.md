# Causa Raiz e Plano de Correção

**Data:** 2026-01-29
**Autor:** Claude (Auditoria Forense L8)
**Severidade:** CRÍTICA

---

## 1. Resumo Executivo

A investigação forense dos runs com alta taxa de quarentena (66%-100%) identificou **duas causas raiz principais**:

1. **CAUSA RAIZ #1 (CRÍTICA):** Bug na função `extrair_tipo_leilao_pdf()` - regex tratado como string literal, resultando em `tipo_leilao = None` em 100% dos registros quarentenados.

2. **CAUSA RAIZ #2 (ALTA):** Divergência contrato vs validador - campo `n_edital` marcado como "NÃO obrigatório" no contrato, mas incluído em `REQUIRED_FIELDS` e `SELLABLE_REQUIRED_FIELDS` no validador.

---

## 2. Causa Raiz #1: Bug `extrair_tipo_leilao_pdf()`

### Evidência

**Arquivo:** `src/core/ache_sucatas_miner_v18.py:305-333`

```python
def extrair_tipo_leilao_pdf(texto_pdf: str) -> str:
    """Extrai tipo/modalidade do leilao do texto do PDF."""
    if not texto_pdf:
        return ""

    texto_lower = texto_pdf.lower()

    # BUG: "leil[aã]o eletr[oô]nico" é regex, mas 'in' faz busca literal!
    tem_eletronico = any(p in texto_lower for p in [
        "leil[aã]o eletr[oô]nico", "eletr[oô]nico", "online",
        "modo eletronico", "forma eletronica", "virtual"
    ])
```

**Problema:** A expressão `any(p in texto_lower for p in [...])` faz busca de substring literal. Os patterns `"leil[aã]o eletr[oô]nico"` contêm sintaxe regex (`[aã]`, `[oô]`), mas são tratados como strings literais.

**Resultado:** A string `"leil[aã]o eletr[oô]nico"` nunca será encontrada no texto porque o texto real contém `"leilão eletrônico"` (com acentos), não `"leil[aã]o eletr[oô]nico"`.

### Prova

- 100% dos registros quarentenados nos 4 runs alvo tinham `tipo_leilao = None`
- A função retorna `""` quando nenhum pattern é encontrado
- O validador trata `""` como campo faltante (via `_is_missing()`)

### Correção

```python
# ANTES (bugado):
tem_eletronico = any(p in texto_lower for p in [
    "leil[aã]o eletr[oô]nico", ...
])

# DEPOIS (corrigido):
ELETRONICO_PATTERNS = [
    r"leil[aã]o\s+eletr[oô]nico",
    r"eletr[oô]nico",
    "online",
    "modo eletronico",
    "forma eletronica",
    "virtual"
]

tem_eletronico = any(
    re.search(p, texto_lower) if '[' in p or '\\' in p else p in texto_lower
    for p in ELETRONICO_PATTERNS
)
```

### Risco

- **Baixo:** Correção localizada, não afeta outros fluxos
- **Teste:** Executar pipeline com textos conhecidos contendo "leilão eletrônico"

### Rollback

- Reverter alteração no arquivo se taxa de quarentena aumentar

---

## 3. Causa Raiz #2: `n_edital` obrigatório incorretamente

### Evidência

**Contrato (`contracts/dataset_contract_v1.md`):**
```markdown
| n_edital | identificação do documento | NÃO | Edital nº 0800100/0001/2026 | PDF |
```

**Validador (`validators/dataset_validator.py:16-31`):**
```python
REQUIRED_FIELDS: Tuple[str, ...] = (
    ...
    "n_edital",  # ← Não deveria estar aqui
    ...
)
```

### Prova

- 162 registros quarentenados globalmente por `n_edital` faltante
- 5 dos 7 registros nos runs alvo tinham `n_edital = None`
- O campo vem do PDF e nem sempre pode ser extraído

### Correção

```python
# ANTES:
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
    "n_edital",        # REMOVER
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
    "n_edital",        # REMOVER
    "tags",
    "valor_estimado",
    "data_publicacao",
)
```

### Risco

- **Muito Baixo:** Alinha implementação com contrato documentado
- **Impacto:** Registros sem `n_edital` passarão para próxima etapa de validação

### Rollback

- Adicionar `n_edital` de volta às listas se necessário

---

## 4. Causa Raiz #3 (Secundária): Fallback de `tipo_leilao`

### Evidência

**Código (`src/core/ache_sucatas_miner_v18.py:2667-2671`):**
```python
tipo_leilao = ""
if texto_pdf:
    tipo_leilao = extrair_tipo_leilao_pdf(texto_pdf)
if not tipo_leilao and edital_db.get("modalidade"):
    tipo_leilao = edital_db.get("modalidade", "")
```

**Problema:** O fallback usa `modalidade` da API, mas:
1. O campo pode estar vazio/None
2. Não há mapeamento de modalidade PNCP → tipo_leilao esperado

### Correção

Adicionar mapeamento explícito:
```python
MODALIDADE_PARA_TIPO = {
    "6": "Eletronico",    # Leilão Eletrônico
    "7": "Presencial",    # Leilão Presencial
    "Leilão": "Eletronico",
    "Leilão Eletrônico": "Eletronico",
}

if not tipo_leilao:
    modalidade = edital_db.get("modalidade", "")
    tipo_leilao = MODALIDADE_PARA_TIPO.get(str(modalidade), "")
```

---

## 5. Plano de Implementação

### Fase 1: Correções Mínimas (Imediato)

| # | Arquivo | Mudança | Risco |
|---|---------|---------|-------|
| 1 | `validators/dataset_validator.py` | Remover `n_edital` de REQUIRED_FIELDS | Baixo |
| 2 | `validators/dataset_validator.py` | Remover `n_edital` de SELLABLE_REQUIRED_FIELDS | Baixo |
| 3 | `src/core/ache_sucatas_miner_v18.py` | Corrigir `extrair_tipo_leilao_pdf()` | Médio |

### Fase 2: Melhorias (Pós-validação)

| # | Arquivo | Mudança | Risco |
|---|---------|---------|-------|
| 4 | `src/core/ache_sucatas_miner_v18.py` | Adicionar mapeamento modalidade→tipo_leilao | Baixo |
| 5 | `validators/dataset_validator.py` | Adicionar campo faltante ao QualityReport | Baixo |

---

## 6. Teste de Validação

### Comando para teste local:

```bash
cd "G:\Meu Drive"

# Setar limite para 10 editais
export RUN_LIMIT=10

# Rodar miner em modo teste
python src/core/ache_sucatas_miner_v18.py --dias 7 --paginas 1 --debug
```

### Critérios de sucesso:

1. Taxa de quarentena < 30%
2. `tipo_leilao` preenchido em > 50% dos registros
3. Nenhum erro `missing_required_field` para `n_edital`
4. Registros válidos aparecem no dashboard

---

## 7. Checklist de Deploy

- [ ] Aplicar patch no validador (remover n_edital)
- [ ] Aplicar patch na função de extração
- [ ] Rodar testes unitários
- [ ] Rodar pipeline em modo teste (RUN_LIMIT=10)
- [ ] Verificar taxa de quarentena
- [ ] Verificar dashboard
- [ ] Commit com mensagem descritiva
- [ ] Monitor próximas 3 execuções

---

## 8. Monitoramento Pós-Deploy

### Métricas a acompanhar:

- `taxa_quarentena_percent` (alvo: < 30%)
- `error_counts.missing_required_field` por campo
- `total_validos` vs `total_processados`

### Alertas:

- Se taxa de quarentena > 50% após patch: rollback imediato
- Se novos campos começarem a falhar: investigar
