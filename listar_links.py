#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import pandas as pd

df = pd.read_csv('analise_editais_v12.csv', encoding='utf-8-sig')

print("="*80)
print("AMOSTRA DE 20 LINKS DE LEILOEIROS EXTRAÍDOS")
print("="*80)
print()

for i, row in df.head(20).iterrows():
    link = row['link_leiloeiro']
    origem = row['arquivo_origem']
    cidade = origem.split('\\')[0] if '\\' in origem else origem.split('/')[0]

    print(f"{i+1:2d}. [{cidade}]")
    print(f"    Link: {link}")
    print()

print("="*80)
print("\nTIPOS DE LINKS:")
print("="*80)

# Contar tipos
presencial = (df['link_leiloeiro'] == 'PRESENCIAL').sum()
links_validos = (df['link_leiloeiro'] != 'PRESENCIAL') & (df['link_leiloeiro'] != 'N/D')
nd = (df['link_leiloeiro'] == 'N/D').sum()

print(f"\n✓ Links de leiloeiros (URLs): {links_validos.sum()}")
print(f"✓ PRESENCIAL (sem leiloeiro): {presencial}")
print(f"✗ N/D (não encontrado): {nd}")
print(f"\nTotal: {len(df)}")
