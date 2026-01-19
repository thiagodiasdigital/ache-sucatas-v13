# Contrato de Dados - Ache Sucatas v2.0

> **Versao:** 2.0
> **Data:** 2026-01-19
> **Responsavel:** CRAUDIO (Auditoria Automatizada)
> **Schema:** `schema/auction_notice_v2.json`

---

## Resumo

Este documento define o contrato canonico para os dados de editais de leilao publicados pelo sistema Ache Sucatas. O contrato garante compatibilidade entre produtores (Miner/Auditor) e consumidores (Frontend/API).

---

## Versionamento

| Versao | Data | Compatibilidade | Descricao |
|--------|------|-----------------|-----------|
| 1.0 | 2025-12 | - | Versao inicial |
| 2.0 | 2026-01-19 | Backward compatible | Campos adicionais, tipos refinados |

**Politica de versionamento:** Semantic Versioning (MAJOR.MINOR)
- MAJOR: Breaking changes (campos removidos, tipos alterados)
- MINOR: Adicoes (novos campos opcionais)

---

## Schema Principal

### Tabela: `editais`

| Campo | Tipo | Nullable | Default | Descricao |
|-------|------|----------|---------|-----------|
| `id` | serial | NOT NULL | auto | ID interno |
| `pncp_id` | text | NOT NULL | - | ID unico no PNCP (chave natural) |
| `orgao_nome` | text | NOT NULL | - | Nome do orgao licitante |
| `orgao_cnpj` | text | NULL | - | CNPJ do orgao |
| `uf` | text | NOT NULL | - | Sigla da UF (2 chars) |
| `municipio` | text | NOT NULL | - | Nome do municipio |
| `titulo` | text | NOT NULL | - | Titulo do edital |
| `descricao` | text | NULL | - | Descricao completa |
| `objeto` | text | NULL | - | Objeto da licitacao |
| `data_publicacao` | timestamp | NULL | - | Data de publicacao PNCP |
| `data_atualizacao` | text | NULL | - | Ultima atualizacao PNCP |
| `data_inicio_propostas` | text | NULL | - | Inicio do prazo |
| `data_fim_propostas` | text | NULL | - | Fim do prazo |
| `data_leilao` | timestamp | NULL | - | Data do leilao |
| `modalidade` | text | NULL | - | Modalidade (Leilao, Alienacao) |
| `situacao` | text | NULL | - | Status (Publicado, Encerrado) |
| `score` | integer | NOT NULL | 0 | Score de relevancia (0-100) |
| `files_url` | text | NULL | - | URL da API de arquivos |
| `link_pncp` | text | NULL | - | Link direto no PNCP |
| `link_leiloeiro` | text | NULL | - | Link do leiloeiro/plataforma |
| `ano_compra` | text | NULL | - | Ano da compra |
| `numero_sequencial` | text | NULL | - | Numero sequencial |
| `storage_path` | text | NULL | - | Caminho no Supabase Storage |
| `pdf_storage_url` | text | NULL | - | URL publica do PDF |
| `valor_estimado` | numeric | NULL | - | Valor estimado (extraido) |
| `quantidade_itens` | integer | NULL | - | Quantidade de lotes/itens |
| `nome_leiloeiro` | text | NULL | - | Nome do leiloeiro oficial |
| `latitude` | numeric | NULL | - | Coordenada (geocoding) |
| `longitude` | numeric | NULL | - | Coordenada (geocoding) |
| `created_at` | timestamp | NOT NULL | now() | Data de insercao |
| `updated_at` | timestamp | NOT NULL | now() | Data de atualizacao |

### Constraints

```sql
-- Primary Key
PRIMARY KEY (id)

-- Unique
UNIQUE (pncp_id)

-- Check
CHECK (uf ~ '^[A-Z]{2}$' OR uf = 'XX')  -- XX para invalidos
CHECK (score >= 0 AND score <= 100)

-- Indexes
CREATE INDEX idx_editais_uf ON editais(uf);
CREATE INDEX idx_editais_municipio ON editais(municipio);
CREATE INDEX idx_editais_data_publicacao ON editais(data_publicacao);
CREATE INDEX idx_editais_score ON editais(score);
CREATE INDEX idx_editais_pncp_id ON editais(pncp_id);
```

