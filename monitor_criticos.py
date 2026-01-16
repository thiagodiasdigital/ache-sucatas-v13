#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Monitor de Campos Críticos - Validação em Tempo Real
"""

import pandas as pd
import re
from pathlib import Path

csv_file = Path('analise_editais_v12.csv')
log_file = Path('auditor_v12_REPROCESSAMENTO.log')

print("="*70)
print("MONITOR DE CAMPOS CRÍTICOS - TEMPO REAL")
print("="*70)

# Verificar progresso do processamento
if log_file.exists():
    with open(log_file, 'r', encoding='utf-8', errors='ignore') as f:
        content = f.read()

    matches = re.findall(r'\[(\d+)/198\]', content)
    processed = int(matches[-1]) if matches else 0

    print(f"\n[PROGRESSO GERAL]")
    print(f"  Processados: {processed}/198 ({processed/198*100:.1f}%)")
    print(f"  Restantes: {198-processed}")
else:
    print("\n[INFO] Log não encontrado - processamento não iniciado")
    exit(0)

# Verificar CSV
if not csv_file.exists():
    print("\n[INFO] CSV ainda não gerado - aguardando conclusão do processamento")
    exit(0)

# Analisar CSV parcial
df = pd.read_csv(csv_file, encoding='utf-8-sig')
print(f"\n[DADOS DISPONÍVEIS]")
print(f"  Registros no CSV: {len(df)}")

if len(df) == 0:
    print("\n[INFO] CSV vazio - processamento em andamento")
    exit(0)

# Validar data_leilao
print(f"\n{'='*70}")
print("CAMPO CRÍTICO #1: data_leilao")
print("="*70)

datas_validas = ((df['data_leilao'] != 'N/D') & df['data_leilao'].notna() & (df['data_leilao'] != '')).sum()
taxa_datas = (datas_validas / len(df) * 100) if len(df) > 0 else 0

print(f"Taxa atual: {datas_validas}/{len(df)} ({taxa_datas:.1f}%)")

if taxa_datas >= 90:
    print(f"[EXCELENTE] ✓✓✓ META ATINGIDA!")
elif taxa_datas >= 70:
    print(f"[BOM] Melhorou significativamente")
elif taxa_datas >= 50:
    print(f"[REGULAR] Progresso parcial")
elif taxa_datas > 28:
    print(f"[MELHOROU] Era 28%, agora {taxa_datas:.1f}%")
else:
    print(f"[BAIXO] Ainda precisa melhorias")

# Mostrar primeiras 5 datas
print(f"\n[PRIMEIRAS 5 DATAS]")
for i, (data, origem) in enumerate(zip(df['data_leilao'].head(5), df['arquivo_origem'].head(5)), 1):
    cidade = origem.split('\\')[0] if '\\' in origem else origem.split('/')[0]
    status = "✓" if data != 'N/D' else "✗"
    print(f"  {i}. [{status}] {cidade}: {data}")

# Validar link_pncp
print(f"\n{'='*70}")
print("CAMPO CRÍTICO #2: link_pncp")
print("="*70)

def validar_formato(link):
    if not link or link == 'N/D':
        return False
    # /editais/14digitos/4digitos/seq
    match = re.search(r'/editais/(\d{14})/(\d{4})/(\d+)$', str(link))
    return match is not None

links_validos = df['link_pncp'].notna() & (df['link_pncp'] != 'N/D')
links_corretos = df[links_validos]['link_pncp'].apply(validar_formato).sum()
taxa_links = (links_corretos / links_validos.sum() * 100) if links_validos.sum() > 0 else 0

print(f"Taxa atual: {links_corretos}/{links_validos.sum()} ({taxa_links:.1f}%)")

if taxa_links >= 95:
    print(f"[PERFEITO] ✓✓✓ FORMATO CORRETO!")
elif taxa_links >= 70:
    print(f"[BOM] Maioria correta")
elif taxa_links > 0:
    print(f"[PARCIAL] {taxa_links:.1f}% correto")
else:
    print(f"[BAIXO] Ainda no formato antigo")

# Mostrar primeiros 3 links
print(f"\n[PRIMEIROS 3 LINKS]")
for i, link in enumerate(df['link_pncp'].head(3), 1):
    if validar_formato(link):
        match = re.search(r'/editais/(\d{14})/(\d{4})/(\d+)$', str(link))
        if match:
            cnpj, ano, seq = match.groups()
            print(f"  {i}. [✓] /{cnpj}/{ano}/{seq}")
    else:
        print(f"  {i}. [✗] {str(link)[:60]}")

# Resumo
print(f"\n{'='*70}")
if processed >= 198:
    print("STATUS: PROCESSAMENTO COMPLETO!")
    print("Execute: python validar_criticos.py")
else:
    print(f"STATUS: PROCESSANDO... ({processed}/198)")
    print(f"Validação parcial baseada em {len(df)} registros")

print("="*70)
