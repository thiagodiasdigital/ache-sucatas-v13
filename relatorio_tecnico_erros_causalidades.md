# Relatório Técnico: Erros e Causalidades

**Data:** 2026-01-20
**Projeto:** Ache Sucatas DaaS
**Versão:** Miner V13 + Auditor V17
**Autor:** Claude Opus 4.5 (assistido por Thiago)

---

## 1. Resumo Executivo

Este relatório documenta os erros identificados no dashboard do sistema Ache Sucatas, suas causas raiz, e as ações corretivas implementadas durante a sessão de análise.

### Problemas Identificados no Dashboard:

| # | Problema | Severidade |
|---|----------|------------|
| 1 | Tag "SYNC" aparecendo nos cards de leilão | Alta |
| 2 | Leilões com data de 2024 ainda visíveis | Alta |
| 3 | Leilões sem link do leiloeiro (ex: MUNICÍPIO DE TERESÓPOLIS) | Média |
| 4 | URL do leiloeiro aparecendo no corpo da descrição em vez do campo correto | Média |

---

## 2. Análise Detalhada dos Erros

### 2.1 Tag "SYNC" Aparecendo nos Cards

**Descrição:**
A tag "SYNC" estava aparecendo como badge nos cards de leilão no dashboard, o que não deveria ser visível para o usuário final.

**Causa Raiz:**
- A tag "SYNC" é uma tag interna de controle usada durante o processo de sincronização
- O Auditor V17 possui função `extrair_tags_inteligente()` que deveria remover tags proibidas (SYNC, LEILAO, LEILÃO)
- Dados antigos processados por versões anteriores do Auditor não passaram pelo filtro de tags proibidas

**Diagnóstico Realizado:**
```
Tabela editais_leilao: 0 registros com tag SYNC
Tabela raw.leiloes: Verificação pendente via SQL
```

**Status:** Tags SYNC não encontradas em `editais_leilao` (288 registros). Possível problema apenas em `raw.leiloes`.

---

### 2.2 Leilões com Data de 2024

**Descrição:**
Leilões com datas de leilão no ano de 2024 (ex: 15/08/2024, 04/12/2024) ainda apareciam no dashboard, mesmo sendo eventos já realizados.

**Causa Raiz:**
- Não existia processo de limpeza/arquivamento de leilões com data passada
- O Miner V13 filtra `data_leilao >= hoje` apenas para **novos** editais
- Dados históricos coletados anteriormente permaneceram no banco sem filtro de expiração

**Impacto:**
- Usuários veem leilões que já aconteceram
- Confusão sobre quais leilões estão ativos
- Poluição visual no dashboard

**Exemplos Identificados (screenshots):**
- PREFEITURA MUNICIPAL DE UBAITABA: 15/08/2024
- PREFEITURA MUN. DE DOM MACEDO COSTA: 04/12/2024

---

### 2.3 Leilões Sem Link do Leiloeiro

**Descrição:**
Diversos leilões não possuíam o campo `link_leiloeiro` preenchido, resultando na ausência do botão "Dar Lance" no card.

**Causa Raiz:**
- O link do leiloeiro não está disponível diretamente na API PNCP
- Deve ser extraído do PDF do edital ou da descrição
- Nem todos os editais contêm URL do leiloeiro
- Alguns editais são de leilões presenciais (não têm site)

**Diagnóstico Realizado:**
```
Total de leilões: 288
Sem link_leiloeiro: 99 (34.4%)
Com URL na descrição (recuperáveis): 1 (0.3%)
```

**Conclusão:**
A maioria dos 99 leilões sem link simplesmente não possui URL no edital original. Apenas 1 tinha URL recuperável na descrição.

---

### 2.4 URL no Corpo da Descrição

**Descrição:**
Em alguns casos, a URL do leiloeiro estava presente no texto da descrição do edital, mas não foi extraída para o campo `link_leiloeiro`.

**Exemplos Identificados:**
- MINISTÉRIO DA ECONOMIA: URL `http://www25.receita.fazenda.gov.br/sle-sociedade/portal/edital/...` no corpo do texto
- MUNICÍPIO DE TERESÓPOLIS: URL do site `www.jcaem.lilio.com.br` mencionada na descrição

