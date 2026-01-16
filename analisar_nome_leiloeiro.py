#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Analisa editais com nome_leiloeiro = N/D para identificar padrões
e melhorar a extração.
"""

import pandas as pd
import re
from pathlib import Path

df = pd.read_csv('analise_editais_v12.csv', encoding='utf-8-sig')

print("="*80)
print("ANALISE: nome_leiloeiro")
print("="*80)
print()

# Estatísticas
total = len(df)
com_nome = (df['nome_leiloeiro'] != 'N/D').sum()
sem_nome = (df['nome_leiloeiro'] == 'N/D').sum()

print(f"Cobertura atual: {com_nome}/{total} ({(com_nome/total)*100:.1f}%)")
print(f"Sem nome:        {sem_nome}/{total} ({(sem_nome/total)*100:.1f}%)")
print()

# Pegar 10 editais sem nome
nd = df[df['nome_leiloeiro'] == 'N/D'].head(10)

print(f"Analisando 10 editais SEM nome_leiloeiro...\n")

PASTA_EDITAIS = Path("ACHE_SUCATAS_DB")

for idx, row in nd.iterrows():
    arquivo_origem = row['arquivo_origem']
    pasta_edital = PASTA_EDITAIS / arquivo_origem

    print(f"[{idx+1}] {arquivo_origem[:60]}")

    if not pasta_edital.exists():
        print("    [ERRO] Pasta nao encontrada\n")
        continue

    # Ler PDF
    pdfs = list(pasta_edital.glob("*.pdf"))
    if not pdfs:
        print("    [AVISO] Nenhum PDF encontrado\n")
        continue

    # Ler texto do primeiro PDF
    pdf_path = pdfs[0]

    try:
        import pdfplumber
        texto = ""
        with pdfplumber.open(pdf_path) as pdf:
            for page in pdf.pages[:5]:  # Primeiras 5 páginas
                texto += page.extract_text() or ""

        # Procurar padrões de leiloeiro
        padroes = [
            (r'(?:leiloeiro|leiloeira)\s*(?:oficial|público|a)?\s*[:\-]?\s*([A-ZÀ-Ú][a-zà-ú]+(?:\s+[A-ZÀ-Ú][a-zà-ú]+){1,5})', 'Leiloeiro: Nome'),
            (r'(?:Leiloeiro|LEILOEIRO)[:\s]+([A-ZÀ-Ú\s]{3,50})', 'LEILOEIRO: NOME'),
            (r'(?:Matrícula|JUCERGS|JUCEMG|JUCESP)[:\s]+\d+[^\n]*([A-ZÀ-Ú][a-zà-ú]+(?:\s+[A-ZÀ-Ú][a-zà-ú]+){1,4})', 'Matricula + Nome'),
            (r'(?:Responsável|Condutor|Presidente)\s*(?:pelo)?\s*(?:Leilão|leilão)[:\s]*([A-ZÀ-Ú][a-zà-ú]+(?:\s+[A-ZÀ-Ú][a-zà-ú]+){1,4})', 'Responsavel pelo Leilão'),
            (r'www\.([a-z]+)leiloes?\.(com|net)', 'Site leilões (domínio)'),
        ]

        encontrado = False
        for padrao, desc in padroes:
            matches = re.findall(padrao, texto[:5000], re.IGNORECASE)
            if matches:
                print(f"    [ENCONTRADO] {desc}: {matches[:3]}")  # Primeiros 3
                encontrado = True

        if not encontrado:
            # Mostrar trechos relevantes
            trechos = re.findall(r'.{0,50}(?:leiloeir|matrícula|responsável).{0,50}', texto[:3000], re.IGNORECASE)
            if trechos:
                print(f"    [TRECHO] {trechos[0][:100]}...")
            else:
                print(f"    [N/D] Nenhum padrao encontrado")

    except Exception as e:
        print(f"    [ERRO] {str(e)[:50]}")

    print()

print("="*80)
print("ANALISE DE EDITAIS COM nome_leiloeiro (para comparacao)")
print("="*80)
print()

# Pegar 10 editais COM nome
com = df[df['nome_leiloeiro'] != 'N/D'].head(10)

print("Exemplos de editais que JA tem nome_leiloeiro:\n")

for i, row in com.iterrows():
    arquivo = row['arquivo_origem'][:45]
    nome = row['nome_leiloeiro']
    print(f"  {arquivo:45s} -> {nome}")

print()
print("="*80)
print("PADROES COMUNS EM NOMES DE LEILOEIRO")
print("="*80)
print()

# Analisar padrões nos nomes existentes
nomes_existentes = df[df['nome_leiloeiro'] != 'N/D']['nome_leiloeiro'].unique()

print(f"Total de nomes unicos encontrados: {len(nomes_existentes)}")
print()
print("Amostra de 15 nomes:")
for nome in nomes_existentes[:15]:
    print(f"  - {nome}")

print()
print("="*80)
print("RECOMENDACOES")
print("="*80)
print()

print("1. Melhorar padroes de regex no PDF:")
print("   - Adicionar variações: 'condutor do leilão', 'presidente'")
print("   - Procurar após 'Matrícula JUCEX'")
print("   - Buscar em rodapés e cabeçalhos")
print()
print("2. Extrair do link_leiloeiro:")
print("   - Ex: www.fernandoleiloeiro.com.br -> Fernando")
print("   - Ex: www.lopesleiloes.net.br -> Lopes")
print()
print("3. Analisar campo 'objetoCompra' da API:")
print("   - Pode conter menção ao leiloeiro")
print()
print("4. Buscar em metadados do PDF:")
print("   - Autor, Criador podem conter nome")
print()
print("5. Cross-reference com link_leiloeiro:")
print("   - Se vários editais têm mesmo link, podem ter mesmo leiloeiro")
print()
print("="*80)
