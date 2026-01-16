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

### Fase 3 - Persistência (CONCLUÍDA)
- [x] Supabase configurado
- [x] Freios de segurança ativos
- [x] Miner V10 com integração Supabase (16/01/2026)
- [x] Migração dos 198 editais existentes

### Fase 4 - Cloud Native (CONCLUÍDA - 16/01/2026)
- [x] **Miner V11** - Upload de PDFs para Supabase Storage
- [x] **Auditor V14** - Lê PDFs do Storage (não mais local)
- [x] **GitHub Actions** - Automação 3x/dia (cron)
- [x] Supabase Storage configurado (bucket: editais-pdfs)

### Fase 5 - Expansão (FUTURO)
- [ ] Dashboard de visualização
- [ ] API REST para consultas
- [ ] Alertas de novos editais

## Arquitetura

### Arquitetura V11 - 100% Cloud

```
┌─────────────────────────────────────────────────────────┐
│                   GITHUB ACTIONS                        │
│              (Cron: 08:00, 16:00, 00:00 UTC)           │
├─────────────────────────────────────────────────────────┤
│                                                         │
│   ┌─────────────┐         ┌─────────────┐              │
│   │  Miner V11  │────────▶│ Auditor V14 │              │
│   │  (coleta)   │         │  (extração) │              │
│   └──────┬──────┘         └──────┬──────┘              │
│          │                       │                      │
└──────────┼───────────────────────┼──────────────────────┘
           │                       │
           ▼                       ▼
    ┌─────────────────────────────────────┐
    │           SUPABASE                   │
    │  ┌─────────────┐  ┌──────────────┐  │
    │  │   Storage   │  │  PostgreSQL  │  │
    │  │   (PDFs)    │  │  (metadados) │  │
    │  └─────────────┘  └──────────────┘  │
    └─────────────────────────────────────┘
```

**Fluxo do Miner V11 (Cloud):**
1. Coleta editais da API PNCP
2. Download do PDF em memória (bytes)
3. Upload PDF para Supabase Storage
4. Insere metadados no PostgreSQL
5. Registra execução em execucoes_miner

**Fluxo do Auditor V14 (Cloud):**
1. Query editais pendentes no PostgreSQL
2. Download PDF do Storage → BytesIO
3. pdfplumber.open(BytesIO) → extrai texto
4. Update no PostgreSQL com dados extraídos

### Arquitetura Legada (V10 - Local)

```
┌─────────────┐     ┌─────────────┐     ┌─────────────┐
│ Miner V10   │────▶│   Local     │────▶│ Auditor V13 │
│  (coleta)   │     │  (PDFs)     │     │  (parsing)  │
└──────┬──────┘     └─────────────┘     └──────┬──────┘
       │                                       │
       ▼                                       ▼
  ┌─────────────────────────────────────────────┐
  │              Supabase PostgreSQL             │
  └─────────────────────────────────────────────┘
```

## Arquivos Principais

### Scripts de Produção (V11 - Cloud)
| Arquivo | Função |
|---------|--------|
| `ache_sucatas_miner_v11.py` | **Miner V11** - coleta 100% cloud (Storage) |
| `cloud_auditor_v14.py` | **Auditor V14** - extrai PDFs do Storage |
| `supabase_storage.py` | Repositório Supabase Storage (upload/download) |
| `supabase_repository.py` | Repositório Supabase PostgreSQL |
| `.github/workflows/ache-sucatas.yml` | GitHub Actions (cron 3x/dia) |

### Scripts Legados (V10 - Local)
| Arquivo | Função |
|---------|--------|
| `ache_sucatas_miner_v10.py` | Miner V10 - coleta + Supabase (local backup) |
| `local_auditor_v13.py` | Auditor V13 - lê PDFs locais |
| `migrar_v13_robusto.py` | Script de migração em lote |
| `ache_sucatas_miner_v9_cron.py` | Miner V9 (legado, sem Supabase) |

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

### Executar Miner V10 (com Supabase)
```bash
python ache_sucatas_miner_v10.py
```

### Executar Auditor V13
```bash
python local_auditor_v13.py
```

### Migrar editais existentes para Supabase
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
| **Miner V10** | Integração Supabase completa (16/01/2026) |

### Em Andamento
| Item | Progresso | Bloqueio |
|------|-----------|----------|
| Migração 198 editais | 5/198 (2.5%) | Pausado pelo usuário |

### Pendente
| Item | Prioridade | Dependência |
|------|------------|-------------|
| Completar migração | Alta | Nenhuma |
| Cron/Task Scheduler | Alta | Nenhuma |
| Dashboard | Baixa | Dados no Supabase |

## Próximos Passos

1. **Imediato:** Executar `python migrar_v13_robusto.py` para migrar 193 editais restantes
2. **Depois:** Configurar agendamento automático do Miner V10 (cron ou Task Scheduler)
3. **Futuro:** Considerar dashboard de visualização

### Agendamento Recomendado (Miner V10)
- **Windows:** Task Scheduler - 3x/dia (00:00, 08:00, 16:00)
- **Linux:** Crontab: `0 0,8,16 * * * cd /path && python ache_sucatas_miner_v10.py`

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

## IMPORTANTE: Dados Locais (não estão no Git)