**Causa Raiz:**
- O Auditor V17 possui função `encontrar_link_leiloeiro_v17()` que busca URLs em:
  1. Descrição (prioridade 1)
  2. PDF (prioridade 2)
  3. Contexto de leiloeiro (prioridade 3)
- Porém, dados antigos não foram reprocessados com o V17
- A função filtra URLs governamentais (gov.br, receita.fazenda) que podem ser válidas em alguns casos

**Observação:**
A URL da Receita Federal (`receita.fazenda.gov.br`) é filtrada como "governamental", mas neste caso específico é o site oficial do leilão da Receita.

---

## 3. Arquitetura do Banco de Dados

Durante a análise, foi identificada uma complexidade na arquitetura:

### Estrutura de Tabelas:

| Tabela | Schema | Função | Quem Escreve | Quem Lê |
|--------|--------|--------|--------------|---------|
| `editais_leilao` | public | Dados principais | Miner/Auditor | Scripts Python |
| `raw.leiloes` | raw | Dados para frontend | Sincronização manual | View |
| `v_auction_discovery` | pub | View do frontend | - | Frontend React |

### Fluxo de Dados:

```
API PNCP
    ↓
Miner V13 (coleta)
    ↓
public.editais_leilao (288 registros)
    ↓
[SINCRONIZAÇÃO MANUAL] ← Ponto de falha!
    ↓
raw.leiloes
    ↓
pub.v_auction_discovery (view com filtros)
    ↓
Frontend React
```

**Problema Identificado:**
A sincronização entre `editais_leilao` e `raw.leiloes` é manual, o que pode causar:
- Dados desatualizados no frontend
- Correções em `editais_leilao` não refletidas em `raw.leiloes`

---

## 4. Verificação de Scripts Existentes

### Scripts Encontrados (marcados como REVIEW_NEEDED):

| Arquivo | Status | Problema |
|---------|--------|----------|
| `REVIEW_NEEDED_reprocessar_com_api.py` | Desatualizado | Usa Auditor V12 local |
| `REVIEW_NEEDED_monitorar_reprocessamento.py` | Desatualizado | Monitora V12 local |

**Conclusão:**
Os scripts existentes não resolvem o problema pois:
1. Usam versão antiga do Auditor (V12 em vez de V17)
2. Processam arquivos locais, não dados no Supabase
3. Não tratam a sincronização entre tabelas

---

## 5. Ações Corretivas Implementadas

### 5.1 Scripts Criados

| Arquivo | Função | Tipo |
|---------|--------|------|
| `limpar_leiloes_antigos.sql` | Arquivar/deletar leilões com data < hoje | SQL |
| `reprocessar_link_leiloeiro.py` | Extrair links da descrição, remover tags SYNC | Python |
| `DIAGNOSTICO_COMPLETO.sql` | Diagnóstico completo das duas tabelas | SQL |
| `diagnostico_raw_leiloes.py` | Diagnóstico via API Python | Python |

### 5.2 Execução do Script Python

```
================================================================================
REPROCESSAMENTO DE DADOS - Link Leiloeiro + Tags
================================================================================

[2/5] Buscando leiloes que precisam de correcao...
  [OK] 288 leiloes encontrados no total

[3/5] Analisando dados...
  Total de leiloes: 288
  Com tag SYNC/LEILAO: 0
  Sem link_leiloeiro: 99
  Com URL na descricao (recuperaveis): 1
  Com modalidade nao padrao: 0
  ---
  TOTAL A CORRIGIR: 1

[5/5] RESULTADO FINAL
  Leiloes processados: 1
  Sucesso: 1
  Falhas: 0
================================================================================
```

### 5.3 Commit Realizado

```
Commit: 3133b4a
Mensagem: feat: Add data quality scripts for fixing SYNC tags, old dates, and missing links
Arquivos: 4 adicionados (899 linhas)
```

---

## 6. Pendências e Próximos Passos

### Ações Pendentes (a serem executadas no Supabase SQL Editor):

