#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import pandas as pd

# Ler arquivo
df = pd.read_excel(r'C:\Users\Larissa\Desktop\testes-12-01-17h\RESULTADO_FINAL.xlsx')

print('='*60)
print('VALIDACAO RESULTADO_FINAL.xlsx')
print('='*60)
print(f'Total de registros: {len(df)}')
print(f'Total de colunas: {len(df.columns)}')

print('\nColunas encontradas:')
for i, col in enumerate(df.columns, 1):
    print(f'  {i}. {col}')

print(f'\n{"-"*60}')
print(f'{"[CAMPO]":<25} {"[PREENCHIDOS]":<20} {"[TAXA]":<10}')
print('-'*60)

for col in df.columns:
    total = len(df)
    filled = ((df[col] != 'N/D') & df[col].notna() & (df[col] != '')).sum()
    taxa = (filled / total * 100) if total > 0 else 0
    status = '[OK]' if taxa >= 80 else '[PARCIAL]' if taxa >= 50 else '[BAIXO]'
    print(f'{col:<25} {filled:3d}/{total:3d} ({taxa:5.1f}%)    {status}')

print('='*60)
print('\nPrimeiras 3 linhas (amostra):')
print(df.head(3).to_string())
