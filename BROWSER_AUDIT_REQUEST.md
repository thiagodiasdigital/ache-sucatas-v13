# BROWSER_AUDIT_REQUEST.md

> **Gerado por:** Claude Code Opus 4.5
> **Data:** 2026-01-19
> **Contexto:** Complemento da auditoria local SECURITY_AUDIT_LOCAL.json

---

## OBJETIVO

Este documento lista os itens que **NAO PODEM** ser verificados sem acesso a navegador/UI.
A persona responsavel deve acessar Supabase Dashboard e GitHub UI para coletar as evidencias abaixo.

---

## 1. SUPABASE DASHBOARD - Verificacoes Obrigatorias

### 1.1 Rotacao de Credenciais (CRITICO)

**URL:** `https://supabase.com/dashboard/project/[PROJECT_ID]/settings/api`

| Item | O que verificar | Evidencia esperada |
|------|-----------------|-------------------|
| Service Role Key | Data de criacao/rotacao | Deve ser posterior a 2026-01-16 22:41 UTC |
| Anon Key | Status e data | Verificar se foi rotacionada junto |
| JWT Secret | Se foi alterado | Idealmente rotacionado apos incidente |

**Acao:** Capturar screenshot da secao "API Keys" mostrando timestamps.

---

### 1.2 Row Level Security (RLS)

**URL:** `https://supabase.com/dashboard/project/[PROJECT_ID]/auth/policies`

| Tabela | Verificar | Status esperado |
|--------|-----------|-----------------|
| `editais_leilao` | RLS ativado | ENABLED |
| `execucoes_miner` | RLS ativado | ENABLED |
| `metricas_diarias` | RLS ativado | ENABLED |
| `raw.leiloes` | RLS ativado | ENABLED |
| `audit.consumption_logs` | RLS ativado | ENABLED |

**Acao:** Capturar screenshot de cada tabela mostrando "RLS enabled".

---

### 1.3 Politicas de Acesso Ativas

**URL:** `https://supabase.com/dashboard/project/[PROJECT_ID]/auth/policies`

Verificar se existem APENAS estas politicas:

| Tabela | Politica | Role | Tipo |
|--------|----------|------|------|
| `editais_leilao` | Service role tem acesso total | service_role | ALL |
| `raw.leiloes` | Authenticated users can view | authenticated | SELECT |
| `raw.leiloes` | Service role can manage | service_role | ALL |
| `audit.consumption_logs` | Users can view own logs | authenticated | SELECT |
| `audit.consumption_logs` | Service role can manage | service_role | ALL |

**Alerta:** Se houver politica para `anon` em tabelas sensiveis, reportar como HIGH.

---

### 1.4 Storage Bucket Permissions

**URL:** `https://supabase.com/dashboard/project/[PROJECT_ID]/storage/buckets`

| Bucket | Verificar | Esperado |
|--------|-----------|----------|
| `pncp-pdfs` (ou similar) | Public access | Deve ser PRIVATE ou com policies |
| Qualquer bucket | Policies | Nao deve ter acesso anonimo irrestrito |

**Acao:** Capturar screenshot das policies de cada bucket.

---

### 1.5 Database Connections

**URL:** `https://supabase.com/dashboard/project/[PROJECT_ID]/settings/database`

| Item | Verificar |
|------|-----------|
| Connection pooling | Deve estar habilitado |
| SSL enforcement | Deve ser REQUIRED |
| Direct connections | Verificar IPs permitidos (se houver) |

---

### 1.6 Authentication Settings

**URL:** `https://supabase.com/dashboard/project/[PROJECT_ID]/auth/providers`

| Item | Verificar |
|------|-----------|
| Email confirmations | Deve estar ENABLED para producao |
| Password requirements | Verificar politica minima |
| Rate limiting | Verificar se ha protecao contra brute force |

---

### 1.7 API Rate Limits

**URL:** `https://supabase.com/dashboard/project/[PROJECT_ID]/settings/api`

| Item | Valor recomendado |
|------|-------------------|
| Rate limit | Configurado (nao unlimited) |
| Request size limit | <= 5MB |

---

## 2. GITHUB UI - Verificacoes Obrigatorias

### 2.1 Repository Secrets

**URL:** `https://github.com/[OWNER]/[REPO]/settings/secrets/actions`

| Secret | Verificar | Esperado |
|--------|-----------|----------|
| SUPABASE_URL | Existe | Updated recentemente |
| SUPABASE_SERVICE_KEY | Existe | Updated apos 2026-01-16 22:41 UTC |
| EMAIL_ADDRESS | Existe | Para notificacoes |
| EMAIL_APP_PASSWORD | Existe | Para SMTP |

**Acao:** Capturar screenshot da lista de secrets (sem valores) com timestamps.

---

### 2.2 Branch Protection Rules

**URL:** `https://github.com/[OWNER]/[REPO]/settings/branches`

| Branch | Regra esperada |
|--------|----------------|
| `master` ou `main` | Require PR before merging |
| `master` ou `main` | Require status checks (CI) |
| `master` ou `main` | Restrict force pushes |

---

### 2.3 Security Tab

**URL:** `https://github.com/[OWNER]/[REPO]/security`

| Item | Verificar |
|------|-----------|
| Dependabot alerts | Quantos alertas abertos? |
| Secret scanning | Habilitado? |
| Code scanning | Habilitado? |

**Acao:** Capturar screenshot do security overview.

---

### 2.4 Actions Permissions

**URL:** `https://github.com/[OWNER]/[REPO]/settings/actions`

| Item | Esperado |
|------|----------|
| Actions permissions | Restricted (apenas actions especificas) |
| Workflow permissions | Read repository contents |
| Fork PR workflows | Require approval |

---

## 3. EVIDENCIAS A COLETAR

Ao final da auditoria via browser, gerar:

```
BROWSER_AUDIT_EVIDENCE/
├── supabase/
│   ├── api_keys_timestamp.png
│   ├── rls_editais_leilao.png
│   ├── rls_raw_leiloes.png
│   ├── rls_audit_logs.png
│   ├── storage_policies.png
│   ├── database_settings.png
│   └── auth_settings.png
├── github/
│   ├── secrets_list.png
│   ├── branch_protection.png
│   ├── security_overview.png
│   └── actions_permissions.png
└── BROWSER_AUDIT_RESULTS.json
```

---

## 4. FORMATO DO RESULTADO

Gerar arquivo `BROWSER_AUDIT_RESULTS.json` com estrutura:

```json
{
  "audit_date": "2026-01-XX",
  "auditor": "Nome",
  "supabase_findings": {
    "service_key_rotated": true|false,
    "service_key_rotation_date": "ISO8601",
    "rls_all_tables_enabled": true|false,
    "anon_policies_found": [],
    "storage_public_buckets": [],
    "ssl_enforced": true|false
  },
  "github_findings": {
    "secrets_configured": ["SUPABASE_URL", "SUPABASE_SERVICE_KEY", ...],
    "branch_protection_enabled": true|false,
    "dependabot_alerts_open": 0,
    "secret_scanning_enabled": true|false,
    "code_scanning_enabled": true|false
  },
  "critical_issues": [],
  "recommendations": []
}
```

---

## 5. PRIORIDADE DE VERIFICACAO

1. **CRITICO:** Rotacao de Service Key (item 1.1)
2. **ALTO:** RLS em todas as tabelas (item 1.2)
3. **ALTO:** GitHub Secret Scanning (item 2.3)
4. **MEDIO:** Storage bucket policies (item 1.4)
5. **MEDIO:** Branch protection (item 2.2)

---

**FIM DO DOCUMENTO**
