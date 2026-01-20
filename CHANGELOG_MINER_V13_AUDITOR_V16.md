# Changelog - Miner V13 + Auditor V16

**Data:** 2026-01-20
**Autor:** Claude Code (CRAUDIO)
**Solicitado por:** Thiago

---

## Resumo

Foram criadas novas versoes dos scripts para corrigir problemas de qualidade de dados na **origem**, evitando que os mesmos erros se repitam no futuro.

| Componente | Versao Anterior | Nova Versao | Arquivo |
|------------|-----------------|-------------|---------|
| Miner | V12 | **V13** | `src/core/ache_sucatas_miner_v13.py` |
| Auditor | V15 | **V16** | `src/core/cloud_auditor_v16.py` |

---

## Miner V13 - DATA QUALITY

### Problema Resolvido
O Miner V12 nao filtrava leiloes com data passada, resultando em 6 editais de 2024 no banco de dados.

### Correcao Implementada

```python
# NOVA VALIDACAO DE DATA PASSADA (linhas 320-327)
if Settings.FILTRAR_DATA_PASSADA and data_leilao:
    hoje = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
    if data_leilao < hoje:
        self.metrics.increment("editais_filtrados_data_passada")
        log.debug(f"Edital {pncp_id} IGNORADO: data_leilao < hoje")
        return  # Nao processa este edital
```

### Novas Configuracoes

| Setting | Valor Padrao | Descricao |
|---------|--------------|-----------|
| `FILTRAR_DATA_PASSADA` | `true` | Ignora editais com data_leilao < hoje |

### Nova Metrica

| Metrica | Descricao |
|---------|-----------|
| `editais_filtrados_data_passada` | Contador de editais ignorados por data passada |

### Arquivos Modificados
- `src/core/ache_sucatas_miner_v13.py` (NOVO - copiado de V12)

---

## Auditor V16 - DATA QUALITY

### Problemas Resolvidos

1. **Modalidades inconsistentes**: 7 variacoes diferentes para 3 valores
2. **Tags inuteis**: Tags "sync" e "leilao" sem valor para o usuario
3. **Modalidade contraditoria**: Titulo dizia "Online" mas modalidade era "Presencial"

### Correcoes Implementadas

#### 1. Normalizacao de Modalidades

```python
# MAPEAMENTO DE NORMALIZACAO (Settings)
MODALIDADES_NORMALIZACAO = {
    "Leilao - Eletronico": "Eletronico",
    "PRESENCIAL": "Presencial",
    "Leilao - Presencial": "Presencial",
    "HIBRIDO": "Hibrido",
    # ... etc
}
```

#### 2. Deteccao de Contradicoes

```python
# Se modalidade e "Presencial" mas texto menciona "online", corrige
def normalizar_modalidade(modalidade, titulo, descricao):
    if modalidade_normalizada == "Presencial":
        if "online" in texto:
            if "presencial" in texto:
                return "Hibrido"
            return "Eletronico"
```

#### 3. Limpeza de Tags Proibidas

```python
# Tags que NAO devem existir
TAGS_PROIBIDAS = {"sync", "leilao"}

def limpar_tags(tags):
    return [t for t in tags if t.lower() not in Settings.TAGS_PROIBIDAS]
```

### Novas Configuracoes

| Setting | Valor | Descricao |
|---------|-------|-----------|
| `TAGS_PROIBIDAS` | `{"sync", "leilao"}` | Tags a serem removidas |
| `MODALIDADES_NORMALIZACAO` | (mapeamento) | Normalizacao para 3 valores |

### Funcoes Adicionadas

| Funcao | Descricao |
|--------|-----------|
| `normalizar_modalidade()` | Normaliza e detecta contradicoes |
| `limpar_tags()` | Remove tags proibidas |

### Arquivos Modificados
- `src/core/cloud_auditor_v16.py` (NOVO - copiado de V15)

---

## Como Usar

### Miner V13

```bash
# Execucao normal
cd src/core
python ache_sucatas_miner_v13.py

# Modo teste (limite 10)
python ache_sucatas_miner_v13.py --test-mode

# Limitar quantidade
python ache_sucatas_miner_v13.py --limit 50
```

### Auditor V16

```bash
# Execucao normal (processa editais pendentes)
cd src/core
python cloud_auditor_v16.py

# Processar apenas editais sem data_leilao
python cloud_auditor_v16.py --only-missing-data

# Reprocessar TODOS os editais
python cloud_auditor_v16.py --reprocess-all

# Modo teste (limite 5)
python cloud_auditor_v16.py --test-mode
```

---

## Fluxo de Dados Corrigido

```
PNCP API
    |
    v
[Miner V13] ---> Filtra data passada ---> Supabase DB
    |
    v
[Auditor V16] ---> Normaliza modalidade ---> Supabase DB
              ---> Limpa tags
              ---> Corrige contradicoes
```

---

## Verificacao Pos-Deploy

Apos implantar as novas versoes, execute estas queries para verificar:

```sql
-- Verificar se nao existem mais leiloes com data passada
SELECT COUNT(*) FROM editais_leilao WHERE data_leilao < CURRENT_DATE;

-- Verificar modalidades normalizadas
SELECT DISTINCT modalidade_leilao, COUNT(*)
FROM editais_leilao
GROUP BY modalidade_leilao;

-- Verificar tags limpas
SELECT id, tags
FROM editais_leilao
WHERE 'sync' = ANY(tags) OR 'leilao' = ANY(tags);
```

---

## Historico de Versoes

| Versao | Data | Descricao |
|--------|------|-----------|
| Miner V12 | 2026-01-19 | Rate limiting para evitar 429 |
| **Miner V13** | 2026-01-20 | Filtro de data passada |
| Auditor V15 | 2026-01-19 | Fallback API PNCP |
| **Auditor V16** | 2026-01-20 | Normalizacao modalidades + tags |

---

## Autor

- **Criado por:** Claude Code (claude-opus-4-5-20251101)
- **Data/Hora:** 2026-01-20
