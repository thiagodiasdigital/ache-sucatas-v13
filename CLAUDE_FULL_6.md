# CLAUDE_FULL_6.md - Operacoes e Historico

> **Comandos uteis** | **Troubleshooting** | **Roadmap** | **Historico de commits**

---

## Navegacao da Documentacao

| # | Arquivo | Conteudo |
|---|---------|----------|
| 1 | [CLAUDE_FULL_1.md](./CLAUDE_FULL_1.md) | Estado atual, Frontend React, Hotfixes |
| 2 | [CLAUDE_FULL_2.md](./CLAUDE_FULL_2.md) | Arquitetura e Fluxos |
| 3 | [CLAUDE_FULL_3.md](./CLAUDE_FULL_3.md) | CI/CD, Testes, Workflows |
| 4 | [CLAUDE_FULL_4.md](./CLAUDE_FULL_4.md) | Banco de Dados e API PNCP |
| 5 | [CLAUDE_FULL_5.md](./CLAUDE_FULL_5.md) | Seguranca e Configuracao |
| **6** | **CLAUDE_FULL_6.md** (este) | Operacoes e Historico |

---

## Comandos Uteis

### Execucao Cloud (RECOMENDADO)

```bash
# Disparar workflow de coleta manualmente (todos os jobs)
gh workflow run ache-sucatas.yml

# Disparar apenas Miner
gh workflow run ache-sucatas.yml -f run_auditor=false

# Disparar apenas Auditor (limitar a 5 editais)
gh workflow run ache-sucatas.yml -f run_miner=false -f auditor_limit=5

# Verificar status dos ultimos workflows de coleta
gh run list --workflow=ache-sucatas.yml --limit 5

# Verificar status dos ultimos workflows de CI
gh run list --workflow=ci.yml --limit 5

# Acompanhar execucao em tempo real
gh run watch <RUN_ID>

# Ver logs de uma execucao
gh run view <RUN_ID> --log

# Ver logs de um job especifico
gh run view <RUN_ID> --log --job=<JOB_ID>
```

### CI e Testes

```bash
# Instalar ferramentas de CI
pip install ruff pytest

# Executar linting
ruff check .

# Executar linting com correcao automatica
ruff check . --fix

# Verificar formato
ruff format --check .

# Formatar codigo automaticamente
ruff format .

# Executar testes (sem Supabase)
ENABLE_SUPABASE=false pytest tests/ -v

# Executar testes com saida curta
pytest tests/ --tb=short

# Executar apenas um arquivo de teste
pytest tests/test_auditor_extraction.py -v

# Executar apenas uma classe de teste
pytest tests/test_auditor_extraction.py::TestFormatarDataBr -v

# Executar apenas um teste especifico
pytest tests/test_auditor_extraction.py::TestFormatarDataBr::test_iso_format -v
```

### Execucao Local (Debug/Testes)

```bash
# Miner V11 (requer .env configurado)
python ache_sucatas_miner_v11.py

# Auditor V14 (requer .env configurado)
python cloud_auditor_v14.py

# Auditor com limite
python cloud_auditor_v14.py --limit 5

# Coleta historica (30 dias)
python coleta_historica_30d.py
```

### Verificacao de Status

```bash
# Contar editais no banco
python -c "from supabase_repository import SupabaseRepository; r = SupabaseRepository(); print(f'Editais: {r.contar_editais()}')"

# Contar editais no Storage
python -c "from supabase_storage import SupabaseStorageRepository; s = SupabaseStorageRepository(); print(f'Storage: {len(s.listar_editais())}')"

# Listar ultimas execucoes
python -c "
from supabase_repository import SupabaseRepository
r = SupabaseRepository()
resp = r.client.table('execucoes_miner').select('*').order('execution_start', desc=True).limit(5).execute()
for e in resp.data:
    print(f\"[{e['status']}] {e['versao_miner']} - novos:{e.get('editais_novos', 0)}\")
"

# Testar conexao com Supabase
python -c "from supabase_repository import SupabaseRepository; r = SupabaseRepository(); print('OK' if r.enable_supabase else 'FALHOU')"
```

### Seguranca

```bash
# Instalar hooks de seguranca (uma vez)
python instalar_hooks_seguranca.py

# Rotacionar credenciais (interativo)
python rotacionar_credenciais.py

# Verificar GitHub Secrets (deve mostrar 4)
gh secret list

# Verificar se hook esta ativo
git config core.hooksPath
```

