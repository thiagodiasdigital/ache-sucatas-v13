#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Lista todos os editais com link_leiloeiro = N/D para verificação manual
"""

import pandas as pd

df = pd.read_csv('analise_editais_v12.csv', encoding='utf-8-sig')

# Filtrar N/D
nd = df[df['link_leiloeiro'] == 'N/D'].copy()

print("="*100)
print("EDITAIS COM link_leiloeiro = N/D (NAO ENCONTRADO)")
print(f"Total: {len(nd)} editais")
print("="*100)
print()

for i, row in nd.iterrows():
    numero = i + 1
    origem = row['arquivo_origem']

    # Extrair cidade/estado
    if '\\' in origem:
        cidade_estado = origem.split('\\')[0]
    else:
        cidade_estado = origem.split('/')[0]

    n_edital = row['n_edital']
    titulo = row['titulo']
    data_leilao = row['data_leilao']
    modalidade = row['modalidade_leilao']
    link_pncp = row['link_pncp']

    print(f"{numero}. {cidade_estado}")
    print(f"   N. Edital: {n_edital}")
    print(f"   Titulo: {titulo[:70]}...")
    print(f"   Data Leilao: {data_leilao}")
    print(f"   Modalidade: {modalidade}")
    print(f"   Link PNCP: {link_pncp}")
    print()

print("="*100)
print(f"\nTOTAL: {len(nd)} editais precisam de verificacao manual")
print("="*100)
