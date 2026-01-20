# PROMPT PARA .DEV SENIOR - AUDITORIA CHROME (2026-01-19)

> **Contexto:** Auditoria de canonizacao CRAUDIO (AURION GATE)
> **Objetivo:** Verificar e coletar evidencias de configuracoes que requerem navegador
> **Tempo estimado:** 15-20 minutos
> **Requisitos:** Acesso admin ao Supabase e GitHub do projeto

---

## INSTRUCOES GERAIS

1. Execute cada tarefa na ordem apresentada
2. Para cada tarefa, colete a evidencia solicitada (screenshot ou texto)
3. Anote o resultado no template de output ao final
4. Se encontrar problemas, documente e prossiga

---

## TAREFAS SUPABASE

### TASK-SUP-01: Verificar SSL Enforcement

**Caminho:** Supabase Dashboard > Project Settings > Database

1. Acesse o projeto Ache Sucatas no Supabase
2. Va em: `Settings` > `Database` > `SSL Configuration`
3. Verifique se `SSL Enforcement` esta **ON**

**Evidencia:** Screenshot ou texto "SSL Enforcement: ON/OFF"

---

### TASK-SUP-02: Verificar Bucket Storage

**Caminho:** Supabase Dashboard > Storage

1. Acesse: `Storage` no menu lateral
2. Localize o bucket `editais-pdfs`
3. Clique no bucket e verifique a configuracao de privacidade

**Evidencia:** Screenshot mostrando "Public: No" ou "Private"

---

### TASK-SUP-03: Verificar RLS Policies

**Caminho:** Supabase Dashboard > Authentication > Policies

1. Acesse: `Authentication` > `Policies`
2. Verifique se as seguintes tabelas tem RLS habilitado:
   - `editais`
   - `execucoes_miner`
   - `municipios`

**Evidencia:** Lista de tabelas com RLS ON/OFF

---

### TASK-SUP-04: Verificar Anon Grants

**Caminho:** Supabase Dashboard > SQL Editor

1. Acesse: `SQL Editor`
2. Execute a query:

```sql
SELECT grantee, table_name, privilege_type
FROM information_schema.role_table_grants
WHERE grantee = 'anon'
AND table_schema = 'public';
```

3. Resultado esperado: Nenhuma linha (anon sem permissoes)

**Evidencia:** Output da query (0 rows ou lista de grants)

---

### TASK-SUP-05: Verificar JWT Secret Rotation

**Caminho:** Supabase Dashboard > Settings > API

1. Acesse: `Settings` > `API`
2. Verifique a secao `JWT Settings`
3. Confirme se esta usando algoritmo ECC (P-256) ou RSA

**Evidencia:** Algoritmo JWT atual (HS256/RS256/ES256)

---

## TAREFAS GITHUB

### TASK-GH-01: Verificar Secret Scanning

**Caminho:** GitHub > Settings > Security > Code security and analysis

1. Acesse o repositorio no GitHub
2. Va em: `Settings` > `Code security and analysis`
3. Verifique se `Secret scanning` esta **Enabled**
4. Verifique se ha alertas abertos em `Security` > `Secret scanning alerts`

**Evidencia:** Status (Enabled/Disabled) + quantidade de alertas abertos

---

### TASK-GH-02: Verificar Branch Protection

**Caminho:** GitHub > Settings > Branches

1. Acesse: `Settings` > `Branches`
2. Verifique a regra de protecao para `master`
3. Confirme:
   - Require a pull request before merging: ON/OFF
   - Require approvals: Numero
   - Branches aplicadas: Lista

**Evidencia:** Screenshot ou lista de configuracoes

---

### TASK-GH-03: Verificar Dependabot

**Caminho:** GitHub > Settings > Security > Dependabot

1. Acesse: `Settings` > `Code security and analysis`
2. Verifique:
   - Dependabot alerts: ON/OFF
   - Dependabot security updates: ON/OFF
3. Verifique quantidade de alertas em `Security` > `Dependabot alerts`

**Evidencia:** Status + quantidade de alertas

---

### TASK-GH-04: Verificar CodeQL Alerts

**Caminho:** GitHub > Security > Code scanning alerts

1. Acesse: `Security` > `Code scanning`
2. Filtre por severidade:
   - Critical: X
   - High: X
   - Medium: X
   - Low: X
   - Note: X

**Evidencia:** Contagem por severidade

---

### TASK-GH-05: Verificar Ultimo Workflow

**Caminho:** GitHub > Actions

1. Acesse: `Actions`
2. Filtre por workflow `ACHE SUCATAS - Coleta e Processamento`
3. Verifique a ultima execucao:
   - Data/hora
   - Status (Success/Failure)
   - Duracao

**Evidencia:** Screenshot ou texto com status da ultima execucao

---

## TEMPLATE DE OUTPUT

Copie o template abaixo, preencha e retorne para o CRAUDIO:

```
=== OUTPUT AUDITORIA CHROME 2026-01-19 ===

SUPABASE:
- [SUP-01] SSL Enforcement: ________
- [SUP-02] Bucket editais-pdfs: ________ (Public/Private)
- [SUP-03] RLS Policies:
  - editais: ________
  - execucoes_miner: ________
  - municipios: ________
- [SUP-04] Anon Grants: ________ (0 rows / X rows)
- [SUP-05] JWT Algorithm: ________

GITHUB:
- [GH-01] Secret Scanning: ________ (Enabled/Disabled)
  - Alertas abertos: ________
- [GH-02] Branch Protection master:
  - Require PR: ________
  - Require approvals: ________
  - Branches aplicadas: ________
- [GH-03] Dependabot:
  - Alerts: ________
  - Security updates: ________
  - Alertas abertos: ________
- [GH-04] CodeQL Alerts:
  - Critical: ________
  - High: ________
  - Medium: ________
  - Low: ________
  - Note: ________
- [GH-05] Ultimo workflow ache-sucatas:
  - Data: ________
  - Status: ________
  - Duracao: ________

OBSERVACOES:
(adicione aqui qualquer problema encontrado ou observacao relevante)

=== FIM OUTPUT ===
```

---

## ACOES CORRETIVAS (SE NECESSARIO)

### Se SSL Enforcement OFF:

1. `Settings` > `Database` > `SSL Configuration`
2. Toggle para ON
3. Salvar

### Se Bucket Publico:

1. `Storage` > `editais-pdfs` > `Settings`
2. Alterar para Private
3. Salvar

### Se Branch Protection nao aplica a master:

1. `Settings` > `Branches`
2. Editar regra
3. Alterar pattern de `main` para `master`
4. Salvar

### Se ha alertas Critical/High no CodeQL:

1. Investigar cada alerta
2. Corrigir ou justificar dismiss
3. Documentar decisao

---

## APOS CONCLUSAO

1. Preencha o template de output
2. Retorne o output preenchido para o CRAUDIO
3. Aguarde a validacao e geracao do relatorio final

---

*Prompt gerado automaticamente pela auditoria CRAUDIO em 2026-01-19*
