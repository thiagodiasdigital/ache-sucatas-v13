# CLAUDE_FULL_3.md - CI/CD, Testes e Workflows

> **Status:** 98 testes passando | CI automatico em cada push/PR

---

## Navegacao da Documentacao

| # | Arquivo | Conteudo |
|---|---------|----------|
| 1 | [CLAUDE_FULL_1.md](./CLAUDE_FULL_1.md) | Estado atual, Frontend React, Hotfixes |
| 2 | [CLAUDE_FULL_2.md](./CLAUDE_FULL_2.md) | Arquitetura e Fluxos |
| **3** | **CLAUDE_FULL_3.md** (este) | CI/CD, Testes, Workflows |
| 4 | [CLAUDE_FULL_4.md](./CLAUDE_FULL_4.md) | Banco de Dados e API PNCP |
| 5 | [CLAUDE_FULL_5.md](./CLAUDE_FULL_5.md) | Seguranca e Configuracao |
| 6 | [CLAUDE_FULL_6.md](./CLAUDE_FULL_6.md) | Operacoes e Historico |

---

## GitHub Actions - Visao Geral

| Workflow | Arquivo | Trigger | Jobs | Tempo |
|----------|---------|---------|------|-------|
| Coleta e Processamento | `ache-sucatas.yml` | Cron 3x/dia, manual | 4 | ~2 min |
| CI - Lint & Test | `ci.yml` | Push/PR para master | 2 | ~40s |

---

## Workflow: ache-sucatas.yml (Coleta)

**Arquivo:** `.github/workflows/ache-sucatas.yml`
**Linhas:** 247

### Triggers

| Trigger | Configuracao | Descricao |
|---------|--------------|-----------|
| schedule | `0 0,8,16 * * *` | 3x/dia: 00:00, 08:00, 16:00 UTC |
| workflow_dispatch | manual | Execucao manual com parametros |

**Horarios em BRT (Brasil):**
- 00:00 UTC = 21:00 BRT (dia anterior)
- 08:00 UTC = 05:00 BRT
- 16:00 UTC = 13:00 BRT

### Inputs (workflow_dispatch)

| Input | Tipo | Default | Descricao |
|-------|------|---------|-----------|
| run_miner | boolean | true | Executar Miner V11 |
| run_auditor | boolean | true | Executar Auditor V14 |
| auditor_limit | number | 0 | Limite de editais (0 = sem limite) |

### Jobs

| Job | Nome | Depende de | Timeout | Condicao |
|-----|------|------------|---------|----------|
| miner | Miner V11 - Coleta | - | 30 min | Sempre |
| auditor | Auditor V14 - Processamento | miner | 60 min | Miner sucesso |
| verify | Verificacao Final | miner, auditor | - | Sempre |
| notify-failure | Notificar Falha por Email | miner, auditor | - | Se falhou |

### Variaveis de Ambiente

```yaml
env:
  SUPABASE_URL: ${{ secrets.SUPABASE_URL }}
  SUPABASE_SERVICE_KEY: ${{ secrets.SUPABASE_SERVICE_KEY }}
  ENABLE_SUPABASE: 'true'
  ENABLE_SUPABASE_STORAGE: 'true'
  ENABLE_LOCAL_BACKUP: 'false'
  PYTHON_VERSION: '3.11'
```

### Artifacts Gerados

| Artifact | Arquivos | Retencao |
|----------|----------|----------|
| miner-metrics-{N} | ache_sucatas_metrics.jsonl, .ache_sucatas_checkpoint.json | 30 dias |
| auditor-results-{N} | analise_editais_v14.csv | 30 dias |

### Tempos de Execucao

| Job | Tempo Medio |
|-----|-------------|
| Miner V11 | 41s |
| Auditor V14 | 29s |
| Verificacao | 30s |
| Notificacao | 8s (se falhar) |
| **Total** | ~2 min |

---

## Workflow: ci.yml (CI)

**Arquivo:** `.github/workflows/ci.yml`
**Linhas:** 75

```yaml
name: CI - Lint & Test

on:
  push:
    branches: [master]
  pull_request:
    branches: [master]

env:
  PYTHON_VERSION: '3.11'

jobs:
  lint:
    name: Lint with Ruff
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: ${{ env.PYTHON_VERSION }}
      - run: pip install ruff
      - run: ruff check .

  test:
    name: Unit Tests
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: ${{ env.PYTHON_VERSION }}
          cache: 'pip'
      - run: |
          pip install pytest
          pip install -r requirements.txt
      - run: pytest tests/ -v --tb=short
        env:
          ENABLE_SUPABASE: 'false'
          ENABLE_SUPABASE_STORAGE: 'false'
```

