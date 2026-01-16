# 🔒 GUIA DE SEGURANÇA MÁXIMA - ACHE SUCATAS DaaS
## ZERO VAZAMENTO DE DADOS - CONFIDENCIAL

**Data**: 2026-01-16
**Classificação**: 🔴 CONFIDENCIAL - INTERNO
**Objetivo**: Proteger 100% dos dados comerciais e estratégias do negócio

---

## 🚨 PRINCÍPIOS DE SEGURANÇA

### 1. **Defense in Depth (Defesa em Camadas)**
- Múltiplas camadas de segurança
- Princípio do menor privilégio
- Zero trust architecture

### 2. **Data Classification**
- 🔴 **CRÍTICO**: Credenciais, API keys, senhas
- 🟠 **CONFIDENCIAL**: Dados comerciais, estratégias de busca
- 🟡 **INTERNO**: Código-fonte, documentação técnica
- 🟢 **PÚBLICO**: Dados já públicos no PNCP (apenas referência)

### 3. **Privacy by Design**
- Dados sensíveis nunca commitados no Git
- Criptografia de dados em repouso
- Logs sem informações sensíveis
- Auditoria completa de acessos

---

## 🔐 PARTE 1: SETUP SEGURO DO SUPABASE

### 1.1 Criar Projeto (Com Segurança Máxima)

**Passo 1**: Acessar Supabase
```
URL: https://supabase.com/dashboard
Ação: Sign In com conta PRIVADA/EMPRESARIAL
```

**Passo 2**: Criar Novo Projeto
```
Nome: ache-sucatas-prod (NÃO usar nome revelador publicamente)
Database Password: [GERAR SENHA FORTE - 32 caracteres]
Region: South America (São Paulo) - DADOS NO BRASIL
Pricing Plan: Pro (se possível) para recursos de segurança extras
```

⚠️ **IMPORTANTE**: Salvar a senha do banco em gerenciador de senhas (1Password, Bitwarden, etc.)

---

### 1.2 Configurar Row Level Security (RLS)

**O QUE É RLS?**
- Sistema de políticas de acesso a nível de linha
- Impede acesso não autorizado aos dados
- Cada tabela tem suas próprias políticas

**EXECUTAR NO SQL EDITOR DO SUPABASE:**

```sql
-- ============================================
-- ATIVAR RLS EM TODAS AS TABELAS
-- ============================================

ALTER TABLE editais_leilao ENABLE ROW LEVEL SECURITY;
ALTER TABLE execucoes_miner ENABLE ROW LEVEL SECURITY;
ALTER TABLE metricas_diarias ENABLE ROW LEVEL SECURITY;

-- ============================================
-- POLÍTICA 1: ACESSO TOTAL VIA SERVICE KEY
-- (Para o backend Python)
-- ============================================

-- Editais: Service Key pode fazer TUDO
CREATE POLICY "Service role tem acesso total a editais"
ON editais_leilao
FOR ALL
TO service_role
USING (true)
WITH CHECK (true);

-- Execuções: Service Key pode fazer TUDO
CREATE POLICY "Service role tem acesso total a execucoes"
ON execucoes_miner
FOR ALL
TO service_role
USING (true)
WITH CHECK (true);

-- Métricas: Service Key pode fazer TUDO
CREATE POLICY "Service role tem acesso total a metricas"
ON metricas_diarias
FOR ALL
TO service_role
USING (true)
WITH CHECK (true);

-- ============================================
-- POLÍTICA 2: BLOQUEIO TOTAL VIA API PÚBLICA
-- (Ninguém pode acessar via API anon key)
-- ============================================

-- NENHUMA política para 'anon' = ACESSO BLOQUEADO
-- Isso garante que mesmo se a anon key vazar, ninguém acessa nada

-- ============================================
-- POLÍTICA 3: USUÁRIOS AUTENTICADOS (FUTURO)
-- (Quando adicionar auth, criar políticas específicas)
-- ============================================

-- Exemplo para futuro (NÃO executar agora):
-- CREATE POLICY "Usuários veem apenas seus editais"
-- ON editais_leilao
-- FOR SELECT
-- TO authenticated
-- USING (auth.uid() = user_id);
```

