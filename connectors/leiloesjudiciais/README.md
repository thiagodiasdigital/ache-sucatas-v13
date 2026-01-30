# Conector Leilões Judiciais

Conector para scraping do site [leiloesjudiciais.com.br](https://www.leiloesjudiciais.com.br/), integrando dados de leilões de veículos e sucatas ao Ache Sucatas.

## Visão Geral

Este conector implementa um pipeline completo de coleta de dados:

1. **Descoberta**: Extrai URLs de lotes do sitemap.xml
2. **Fetch**: Busca páginas com rate limiting e retry
3. **Parse**: Extrai dados do HTML (título, localização)
4. **Normalização**: Converte para o Contrato Canônico
5. **Emissão**: Salva em JSONL e/ou Supabase

## Estrutura

```
connectors/leiloesjudiciais/
├── __init__.py       # Package init
├── config.py         # Configurações e constantes
├── discover.py       # Descoberta de URLs via sitemap
├── fetch.py          # Fetcher HTTP com retry/rate limiting
├── parse.py          # Parser de HTML
├── normalize.py      # Normalização para Contrato Canônico
├── emit.py           # Emissão de dados e relatórios
├── run_scraper.py    # Script principal
└── README.md         # Este arquivo
```

## Uso

### Execução Básica

```bash
# Processar até 100 lotes (padrão)
python connectors/leiloesjudiciais/run_scraper.py

# Processar 500 lotes
python connectors/leiloesjudiciais/run_scraper.py --max-lots 500

# Modo simulação (não faz fetch)
python connectors/leiloesjudiciais/run_scraper.py --dry-run

# Persistir no Supabase
python connectors/leiloesjudiciais/run_scraper.py --persist

# Modo verboso
python connectors/leiloesjudiciais/run_scraper.py -v
```

### Argumentos

| Argumento | Descrição | Padrão |
|-----------|-----------|--------|
| `--mode` | `incremental` ou `full` | incremental |
| `--max-lots` | Máximo de lotes a processar | 100 |
| `--category` | `vehicles` ou `all` | vehicles |
| `--persist` | Persistir no Supabase | False |
| `--dry-run` | Modo simulação | False |
| `--output` | Arquivo de saída customizado | - |
| `-v, --verbose` | Modo debug | False |

## Variáveis de Ambiente

Para persistência no Supabase, configure:

```bash
# Set SUPABASE_URL and SUPABASE_SERVICE_KEY in your .env file
```

## Saídas

### Arquivos Gerados

```
out/
├── leiloesjudiciais_items.jsonl    # Itens válidos (JSONL)
├── reports/
│   └── report_leiloesjudiciais_*.json  # Relatórios de execução
└── quarantine/
    └── quarantine_leiloesjudiciais_*.jsonl  # Itens inválidos
```

### Formato do Item (JSONL)

```json
{
  "id_interno": "leiloesjudiciais|ABC123DEF456",
  "titulo": "FIAT/OGGI CS 1983/1983",
  "descricao": "Veículo FIAT/OGGI CS 1983/1983. Localização: Cordeiro/RJ",
  "cidade": "Cordeiro",
  "uf": "RJ",
  "data_publicacao": "29-01-2026",
  "link_leiloeiro": "https://www.leiloesjudiciais.com.br/lote/34116/119545",
  "link_pncp": null,
  "pncp_id": null,
  "tags": ["CARRO"],
  "objeto_resumido": "FIAT/OGGI CS 1983/1983",
  "source_type": "leiloeiro",
  "source_name": "Leilões Judiciais",
  "metadata": {
    "leilao_id": "34116",
    "lote_id": "119545",
    "source_url": "https://www.leiloesjudiciais.com.br/lote/34116/119545"
  },
  "publication_status": "published",
  "score": 60
}
```

## Limitações

### Site é uma SPA (Vue.js)

O site carrega conteúdo via JavaScript/API, o que limita a extração via HTTP puro:

- **Título da página**: Contém descrição do veículo e localização
- **Meta tags**: Podem estar ausentes
- **Valores/Datas**: Não disponíveis no HTML estático

### Dados Disponíveis

| Campo | Disponível | Fonte |
|-------|------------|-------|
| Descrição veículo | ✅ | Title |
| Cidade/UF | ✅ | Title |
| URL do lote | ✅ | Sitemap |
| Valor avaliação | ❌ | Requer JS |
| Data do leilão | ❌ | Requer JS |
| Imagens | Parcial | HTML |
| Documentos | ❌ | Requer JS |

### Possíveis Melhorias Futuras

1. Usar Playwright/Selenium para renderização JS
2. Descobrir API interna do site
3. Integrar OCR para imagens de documentos

## Rate Limiting

O conector implementa:

- **1 requisição/segundo** (configurável)
- **Retry com backoff exponencial** (3 tentativas)
- **Tombstone para 404/410** (não tenta novamente)
- **Tratamento de 429/503** (aguarda e retenta)

## Idempotência

Cada lote tem um `id_interno` único gerado a partir de:

```
leiloesjudiciais|{hash(leilao_id + lote_id)}
```

Isso garante que re-execuções não dupliquem dados no Supabase.

## Integração com Dashboard

Após a migração SQL (`007_add_source_type_for_leiloeiro.sql`), o dashboard mostra:

- **Badge "LEILOEIRO"** para itens com `source_type='leiloeiro'`
- **Badge "PNCP"** para itens com `source_type='pncp'`
- **Botão "Ver Lote"** usando `link_leiloeiro` como URL principal

## Dependências

```
httpx>=0.24.0
beautifulsoup4>=4.12.0  # Opcional, melhora parsing
```

Instalar:

```bash
pip install httpx beautifulsoup4
```

## Criando Novos Conectores

Este conector serve como modelo para outros sites de leiloeiros.

1. Copie a estrutura de `connectors/leiloesjudiciais/`
2. Ajuste `config.py` com URLs e padrões do novo site
3. Implemente `discover.py` para descoberta de lotes
4. Implemente `parse.py` para extração de dados
5. O restante (normalize, emit) pode ser reutilizado

Veja `connectors/base_connector.py` para interface abstrata.

## Troubleshooting

### Nenhum lote encontrado

```
WARN: Nenhum lote encontrado!
```

Verificar:
1. Sitemap está acessível?
2. Padrão de URL mudou?
3. Site está bloqueando requests?

### Muitos itens em quarentena

Verificar `out/quarantine/` para detalhes dos erros.

Causas comuns:
- Título não segue padrão esperado
- Cidade/UF não identificados
- Site mudou estrutura HTML

### Timeout/Rate limiting

Ajustar em `config.py`:
```python
REQUESTS_PER_SECOND = 0.5  # Mais lento
REQUEST_TIMEOUT_SECONDS = 60  # Mais tolerante
```