### Jobs do CI

| Job | Nome | Tempo | O que faz |
|-----|------|-------|-----------|
| lint | Lint with Ruff | ~8s | Verifica erros de codigo |
| test | Unit Tests | ~32s | Executa 98 testes unitarios |

---

## Configuracao do Ruff (ruff.toml)

```toml
# Target Python 3.11
target-version = "py311"

# Line length
line-length = 120

# Exclude legacy files
exclude = [
    ".git", ".venv", "venv", "__pycache__",
    "antes-dia-*", "ACHE_SUCATAS_DB", "logs"
]

[lint]
# Rules enabled
select = ["E", "F", "W"]  # pycodestyle, Pyflakes, warnings

# Rules ignored (existing code patterns)
ignore = [
    "E402",  # Import not at top
    "E501",  # Line too long
    "E701",  # Multiple statements on one line
    "E722",  # Bare except
    "E731",  # Lambda assignment
    "F401",  # Import unused
    "F541",  # f-string without placeholders
    "F841",  # Variable unused
    "W291",  # Trailing whitespace
    "W292",  # No newline at end
    "W293",  # Blank line whitespace
    "W605",  # Invalid escape sequence
]

# Per-file ignores for legacy code
[lint.per-file-ignores]
"ache_sucatas_miner_v10.py" = ["E", "F", "W"]
"ache_sucatas_miner_v9*.py" = ["E", "F", "W"]
"local_auditor_v*.py" = ["E", "F", "W"]
"migrar_*.py" = ["E", "F", "W"]
```

---

## Configuracao do Pytest (pytest.ini)

```ini
[pytest]
testpaths = tests
python_files = test_*.py
python_classes = Test*
python_functions = test_*
addopts = -v --tb=short
filterwarnings =
    ignore::DeprecationWarning
    ignore::PendingDeprecationWarning
```

---

## Testes Unitarios

### Visao Geral

| Metrica | Valor |
|---------|-------|
| Total de testes | 98 |
| Passando | 98 (100%) |
| Falhando | 0 |
| Tempo de execucao | ~3 segundos |
| Framework | pytest |
| Cobertura | Funcoes puras (sem Supabase) |

### Estrutura de Testes

```
tests/
|-- __init__.py                    # Pacote de testes
|-- conftest.py                    # Configuracao e fixtures
|-- test_auditor_extraction.py     # 53 testes
|-- test_miner_scoring.py          # 19 testes
+-- test_repository_parsing.py     # 26 testes
```

### test_auditor_extraction.py (53 testes)

| Classe de Teste | Testes | Funcao Testada |
|-----------------|--------|----------------|
| TestCorrigirEncoding | 4 | `corrigir_encoding()` |
| TestLimparTexto | 7 | `limpar_texto()` |
| TestFormatarDataBr | 8 | `formatar_data_br()` |
| TestFormatarValorBr | 6 | `formatar_valor_br()` |
| TestExtrairUrlsDeTexto | 5 | `extrair_urls_de_texto()` |
| TestNormalizarUrl | 6 | `normalizar_url()` |
| TestExtrairValorEstimado | 4 | `extrair_valor_estimado()` |
| TestExtrairQuantidadeItens | 4 | `extrair_quantidade_itens()` |
| TestExtrairNomeLeiloeiro | 3 | `extrair_nome_leiloeiro()` |
| TestExtrairDataLeilaoCascata | 6 | `extrair_data_leilao_cascata()` |

**Exemplo:**
```python
class TestFormatarDataBr:
    def test_iso_format(self):
        assert formatar_data_br("2026-01-15") == "15/01/2026"

    def test_none_returns_nd(self):
        assert formatar_data_br(None) == "N/D"
```

### test_miner_scoring.py (19 testes)

| Classe de Teste | Testes | Classe/Funcao Testada |
|-----------------|--------|----------------------|
| TestScoringEngine | 8 | `ScoringEngine.calculate_score()` |
| TestFileTypeDetector | 11 | `FileTypeDetector.detect_by_content_type()`, `detect_by_magic_bytes()` |

**Exemplo:**
```python
class TestScoringEngine:
    def test_base_score(self):
        """Empty text should return base score of 50"""
        score = ScoringEngine.calculate_score("", "", "")
        assert score == 50

    def test_positive_keywords_increase_score(self):
        score = ScoringEngine.calculate_score(
            "leilao de veiculos",
            "sucata inservivel",
            ""
        )
        assert score > 50
```

