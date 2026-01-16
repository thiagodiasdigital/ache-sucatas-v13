#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Analisa editais com quantidade_itens = N/D para identificar padrões
e melhorar a extração.
"""

import pandas as pd
import re
from pathlib import Path
import pdfplumber

df = pd.read_csv('analise_editais_v12.csv', encoding='utf-8-sig')

print("="*80)
print("ANALISE: quantidade_itens")
print("="*80)
print()

# Estatísticas
total = len(df)
com_qtd = (df['quantidade_itens'] != 'N/D').sum()
sem_qtd = (df['quantidade_itens'] == 'N/D').sum()

print(f"Cobertura atual: {com_qtd}/{total} ({(com_qtd/total)*100:.1f}%)")
print(f"Sem quantidade:  {sem_qtd}/{total} ({(sem_qtd/total)*100:.1f}%)")
print()

# Pegar 10 editais sem quantidade
nd = df[df['quantidade_itens'] == 'N/D'].head(10)

print(f"Analisando 10 editais SEM quantidade_itens...\n")

PASTA_EDITAIS = Path("ACHE_SUCATAS_DB")

for i, row in nd.iterrows():
    arquivo_origem = row['arquivo_origem']
    pasta_edital = PASTA_EDITAIS / arquivo_origem

    print(f"[{len([x for x in nd.iterrows() if x[0] <= i])}] {arquivo_origem[:60]}")

    if not pasta_edital.exists():
        print("    [ERRO] Pasta nao encontrada\n")
        continue

    # Ler PDF
    pdfs = list(pasta_edital.glob("*.pdf"))
    if not pdfs:
        print("    [AVISO] Nenhum PDF encontrado\n")
        continue

    # Ler texto do primeiro PDF (usando pdfplumber como o auditor)
    pdf_path = pdfs[0]

    try:
        texto = ""
        with pdfplumber.open(pdf_path) as pdf:
            for page in pdf.pages[:5]:  # Primeiras 5 páginas
                texto += page.extract_text() or ""

        # Procurar padrões de quantidade
        padroes = [
            (r'\b(\d+)\s*(?:lotes?|itens?)\b', 'X lotes/itens'),
            (r'total\s*de\s*(\d+)', 'total de X'),
            (r'(?:composto|constituído|constituido)\s*(?:de|por)\s*(\d+)', 'composto de X'),
            (r'quantidade[:\s]*(\d+)', 'quantidade: X'),
            (r'(\d+)\s*(?:veículos?|veiculos?|bens?)', 'X veiculos/bens'),
            (r'aproximadamente\s*(\d+)', 'aproximadamente X'),
            (r'lote\s*(?:único|unico)\b', 'lote unico (1)'),
        ]

        encontrado = False
        for padrao, desc in padroes:
            matches = re.findall(padrao, texto[:5000], re.IGNORECASE)
            if matches:
                if isinstance(matches[0], str):
                    print(f"    [ENCONTRADO] {desc}: {matches[:3]}")
                else:
                    print(f"    [ENCONTRADO] {desc}: 1")
                encontrado = True
                break

        if not encontrado:
            # Mostrar trecho relevante
            trechos = re.findall(r'.{0,50}(?:lote|item|veículo|veiculo|bem|quantidade).{0,50}', texto[:3000], re.IGNORECASE)
            if trechos:
                print(f"    [TRECHO] {trechos[0][:80]}...")
            else:
                print(f"    [N/D] Nenhum padrao encontrado")

    except Exception as e:
        print(f"    [ERRO] {str(e)[:80]}")

    print()

print("="*80)
print("ANALISE DE EDITAIS COM quantidade_itens (para comparacao)")
print("="*80)
print()

# Pegar 5 editais COM quantidade
com = df[df['quantidade_itens'] != 'N/D'].head(5)

print("Exemplos de editais que JA tem quantidade:\n")

for i, row in com.iterrows():
    arquivo = row['arquivo_origem'][:50]
    qtd = row['quantidade_itens']
    print(f"  {arquivo:50s} -> {qtd}")

print()
print("="*80)
print("RECOMENDACOES")
print("="*80)
print()

print("1. Melhorar padroes de regex no PDF:")
print("   - Adicionar mais variações de texto")
print("   - Procurar em tabelas/anexos")
print("   - Aumentar area de busca (5000 chars)")
print()
print("2. Analisar descrição do JSON PNCP:")
print("   - Campo 'objetoCompra' pode conter quantidade")
print()
print("3. Buscar em Excel/CSV anexos:")
print("   - Contar linhas de planilhas de itens")
print()
print("4. API PNCP endpoint de itens:")
print("   - Verificar se existe endpoint separado para itens")
print("   - Ex: /orgaos/{cnpj}/compras/{ano}/{seq}/itens")
print()
print("="*80)