---

### 1.3 Desabilitar API Pública (Máxima Segurança)

**No Dashboard do Supabase:**

1. **Settings** → **API**
2. **Desabilitar** `Public API` (se disponível)
3. Ou adicionar **IP Whitelist** (somente seu servidor pode acessar)

**Se não tiver IP Whitelist nativo:**
- Usar somente `service_role` key (nunca `anon` key)
- Configurar Supabase Edge Functions com auth (avançado)

---

### 1.4 Configurar Backups Automáticos

**No Dashboard do Supabase:**

1. **Settings** → **Database** → **Backups**
2. Configurar:
   - Daily Backups: ✅ Ativado
   - Retention: 30 dias (máximo disponível)
   - Point-in-Time Recovery: ✅ Ativado (se Pro plan)

---

### 1.5 Configurar Logs de Auditoria

**No Dashboard do Supabase:**

1. **Logs** → **Database**
2. Ativar logs para:
   - ✅ Queries SQL
   - ✅ Conexões
   - ✅ Erros
3. Revisar logs semanalmente

---

### 1.6 Obter Credenciais (Com Segurança)

**No Dashboard do Supabase:**

1. **Settings** → **API**
2. Copiar:
   - `Project URL` (pode ser público)
   - `service_role key` (🔴 CONFIDENCIAL - NUNCA COMPARTILHAR)
   - ❌ **NÃO USAR** `anon key` (é pública e não tem acesso com RLS)

**Salvar em:**
- ✅ Gerenciador de senhas (1Password, Bitwarden)
- ✅ Arquivo `.env` LOCAL (nunca commitar)
- ❌ NUNCA em email, Slack, WhatsApp, etc.

---

## 🔐 PARTE 2: SETUP SEGURO DO GITHUB

### 2.1 Criar Repositório PRIVADO

**Passo 1**: Acessar GitHub
```
URL: https://github.com/new
```

**Passo 2**: Configurar Repositório
```
Repository Name: ache-sucatas-daas
Description: [DEIXAR EM BRANCO ou usar nome genérico: "Data processing pipeline"]
Visibility: 🔴 PRIVATE (OBRIGATÓRIO)
Initialize:
  - ✅ Add .gitignore (Python)
  - ✅ Add README.md
  - ❌ Choose a license (não adicionar - código proprietário)
```

**Passo 3**: Criar Repository

---

### 2.2 Configurar Branch Protection

**No repositório GitHub:**

1. **Settings** → **Branches**
2. Clicar em **Add branch protection rule**
3. Branch name pattern: `main`
4. Configurar:
   - ✅ Require a pull request before merging
   - ✅ Require approvals: 1 (se tiver equipe)
   - ✅ Require status checks to pass (se tiver CI/CD)
   - ✅ Do not allow bypassing the above settings

---

### 2.3 Configurar Secrets (GitHub Actions - Opcional)

**Se usar CI/CD:**

1. **Settings** → **Secrets and variables** → **Actions**
2. Adicionar secrets:
   - `SUPABASE_URL`
   - `SUPABASE_SERVICE_KEY`
3. ⚠️ Secrets NUNCA aparecem em logs

---

### 2.4 .gitignore Robusto (CRÍTICO)

**CRIAR ARQUIVO `.gitignore` NA RAIZ:**