### test_repository_parsing.py (26 testes)

| Classe de Teste | Testes | Metodo Testado |
|-----------------|--------|----------------|
| TestParseValor | 7 | `_parse_valor()` |
| TestParseInt | 6 | `_parse_int()` |
| TestParseData | 6 | `_parse_data()` |
| TestParseDatetime | 5 | `_parse_datetime()` |

**Exemplo:**
```python
class TestParseValor:
    @pytest.fixture
    def repo(self):
        return SupabaseRepository(enable_supabase=False)

    def test_with_currency_symbol(self, repo):
        assert repo._parse_valor("R$ 1.234,56") == 1234.56
```

### Funcoes Testadas (Resumo)

| Arquivo Fonte | Funcoes Testadas | Tipo |
|---------------|------------------|------|
| `cloud_auditor_v14.py` | corrigir_encoding, limpar_texto, formatar_data_br, formatar_valor_br, extrair_urls_de_texto, normalizar_url, extrair_valor_estimado, extrair_quantidade_itens, extrair_nome_leiloeiro, extrair_data_leilao_cascata | Funcoes puras |
| `ache_sucatas_miner_v11.py` | ScoringEngine.calculate_score, FileTypeDetector.detect_by_content_type, FileTypeDetector.detect_by_magic_bytes | Metodos estaticos |
| `supabase_repository.py` | _parse_valor, _parse_int, _parse_data, _parse_datetime | Metodos internos |

---

## Sistema de Notificacoes por Email

### Visao Geral

| Propriedade | Valor |
|-------------|-------|
| Tipo | Email via Gmail SMTP |
| Servidor | smtp.gmail.com |
| Porta | 465 (SSL/TLS) |
| Autenticacao | App Password |
| Destinatario | thiagodias180986@gmail.com |
| Trigger | Quando miner OU auditor falha |

### Configuracao Tecnica

```yaml
notify-failure:
  name: Notificar Falha por Email
  runs-on: ubuntu-latest
  needs: [miner, auditor]
  if: failure()

  steps:
    - name: Send email notification
      uses: dawidd6/action-send-mail@v3
      with:
        server_address: smtp.gmail.com
        server_port: 465
        secure: true
        username: ${{ secrets.EMAIL_ADDRESS }}
        password: ${{ secrets.EMAIL_APP_PASSWORD }}
        subject: "ACHE SUCATAS - Workflow Falhou"
        to: ${{ secrets.EMAIL_ADDRESS }}
        from: ACHE SUCATAS <${{ secrets.EMAIL_ADDRESS }}>
```

### Formato do Email

**Assunto:**
```
ACHE SUCATAS - Workflow Falhou
```

**Corpo:**
```
O workflow ACHE SUCATAS falhou!

----------------------------------------
DETALHES DA EXECUCAO
----------------------------------------

Repositorio: thiagodiasdigital/ache-sucatas-v13
Branch: master

----------------------------------------
STATUS DOS JOBS
----------------------------------------

Miner V11:   failure
Auditor V14: skipped

----------------------------------------
ACAO NECESSARIA
----------------------------------------

Verifique os logs em:
https://github.com/.../actions/runs/123456789
```

### Secrets Necessarios

| Secret | Descricao | Como Obter |
|--------|-----------|------------|
| `EMAIL_ADDRESS` | Email Gmail completo | Seu email @gmail.com |
| `EMAIL_APP_PASSWORD` | Senha de app de 16 caracteres | myaccount.google.com/apppasswords |

---

## Como Executar CI Localmente

```bash
# Instalar ferramentas
pip install ruff pytest

# Executar linting
ruff check .

# Executar testes
ENABLE_SUPABASE=false pytest tests/ -v

# Verificar formato (desabilitado no CI)
ruff format --check .

# Formatar codigo automaticamente
ruff format .
```

---

## Adicionar Novos Testes

1. Crie um arquivo `tests/test_<modulo>.py`
2. Use a convencao `Test<Classe>` para classes de teste
3. Use a convencao `test_<funcionalidade>` para metodos
4. Execute localmente: `pytest tests/ -v`
5. Push para validar no CI

---

> Anterior: [CLAUDE_FULL_2.md](./CLAUDE_FULL_2.md) | Proximo: [CLAUDE_FULL_4.md](./CLAUDE_FULL_4.md)
