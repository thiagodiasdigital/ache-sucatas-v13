# 🚨 FREIO DE SEGURANÇA - LIMITE $50 USD

**REGRA MÁXIMA:** Nenhum serviço pode ultrapassar $50 dólares sem aprovação explícita.

---

## 1️⃣ SUPABASE - CONFIGURAÇÃO OBRIGATÓRIA

### ⚠️ AÇÃO IMEDIATA NO DASHBOARD

Acesse: https://supabase.com/dashboard/project/SEU_PROJECT_ID/settings/billing

#### **Passo 1: Bloquear Upgrade Automático**
1. Vá em **Settings** → **Billing**
2. **Certifique-se que está no FREE TIER**
3. **DESABILITAR:** "Automatically upgrade when limits exceeded"
4. **HABILITAR:** "Pause project when quota exceeded"

#### **Passo 2: Configurar Spending Cap**
1. Em **Billing Settings**
2. Procurar por "Spending Limit" ou "Usage Cap"
3. Definir: **$0.00** (zero - força free tier)
4. Se houver opção de "Maximum Monthly Spend": **$50.00**

#### **Passo 3: Alertas de Email**
1. Em **Settings** → **Billing** → **Email Alerts**
2. Habilitar alertas para:
   - ✅ 50% de uso (250 MB database / 500 GB bandwidth)
   - ✅ 75% de uso
   - ✅ 90% de uso
   - ✅ 100% de uso

#### **Passo 4: Verificar Limites Atuais**
No Dashboard, verificar:
- **Database:** _____ MB / 500 MB (free)
- **Bandwidth:** _____ GB / 2 GB/mês (free)
- **Storage:** _____ GB / 1 GB (free)

---

## 2️⃣ GITHUB - CONFIGURAÇÃO (quando criar repo)

### Limites para Repositório Privado FREE

**GitHub Actions:**
- FREE: 2.000 minutos/mês (workflows)
- CONFIGURAR: Disable Actions ou limit to specific workflows
- CUSTO EXTRA: $0.008/minuto além do limite

**Configuração:**
1. Repo Settings → Actions → General
2. Selecionar: "Disable actions" OU "Allow specific actions"
3. **NÃO USAR:** Self-hosted runners pagos
4. **NÃO USAR:** GitHub Packages storage (além de 500 MB)

**Codespaces:**
- **NÃO HABILITAR** (pode gerar custo)

---

## 3️⃣ MONITORAMENTO AUTOMÁTICO LOCAL

### Script de Verificação de Uso Supabase

Execute diariamente para monitorar:

```bash
python monitorar_uso_supabase.py
```

**Alertas configurados:**
- ⚠️ Database > 400 MB (80% do free tier)
- ⚠️ Editais > 10.000 (limite estimado para 500 MB)
- 🚨 Qualquer indicação de billing ativo

---

## 4️⃣ LIMITES TÉCNICOS IMPLEMENTADOS

### No Código Python

**Arquivo:** `supabase_repository.py`
- ✅ Feature flag `enable_supabase` permite desligar facilmente
- ✅ Timeout em queries (max 30s)
- ✅ Batch insert limitado (max 100 por vez)

**Arquivo:** `local_auditor_v13.py`
- ✅ Limite de editais processados (configurável)
- ✅ Não faz re-insert de duplicados (economia de bandwidth)
- ✅ Fallback para CSV local se Supabase falhar

---

## 5️⃣ CÁLCULO DE CUSTOS ESTIMADOS

### Cenário FREE TIER (atual)
| Item | Uso Estimado | Limite Free | Status |
|------|--------------|-------------|--------|
| Database | ~20 MB (198 editais) | 500 MB | ✅ 4% usado |
| Bandwidth | ~5 MB/mês (read/write) | 2 GB/mês | ✅ 0.25% usado |
| API Requests | ~500/dia | Ilimitado (free) | ✅ OK |
| Storage (files) | 0 MB | 1 GB | ✅ 0% usado |

**Custo mensal:** $0.00

### Se Ultrapassar FREE TIER (Pro Plan)
| Recurso Extra | Custo |
|---------------|-------|
| Pro Plan base | $25/mês |
| Database extra 1 GB | $0.125/GB |
| Bandwidth extra 1 GB | $0.09/GB |
| Storage extra 1 GB | $0.021/GB |

**PROTEÇÃO:** Se configurar spending cap em $50, Supabase vai PAUSAR antes de cobrar.

---

## 6️⃣ TRIGGERS DE EMERGÊNCIA

### Quando Acionar Freio de Emergência

**🚨 PARAR TUDO SE:**
- Supabase mostrar cobrança > $0.00
- Database > 450 MB (90% do free)
- Bandwidth > 1.8 GB/mês (90% do free)
- Email de billing do Supabase

**Ação Imediata:**
```bash
# Desligar Supabase no código
python desligar_supabase.py

# Continuar apenas com CSV local
python local_auditor_v13.py --no-supabase
```

---

## 7️⃣ CHECKLIST DE SEGURANÇA FINANCEIRA

Antes de continuar, CONFIRME:

- [ ] Supabase está em FREE TIER (verificar no Dashboard)
- [ ] Spending cap configurado em $0 ou $50 (Dashboard)
- [ ] Alertas de email habilitados (50%, 75%, 90%, 100%)
- [ ] "Auto-upgrade" está DESABILITADO
- [ ] Não há cartão de crédito vinculado (opcional - mais seguro)
- [ ] Script de monitoramento rodando (`monitorar_uso_supabase.py`)

---

## 8️⃣ ALTERNATIVAS SE ATINGIR LIMITES

### Opção 1: PostgreSQL Local (FREE)
- Instalar PostgreSQL no seu computador
- Migrar schema para DB local
- **Custo:** $0.00

### Opção 2: Railway.app (FREE tier)
- 500 MB database + 5 GB bandwidth
- **Custo:** $0.00

### Opção 3: Supabase Pro ($25/mês)
- Só se aprovar explicitamente
- Spending cap em $50 = $25 fixo

---

## 9️⃣ LOGS E AUDITORIA

Todos os acessos ao Supabase são logados:
- `logs/supabase_usage_YYYY-MM-DD.log` (será criado)
- Tracking de: inserts, updates, queries, bytes transferidos

---

## 🔟 COMANDOS DE MONITORAMENTO

```bash
# Ver uso atual do database
python -c "from monitorar_uso_supabase import verificar_uso; verificar_uso()"

# Estimativa de custo (deve ser $0.00)
python -c "from monitorar_uso_supabase import estimar_custo; estimar_custo()"

# Desligar Supabase (emergência)
python desligar_supabase.py

# Re-ativar (após aprovação)
python reativar_supabase.py
```

---

## ✅ STATUS ATUAL

**Revisado em:** 2026-01-16
**Supabase Tier:** FREE
**Custo Mensal:** $0.00
**Limite Configurado:** $50.00 (não aprovado ultrapassar)
**Proteções Ativas:** ⏳ Aguardando configuração no Dashboard

---

## 📞 AÇÃO OBRIGATÓRIA AGORA

**VOCÊ PRECISA FAZER (no Dashboard do Supabase):**
1. Acessar: https://supabase.com/dashboard/project/SEU_PROJECT_ID/settings/billing
2. Desabilitar "auto-upgrade"
3. Configurar spending cap em $0 (ou máximo $50)
4. Habilitar alertas de email
5. Confirmar que está no FREE tier
6. **RESPONDER:** "Configuração do Dashboard concluída" para eu continuar

**Enquanto isso, vou criar os scripts de monitoramento automático...**
