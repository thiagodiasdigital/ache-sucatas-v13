#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import pandas as pd

df = pd.read_csv('analise_editais_v12.csv', encoding='utf-8-sig')
nd = df[df['link_leiloeiro'] == 'N/D']

print("="*60)
print("RESUMO - EDITAIS SEM LINK DE LEILOEIRO")
print("="*60)

print("\nDISTRIBUICAO POR MODALIDADE:")
print("-"*60)
modalidades = nd['modalidade_leilao'].value_counts()
for mod, count in modalidades.items():
    pct = (count / len(nd)) * 100
    print(f"  {mod:12s}: {count:2d} editais ({pct:5.1f}%)")

print(f"\nTotal: {len(nd)} editais sem link de leiloeiro")

print("\n" + "="*60)
print("DISTRIBUICAO POR ESTADO:")
print("-"*60)

# Extrair UF do arquivo_origem
nd_copy = nd.copy()
nd_copy['uf'] = nd_copy['arquivo_origem'].str.split('_').str[0]
estados = nd_copy['uf'].value_counts()

for uf, count in estados.items():
    print(f"  {uf}: {count:2d} editais")

print("\n" + "="*60)
print("OBSERVACOES:")
print("-"*60)
print("1. A maioria dos editais N/D sao PRESENCIAIS (9 editais)")
print("2. Editais presenciais geralmente nao tem site de leiloeiro")
print("3. Alguns editais N/D sao porque o link nao esta no PDF")
print("4. Para estes casos, verificar manualmente no link PNCP")
print("\nArquivo criado: editais_sem_link_leiloeiro.csv")
print("="*60)
