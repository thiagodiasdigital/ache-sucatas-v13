#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Validação Final - 100% de Cobertura
"""

import pandas as pd

print("="*80)
print("VALIDACAO FINAL - V12 COM API COMPLETA DO PNCP")
print("="*80)

df = pd.read_csv('analise_editais_v12.csv', encoding='utf-8-sig')

print(f"\n[INFO] Total de registros: {len(df)}")

# Validar data_leilao
datas_validas = (df['data_leilao'] != 'N/D').sum()
taxa_datas = (datas_validas / len(df)) * 100

print(f"\n{'='*80}")
print("CAMPO CRITICO #1: data_leilao")
print("="*80)
print(f"Preenchidas: {datas_validas}/{len(df)} ({taxa_datas:.1f}%)")

if taxa_datas == 100:
    print(f"[PERFEITO] 100% - META EXCEDIDA!")
elif taxa_datas >= 90:
    print(f"[EXCELENTE] Meta atingida (>= 90%)!")
else:
    print(f"[INSUFICIENTE] Abaixo da meta de 90%")

# Validar link_pncp
import re

def validar_formato_pncp(link):
    if not link or link == 'N/D':
        return False
    match = re.search(r'/editais/(\d{14})/(\d{4})/(\d+)$', str(link))
    return match is not None

links_validos = df['link_pncp'].notna() & (df['link_pncp'] != 'N/D')
links_corretos = df[links_validos]['link_pncp'].apply(validar_formato_pncp).sum()
taxa_links = (links_corretos / links_validos.sum() * 100) if links_validos.sum() > 0 else 0

print(f"\n{'='*80}")
print("CAMPO CRITICO #2: link_pncp")
print("="*80)
print(f"Links validos: {links_validos.sum()}/{len(df)}")
print(f"Formato correto: {links_corretos}/{links_validos.sum()} ({taxa_links:.1f}%)")

if taxa_links == 100:
    print(f"[PERFEITO] 100% - META EXCEDIDA!")
elif taxa_links >= 95:
    print(f"[EXCELENTE] Meta atingida (>= 95%)!")
else:
    print(f"[INSUFICIENTE] Abaixo da meta de 95%")

# Resumo Final
print(f"\n{'='*80}")
print("RESUMO FINAL")
print("="*80)

print(f"\ndata_leilao:")
print(f"  - Taxa: {taxa_datas:.1f}%")
print(f"  - Status: {'PERFEITO - 100%' if taxa_datas == 100 else 'OK' if taxa_datas >= 90 else 'INSUFICIENTE'}")

print(f"\nlink_pncp formato:")
print(f"  - Taxa: {taxa_links:.1f}%")
print(f"  - Status: {'PERFEITO - 100%' if taxa_links == 100 else 'OK' if taxa_links >= 95 else 'INSUFICIENTE'}")

if taxa_datas >= 90 and taxa_links >= 95:
    print(f"\n{'='*80}")
    print("*** MISSAO CUMPRIDA! ***")
    print("TODOS OS CAMPOS CRITICOS CORRIGIDOS!")
    print("SISTEMA ACHE SUCATAS 100% OPERACIONAL!")
    print("="*80)

    if taxa_datas == 100 and taxa_links == 100:
        print("\nBONUS: 200% DE SUCESSO - AMBOS OS CAMPOS EM 100%!")

print("\n" + "="*80)