```gitignore
# ============================================
# 🔴 SEGURANÇA - NUNCA COMMITAR
# ============================================

# Credenciais e configurações sensíveis
.env
.env.*
*.env
!.env.example
.env.local
.env.production
config.ini
secrets.yaml
credentials.json

# Chaves SSH e certificados
*.pem
*.key
*.crt
*.p12
*.pfx
id_rsa*
id_ed25519*

# Supabase
supabase/.env
.supabase/

# ============================================
# 🟠 DADOS COMERCIAIS - NUNCA COMMITAR
# ============================================

# Base de dados local
ACHE_SUCATAS_DB/
*.db
*.sqlite
*.sqlite3

# Arquivos processados
data/
downloads/
*.pdf
*.zip

# Checkpoints e métricas (contêm dados sensíveis)
.ache_sucatas_checkpoint.json
ache_sucatas_metrics.jsonl
*.checkpoint
*.metrics

# Outputs com dados reais
analise_editais*.csv
RESULTADO_FINAL*.xlsx
*.csv
*.xlsx
!schema.xlsx
!template.xlsx

# Backups
backups/
*.backup
*.bak

# Logs (podem conter informações sensíveis)
logs/
*.log
auditor*.log
miner*.log

# ============================================
# 🟡 PYTHON - ARQUIVOS TEMPORÁRIOS
# ============================================

# Byte-compiled / optimized / DLL files
__pycache__/
*.py[cod]
*$py.class
*.so
.Python

# Virtual environments
venv/
env/
ENV/
.venv

# IDEs
.vscode/
.idea/
*.swp
*.swo
*~

# OS
.DS_Store
Thumbs.db
desktop.ini

# Temporary files
tmp/
temp/
*.tmp
*.temp

# Cache
.cache/
*.cache

# ============================================
# 🟢 PERMITIR (whitelist específico)
# ============================================

# Templates e exemplos (sem dados reais)
!.env.example
!docs/examples/*.csv
!tests/fixtures/*.json

# Schemas e documentação
!docs/
!README.md
!*.md
```

---

### 2.5 Criar .env.example (Template Público)

**CRIAR ARQUIVO `.env.example` NA RAIZ:**

```bash
# ============================================
# ACHE SUCATAS DaaS - CONFIGURAÇÃO
# ============================================
# ESTE É UM TEMPLATE - NÃO CONTÉM CREDENCIAIS REAIS
# Copie para .env e preencha com valores reais

# ============================================
# SUPABASE (🔴 CONFIDENCIAL)
# ============================================
SUPABASE_URL=https://seu-projeto.supabase.co
SUPABASE_SERVICE_KEY=sua-service-key-aqui

# ⚠️ NUNCA use 'anon' key em produção!
# ⚠️ NUNCA comite o arquivo .env real!

# ============================================
# PNCP API (🟢 PÚBLICO)
# ============================================
PNCP_BASE_URL=https://pncp.gov.br/api/consulta/v1
PNCP_ARQUIVOS_URL=https://pncp.gov.br/pncp-api/v1

# ============================================
# CONFIGURAÇÕES LOCAIS
# ============================================

# Diretórios
DOWNLOAD_DIR=./data/ACHE_SUCATAS_DB
LOG_DIR=./logs
BACKUP_DIR=./backups

# Limites
MAX_PAGES_PDF=50
MAX_RESULTS_PER_PAGE=500
REQUEST_TIMEOUT=30

# ============================================
# FEATURES FLAGS
# ============================================

# Ativar integração com Supabase
ENABLE_SUPABASE=true

# Manter backup local (CSV/XLSX)
ENABLE_LOCAL_BACKUP=true

# Cache de PDFs local (economiza downloads)
ENABLE_PDF_CACHE=true

# Modo debug (mais logs)
DEBUG=false

# ============================================
# CRON (V10 MINER)
# ============================================

CRON_MODE=true
JANELA_TEMPORAL_HORAS=24
PAGE_LIMIT=3
MAX_DOWNLOADS=200

# ============================================
# SEGURANÇA
# ============================================

# Log de auditoria (rastrear todas as operações)
ENABLE_AUDIT_LOG=true

# Verificar integridade de arquivos (SHA256)
ENABLE_FILE_VERIFICATION=true
```

---

## 🔐 PARTE 3: CÓDIGO SEGURO (Auditor V13)

### 3.1 Gerenciamento de Credenciais

**NÃO FAZER (❌ INSEGURO):**
```python
# ❌ NUNCA hardcode credenciais
SUPABASE_URL = "https://meu-projeto.supabase.co"
SUPABASE_KEY = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9..."
```

