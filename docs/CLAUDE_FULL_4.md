# CLAUDE_FULL_4.md - Banco de Dados e API PNCP

> **Supabase:** PostgreSQL + Storage | **API:** PNCP (Portal Nacional de Contratacoes)

---

## Navegacao da Documentacao

| # | Arquivo | Conteudo |
|---|---------|----------|
| 1 | [CLAUDE_FULL_1.md](./CLAUDE_FULL_1.md) | Estado atual, Frontend React, Hotfixes |
| 2 | [CLAUDE_FULL_2.md](./CLAUDE_FULL_2.md) | Arquitetura e Fluxos |
| 3 | [CLAUDE_FULL_3.md](./CLAUDE_FULL_3.md) | CI/CD, Testes, Workflows |
| **4** | **CLAUDE_FULL_4.md** (este) | Banco de Dados e API PNCP |
| 5 | [CLAUDE_FULL_5.md](./CLAUDE_FULL_5.md) | Seguranca e Configuracao |
| 6 | [CLAUDE_FULL_6.md](./CLAUDE_FULL_6.md) | Operacoes e Historico |

---

## Banco de Dados (Supabase PostgreSQL)

### Tabela: editais_leilao

Tabela principal com os editais coletados.

| Campo | Tipo | Constraints | Descricao |
|-------|------|-------------|-----------|
| id | SERIAL | PK, AUTO | ID auto-incremento |
| pncp_id | TEXT | UNIQUE, NOT NULL | ID unico do PNCP (ex: 18188243000160-1-000161-2025) |
| titulo | TEXT | | Titulo do edital |
| orgao | TEXT | | Orgao responsavel (prefeitura) |
| municipio | TEXT | | Nome da cidade |
| uf | CHAR(2) | CHECK (lista UFs) | Estado (XX = invalido) |
| data_publicacao | TIMESTAMP | | Data de publicacao no PNCP |
| data_leilao | TIMESTAMP | | Data do leilao (extraida do PDF) |
| valor_estimado | DECIMAL(15,2) | | Valor estimado total |
| link_pncp | TEXT | | URL do edital no PNCP |
| link_leiloeiro | TEXT | | URL do site do leiloeiro |
| nome_leiloeiro | TEXT | | Nome do leiloeiro oficial |
| quantidade_itens | INTEGER | | Quantidade de itens/lotes |
| descricao | TEXT | | Descricao resumida dos itens |
| score | INTEGER | | Score de qualidade (0-100) |
| storage_path | TEXT | | Caminho no Supabase Storage |
| pdf_storage_url | TEXT | | URL publica do PDF (se habilitado) |
| processado_auditor | BOOLEAN | DEFAULT false | Flag de processamento |
| created_at | TIMESTAMP | DEFAULT now() | Data de criacao |
| updated_at | TIMESTAMP | | Data de ultima atualizacao |

**Indices:**
- `idx_editais_pncp_id` (pncp_id)
- `idx_editais_processado` (processado_auditor)
- `idx_editais_uf` (uf)
- `idx_editais_data_publicacao` (data_publicacao)

**Constraint check_uf:**
```sql
CHECK (uf IN ('AC','AL','AP','AM','BA','CE','DF','ES','GO','MA',
              'MT','MS','MG','PA','PB','PR','PE','PI','RJ','RN',
              'RS','RO','RR','SC','SP','SE','TO','XX'))
```

---

### Tabela: execucoes_miner

Log de todas as execucoes do Miner.

| Campo | Tipo | Descricao |
|-------|------|-----------|
| id | SERIAL | PK |
| versao_miner | TEXT | Versao (V11_CLOUD) |
| execution_start | TIMESTAMP | Inicio da execucao |
| execution_end | TIMESTAMP | Fim da execucao |
| status | TEXT | RUNNING, SUCCESS, FAILED |
| editais_novos | INTEGER | Novos encontrados |
| downloads | INTEGER | Downloads realizados |
| storage_uploads | INTEGER | Uploads no Storage |
| supabase_inserts | INTEGER | Inserts no banco |
| error_message | TEXT | Mensagem de erro (se falhou) |

---

### Tabela: metricas_diarias

Metricas agregadas por dia.

| Campo | Tipo | Descricao |
|-------|------|-----------|
| id | SERIAL | PK |
| data | DATE | UNIQUE - Data da metrica |
| total_editais | INTEGER | Total acumulado |
| novos_editais | INTEGER | Novos no dia |
| execucoes | INTEGER | Quantidade de execucoes |

---

### Tabelas de Notificacoes (Frontend Semana 2)

#### user_filters

| Campo | Tipo | Descricao |
|-------|------|-----------|
| id | UUID | PK |
| user_id | UUID | FK auth.users |
| label | TEXT | Nome do filtro |
| filter_params | JSONB | Parametros (uf, cidade, tags, valor_min, valor_max) |
| is_active | BOOLEAN | Filtro ativo |
| created_at | TIMESTAMPTZ | Data criacao |

#### notifications

| Campo | Tipo | Descricao |
|-------|------|-----------|
| id | UUID | PK |
| user_id | UUID | FK auth.users |
| auction_id | BIGINT | FK raw.leiloes |
| filter_id | UUID | FK user_filters |
| is_read | BOOLEAN | Lida |
| created_at | TIMESTAMPTZ | Data criacao |