### Frontend

```bash
# Instalar dependencias
cd frontend && npm install

# Rodar em desenvolvimento
npm run dev

# Build para producao
npm run build

# Preview do build
npm run preview
```

### Git

```bash
# Status
git status

# Ultimos commits
git log --oneline -10

# Push
git push
```

### EMERGENCIA

```bash
# DESLIGAR TUDO IMEDIATAMENTE
python desligar_supabase.py

# Reativar apos resolver problema
python reativar_supabase.py
```

---

## Troubleshooting

### Problema: Workflow nao executa no horario

```
Sintoma: Cron nao disparou as 00:00 UTC
Causa: GitHub Actions tem delay de ate 15 minutos
Solucao: Normal, aguardar ou disparar manualmente
Comando: gh workflow run ache-sucatas.yml
```

### Problema: Erro de autenticacao no Storage

```
Sintoma: "Invalid API key" no upload
Causa: SUPABASE_SERVICE_KEY incorreta ou expirada
Solucao:
  1. Verificar secret: gh secret list
  2. Rotacionar: python rotacionar_credenciais.py
  3. Atualizar: gh secret set SUPABASE_SERVICE_KEY
```

### Problema: Pre-commit bloqueou meu commit

```
Sintoma: "COMMIT BLOQUEADO: Secrets detectados!"
Causa: Arquivo contem credenciais
Solucao:
  1. Remova as credenciais do arquivo
  2. Use variaveis de ambiente (.env)
  3. Tente commitar novamente
NUNCA: git commit --no-verify (exceto emergencia)
```

### Problema: Miner retorna 0 editais novos

```
Sintoma: "Editais novos: 0" no log
Causa: Todos editais ja estao no checkpoint
Verificar: cat .ache_sucatas_checkpoint.json
Solucao (teste): Deletar checkpoint e re-executar
Solucao (prod): Normal se nao ha editais novos
```

### Problema: Auditor nao processa editais

```
Sintoma: "Nenhum edital pendente"
Causa: Todos editais ja tem processado_auditor=true
Verificar: SELECT COUNT(*) FROM editais_leilao WHERE processado_auditor = false
Solucao: UPDATE editais_leilao SET processado_auditor = false WHERE ...
```

### Problema: Violacao de constraint check_uf

```
Sintoma: new row violates check constraint "check_uf"
Causa: API PNCP retornando UF vazia ou invalida
Solucao: Ja tratado - UF invalida vira "XX"
Commit: 4deadc2 fix: Handle empty/invalid UF values
```

### Problema: Rate limiting da API PNCP

```
Sintoma: API returned status 429 (Too Many Requests)
Causa: Muitas requisicoes em sequencia
Solucao: Nao e critico, sistema continua na proxima execucao
Mitigacao: JANELA_TEMPORAL_HORAS=24 reduz requisicoes
```

### Problema: Bucket nao encontrado no Storage

```
Sintoma: {'statusCode': 404, 'error': 'Bucket not found'}
Causa: Bucket editais-pdfs nao existe
Solucao:
  1. Supabase Dashboard -> Storage -> New bucket
  2. Nome: editais-pdfs
  3. Public: No (privado)
  4. File size limit: 50MB
```

### Problema: Erro SSL ao enviar email

```
Sintoma: ssl3_get_record:wrong version number
Causa: Porta errada (587 em vez de 465)
Solucao: Ja corrigido - workflow usa porta 465 com SSL
Commit: 75548f1 fix: Use SSL port 465 instead of STARTTLS port 587
```

### Problema: CI falhou no lint

```
Sintoma: ruff check . falhou
Causa: Codigo com erros de estilo/sintaxe
Solucao:
  1. Executar localmente: ruff check .
  2. Corrigir erros ou adicionar ao ignore em ruff.toml
  3. Para correcao automatica: ruff check . --fix
```

### Problema: CI falhou nos testes

```
Sintoma: pytest tests/ falhou
Causa: Teste quebrado ou funcao alterada
Solucao:
  1. Executar localmente: pytest tests/ -v
  2. Ver qual teste falhou
  3. Corrigir o teste ou a funcao
  4. Re-executar para validar
```

