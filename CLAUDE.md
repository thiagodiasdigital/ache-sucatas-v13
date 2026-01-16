# CLAUDE.md - Contexto do Projeto ACHE SUCATAS

## Visão Geral

**ACHE SUCATAS DaaS** - Sistema de coleta e análise de editais de leilão público do Brasil.
- Coleta dados da API PNCP (Portal Nacional de Contratações Públicas)
- Faz download e parsing de PDFs de editais
- Extrai informações estruturadas (título, data, valores, itens, etc.)
- Persiste no Supabase PostgreSQL

## Arquitetura

```
┌─────────────┐     ┌─────────────┐     ┌─────────────┐
│  Miner V9   │────▶│   Database  │────▶│ Auditor V13 │
│  (coleta)   │     │  (PDFs)     │     │  (parsing)  │
└─────────────┘     └─────────────┘     └──────┬──────┘
                                               │
                                               ▼
                                        ┌─────────────┐
                                        │  Supabase   │
                                        │ PostgreSQL  │
                                        └─────────────┘
```

## Arquivos Principais

### Scripts de Produção
| Arquivo | Função |
|---------|--------|
| `local_auditor_v13.py` | Auditor principal - extrai dados dos PDFs |
| `ache_sucatas_miner_v9_cron.py` | Miner - coleta editais da API PNCP |
| `supabase_repository.py` | Repositório Supabase com freios de segurança |
| `migrar_v13_robusto.py` | Script de migração em lote |

### Scripts de Segurança
| Arquivo | Função |
|---------|--------|
| `desligar_supabase.py` | KILL SWITCH - desativa Supabase imediatamente |
| `reativar_supabase.py` | Reativa Supabase após desligamento |
| `monitorar_uso_supabase.py` | Monitor de uso com alertas |
| `testar_freio_seguranca.py` | Testa limite de 10.000 editais |

### Configuração
| Arquivo | Função |
|---------|--------|
| `.env` | Credenciais (NUNCA versionar!) |
| `schemas_v13_supabase.sql` | Schema das 3 tabelas Supabase |
| `.gitignore` | Proteções de arquivos sensíveis |

## Estrutura de Pastas

```
testes-12-01-17h/
├── ACHE_SUCATAS_DB/          # PDFs dos editais (198 pastas)
│   ├── AL_MACEIO/
│   ├── AM_MANAUS/
│   └── ...
├── logs/                      # Logs de execução
├── .env                       # CREDENCIAIS (não versionado)
└── *.py                       # Scripts Python
```

## Variáveis de Ambiente (.env)

```env
# Supabase
SUPABASE_URL=https://xxx.supabase.co
SUPABASE_SERVICE_KEY=eyJ...
ENABLE_SUPABASE=true
MAX_EDITAIS_SUPABASE=10000

# PNCP API
PNCP_API_URL=https://pncp.gov.br/api/consulta/v1
```

## Comandos Úteis

### Executar Auditor V13
```bash
python local_auditor_v13.py
```

### Migrar editais para Supabase
```bash
python migrar_v13_robusto.py
```

### Monitorar uso Supabase
```bash
python monitorar_uso_supabase.py
```

### EMERGÊNCIA - Desligar Supabase
```bash
python desligar_supabase.py
```

## Supabase - Tabelas

1. **editais_leilao** - Dados extraídos dos editais
2. **execucoes_miner** - Log de execuções do Miner
3. **metricas_diarias** - Métricas agregadas

## Freios de Segurança

| Proteção | Limite |
|----------|--------|
| MAX_EDITAIS_SUPABASE | 10.000 registros |
| Custo máximo aprovado | $50 USD |
| Feature flag | ENABLE_SUPABASE=true/false |
| Kill switch | `desligar_supabase.py` |

## Status Atual

- [x] Auditor V13 funcionando
- [x] Supabase integrado
- [x] Freios de segurança ativos
- [x] GitHub configurado (privado)
- [ ] Migração 198 editais (pendente)
- [ ] Miner V10 + Supabase (pendente)

## Convenções de Código

- Python 3.x com type hints
- Encoding UTF-8 para Windows: `sys.stdout.reconfigure(encoding='utf-8')`
- Logs com módulo `logging`
- Try/except em operações de I/O e rede

## GitHub

- **Repo:** https://github.com/thiagodiasdigital/ache-sucatas-v13
- **Visibilidade:** Privado
- **Branch principal:** master

## Dependências Python

Instalar com: `pip install -r requirements.txt`

| Pacote | Uso |
|--------|-----|
| pdfplumber | Parsing de PDFs |
| pandas | Manipulação de dados |
| openpyxl | Exportação Excel |
| supabase | Cliente Supabase |
| python-dotenv | Variáveis de ambiente |
| requests | HTTP requests |
| aiohttp | HTTP async (Miner) |
| aiofiles | I/O async (Miner) |

## API PNCP

- **Base URL:** `https://pncp.gov.br/api/consulta/v1`
- **Endpoint principal:** `/contratacoes/publicacao`
- **Filtros usados:** `modalidadeId=8` (Leilão), `dataPublicacaoFim/Inicio`
- **Rate limit:** Sem limite documentado, mas usar com moderação
- **Docs:** https://pncp.gov.br/api/consulta/swagger-ui/index.html

## Campos Extraídos dos Editais

| Campo | Fonte | Descrição |
|-------|-------|-----------|
| titulo | PDF/JSON | Título do edital |
| n_edital | PDF/JSON | Número do edital |
| orgao | JSON | Órgão responsável |
| municipio | Pasta | Cidade do leilão |
| uf | Pasta | Estado |
| data_publicacao | JSON | Data de publicação |
| data_leilao | PDF | Data do leilão |
| valor_estimado | PDF/API | Valor estimado total |
| link_pncp | JSON | Link no PNCP |
| link_leiloeiro | PDF | Link do leiloeiro |
| nome_leiloeiro | PDF | Nome do leiloeiro |
| quantidade_itens | PDF | Qtd de itens/lotes |
| descricao | PDF | Descrição extraída |
| score | Calculado | Score de qualidade (0-100) |

## Problemas Conhecidos

### Warning de PDF (não crítico)
```
Cannot set gray non-stroke color because /'Pattern1' is an invalid float value
```
- **Causa:** PDFs com padrões de cor inválidos
- **Impacto:** Nenhum - dados são extraídos normalmente
- **Ação:** Ignorar, é warning do pdfplumber

### PDFs problemáticos
- Alguns PDFs demoram mais para processar
- Script `migrar_v13_robusto.py` tem try/except para continuar mesmo com erros

## Backup Local

Além do Supabase, o sistema gera backups locais:
- `analise_editais_v13.csv` - Dados em CSV
- `RESULTADO_FINAL.xlsx` - Dados em Excel
- `ACHE_SUCATAS_DB/` - PDFs originais

## Notas Importantes

1. **NUNCA commitar `.env`** - contém credenciais Supabase
2. **ACHE_SUCATAS_DB/** está no .gitignore (PDFs muito grandes)
3. Limite de $50 USD aprovado para Supabase
4. Sempre testar com poucos editais antes de migração em lote
5. Rodar `pip install -r requirements.txt` em novo ambiente
