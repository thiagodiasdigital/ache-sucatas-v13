# Discovery Pipeline - Leiloes de Veiculos Governamentais

Pipeline de descoberta e coleta automatizada de leiloes de veiculos do governo (DETRANs, PRF, Receita Federal).

## Status dos Scrapers

| Fonte | Status | Volume Estimado | Frequencia |
|-------|--------|-----------------|------------|
| DETRAN-MG | **Funcionando** | ~500-1000/dia | Diario |
| DETRAN-SP | Planejado | ~1000+/dia | - |
| PRF | Planejado | ~500/dia | - |

## Quick Start

### 1. Executar scraper manualmente

```bash
cd discovery_leiloes_gov

# Teste com 2 leiloes
python scrapers/detran_mg.py --max-leiloes 2

# Coleta completa
python scrapers/detran_mg.py

# Ver resultados
cat outputs/detran_mg/latest.jsonl | head -5
```

### 2. Executar todos os scrapers

```bash
# Dry-run (apenas mostra o que seria feito)
python scrapers/run_daily.py --dry-run

# Execucao real
python scrapers/run_daily.py

# Com persistencia no Supabase
python scrapers/run_daily.py --persist
```

### 3. Configurar execucao automatica (GitHub Actions)

O workflow `.github/workflows/daily-scraper.yml` executa diariamente as 06:00 UTC.

Para ativar:
1. Copie a pasta `.github/workflows/` para a raiz do repo
2. Configure os secrets `SUPABASE_URL` e `SUPABASE_SERVICE_KEY`
3. O workflow executara automaticamente

## Estrutura

```
discovery_leiloes_gov/
├── README.md
├── scrapers/
│   ├── __init__.py
│   ├── detran_mg.py          # Scraper DETRAN-MG
│   └── run_daily.py          # Runner diario
├── sql/
│   └── 001_create_discovery_veiculos.sql  # Schema Supabase
├── outputs/
│   └── detran_mg/
│       ├── veiculos_YYYYMMDD.jsonl
│       ├── metrics_YYYYMMDD.json
│       └── latest.jsonl
├── config/
│   ├── keywords.txt
│   └── seeds.json
└── .github/
    └── workflows/
        └── daily-scraper.yml
```

## Contrato de Dados

Cada veiculo coletado segue o schema:

```json
{
  "id_fonte": "abc123def456",
  "fonte": "DETRAN-MG",
  "edital": "3119/2026",
  "cidade": "Uberlandia",
  "data_encerramento": "11/02/2026 17:00",
  "status_leilao": "Publicado",
  "lote": 1,
  "categoria": "Sucata",
  "marca_modelo": "GM/CORSA SUPER",
  "ano": 1999,
  "valor_inicial": 700.0,
  "url_lote": "https://leilao.detran.mg.gov.br/lotes/...",
  "coletado_em": "2026-01-31T03:44:06Z"
}
```

## Metricas

Cada execucao gera um arquivo de metricas:

```json
{
  "started_at": "2026-01-31T03:40:00Z",
  "finished_at": "2026-01-31T03:44:06Z",
  "requests_made": 35,
  "leiloes_found": 21,
  "veiculos_found": 257,
  "errors": []
}
```

## Configuracao Supabase

1. Execute o SQL em `sql/001_create_discovery_veiculos.sql`
2. Configure as variaveis de ambiente:

Configure via GitHub Secrets ou arquivo `.env`:
- `SUPABASE_URL`: URL do seu projeto Supabase
- `SUPABASE_SERVICE_KEY`: Service key do Supabase

3. Execute com `--persist`:

```bash
python scrapers/run_daily.py --persist
```

## Rate Limits e Boas Praticas

- **Rate limit**: 1 request/segundo por dominio
- **User-Agent**: Identificavel (Mozilla/5.0 padrao)
- **Timeout**: 30 segundos
- **Retries**: 3 tentativas com backoff exponencial
- **Horario**: Preferencialmente madrugada (03:00 BRT)

## Adicionar Novo Scraper

1. Crie `scrapers/nome_fonte.py` seguindo o padrao de `detran_mg.py`
2. Implemente a classe com metodos:
   - `get_leiloes_ativos()` -> Lista de leiloes
   - `get_lotes_leilao()` -> Lotes de um leilao
   - `run()` -> Execucao completa
3. Adicione ao `run_daily.py`
4. Teste: `python scrapers/nome_fonte.py --max-leiloes 1`

## Troubleshooting

### Erro SSL/Certificate
Alguns sites governamentais tem certificados problematicos. Use:
```python
import urllib3
urllib3.disable_warnings()
requests.get(url, verify=False)
```

### Timeout
Aumente o timeout ou adicione mais retries:
```python
TIMEOUT = 60
MAX_RETRIES = 5
```

### Site mudou estrutura
O parsing e baseado em regex. Se o site mudar:
1. Salve o HTML: `curl -o test.html URL`
2. Analise a nova estrutura
3. Ajuste os patterns em `_parse_lotes_page()`

---

*Parte do projeto Ache Sucatas*