---

## Roadmap

### Fases Concluidas

| Fase | Descricao | Status | Data |
|------|-----------|--------|------|
| 1 - Coleta | Miner V9 coletando da API PNCP | CONCLUIDA | 2026-01-16 |
| 2 - Extracao | Auditor V13 extraindo dados dos PDFs | CONCLUIDA | 2026-01-16 |
| 3 - Persistencia | Supabase PostgreSQL configurado | CONCLUIDA | 2026-01-16 |
| 4 - Cloud Native | V11 + V14 100% na nuvem | CONCLUIDA | 2026-01-16 |
| 5 - Seguranca | Auditoria e correcoes | CONCLUIDA | 2026-01-16 |
| 6 - Notificacoes | Email de falha via Gmail | CONCLUIDA | 2026-01-17 |
| 7 - CI | Linting (ruff) + Testes (pytest) | CONCLUIDA | 2026-01-17 |
| **8 - Frontend React** | Dashboard multi-view + notificacoes | **CONCLUIDA** | 2026-01-18 |

### Fase 9 - Expansao (FUTURO)

| Item | Descricao | Prioridade |
|------|-----------|------------|
| API REST | Endpoint para consultas externas | Alta |
| Retry backoff | Retry exponencial para API PNCP | Media |
| Deploy do Frontend | Deploy em Vercel/Netlify/Cloudflare | Alta |
| Geocodificacao | Coordenadas reais dos municipios para o mapa | Media |

### Dividas Tecnicas

| Item | Descricao | Esforco | Status |
|------|-----------|---------|--------|
| Format check | Verificacao de formatacao | Baixo | Pendente (67 arquivos) |
| Monitoramento custos | Alerta quando Storage > 500MB | Baixo | Pendente |
| Limpeza editais antigos | Remover editais > 1 ano | Baixo | Pendente |

---

## Historico de Commits

### Commits Recentes (2026-01-18)

| Hash | Descricao |
|------|-----------|
| `bf5d431` | fix: Resolve React DOM reconciliation error with LoaderCircle |
| `7559793` | docs: Update CLAUDE_FULL.md with Week 2 realtime & geo-intel enhancements |
| `dfe15df` | feat: Week 2 realtime & geo-intel enhancements |
| `fa6f18f` | feat: Add Week 2 frontend - notifications, multi-view dashboard |
| `b1b23a2` | docs: Update CLAUDE.md files with Week 2 frontend documentation |
| `9839b3b` | feat: Add historical collection script with duplicate detection |

### Commits de 2026-01-17

| Hash | Descricao |
|------|-----------|
| `91cd89e` | chore: Bump dashboard version to force Streamlit Cloud redeploy |
| `bb47f2f` | fix: Add type check to prevent AttributeError in listar_tags_disponiveis |
| `e5343be` | fix: Resolve 8 critical bugs in dashboard and auditor |
| `3ef2ac1` | fix: Use correct column name storage_path instead of pdf_storage_url |
| `2fdb234` | feat: Add Streamlit dashboard for visualizing auction notices |
| `06b615c` | fix: Auditor now sets processado_auditor=True after processing |
| `df67098` | fix: Auditor now correctly uses storage_path to download PDFs |
| `c9b813c` | feat: Add CI workflow with ruff linting and pytest |
| `80ae043` | docs: Ultra-detailed CLAUDE.md update with notifications system |
| `e566fd0` | chore: Remove email test workflow |
| `75548f1` | fix: Use SSL port 465 instead of STARTTLS port 587 for Gmail |
| `c3a9817` | feat: Add email notification on workflow failure |

### Commits de 2026-01-16 (Primeiras Decisoes)

| Hash | Descricao |
|------|-----------|
| `cf6cc99` | docs: Comprehensive CLAUDE.md rewrite with ultra-detailed documentation |
| `f687f46` | fix: Relax pre-commit hook regex to catch smaller secrets |
| `f437982` | docs: Update CLAUDE.md with security audit and credential rotation |
| `dd57120` | security: Remove exposed credentials and add protection mechanisms |
| `6642d33` | docs: Comprehensive CLAUDE.md update with V11 cloud architecture |
| `4deadc2` | fix: Handle empty/invalid UF values in edital mapping |
| `11ac508` | feat: Add 100% cloud architecture with Supabase Storage and GitHub Actions |
| `a639ebd` | feat: Add Miner V10 with Supabase integration |
| `ac0a52f` | docs: Add .env.example and resolve documentation gaps |
| `aeb193a` | docs: Add Quick Start, Troubleshooting and Architecture Decisions |
| `36c0595` | docs: Add project scope, roadmap and next steps to CLAUDE.md |

