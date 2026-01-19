# SECURITY REMEDIATION CHECKLIST

> **Projeto:** Ache Sucatas - DaaS de Leiloes Publicos Veiculares
> **Data da Auditoria:** 2026-01-19
> **Risk Level Atual:** CRITICAL
> **Proxima Auditoria:** 2026-01-26

---

## BLOCKING ISSUES (Impedem Deploy)

### BLOCK-001: Storage Bucket Publico
- [ ] Acessar: `Supabase Dashboard > Storage > editais-pdfs`
- [ ] Clicar em "Settings" do bucket
- [ ] Escolher UMA das opcoes:
  - [ ] **Opcao A:** Tornar bucket PRIVATE
  - [ ] **Opcao B:** Adicionar policies restritivas (authenticated only)
- [ ] Testar: Tentar acessar um PDF sem autenticacao (deve falhar)
- [ ] Data conclusao: ____/____/____

### BLOCK-002: SSL Enforcement Desativado
- [ ] Acessar: `Supabase Dashboard > Database > Settings`
- [ ] Localizar secao "SSL Configuration"
- [ ] Ativar toggle "Enforce SSL on incoming connections"
- [ ] Aguardar aplicacao (pode levar alguns segundos)
- [ ] Testar: Conexao sem SSL deve ser recusada
- [ ] Data conclusao: ____/____/____

---

## ALTA PRIORIDADE (Esta Semana)

### SEC-003: Habilitar Secret Scanning no GitHub
- [ ] Acessar: `GitHub > Settings > Code security and analysis`
- [ ] Localizar "Secret scanning"
- [ ] Clicar "Enable"
- [ ] Verificar se "Push protection" tambem esta habilitado
- [ ] Data conclusao: ____/____/____

### SEC-004: Configurar Branch Protection
- [ ] Acessar: `GitHub > Settings > Branches`
- [ ] Clicar "Add branch protection rule"
- [ ] Branch name pattern: `master`
- [ ] Marcar opcoes:
  - [ ] Require a pull request before merging
  - [ ] Require status checks to pass before merging
  - [ ] Require branches to be up to date before merging
  - [ ] Do not allow bypassing the above settings
- [ ] Clicar "Create"
- [ ] Data conclusao: ____/____/____

### SEC-005: Decisao de Negocio - Acesso Anonimo
**Pergunta:** Os dados de editais do PNCP devem ser acessiveis sem autenticacao?

**ANALISE (2026-01-19):**
- Dados do PNCP sao publicos por lei (transparencia governamental)
- Frontend JA exige autenticacao (ProtectedRoute bloqueia anonimos)
- Grants para `anon` no banco sao REDUNDANTES
- Remover anon = defesa em profundidade sem impacto funcional

**RECOMENDACAO TECNICA:** Remover grants para `anon`

- [ ] **DECISAO: REMOVER ACESSO ANONIMO** (Recomendado)
  - [ ] Executar script: `data/sql/remove_anon_grants.sql` no Supabase SQL Editor
  - [ ] Verificar que frontend continua funcionando (deve funcionar)
  - [ ] Testar chamada direta a API sem token (deve retornar 403)

- [ ] **DECISAO: MANTER ACESSO ANONIMO** (Apenas se necessario)
  - [ ] Documentar motivo (API publica futura, landing page com preview, etc)
  - [ ] Aceitar risco de scraping/abuso

**Decisao tomada:** ________________
**Data:** ____/____/____
**Responsavel:** ________________

---

## MEDIA PRIORIDADE (Proximo Sprint)

### SEC-006: Revogar JWT Legado
- [ ] Acessar: `Supabase Dashboard > Settings > API`
- [ ] Localizar secao "JWT Settings"
- [ ] Verificar se todos os clientes usam nova chave ECC P-256
- [ ] Revogar chave legada HS256
- [ ] Testar aplicacao apos revogacao
- [ ] Data conclusao: ____/____/____

### SEC-007: Corrigir Logging de Secret
- [ ] Editar arquivo: `src/scripts/REVIEW_NEEDED_testar_supabase_conexao.py`
- [ ] Linha 30: Remover impressao parcial da key
- [ ] Substituir por: `print("[OK] SUPABASE_SERVICE_KEY: [CONFIGURADA]")`
- [ ] Commitar alteracao
- [ ] Data conclusao: ____/____/____

### SEC-008: Adicionar Gitleaks ao CI
- [ ] Criar/editar: `.github/workflows/ci.yml`
- [ ] Adicionar step:
```yaml
- name: Gitleaks Scan
  uses: gitleaks/gitleaks-action@v2
  env:
    GITHUB_TOKEN: ${{ secrets.GITHUB_TOKEN }}
```
- [ ] Commitar e testar
- [ ] Data conclusao: ____/____/____

### SEC-009: Documentar Ativacao de Hooks
- [ ] Editar README.md
- [ ] Adicionar secao "Seguranca"
- [ ] Incluir comando: `git config core.hooksPath .githooks`
- [ ] Commitar alteracao
- [ ] Data conclusao: ____/____/____

---

## VERIFICACAO POS-REMEDIACAO

### Checklist Final
- [ ] Todos os BLOCKING ISSUES resolvidos
- [ ] SSL enforcement ativo
- [ ] Bucket protegido
- [ ] Secret scanning habilitado
- [ ] Branch protection configurada
- [ ] Decisao sobre acesso anonimo documentada

### Atualizar Risk Level
Apos completar BLOCK-001 e BLOCK-002:

```bash
# Editar SECURITY_AUDIT_CONSOLIDATED.json
# Alterar:
"risk_level": "CRITICAL"
# Para:
"risk_level": "MEDIUM"  # ou "LOW" se todos os HIGH tambem resolvidos

# Atualizar blocking_issues para array vazio:
"blocking_issues": []
```

### Nova Auditoria
- [ ] Agendar para: 2026-01-26
- [ ] Executar auditoria local
- [ ] Executar auditoria browser
- [ ] Gerar novo SECURITY_AUDIT_CONSOLIDATED.json
- [ ] Verificar `risk_level` != CRITICAL
- [ ] Verificar `blocking_issues` = []

---

## HISTORICO DE ALTERACOES

| Data | Item | Status | Responsavel |
|------|------|--------|-------------|
| 2026-01-19 | Auditoria inicial | Concluida | Claude Code |
| 2026-01-19 | Dependabot configurado | DONE | Claude Code |
| 2026-01-19 | CodeQL configurado | DONE | Claude Code |
| 2026-01-19 | SECURITY.md criado | DONE | Claude Code |
| | | | |
| | | | |
| | | | |

---

## CONTATOS

| Funcao | Nome | Contato |
|--------|------|---------|
| Security Lead | | |
| DevOps | | |
| Product Owner | | |

---

**Status do Deploy:** :x: NAO AUTORIZADO (2 blocking issues pendentes)

*Ultima atualizacao: 2026-01-19*
