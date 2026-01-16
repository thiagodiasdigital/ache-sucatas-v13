# CLAUDE.md - Contexto do Projeto ACHE SUCATAS

## Visão Geral

**ACHE SUCATAS DaaS** - Sistema de coleta e análise de editais de leilão público do Brasil.
- Coleta dados da API PNCP (Portal Nacional de Contratações Públicas)
- Faz download e parsing de PDFs de editais
- Extrai informações estruturadas (título, data, valores, itens, etc.)
- Persiste no Supabase PostgreSQL

## Escopo do Projeto

### Objetivo de Negócio
Criar um banco de dados estruturado de **leilões públicos municipais** do Brasil, focando em:
- Veículos e máquinas inservíveis
- Sucatas e materiais recicláveis
- Bens móveis de prefeituras

### Público-Alvo
- Empresas de reciclagem e sucata
- Compradores de leilões públicos
- Analistas de mercado de leilões

### Fontes de Dados
1. **API PNCP** - Metadados dos editais (título, órgão, datas, links)
2. **PDFs dos Editais** - Detalhes extraídos (itens, valores, leiloeiro)

### Fora do Escopo (por enquanto)
- Leilões federais e estaduais
- Leilões de imóveis
- Integração com sistemas de leiloeiros
- Interface web/dashboard

## Roadmap

### Fase 1 - Coleta (CONCLUÍDA)
- [x] Miner V9 coletando da API PNCP
- [x] Download automático de PDFs
- [x] 198 editais coletados

### Fase 2 - Extração (CONCLUÍDA)
- [x] Auditor V13 extraindo dados dos PDFs
- [x] 14 campos estruturados
- [x] Score de qualidade calculado

### Fase 3 - Persistência (EM ANDAMENTO)
- [x] Supabase configurado
- [x] Freios de segurança ativos
- [ ] Migração dos 198 editais
- [ ] Miner V10 logando no Supabase

### Fase 4 - Automação (PENDENTE)
- [ ] Cron job para execução diária
- [ ] Alertas de novos editais
- [ ] Monitoramento de erros

### Fase 5 - Expansão (FUTURO)
- [ ] Dashboard de visualização
- [ ] API REST para consultas
- [ ] Mais filtros e análises

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

## Status Atual (Janeiro 2026)

### Completo
| Item | Detalhes |
|------|----------|
| Coleta PNCP | 198 editais baixados |
| Auditor V13 | Extração de 14 campos |
| Supabase | Schema criado, RLS ativo |
| Segurança | Freios $50 USD configurados |
| GitHub | Repo privado sincronizado |

### Em Andamento
| Item | Progresso | Bloqueio |
|------|-----------|----------|
| Migração 198 editais | 5/198 (2.5%) | Pausado pelo usuário |

### Pendente
| Item | Prioridade | Dependência |
|------|------------|-------------|
| Completar migração | Alta | Nenhuma |
| Miner V10 + Supabase | Média | Migração |
| Cron/Agendamento | Média | Miner V10 |
| Dashboard | Baixa | Dados no Supabase |

## Próximos Passos

1. **Imediato:** Executar `python migrar_v13_robusto.py` para migrar 198 editais
2. **Depois:** Integrar Miner V10 com Supabase (tabela execucoes_miner)
3. **Depois:** Configurar agendamento automático (cron ou Task Scheduler)
4. **Futuro:** Considerar dashboard de visualização

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

## Quick Start (Novo Ambiente)

```bash
# 1. Clonar repositório
git clone https://github.com/thiagodiasdigital/ache-sucatas-v13.git
cd ache-sucatas-v13

# 2. Instalar dependências
pip install -r requirements.txt

# 3. Criar arquivo .env (copiar de .env.example ou pedir credenciais)
# SUPABASE_URL=https://xxx.supabase.co
# SUPABASE_SERVICE_KEY=eyJ...
# ENABLE_SUPABASE=true
# MAX_EDITAIS_SUPABASE=10000

# 4. Verificar conexão Supabase
python testar_supabase_conexao.py

# 5. Verificar estado atual
python -c "from supabase_repository import SupabaseRepository; r = SupabaseRepository(); print(f'Editais no Supabase: {r.contar_editais()}')"
```

## Troubleshooting

### Erro de conexão Supabase
```
Problema: "Could not connect to Supabase"
Causa: Credenciais inválidas ou Supabase desligado
Solução:
  1. Verificar .env (SUPABASE_URL e SUPABASE_SERVICE_KEY)
  2. Verificar se ENABLE_SUPABASE=true
  3. Testar no Dashboard: https://supabase.com/dashboard
```

### Migração travou no meio
```
Problema: Script parou em X/198 editais
Causa: PDF problemático ou timeout
Solução:
  1. O script migrar_v13_robusto.py tem try/except
  2. Ele pula editais com erro e continua
  3. Verifique o log para ver quais falharam
  4. Execute novamente - editais já migrados são atualizados (upsert)
```

### Warning de PDF (ignorar)
```
Problema: "Cannot set gray non-stroke color..."
Causa: PDF com padrões de cor inválidos
Solução: IGNORAR - não afeta extração dos dados
```

### Limite de segurança atingido
```
Problema: "LIMITE ATINGIDO: X/10000 editais"
Causa: Freio de segurança ativado
Solução:
  1. Verificar custo no Dashboard Supabase
  2. Se dentro do limite $50, aumentar MAX_EDITAIS_SUPABASE no .env
  3. Ou deletar editais antigos/duplicados
```

## Decisões de Arquitetura

| Decisão | Motivo |
|---------|--------|
| Limite $50 USD | Aprovado pelo usuário para controle de custos |
| MAX_EDITAIS=10.000 | Margem segura para ~200 editais/mês |
| Supabase PostgreSQL | Free tier generoso, fácil setup, RLS nativo |
| Feature flag ENABLE_SUPABASE | Permite desligar rapidamente sem alterar código |
| Dual storage (Supabase + CSV) | Backup local caso Supabase falhe |
| Script robusto com try/except | Continua migração mesmo com PDFs problemáticos |
| V13 (não V12) | V13 adiciona integração Supabase ao V12 |

## Estado Atual do Banco (verificar sempre)

Para verificar o estado atual, execute:
```bash
python -c "from supabase_repository import SupabaseRepository; r = SupabaseRepository(); print(f'Editais: {r.contar_editais()}/198')"
```

**Última verificação:** 5 editais no Supabase (Janeiro 2026)
**Pendente:** 193 editais para migrar

## Notas Importantes

1. **NUNCA commitar `.env`** - contém credenciais Supabase
2. **ACHE_SUCATAS_DB/** está no .gitignore (PDFs muito grandes)
3. Limite de $50 USD aprovado para Supabase
4. Sempre testar com poucos editais antes de migração em lote
5. Rodar `pip install -r requirements.txt` em novo ambiente
6. **Se em dúvida, pergunte antes de executar comandos destrutivos**
