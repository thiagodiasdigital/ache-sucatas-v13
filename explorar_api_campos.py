#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Explora a API PNCP para identificar campos disponíveis para:
- valor_estimado
- quantidade_itens
- nome_leiloeiro (se houver)
"""

import requests
import pandas as pd
import json
from pathlib import Path

def extrair_componentes_do_path(arquivo_origem: str) -> tuple:
    """Extrai CNPJ, ANO, SEQUENCIAL do path."""
    import re
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
print("EXPLORACAO DA API PNCP - CAMPOS SECUNDARIOS")
print("="*80)
print()

# Pegar 10 editais para análise
amostra = df.head(10)

print("Analisando 10 editais para identificar campos disponíveis...\n")

campos_encontrados = {
    'valorTotalEstimado': 0,
    'valorTotalHomologado': 0,
    'itens': 0,
    'itens_com_valor': 0,
    'itens_com_quantidade': 0,
    'leiloeiro': 0,
    'nomeResponsavel': 0,
    'informacaoComplementar': 0
}

exemplos = []

for i, row in amostra.iterrows():
    arquivo_origem = row['arquivo_origem']
    cnpj, ano, sequencial = extrair_componentes_do_path(arquivo_origem)

    if not cnpj:
        continue

    print(f"[{i+1}/10] Consultando API: {arquivo_origem[:50]}...")

    api_data = buscar_api_completa(cnpj, ano, sequencial)

    if api_data:
        # Verificar campos de valor
        if 'valorTotalEstimado' in api_data and api_data['valorTotalEstimado']:
            campos_encontrados['valorTotalEstimado'] += 1

        if 'valorTotalHomologado' in api_data and api_data['valorTotalHomologado']:
            campos_encontrados['valorTotalHomologado'] += 1

        # Verificar itens
        if 'itens' in api_data and api_data['itens']:
            campos_encontrados['itens'] += 1
            itens = api_data['itens']

            # Verificar se itens têm valor e quantidade
            for item in itens:
                if 'valorUnitarioEstimado' in item or 'valorTotalEstimado' in item:
                    campos_encontrados['itens_com_valor'] += 1
                    break

            for item in itens:
                if 'quantidade' in item:
                    campos_encontrados['itens_com_quantidade'] += 1
                    break

        # Verificar campos relacionados a leiloeiro/responsável
        if 'nomeResponsavel' in api_data and api_data['nomeResponsavel']:
            campos_encontrados['nomeResponsavel'] += 1

        if 'informacaoComplementar' in api_data and api_data['informacaoComplementar']:
            campos_encontrados['informacaoComplementar'] += 1

        # Guardar exemplo para análise
        if len(exemplos) < 2:
            exemplos.append({
                'arquivo': arquivo_origem,
                'dados': api_data
            })

        print(f"    [OK] API respondeu ({len(api_data)} campos)")
    else:
        print(f"    [FALHA] API nao respondeu")

    print()

print("="*80)
print("RESUMO DOS CAMPOS ENCONTRADOS")
print("="*80)
print()

print("CAMPOS DE VALOR:")
print(f"  valorTotalEstimado:    {campos_encontrados['valorTotalEstimado']}/10 editais")
print(f"  valorTotalHomologado:  {campos_encontrados['valorTotalHomologado']}/10 editais")
print()

print("CAMPOS DE ITENS:")
print(f"  itens[]:                     {campos_encontrados['itens']}/10 editais")
print(f"  itens[] com valorEstimado:   {campos_encontrados['itens_com_valor']}/10 editais")
print(f"  itens[] com quantidade:      {campos_encontrados['itens_com_quantidade']}/10 editais")
print()

print("CAMPOS DE RESPONSAVEL/LEILOEIRO:")
print(f"  nomeResponsavel:             {campos_encontrados['nomeResponsavel']}/10 editais")
print(f"  informacaoComplementar:      {campos_encontrados['informacaoComplementar']}/10 editais")
print()

# Mostrar estrutura de 2 exemplos
print("="*80)
print("EXEMPLOS DE ESTRUTURA DA API")
print("="*80)

for idx, exemplo in enumerate(exemplos, 1):
    print(f"\nEXEMPLO {idx}: {exemplo['arquivo'][:60]}")
    print("-"*80)

    dados = exemplo['dados']

    # Mostrar campos principais
    print("\nCampos principais:")
    campos_importantes = [
        'numeroEdital', 'modalidadeNome', 'dataAberturaProposta',
        'valorTotalEstimado', 'valorTotalHomologado',
        'nomeResponsavel', 'informacaoComplementar'
    ]

    for campo in campos_importantes:
        if campo in dados:
            valor = dados[campo]
            if isinstance(valor, str) and len(valor) > 60:
                valor = valor[:60] + "..."
            print(f"  {campo}: {valor}")

    # Mostrar estrutura de itens
    if 'itens' in dados and dados['itens']:
        print(f"\nItens ({len(dados['itens'])} encontrados):")
        primeiro_item = dados['itens'][0]
        print("  Estrutura do primeiro item:")
        for key in list(primeiro_item.keys())[:10]:
            valor = primeiro_item[key]
            if isinstance(valor, str) and len(valor) > 40:
                valor = valor[:40] + "..."
            print(f"    {key}: {valor}")

    print()

print("="*80)
print("CONCLUSOES E RECOMENDACOES")
print("="*80)
print()

# Análise automática
if campos_encontrados['valorTotalEstimado'] >= 7:
    print("[OK] valorTotalEstimado: Disponivel na maioria dos editais!")
    print("     RECOMENDACAO: Integrar no auditor para melhorar valor_estimado")
    print()

if campos_encontrados['itens'] >= 7:
    print("[OK] itens[]: Disponivel na maioria dos editais!")
    print("     RECOMENDACAO: Usar len(itens) para melhorar quantidade_itens")
    print()

if campos_encontrados['itens_com_quantidade'] >= 7:
    print("[OK] itens[].quantidade: Disponivel na maioria dos editais!")
    print("     RECOMENDACAO: Somar quantidade dos itens")
    print()

if campos_encontrados['nomeResponsavel'] < 3:
    print("[AVISO] nomeResponsavel: Pouco disponivel")
    print("        Nome do leiloeiro provavelmente NAO esta na API")
    print("        Manter extracao via PDF/descrição")
    print()

print("="*80)

# Salvar um exemplo completo em JSON
if exemplos:
    with open('exemplo_api_completa.json', 'w', encoding='utf-8') as f:
        json.dump(exemplos[0]['dados'], f, indent=2, ensure_ascii=False)
    print("\nExemplo completo salvo em: exemplo_api_completa.json")
    print("="*80)