### Por Categoria

#### Funcionalidades (feat)
- `dfe15df` - Week 2 enhancements - clusterizacao, animate-ping, cores
- `fa6f18f` - Frontend React Semana 2 - notificacoes, multi-view dashboard
- `9839b3b` - Script de coleta historica
- `c9b813c` - CI workflow com ruff linting e pytest
- `c3a9817` - Notificacao por email quando workflow falha
- `11ac508` - Arquitetura 100% cloud com Supabase Storage
- `a639ebd` - Miner V10 com integracao Supabase

#### Correcoes (fix)
- `bf5d431` - React DOM reconciliation error
- `bb47f2f` - AttributeError em listar_tags_disponiveis
- `e5343be` - 8 bugs criticos
- `75548f1` - Porta SSL 465 para Gmail SMTP
- `4deadc2` - Tratamento de UF invalida

#### Seguranca (security)
- `dd57120` - Remocao de credenciais expostas

---

## Checklist para Nova Sessao

Execute estes comandos no inicio de cada sessao:

```bash
# 1. Verificar status do ultimo workflow de coleta
gh run list --workflow=ache-sucatas.yml --limit 3

# 2. Verificar status do ultimo CI
gh run list --workflow=ci.yml --limit 3

# 3. Verificar editais no banco
python -c "from supabase_repository import SupabaseRepository; r = SupabaseRepository(); print(f'Editais no banco: {r.contar_editais()}')"

# 4. Verificar secrets configurados (deve mostrar 4)
gh secret list

# 5. Executar testes localmente
pytest tests/ -v --tb=short
```

### Resultados Esperados

```
# Workflow de coleta
completed  success  ACHE SUCATAS - Coleta e Processamento  master  ...

# Workflow de CI
completed  success  CI - Lint & Test  master  ...

# Banco
Editais no banco: 294

# Secrets (4 secrets)
EMAIL_ADDRESS         2026-01-16T23:41:58Z
EMAIL_APP_PASSWORD    2026-01-16T23:43:24Z
SUPABASE_SERVICE_KEY  2026-01-16T22:41:56Z
SUPABASE_URL          2026-01-16T21:21:31Z

# Testes
98 passed in 3.00s
```

### Se Algum Falhar

| Problema | Acao |
|----------|------|
| Workflow de coleta falhou | `gh run view <ID> --log` para ver erro |
| CI falhou | `ruff check .` e `pytest tests/ -v` localmente |
| Supabase nao conecta | Verificar .env ou GitHub Secrets |
| Menos de 4 secrets | Configurar EMAIL_ADDRESS e EMAIL_APP_PASSWORD |
| Testes falharam | Ver output e corrigir teste ou funcao |

---

## Notas Importantes

1. **NUNCA commitar `.env`** - contem credenciais Supabase
2. **Pre-commit hook ativo** - bloqueia commits com secrets
3. **Credenciais rotacionadas** - em 2026-01-16 22:41 UTC
4. **Sistema 100% cloud** - nao precisa mais de PC local ligado
5. **Execucao automatica 3x/dia** - 00:00, 08:00, 16:00 UTC
6. **4 GitHub Secrets configurados** - SUPABASE_URL, SUPABASE_SERVICE_KEY, EMAIL_ADDRESS, EMAIL_APP_PASSWORD
7. **Gmail SMTP porta 465** - SSL/TLS, nao usar porta 587
8. **98 testes unitarios** - cobrindo funcoes puras
9. **Atalhos de teclado** - G (Grid), M (Mapa), C (Calendario) no frontend
10. **MapLibre GL** - Requer selecionar UF para visualizar mapa

---

> Documento gerado e mantido pelo Claude Code
> Ultima atualizacao: 2026-01-18 22:00 UTC
>
> Anterior: [CLAUDE_FULL_5.md](./CLAUDE_FULL_5.md) | Inicio: [CLAUDE_FULL_1.md](./CLAUDE_FULL_1.md)