---

## Supabase Storage

### Bucket: editais-pdfs

| Propriedade | Valor |
|-------------|-------|
| Nome | editais-pdfs |
| Visibilidade | Privado |
| Tamanho maximo arquivo | 50 MB |
| Tipos permitidos | PDF, JSON, XLSX, DOC, DOCX |
| Editais armazenados | 698+ |

### Estrutura no Storage

```
Bucket: editais-pdfs (privado)
|
|-- 18188243000160-1-000161-2025/      # Pasta por pncp_id
|   |-- metadados.json                 # Metadados do edital
|   |-- edital_a1b2c3d4.pdf            # PDF principal
|   +-- anexo_e5f6g7h8.xlsx            # Anexos (se houver)
|
|-- 00394460005887-1-000072-2025/
|   +-- ...
|
+-- [698+ editais armazenados]
```

### Estrutura no PostgreSQL

```
Schema: public
|
|-- editais_leilao                     # Tabela principal (294 registros)
|-- execucoes_miner                    # Log de execucoes
+-- metricas_diarias                   # Metricas agregadas
```

---

## API PNCP

### Informacoes Gerais

| Propriedade | Valor |
|-------------|-------|
| Base URL (consulta) | https://pncp.gov.br/api/consulta/v1 |
| Base URL (arquivos) | https://pncp.gov.br/pncp-api/v1 |
| Documentacao | https://pncp.gov.br/api/consulta/swagger-ui/index.html |
| Autenticacao | Nenhuma (API publica) |
| Rate Limit | ~100 req/min (estimado, nao documentado) |

### Endpoints Utilizados

#### 1. Listar Editais

```
GET /contratacoes/publicacao
```

| Parametro | Tipo | Exemplo | Descricao |
|-----------|------|---------|-----------|
| modalidadeId | int | 8 | 8 = Leilao |
| dataPublicacaoInicio | date | 2026-01-15 | Data inicio |
| dataPublicacaoFim | date | 2026-01-16 | Data fim |
| pagina | int | 1 | Numero da pagina |
| tamanhoPagina | int | 500 | Itens por pagina (max 500) |

**Resposta:**
```json
{
  "data": [
    {
      "orgaoEntidade": {
        "cnpj": "18188243000160",
        "razaoSocial": "PREFEITURA MUNICIPAL DE ...",
        "uf": "RS"
      },
      "numeroControlePNCP": "18188243000160-1-000161/2025",
      "titulo": "Leilao de veiculos inserviveis",
      "dataPublicacao": "2026-01-16T10:00:00",
      ...
    }
  ],
  "paginacao": {
    "pagina": 1,
    "totalPaginas": 5,
    "totalRegistros": 2345
  }
}
```

#### 2. Listar Arquivos do Edital

```
GET /orgaos/{cnpj}/compras/{ano}/{sequencial}/arquivos
```

**Exemplo:**
```
GET /orgaos/18188243000160/compras/2025/000161/arquivos
```

**Resposta:**
```json
[
  {
    "sequencialDocumento": 1,
    "titulo": "Edital de Leilao",
    "url": "https://pncp.gov.br/pncp-api/v1/orgaos/.../arquivos/1"
  }
]
```

### Fontes de Dados

| Fonte | Tipo | Uso |
|-------|------|-----|
| API PNCP | REST API | Metadados dos editais (titulo, orgao, datas, links) |
| PDFs dos Editais | Documentos | Detalhes extraidos (itens, valores, leiloeiro) |

### Filtros de Coleta

- **Modalidade:** Leilao (modalidadeId=8)
- **Janela temporal:** Ultimas 24 horas
- **Score minimo:** 30 pontos (relevancia)

### Fora do Escopo (por enquanto)

- Leiloes de imoveis
- Integracao com sistemas de leiloeiros

### Rate Limiting

- **Comportamento:** HTTP 429 Too Many Requests
- **Quando ocorre:** Apos ~9 termos de busca consecutivos
- **Mitigacao:** Janela temporal de 24h reduz requisicoes repetidas
- **Tratamento:** Nao e erro critico, sistema continua na proxima execucao

---

## Queries Uteis

### Contar editais por UF
```sql
SELECT uf, COUNT(*) as total
FROM editais_leilao
GROUP BY uf
ORDER BY total DESC;
```

### Editais pendentes de auditoria
```sql
SELECT pncp_id, titulo, data_publicacao
FROM editais_leilao
WHERE processado_auditor = false
ORDER BY data_publicacao DESC;
```

### Ultimas execucoes do Miner
```sql
SELECT versao_miner, status, editais_novos, execution_start
FROM execucoes_miner
ORDER BY execution_start DESC
LIMIT 5;
```

### Editais com leiloeiro identificado
```sql
SELECT pncp_id, titulo, nome_leiloeiro, link_leiloeiro
FROM editais_leilao
WHERE nome_leiloeiro IS NOT NULL
  AND nome_leiloeiro != 'N/D';
```

---

> Anterior: [CLAUDE_FULL_3.md](./CLAUDE_FULL_3.md) | Proximo: [CLAUDE_FULL_5.md](./CLAUDE_FULL_5.md)