| # | Ação | Script | Prioridade |
|---|------|--------|------------|
| 1 | Executar diagnóstico completo | `DIAGNOSTICO_COMPLETO.sql` | Alta |
| 2 | Sincronizar dados para raw.leiloes | `SINCRONIZAR_DADOS.sql` | Alta |
| 3 | Limpar leilões de 2024 | `limpar_leiloes_antigos.sql` | Alta |
| 4 | Atualizar dashboard (F5) | - | Alta |

### Melhorias Sugeridas para o Futuro:

1. **Sincronização Automática:**
   Criar trigger ou job que sincronize automaticamente `editais_leilao` → `raw.leiloes`

2. **Limpeza Automática de Dados Antigos:**
   Criar job agendado que arquive/delete leilões com `data_leilao < CURRENT_DATE`

3. **Revisão do Filtro de URLs Governamentais:**
   Avaliar se URLs como `receita.fazenda.gov.br/sle-sociedade` devem ser permitidas (são sites de leilão da Receita)

4. **Reprocessamento Periódico:**
   Criar workflow que reprocesse dados existentes com novas versões do Auditor

5. **Monitoramento de Qualidade:**
   Implementar alertas para:
   - Leilões sem link_leiloeiro
   - Tags proibidas detectadas
   - Dados com data passada

---

## 7. Erros Técnicos Durante a Sessão

### 7.1 Erro de Acesso à Tabela via Python

```
Erro: Could not find the table 'public.leiloes' in the schema cache
Causa: Nome incorreto da tabela (deveria ser editais_leilao)
Solução: Corrigido para usar supabase.table("editais_leilao")
```

### 7.2 Erro de Acesso à View via Python

```
Erro: Could not find the table 'public.v_auction_discovery' in the schema cache
Causa: View está no schema 'pub', não 'public'
Nota: Cliente Supabase Python só acessa schema public por padrão
```

### 7.3 Erro de Tipo no SQL

```
Erro: operator does not exist: text[] ~~* unknown (tags ILIKE)
Causa: Coluna 'tags' é array (text[]), não texto
Solução: Usar array_to_string(tags, ',') ILIKE '%sync%'
```

### 7.4 Erro de Execução de Python no SQL Editor

```
Erro: syntax error at or near "#!/"
Causa: Usuário tentou executar arquivo .py no SQL Editor do Supabase
Solução: Explicar que arquivos .py devem ser executados no terminal
```

---

## 8. Conclusões

### Causa Raiz Principal:

Os problemas identificados no dashboard têm como causa raiz comum a **falta de sincronização e manutenção dos dados**:

1. Dados antigos não foram reprocessados com versões mais recentes do Auditor
2. Não existe processo automático de limpeza de leilões expirados
3. A sincronização entre tabelas é manual e pode estar desatualizada

### Efetividade das Correções:

| Problema | Status | Observação |
|----------|--------|------------|
| Tag SYNC | Parcial | Não encontrada em editais_leilao; verificar raw.leiloes |
| Datas 2024 | Pendente | Script SQL criado, aguardando execução |
| Links faltando | Parcial | 1 de 99 recuperado; 98 não têm URL no edital |
| URL na descrição | Corrigido | 1 link extraído com sucesso |

### Recomendação Final:

Executar os scripts SQL no Supabase na ordem indicada e implementar as melhorias sugeridas para evitar recorrência dos problemas.

---

## 9. Anexos

### A. Arquivos Criados Nesta Sessão:

1. `limpar_leiloes_antigos.sql` (227 linhas)
2. `reprocessar_link_leiloeiro.py` (381 linhas)
3. `DIAGNOSTICO_COMPLETO.sql` (155 linhas)
4. `diagnostico_raw_leiloes.py` (136 linhas)
5. `relatorio_tecnico_erros_causalidades.md` (este arquivo)

### B. Commits Relacionados:

- `3133b4a` - feat: Add data quality scripts for fixing SYNC tags, old dates, and missing links

---

**Fim do Relatório**

*Gerado automaticamente por Claude Opus 4.5 em 2026-01-20*