### ACHE_SUCATAS_DB/ (PDFs dos editais)
Esta pasta contém 198 subpastas com PDFs dos editais. **NÃO está no Git** (muito grande).

**Como obter os PDFs:**
```bash
# Opção 1: Executar o Miner V10 para coletar novamente
python ache_sucatas_miner_v10.py

# Opção 2: Solicitar backup ao proprietário do projeto
# Os PDFs podem estar em backup externo (perguntar ao usuário)
```

**Estrutura esperada:**
```
ACHE_SUCATAS_DB/
├── AL_MACEIO/
│   └── 2025-10-02_S100_04302189000128-1-000019-2025/
│       ├── edital.pdf
│       └── metadados.json
├── AM_MANAUS/
│   └── ...
└── [196 outras pastas por UF_CIDADE]
```

### .env (Credenciais)
Arquivo com credenciais Supabase. **NÃO está no Git** (segurança).

**Como configurar:**
```bash
# Copiar template
cp .env.example .env

# Editar com suas credenciais Supabase
# Obter em: https://supabase.com/dashboard/project/SEU_PROJETO/settings/api
```

## Quick Start (Novo Ambiente)

```bash
# 1. Clonar repositório
git clone https://github.com/thiagodiasdigital/ache-sucatas-v13.git
cd ache-sucatas-v13

# 2. Instalar dependências
pip install -r requirements.txt

# 3. Configurar credenciais
cp .env.example .env
# Editar .env com credenciais Supabase reais

# 4. Obter PDFs dos editais (escolha uma opção):
#    a) Executar Miner V10: python ache_sucatas_miner_v10.py
#    b) Restaurar de backup externo (se disponível)

# 5. Verificar conexão Supabase
python testar_supabase_conexao.py

# 6. Verificar estado atual
python -c "from supabase_repository import SupabaseRepository; r = SupabaseRepository(); print(f'Editais no Supabase: {r.contar_editais()}')"

# 7. Verificar PDFs locais
python -c "from pathlib import Path; p = Path('ACHE_SUCATAS_DB'); print(f'Pastas de editais: {len(list(p.glob(\"*/*\")))}')"
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

## Miner V10 - Detalhes Técnicos

### Funcionalidades
- Coleta editais da API PNCP (igual V9)
- **Insere editais automaticamente no Supabase**
- **Registra execuções na tabela execucoes_miner**
- Mantém salvamento local como backup
- Feature flag `ENABLE_SUPABASE` para desativar

### Métodos Adicionados ao supabase_repository.py
```python
iniciar_execucao_miner(versao, janela, termos, paginas) -> int
    # Registra início da execução (status=RUNNING)

finalizar_execucao_miner(exec_id, metricas, status, erro) -> bool
    # Atualiza execução com métricas finais (SUCCESS/FAILED)

inserir_edital_miner(edital_model_data) -> bool
    # Insere edital vindo do Miner (mapeia EditalModel -> V13)

_mapear_edital_model_para_v13(edital) -> dict
    # Converte campos do Miner para schema Supabase
```

### Verificar Execuções no Supabase
```bash
python -c "
from supabase_repository import SupabaseRepository
r = SupabaseRepository()
resp = r.client.table('execucoes_miner').select('*').order('execution_start', desc=True).limit(5).execute()
for e in resp.data:
    print(f\"[{e['status']}] {e['versao_miner']} - {e['editais_novos']} novos\")
"
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
| Miner V10 fail-safe | Supabase offline não bloqueia coleta local |

## Estado Atual do Banco (verificar sempre)

Para verificar o estado atual, execute:
```bash
python -c "from supabase_repository import SupabaseRepository; r = SupabaseRepository(); print(f'Editais: {r.contar_editais()}/198')"
```

**Última verificação:** 5 editais no Supabase (Janeiro 2026)
**Pendente:** 193 editais para migrar

## Checklist para Nova Sessão Claude

**SEMPRE execute no início de uma nova sessão:**

```bash
# 1. Verificar se .env existe
ls -la .env

# 2. Verificar conexão Supabase
python testar_supabase_conexao.py

# 3. Contar editais no Supabase
python -c "from supabase_repository import SupabaseRepository; r = SupabaseRepository(); print(f'Supabase: {r.contar_editais()} editais')"

# 4. Contar PDFs locais
python -c "from pathlib import Path; p = Path('ACHE_SUCATAS_DB'); folders = list(p.glob('*/*')); print(f'Local: {len(folders)} editais')"
```

**Se algum falhar:**
- `.env` não existe → `cp .env.example .env` e pedir credenciais ao usuário
- Supabase não conecta → Verificar credenciais ou se ENABLE_SUPABASE=true
- PDFs não existem → Executar Miner ou pedir backup ao usuário

## Notas Importantes

1. **NUNCA commitar `.env`** - contém credenciais Supabase
2. **ACHE_SUCATAS_DB/** está no .gitignore (PDFs muito grandes)
3. Limite de $50 USD aprovado para Supabase
4. Sempre testar com poucos editais antes de migração em lote
5. Rodar `pip install -r requirements.txt` em novo ambiente
6. **Se em dúvida, pergunte antes de executar comandos destrutivos**
7. **Executar checklist de nova sessão** antes de qualquer operação