---

## Convencoes

### Naming

| Tipo | Convencao | Exemplo |
|------|-----------|---------|
| Tabelas | snake_case, plural | `editais`, `execucoes_miner` |
| Colunas | snake_case | `data_publicacao`, `orgao_nome` |
| IDs | `id` para PK, `{tabela}_id` para FK | `id`, `edital_id` |
| Timestamps | Sufixo `_at` | `created_at`, `updated_at` |
| URLs | Sufixo `_url` | `pdf_storage_url`, `link_pncp` |
| Datas | Prefixo `data_` | `data_leilao`, `data_publicacao` |

### Nullability

| Regra | Campos |
|-------|--------|
| NOT NULL | `pncp_id`, `orgao_nome`, `uf`, `municipio`, `titulo`, `score` |
| NULL permitido | Campos extraidos, opcionais, derivados |

### Defaults

| Campo | Default | Justificativa |
|-------|---------|---------------|
| `score` | 0 | Score minimo |
| `created_at` | now() | Auditoria |
| `updated_at` | now() | Auditoria |
| `uf` | 'XX' (fallback) | UF invalida |

---

## Formatos de Dados

### Datas

| Formato | Uso | Exemplo |
|---------|-----|---------|
| ISO 8601 | Armazenamento | `2026-01-19T10:30:00` |
| DD/MM/YYYY | Display (BR) | `19/01/2026` |

### Valores Monetarios

| Formato | Uso | Exemplo |
|---------|-----|---------|
| numeric(15,2) | Armazenamento | `150000.00` |
| R$ X.XXX,XX | Display (BR) | `R$ 150.000,00` |

### UF

| Valor | Significado |
|-------|-------------|
| `SP`, `RJ`, etc. | UF valida |
| `XX` | UF invalida/desconhecida |

---

## Views de Consumo

### `pub.v_auction_discovery`

View publica para o frontend:

```sql
CREATE VIEW pub.v_auction_discovery AS
SELECT
  id,
  pncp_id,
  orgao_nome,
  uf,
  municipio,
  titulo,
  descricao,
  data_publicacao,
  data_leilao,
  modalidade,
  situacao,
  score,
  link_pncp,
  link_leiloeiro,
  valor_estimado,
  quantidade_itens,
  nome_leiloeiro,
  latitude,
  longitude,
  created_at
FROM editais
WHERE data_leilao IS NOT NULL;  -- Apenas editais com data definida
```

---

## Compatibilidade

### Backward Compatibility (v1 -> v2)

| Campo v1 | Campo v2 | Status |
|----------|----------|--------|
| Todos existentes | Mantidos | OK |
| - | `latitude` | ADICIONADO |
| - | `longitude` | ADICIONADO |
| - | `quantidade_itens` | ADICIONADO |
| - | `nome_leiloeiro` | ADICIONADO |

### Forward Compatibility

Consumidores devem ignorar campos desconhecidos para garantir forward compatibility.

---

## Validacao

### Script de Validacao

```python
# Exemplo de validacao de edital
def validar_edital(edital: dict) -> list[str]:
    erros = []

    # Campos obrigatorios
    required = ['pncp_id', 'orgao_nome', 'uf', 'municipio', 'titulo']
    for campo in required:
        if not edital.get(campo):
            erros.append(f"Campo obrigatorio ausente: {campo}")

    # UF valida
    uf = edital.get('uf', '')
    if not (len(uf) == 2 and uf.isupper()) and uf != 'XX':
        erros.append(f"UF invalida: {uf}")

    # Score no range
    score = edital.get('score', 0)
    if not (0 <= score <= 100):
        erros.append(f"Score fora do range: {score}")

    return erros
```

---

## Changelog

Ver arquivo: `docs/contracts/changelog.md`

---

## Historico de Alteracoes

| Data | Versao | Descricao |
|------|--------|-----------|
| 2025-12-XX | 1.0 | Versao inicial |
| 2026-01-19 | 2.0 | Campos de geocoding, quantidade, leiloeiro |

---

*Documento criado pela auditoria CRAUDIO em 2026-01-19*
