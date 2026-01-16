# INSTRUÇÕES - EXECUTAR SCHEMA SQL NO SUPABASE

## Passo 1: Acessar SQL Editor do Supabase

1. Acesse: https://supabase.com/dashboard
2. Selecione o projeto: **rwamrppaczwhbnxfpohc**
3. No menu lateral esquerdo, clique em: **SQL Editor**
4. Clique no botão: **New query**

## Passo 2: Copiar e Colar o Schema

1. Abra o arquivo: `schemas_v13_supabase.sql` (neste diretório)
2. Selecione TODO o conteúdo (Ctrl+A)
3. Copie (Ctrl+C)
4. Cole no SQL Editor do Supabase (Ctrl+V)

## Passo 3: Executar

1. Clique no botão verde **Run** (ou pressione Ctrl+Enter)
2. Aguarde a execução (pode levar 5-10 segundos)
3. Verifique se apareceu **"Success"** sem erros

## Passo 4: Validar

Depois de executar o schema, volte aqui e execute:

```bash
python testar_supabase_conexao.py
```

Se aparecer:
- **"[OK] Tabela 'editais_leilao' existe (count: 0)"** = SUCESSO!
- **"[AVISO] Tabela nao existe ainda"** = Execute o schema novamente

## O que o schema cria:

✅ **3 Tabelas**:
   - `editais_leilao` (principal)
   - `execucoes_miner` (log de execuções)
   - `metricas_diarias` (analytics)

✅ **Índices** para performance

✅ **Views** para queries otimizadas

✅ **RLS (Row Level Security)** ativado:
   - Service Key: acesso total
   - Anon Key: BLOQUEADO (segurança máxima)

## Troubleshooting

### Se der erro "permission denied"
- Verifique que está usando a Service Role Key (não a anon key)
- Verifique que está logado como Owner do projeto

### Se der erro "already exists"
- Tudo bem! Significa que já foi executado antes
- Pode continuar normalmente

### Se der erro de sintaxe
- Verifique que copiou TODO o conteúdo do arquivo
- Tente executar novamente

---

**Quando terminar, me avise aqui que executou o schema!**
