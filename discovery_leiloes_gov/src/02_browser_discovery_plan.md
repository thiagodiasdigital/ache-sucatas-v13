# Plano de Descoberta via Browser (Manual)

## Objetivo
Usar buscas no Google para descobrir URLs oficiais de leiloes de veiculos do governo.

## Instrucoes

1. Abra o Chrome
2. Execute cada busca abaixo
3. Para cada resultado relevante, copie a URL para `inputs/manual_candidates.txt`
4. Foque em:
   - Dominios .gov.br
   - Dominios de DETRAN
   - Diarios Oficiais
   - Paginas com editais numerados

---

## Buscas Recomendadas

### 1. DETRANs - Leiloes

```
site:detran.*.gov.br leilao veiculos
site:detran.*.gov.br leilão veículos apreendidos
site:detran.*.gov.br sucata veiculo
site:detran.sp.gov.br leilao
site:detran.rj.gov.br leilao
site:detran.mg.gov.br leilao
site:detran.pr.gov.br leilao
site:detran.rs.gov.br leilao
```

### 2. Receita Federal

```
site:gov.br/receitafederal leilao veiculos
site:receita.fazenda.gov.br leilao
receita federal leilao veiculos 2026
```

### 3. Policia Federal e PRF

```
site:gov.br/pf leilao veiculos
site:gov.br/prf leilao
policia rodoviaria federal leilao veiculos 2026
```

### 4. Diarios Oficiais

```
site:in.gov.br leilao veiculos edital
site:imprensaoficial.com.br leilao veiculos
diario oficial leilao veiculos apreendidos
```

### 5. Prefeituras e Estados

```
site:prefeitura.sp.gov.br leilao veiculos
site:portoalegre.rs.gov.br leilao
site:curitiba.pr.gov.br leilao
site:rio.rj.gov.br leilao veiculos
```

### 6. Busca Generica GOV.BR

```
site:gov.br leilao sucata veiculos
site:gov.br alienacao bens moveis veiculos
site:gov.br veiculos apreendidos leilao edital
```

### 7. Leiloeiras Credenciadas

```
leiloeira oficial governo leilao veiculos
leiloeira credenciada detran
leiloeira publica veiculos apreendidos
```

---

## Criterios de Selecao

### INCLUIR (copiar para candidates.txt):
- [x] Dominio .gov.br
- [x] Dominio oficial de DETRAN (detran.XX.gov.br)
- [x] Diarios oficiais reconhecidos
- [x] Paginas com numeros de edital/processo
- [x] Leiloeiras com mencao a orgao publico credenciador

### EXCLUIR (nao copiar):
- [ ] Blogs e noticias
- [ ] Portais de leilao privado sem credenciamento visivel
- [ ] Paginas com layout de spam/clickbait
- [ ] PDFs (apenas copiar a pagina que linka ao PDF, nao o PDF direto)

---

## Apos Coletar

1. Salve as URLs em `inputs/manual_candidates.txt`
2. Execute: `python src/03_collect_candidates.py`
3. Execute: `python src/04_crawl_from_seeds.py`
4. Execute: `python src/05_officiality_score.py`
5. Analise: `outputs/sources_ranked.csv` e `REPORT.md`

---

## Dicas

- Use aspas para termos exatos: `"leilao de veiculos apreendidos"`
- Use `-` para excluir: `leilao veiculos -particular -privado`
- Adicione ano para resultados recentes: `leilao veiculos 2026`
- Combine operadores: `site:gov.br "edital de leilao" veiculos 2026`