**FAZER (✅ SEGURO):**
```python
import os
from dotenv import load_dotenv

# Carregar .env
load_dotenv()

# Validar que credenciais existem
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_SERVICE_KEY")

if not SUPABASE_URL or not SUPABASE_KEY:
    raise ValueError("🔴 ERRO: Credenciais Supabase não configuradas no .env")

# Usar credenciais
from supabase import create_client
supabase = create_client(SUPABASE_URL, SUPABASE_KEY)
```

---

### 3.2 Logs Sem Dados Sensíveis

**NÃO FAZER (❌ INSEGURO):**
```python
# ❌ NUNCA logar credenciais ou dados sensíveis
logger.info(f"Conectando ao Supabase: {SUPABASE_URL} com key {SUPABASE_KEY}")
logger.info(f"Edital processado: {dados_completos}")
```

**FAZER (✅ SEGURO):**
```python
# ✅ Logar apenas informações necessárias (sem dados sensíveis)
logger.info("Conectando ao Supabase...")
logger.info(f"Edital processado: ID={edital_id}, UF={uf}, Cidade={cidade}")

# ✅ Mascarar dados sensíveis se necessário
def mask_secret(value: str) -> str:
    """Mascara credencial para logs."""
    if len(value) <= 8:
        return "***"
    return f"{value[:4]}...{value[-4:]}"

logger.debug(f"Supabase Key: {mask_secret(SUPABASE_KEY)}")
```

---

### 3.3 Tratamento de Erros (Sem Expor Detalhes)

**NÃO FAZER (❌ INSEGURO):**
```python
# ❌ Expor stack trace completo em produção
try:
    supabase.table("editais").insert(data).execute()
except Exception as e:
    print(f"Erro: {e}")  # Pode expor estrutura do banco
```

**FAZER (✅ SEGURO):**
```python
import logging

try:
    supabase.table("editais").insert(data).execute()
except Exception as e:
    # Logar detalhes internamente
    logger.error(f"Erro ao inserir edital ID={data['id_interno']}: {type(e).__name__}")
    logger.debug(f"Detalhes do erro: {e}", exc_info=True)  # Stack trace só em debug

    # Mensagem genérica para usuário
    print("❌ Erro ao processar edital. Verifique os logs.")
```

---

### 3.4 Validação de Entrada (Prevenir SQL Injection)

**FAZER (✅ SEGURO):**
```python
from pydantic import BaseModel, validator
import re

class EditalInput(BaseModel):
    """Schema de validação para editais."""

    id_interno: str
    pncp_id: str
    orgao: str
    uf: str
    cidade: str

    @validator('uf')
    def validate_uf(cls, v):
        """Valida UF (somente 2 letras maiúsculas)."""
        if not re.match(r'^[A-Z]{2}$', v):
            raise ValueError('UF inválida')
        return v

    @validator('pncp_id')
    def validate_pncp_id(cls, v):
        """Valida formato PNCP ID."""
        if not re.match(r'^\d{14}-\d{4}-\d+$', v):
            raise ValueError('PNCP ID inválido')
        return v

# Uso
try:
    edital = EditalInput(**raw_data)
    # Dados validados e seguros
    supabase.table("editais").insert(edital.dict()).execute()
except ValidationError as e:
    logger.error(f"Dados inválidos: {e}")
```

---

## 🔐 PARTE 4: CHECKLIST DE SEGURANÇA

### 4.1 Antes do Primeiro Commit

- [ ] ✅ `.gitignore` configurado corretamente
- [ ] ✅ `.env` criado localmente (NUNCA commitar)
- [ ] ✅ `.env.example` criado (SEM credenciais reais)
- [ ] ✅ Verificar que nenhum arquivo sensível está staged:
  ```bash
  git status
  # Não deve aparecer: .env, *.pdf, *.csv, *.log, checkpoints
  ```

### 4.2 Antes de Cada Commit

```bash
# 1. Verificar o que será commitado
git diff --cached

# 2. Procurar por padrões perigosos
git diff --cached | grep -iE "(password|secret|key|token|credential)"

# 3. Se encontrar algo suspeito, ABORTAR:
git reset HEAD <arquivo-perigoso>
```

### 4.3 Supabase (Checklist Mensal)

