# REGRAS DE NEGOCIO - ACHE SUCATAS DaaS

Este documento contem regras de negocio IMUTAVEIS que NUNCA devem ser alteradas.
Qualquer violacao destas regras e considerada um bug critico.

---

## CORE BUSINESS RULES

### 1. PNCP Link Format (REGRA IMUTAVEL)

**Formato CORRETO:**
```
https://pncp.gov.br/app/editais/{CNPJ}/{ANO}/{SEQUENCIAL}
```

**Exemplo CORRETO:**
```
https://pncp.gov.br/app/editais/18188243000160/2025/161
```

**Formato ERRADO (NUNCA usar):**
```
https://pncp.gov.br/app/editais/{CNPJ}/1/{SEQUENCIAL}/{ANO}
https://pncp.gov.br/app/editais/{CNPJ}/{SEQUENCIAL}/{ANO}
```

**Exemplo ERRADO:**
```
https://pncp.gov.br/app/editais/18188243000160/1/000161/2025  <- ERRADO!
```

#### Implementacao

**TypeScript (Frontend):**
```typescript
// Usar: frontend/src/utils/pncp.ts
import { getPncpLink, getPncpLinkFromId } from '@/utils/pncp';

// Gerar link a partir dos componentes
const link = getPncpLink("18188243000160", "2025", "161");

// Gerar link a partir de um pncp_id
const link = getPncpLinkFromId("18188243000160-1-000161-2025");
```

**Python (Backend):**
```python
# Usar: src/core/supabase_repository.py
from src.core.supabase_repository import gerar_link_pncp_correto, corrigir_link_pncp_do_pncp_id

# Gerar link a partir dos componentes
link = gerar_link_pncp_correto("18188243000160", "2025", "161")

# Gerar link a partir de um pncp_id
link = corrigir_link_pncp_do_pncp_id("18188243000160-1-000161-2025")
```

#### Validacao

Ao gerar um link PNCP, SEMPRE verificar:
1. CNPJ deve ter 14 digitos (apenas numeros)
2. ANO deve ter 4 digitos
3. SEQUENCIAL pode ter zeros removidos (161 em vez de 000161)
4. Ordem OBRIGATORIA: CNPJ -> ANO -> SEQUENCIAL

---

## Historico de Regressoes

| Data | Arquivo | Problema | Correcao |
|------|---------|----------|----------|
| 2026-01-19 | sincronizar_storage_banco.py:186 | Usava `pncp_id.replace('-', '/')` gerando formato errado | Corrigido para usar formato `CNPJ/ANO/SEQUENCIAL` |

---

## Checklist para Code Review

Antes de aprovar qualquer PR que envolva links PNCP:

- [ ] Link segue formato `/CNPJ/ANO/SEQUENCIAL`
- [ ] NAO contem `/1/` no caminho
- [ ] NAO inverte ANO e SEQUENCIAL
- [ ] Usa funcoes utilitarias em vez de interpolacao direta
- [ ] CNPJ esta limpo (apenas digitos)
