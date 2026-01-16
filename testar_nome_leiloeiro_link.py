#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Testa a extração de nome_leiloeiro a partir do link_leiloeiro.
"""

import pandas as pd
import sys
from pathlib import Path

# Importar função do auditor
sys.path.insert(0, str(Path(__file__).parent))
from local_auditor_v12_final import extrair_nome_do_link

df = pd.read_csv('analise_editais_v12.csv', encoding='utf-8-sig')

print("="*80)
print("TESTE: Extrair nome_leiloeiro do link_leiloeiro")
print("="*80)
print()

# Estatísticas ANTES
total = len(df)
com_nome_antes = (df['nome_leiloeiro'] != 'N/D').sum()
com_link = (df['link_leiloeiro'] != 'N/D') & (df['link_leiloeiro'] != 'PRESENCIAL')
com_link_count = com_link.sum()

print(f"Cobertura ANTES (CSV):")
print(f"  nome_leiloeiro: {com_nome_antes}/{total} ({(com_nome_antes/total)*100:.1f}%)")
print(f"  link_leiloeiro validos: {com_link_count}/{total} ({(com_link_count/total)*100:.1f}%)")
print()

# Testar função em todos os links válidos
resultados = []

for i, row in df[com_link].iterrows():
    link = row['link_leiloeiro']
    nome_csv = row['nome_leiloeiro']

    nome_extraido = extrair_nome_do_link(link)

    if nome_extraido != 'N/D':
        resultados.append({
            'link': link,
            'nome_csv': nome_csv,
            'nome_extraido': nome_extraido,
            'melhorou': nome_csv == 'N/D'
        })

print(f"Testando em {com_link_count} links validos...\n")

# Estatísticas DEPOIS
df_result = pd.DataFrame(resultados)

if not df_result.empty:
    total_testado = len(df_result)
    melhorias = df_result['melhorou'].sum()

    print(f"Resultados:")
    print(f"  Nomes extraidos do link: {total_testado}/{com_link_count} ({(total_testado/com_link_count)*100:.1f}%)")
    print(f"  Melhorias (N/D -> nome): {melhorias}")
    print()

    # Projeção
    cobertura_projetada = com_nome_antes + melhorias
    pct_projetada = (cobertura_projetada / total) * 100

    print("="*80)
    print("PROJECAO")
    print("="*80)
    print(f"\nCobertura ATUAL:     {com_nome_antes}/{total} ({(com_nome_antes/total)*100:.1f}%)")
    print(f"Cobertura PROJETADA: {cobertura_projetada}/{total} ({pct_projetada:.1f}%)")
    print(f"\nMelhoria: +{melhorias} editais (+{(melhorias/total)*100:.1f}%)")

    # Mostrar 10 exemplos
    print()
    print("="*80)
    print("EXEMPLOS (10 primeiros)")
    print("="*80)
    print()

    for i, row in df_result.head(10).iterrows():
        status = "[MELHORIA]" if row['melhorou'] else "[OK]"
        print(f"{status} {row['link'][:45]:45s}")
        print(f"         CSV: {row['nome_csv']}")
        print(f"         Extraido: {row['nome_extraido']}")
        print()

print("="*80)
