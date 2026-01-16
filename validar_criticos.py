#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Validar Campos Críticos - data_leilao e link_pncp
"""

import pandas as pd
import re
from pathlib import Path

csv_file = Path('analise_editais_v12.csv')

if not csv_file.exists():
    print("[ERRO] analise_editais_v12.csv não encontrado!")
    print("[INFO] O reprocessamento ainda está em andamento.")
    exit(1)

print("="*80)
print("VALIDAÇÃO DE CAMPOS CRÍTICOS - V12 REPROCESSADO")
print("="*80)

df = pd.read_csv(csv_file, encoding='utf-8-sig')

print(f"\n[INFO] Total de registros: {len(df)}")

# =============================================================================
# VALIDAÇÃO CRÍTICA #1: data_leilao
# =============================================================================
print(f"\n{'='*80}")
print("CAMPO CRÍTICO #1: data_leilao")
print("="*80)

datas_validas = ((df['data_leilao'] != 'N/D') & df['data_leilao'].notna() & (df['data_leilao'] != '')).sum()
taxa_datas = (datas_validas / len(df) * 100) if len(df) > 0 else 0

print(f"Preenchidas: {datas_validas}/{len(df)} ({taxa_datas:.1f}%)")

if taxa_datas >= 90:
    print(f"[EXCELENTE] ✓ Meta atingida! (≥90%)")
elif taxa_datas >= 70:
    print(f"[BOM] Próximo da meta (70-89%)")
elif taxa_datas >= 50:
    print(f"[REGULAR] Melhorou mas precisa ajustes (50-69%)")
else:
    print(f"[BAIXO] Ainda abaixo do esperado (<50%)")

# Mostrar amostras
print(f"\n[AMOSTRAS - data_leilao]")
for i, data in enumerate(df['data_leilao'].head(10), 1):
    status = "OK" if data != 'N/D' else "N/D"
    print(f"  {i}. [{status}] {data}")

# =============================================================================
# VALIDAÇÃO CRÍTICA #2: link_pncp formato
# =============================================================================
print(f"\n{'='*80}")
print("CAMPO CRÍTICO #2: link_pncp (formato /CNPJ/ANO/SEQUENCIAL)")
print("="*80)

def validar_formato_pncp(link):
    """Valida se link está no formato correto /CNPJ/ANO/SEQUENCIAL"""
    if not link or link == 'N/D':
        return False

    # Formato: https://pncp.gov.br/app/editais/88150495000186/2025/000490
    # ou: https://pncp.gov.br/app/editais/88150495000186/2025/490
    match = re.search(r'/editais/(\d{14})/(\d{4})/(\d+)$', str(link))
    return match is not None

links_validos = df['link_pncp'].notna() & (df['link_pncp'] != 'N/D')
links_formato_correto = df[links_validos]['link_pncp'].apply(validar_formato_pncp).sum()
taxa_links = (links_formato_correto / links_validos.sum() * 100) if links_validos.sum() > 0 else 0

print(f"Links válidos: {links_validos.sum()}/{len(df)}")
print(f"Formato correto: {links_formato_correto}/{links_validos.sum()} ({taxa_links:.1f}%)")

if taxa_links >= 95:
    print(f"[EXCELENTE] ✓ Meta atingida! (≥95%)")
elif taxa_links >= 70:
    print(f"[BOM] Próximo da meta (70-94%)")
elif taxa_links >= 50:
    print(f"[REGULAR] Melhorou mas precisa ajustes (50-69%)")
else:
    print(f"[BAIXO] Ainda abaixo do esperado (<50%)")

# Mostrar amostras de links
print(f"\n[AMOSTRAS - link_pncp]")
for i, link in enumerate(df['link_pncp'].head(10), 1):
    if validar_formato_pncp(link):
        # Extrair componentes
        match = re.search(r'/editais/(\d{14})/(\d{4})/(\d+)$', str(link))
        if match:
            cnpj, ano, seq = match.groups()
            print(f"  {i}. [OK] /{cnpj}/{ano}/{seq}")
    else:
        print(f"  {i}. [ERRO] {str(link)[:60]}")

# =============================================================================
# RESUMO FINAL
# =============================================================================
print(f"\n{'='*80}")
print("RESUMO DA VALIDAÇÃO")
print("="*80)

print(f"\n1. data_leilao:")
print(f"   Taxa: {taxa_datas:.1f}%")
if taxa_datas >= 90:
    print(f"   Status: ✓ SUCESSO - SEM ELA NÃO EXISTE ACHE SUCATAS!")
elif taxa_datas >= 70:
    print(f"   Status: ⚠ BOM MAS PODE MELHORAR")
else:
    print(f"   Status: ✗ PRECISA CORREÇÃO ADICIONAL")

print(f"\n2. link_pncp formato:")
print(f"   Taxa: {taxa_links:.1f}%")
if taxa_links >= 95:
    print(f"   Status: ✓ SUCESSO - FORMATO CORRETO!")
elif taxa_links >= 70:
    print(f"   Status: ⚠ BOM MAS PODE MELHORAR")
else:
    print(f"   Status: ✗ PRECISA CORREÇÃO ADICIONAL")

# Avaliação geral
if taxa_datas >= 90 and taxa_links >= 95:
    print(f"\n{'='*80}")
    print("✓✓✓ MISSÃO CUMPRIDA! CAMPOS CRÍTICOS CORRIGIDOS! ✓✓✓")
    print("="*80)
    print("\nO sistema ACHE SUCATAS está operacional!")
    print("data_leilao e link_pncp estão corretos.")
elif taxa_datas >= 70 or taxa_links >= 70:
    print(f"\n{'='*80}")
    print("⚠ PARCIALMENTE CORRIGIDO - Melhorou significativamente")
    print("="*80)
    print("\nMas ainda há espaço para otimização adicional.")
else:
    print(f"\n{'='*80}")
    print("✗ CORREÇÕES INSUFICIENTES - Necessário ajustes adicionais")
    print("="*80)

print("\n" + "="*80)
