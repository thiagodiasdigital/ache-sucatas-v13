#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Verifica se linkSistemaOrigem da API PNCP pode ser usado como link_leiloeiro.
"""

import requests
import pandas as pd
import re

def extrair_componentes_do_path(arquivo_origem: str) -> tuple:
    """Extrai CNPJ, ANO, SEQUENCIAL do path."""
    match = re.search(r'_(\d{14})-\d+-(\d+)-(\d{4})', arquivo_origem)
    if match:
        cnpj = match.group(1)
        sequencial = match.group(2).lstrip('0') or '0'
        ano = match.group(3)
        return (cnpj, ano, sequencial)
    return (None, None, None)

def buscar_api_completa(cnpj: str, ano: str, sequencial: str) -> dict:
    """Busca JSON completo da API PNCP."""
    url = f"https://pncp.gov.br/api/consulta/v1/orgaos/{cnpj}/compras/{ano}/{sequencial}"
    try:
        headers = {'User-Agent': 'Mozilla/5.0'}
        response = requests.get(url, headers=headers, timeout=10)
        response.raise_for_status()
        return response.json()
    except:
        return {}

# Ler CSV
df = pd.read_csv('analise_editais_v12.csv', encoding='utf-8-sig')

print("="*80)
print("VERIFICACAO: linkSistemaOrigem como link_leiloeiro")
print("="*80)
print()

# Pegar 20 editais para análise
amostra = df.head(20)

print("Analisando 20 editais...\n")

resultados = []

for i, row in amostra.iterrows():
    arquivo_origem = row['arquivo_origem']
    link_atual = row['link_leiloeiro']

    cnpj, ano, sequencial = extrair_componentes_do_path(arquivo_origem)

    if not cnpj:
        continue

    api_data = buscar_api_completa(cnpj, ano, sequencial)

    if api_data:
        link_sistema = api_data.get('linkSistemaOrigem')

        # Verificar se é um link válido
        if link_sistema and link_sistema.startswith('http'):
            status = "ENCONTRADO"

            # Comparar com link atual
            if link_atual == 'N/D' or link_atual == 'PRESENCIAL':
                comparacao = f"[PODE MELHORAR] {link_atual} -> {link_sistema}"
            elif link_sistema.lower() in link_atual.lower() or link_atual.lower() in link_sistema.lower():
                comparacao = "[SIMILAR]"
            else:
                comparacao = f"[DIFERENTE] CSV:{link_atual[:30]}... vs API:{link_sistema[:30]}..."
        else:
            status = "VAZIO/NULL"
            link_sistema = "N/D"
            comparacao = f"[SEM MELHORIA] {link_atual}"

        resultados.append({
            'arquivo': arquivo_origem[:50],
            'link_csv': link_atual,
            'link_api': link_sistema,
            'status': status,
            'comparacao': comparacao
        })

        print(f"[{i+1}/20] {arquivo_origem[:45]:45s}")
        print(f"        CSV: {link_atual[:60]}")
        print(f"        API: {link_sistema[:60] if link_sistema != 'N/D' else 'N/D'}")
        print(f"        {comparacao}")
        print()

print("="*80)
print("ESTATISTICAS")
print("="*80)
print()

df_result = pd.DataFrame(resultados)

if not df_result.empty:
    total = len(df_result)
    encontrados = (df_result['status'] == 'ENCONTRADO').sum()
    vazios = (df_result['status'] == 'VAZIO/NULL').sum()

    pode_melhorar = df_result['comparacao'].str.contains('PODE MELHORAR').sum()

    print(f"Total analisado: {total}")
    print(f"linkSistemaOrigem ENCONTRADO: {encontrados}/{total} ({(encontrados/total)*100:.1f}%)")
    print(f"linkSistemaOrigem VAZIO/NULL: {vazios}/{total} ({(vazios/total)*100:.1f}%)")
    print()
    print(f"Pode melhorar N/D ou PRESENCIAL: {pode_melhorar} editais")
    print()

    if encontrados >= total * 0.7:
        print("="*80)
        print("[RECOMENDACAO] linkSistemaOrigem esta disponivel em >70% dos editais!")
        print("Pode ser integrado no auditor para melhorar link_leiloeiro")
        print("="*80)
    else:
        print("="*80)
        print("[AVISO] linkSistemaOrigem tem baixa disponibilidade (<70%)")
        print("Nao recomendado para integracao principal")
        print("="*80)

print()
