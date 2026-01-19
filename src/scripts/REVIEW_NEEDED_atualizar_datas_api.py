#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Atualizar data_leilao usando API completa do PNCP
Processa TODOS os editais sem data
"""

import requests
import re
import json
import time
from pathlib import Path
from datetime import datetime
from typing import Optional, Dict
import pandas as pd

def extrair_componentes_do_path(path_str: str) -> Optional[Dict[str, str]]:
    """Extrai CNPJ, ANO, SEQUENCIAL do caminho do edital."""
    match = re.search(r'_(\d{14})-\d+-(\d+)-(\d{4})$', path_str)
    if match:
        cnpj = match.group(1)
        sequencial = match.group(2)
        ano = match.group(3)
        return {
            'cnpj': cnpj,
            'ano': ano,
            'sequencial': sequencial.lstrip('0') or '0'
        }
    return None

def buscar_json_completo_pncp(cnpj: str, ano: str, sequencial: str) -> Optional[Dict]:
    """Busca o JSON COMPLETO da API do PNCP."""
    url = f"https://pncp.gov.br/api/consulta/v1/orgaos/{cnpj}/compras/{ano}/{sequencial}"

    try:
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        }
        response = requests.get(url, headers=headers, timeout=10)
        response.raise_for_status()
        return response.json()
    except Exception as e:
        return None

def extrair_data_abertura_proposta(json_completo: Dict) -> Optional[str]:
    """Extrai dataAberturaProposta e converte para formato BR."""
    data_iso = json_completo.get('dataAberturaProposta')

    if not data_iso:
        return None

    try:
        match = re.match(r'^(\d{4})-(\d{2})-(\d{2})', str(data_iso))
        if match:
            ano, mes, dia = match.groups()
            return f"{dia}/{mes}/{ano}"
    except:
        pass

    return None

def processar_edital_com_api(pasta_edital: Path) -> Optional[str]:
    """Processa um edital e retorna a data_leilao extraída da API."""
    path_str = str(pasta_edital)
    componentes = extrair_componentes_do_path(path_str)

    if not componentes:
        return None

    cnpj = componentes['cnpj']
    ano = componentes['ano']
    sequencial = componentes['sequencial']

    json_completo = buscar_json_completo_pncp(cnpj, ano, sequencial)

    if not json_completo:
        return None

    return extrair_data_abertura_proposta(json_completo)

if __name__ == "__main__":
    print("="*80)
    print("ATUALIZANDO DATAS COM API COMPLETA DO PNCP")
    print("="*80)

    # Ler CSV atual
    df = pd.read_csv('analise_editais_v12.csv', encoding='utf-8-sig')
    print(f"\n[INFO] Total de editais: {len(df)}")

    # Filtrar editais SEM data
    sem_data = df[df['data_leilao'] == 'N/D'].copy()
    total_sem_data = len(sem_data)
    print(f"[INFO] Editais sem data_leilao: {total_sem_data}")

    print(f"\n[INFO] Processando TODOS os {total_sem_data} editais...")
    print("="*80)

    total_sucessos = 0
    total_erros = 0

    for contador, (idx, row) in enumerate(sem_data.iterrows(), 1):
        arquivo_origem = row['arquivo_origem']
        print(f"\n[{contador}/{total_sem_data}] {arquivo_origem}")

        # Construir caminho completo
        pasta_edital = Path("ACHE_SUCATAS_DB") / arquivo_origem

        if not pasta_edital.exists():
            print(f"  [ERRO] Pasta não existe")
            total_erros += 1
            continue

        # Processar
        data_leilao = processar_edital_com_api(pasta_edital)

        if data_leilao:
            df.at[idx, 'data_leilao'] = data_leilao
            total_sucessos += 1
            print(f"  [OK] Data: {data_leilao}")
        else:
            total_erros += 1
            print(f"  [FALHA] Não foi possível extrair data")

        # Pequeno delay para não sobrecarregar a API
        if contador < total_sem_data:
            time.sleep(0.3)

    # Salvar CSV atualizado
    print(f"\n{'='*80}")
    print(f"PROCESSAMENTO CONCLUÍDO!")
    print("="*80)
    print(f"Sucessos: {total_sucessos}/{total_sem_data}")
    print(f"Erros: {total_erros}/{total_sem_data}")

    # Calcular nova taxa
    datas_validas = (df['data_leilao'] != 'N/D').sum()
    taxa_final = (datas_validas / len(df)) * 100

    print(f"\nTaxa ANTERIOR: 56.1% (111/198)")
    print(f"Taxa NOVA: {taxa_final:.1f}% ({datas_validas}/198)")
    print(f"Melhoria: +{total_sucessos} editais com data")

    # Salvar
    df.to_csv('analise_editais_v12.csv', index=False, encoding='utf-8-sig')
    print(f"\n[OK] CSV atualizado: analise_editais_v12.csv")

    if taxa_final >= 90:
        print(f"\n{'='*80}")
        print("✓✓✓ META ATINGIDA! data_leilao ≥ 90%!")
        print("✓✓✓ SISTEMA ACHE SUCATAS 100% OPERACIONAL!")
        print("="*80)