- [ ] ✅ Revisar logs de auditoria
- [ ] ✅ Verificar backups automáticos
- [ ] ✅ Rotacionar credenciais (a cada 3-6 meses)
- [ ] ✅ Revisar políticas RLS
- [ ] ✅ Verificar uso de storage (limite de 500MB free)

### 4.4 GitHub (Checklist Mensal)

- [ ] ✅ Revisar commits recentes
- [ ] ✅ Verificar que repo está PRIVATE
- [ ] ✅ Revisar membros com acesso
- [ ] ✅ Verificar GitHub Actions logs (se usar CI/CD)

---

## 🚨 PLANO DE RESPOSTA A INCIDENTES

### Se credenciais vazarem (URGENTE):

**1. Revogar Imediatamente:**
```
Supabase:
  - Dashboard → Settings → API
  - Reset Database Password
  - Regenerar Service Key
```

**2. Atualizar `.env` local:**
```bash
# Editar .env com novas credenciais
vim .env
```

**3. Verificar Logs:**
```
Supabase:
  - Logs → Database
  - Verificar acessos não autorizados nas últimas 24h
```

**4. Notificar (se necessário):**
- Equipe interna
- LGPD compliance (se houver dados pessoais)

---

## 📊 AUDITORIA DE SEGURANÇA

### Logs a Manter (Para Auditoria):

1. **Supabase Audit Log:**
   - Todas as queries SQL
   - Conexões bem-sucedidas e falhas
   - Alterações em tabelas

2. **Application Logs:**
   - Execuções do miner (start/end/status)
   - Processamento de editais (ID, timestamp)
   - Erros e exceções

3. **Git History:**
   - Commits (com mensagens claras)
   - Pull requests (se tiver equipe)

---

## ✅ RESUMO DAS MEDIDAS DE SEGURANÇA

| Camada | Medida | Status |
|--------|--------|--------|
| **Supabase** | RLS ativado em todas as tabelas | 🟡 A implementar |
| **Supabase** | Bloqueio de API pública (anon key) | 🟡 A implementar |
| **Supabase** | Backups automáticos diários | 🟡 A configurar |
| **Supabase** | Logs de auditoria | 🟡 A configurar |
| **GitHub** | Repositório PRIVADO | 🟡 A criar |
| **GitHub** | Branch protection | 🟡 A configurar |
| **GitHub** | .gitignore robusto | 🟡 A implementar |
| **Código** | .env para credenciais | 🟡 A implementar |
| **Código** | Validação de entrada | 🟡 A implementar |
| **Código** | Logs sem dados sensíveis | 🟡 A implementar |

---

## 🎯 PRÓXIMOS PASSOS (SEGURO)

### Você Faz:
1. ✅ Criar projeto Supabase (com senha forte)
2. ✅ Executar scripts SQL de RLS (copiar deste guia)
3. ✅ Copiar credenciais para gerenciador de senhas
4. ✅ Criar repositório GitHub PRIVADO
5. ✅ Me fornecer credenciais via canal seguro (não por chat público)

### Eu Faço:
1. ✅ Criar `.env` local (NUNCA commitar)
2. ✅ Implementar código V13 com segurança máxima
3. ✅ Configurar .gitignore robusto
4. ✅ Testar integração
5. ✅ Fazer commit inicial (SEM dados sensíveis)

---

**LEMBRE-SE**: Segurança não é paranoia, é responsabilidade! 🔒

**Próximo passo**: Você criar o projeto Supabase seguindo este guia e me fornecer:
- `SUPABASE_URL`
- `SUPABASE_SERVICE_KEY`

**Como me fornecer (SEGURO)?**
- Opção 1: Criar arquivo `.env` local e me dizer "credenciais no .env"
- Opção 2: Usar serviço de compartilhamento seguro (OneTimeSecret.com)
- Opção 3: Via ferramenta de gerenciamento de senhas compartilhada

**NÃO me fornecer credenciais via:**
- ❌ Chat público
- ❌ Screenshot commitado no Git
- ❌ Email não criptografado
- ❌ WhatsApp/Telegram

---

**Está claro? Quer que eu explique alguma parte da segurança em mais detalhes?** 🔐
