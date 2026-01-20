# CHANGELOG - Auditor V17 (URL + Date Fix)

**Data**: 2026-01-20
**Autor**: Claude Code (CRAUDIO)
**Versão**: V17_URL_DATE_FIX

---

## Resumo

O Auditor V17 corrige **3 problemas críticos** identificados na análise de qualidade de dados:

1. **URLs do leiloeiro não extraídas** - URLs na descrição eram ignoradas
2. **Leilões com data passada** - Dados de 2024 ainda apareciam no sistema
3. **Tags SYNC aparecendo** - Limpeza de tags não funcionava corretamente

---

## Problemas Corrigidos

### 1. FIX: Extração de URL do Leiloeiro

**Problema**: O V16 extraía URLs apenas do texto do PDF, ignorando URLs na descrição do edital.

**Exemplo afetado**: Leilão de Teresópolis (ID_C9BF2E6D3312)
- Descrição: "...a ser realizado através do site www.jcacem.lilo.com.br"
- Sistema mostrava: "N/D"

**Solução V17**:
```python
# ANTES (V16) - Só PDF
urls = extrair_urls_de_texto(pdf_text)

# DEPOIS (V17) - PDF + Descrição
urls_pdf = extrair_urls_de_texto(pdf_text)
urls_descricao = extrair_urls_de_texto(descricao)
link, fonte = encontrar_link_leiloeiro_v17(urls_pdf, urls_descricao, texto_completo)
```

**Novas funcionalidades**:
- Busca URLs em: PDF, Descrição, Contexto (regex inteligente)
- Prioriza URLs da descrição (mais confiáveis)
- Filtra domínios governamentais (pncp.gov.br, etc.)
- Filtra emails (gmail.com, hotmail.com, etc.)
- Keywords expandidas: jcacem, lilo, mgl, kleiloes, arremate, lanceja, etc.

---

### 2. FIX: Filtro de Data Passada

**Problema**: O Miner V13 filtrava apenas novos editais. Dados antigos (2024) já estavam no banco.

**Exemplo afetado**: Dom Macedo Costa
- Data do leilão: 04/12/2024
- Data atual: Janeiro 2026

**Solução V17**:
```python
# Verificar data passada NO AUDITOR
if Settings.FILTRAR_DATA_PASSADA and data_leilao_atual:
    if is_data_passada(data_leilao_atual):
        if Settings.EXCLUIR_DATA_PASSADA:
            self.excluir_edital(pncp_id)  # Remove do banco
        else:
            # Marca como EXPIRADO (não remove)
            dados["status_leilao"] = "EXPIRADO"
```

**Configuração via variáveis de ambiente**:
- `FILTRAR_DATA_PASSADA=true` - Ativa filtro (padrão: true)
- `EXCLUIR_DATA_PASSADA=false` - Se true, EXCLUI do banco. Se false, marca como EXPIRADO (padrão: false)

---

### 3. FIX: Limpeza de Tags SYNC/LEILAO

**Problema**: Tags "SYNC" e "LEILAO" apareciam no frontend.

**Causa**:
1. Tags criadas por versões antigas do Miner
2. Dados legados não foram reprocessados pelo V16

**Solução V17**:
```python
# Limpeza robusta (case-insensitive)
TAGS_PROIBIDAS = {"sync", "leilao", "leilão"}

def limpar_tags_v17(tags, metrics):
    tags_limpas = []
    for t in tags:
        t_lower = t.lower() if isinstance(t, str) else str(t).lower()
        if t_lower in Settings.TAGS_PROIBIDAS:
            # Contabiliza nas métricas
            if "sync" in t_lower:
                metrics.tags_sync_removidas += 1
        else:
            tags_limpas.append(t)
    return tags_limpas
```

**Novo no V17**:
- Limpeza case-insensitive (SYNC, Sync, sync)
- Métricas de tags removidas
- Processa TODOS os editais (não apenas pendentes)

---

## Novas Métricas V17

```
V17 - CORREÇÕES APLICADAS:
  |- Editais com data passada: X
  |- Editais excluídos: X
  |- URLs extraídas do PDF: X
  |- URLs extraídas da DESCRIÇÃO: X
  |- URLs não encontradas: X
  |- Tags SYNC removidas: X
  |- Tags LEILAO removidas: X
  |- Modalidades corrigidas: X
```

---

## Arquivos Modificados

| Arquivo | Mudança |
|---------|---------|
| `src/core/cloud_auditor_v17.py` | **NOVO** - Auditor com todas as correções |
| `.github/workflows/ache-sucatas.yml` | Atualizado para usar V17 |

---

## Como Executar

### Execução Normal (apenas pendentes)
```bash
python src/core/cloud_auditor_v17.py
```

### Reprocessar TODOS os editais (recomendado na primeira execução)
```bash
python src/core/cloud_auditor_v17.py --reprocess-all
```

### Com limite
```bash
python src/core/cloud_auditor_v17.py --limit 100
```

### Via GitHub Actions
1. Vá em Actions > ACHE SUCATAS
2. Clique em "Run workflow"
3. Marque "Reprocessar TODOS editais" para corrigir dados legados

---

## Compatibilidade

- **Backward compatible**: V17 processa editais de TODAS as versões anteriores
- **Versões suportadas**: V10, V11, V12, V13, V14, V15, V16
- **Marcação**: Editais processados são marcados como `V17_URL_DATE_FIX`

---

## Checklist de Validação

Após executar V17, verificar no dashboard:

- [ ] Leilão Teresópolis (ID_C9BF2E6D3312) agora tem link do leiloeiro
- [ ] Leilão Dom Macedo Costa (data 2024) foi removido ou marcado como EXPIRADO
- [ ] Leilão Taquari (ID_CF1C1DF0F6D0) agora tem link do leiloeiro (mgl.com.br)
- [ ] Nenhum card mostra tag "SYNC" ou "LEILAO"

---

## Próximos Passos Recomendados

1. **Executar V17 com --reprocess-all** para corrigir todos os dados legados
2. **Monitorar métricas** de URLs extraídas e editais expirados
3. **Verificar frontend** para confirmar correções

---

## Contato

Dúvidas ou problemas? Abra uma issue no repositório.
