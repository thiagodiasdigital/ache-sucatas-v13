#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Buscar data_leilao da API completa do PNCP
Usa o relatório técnico para extrair dataAberturaProposta
"""

import requests
import re
import json
from pathlib import Path
from datetime import datetime
from typing import Optional, Dict

def extrair_componentes_do_path(path_str: str) -> Optional[Dict[str, str]]:
    """
    Extrai CNPJ, ANO, SEQUENCIAL do caminho do edital.
    Exemplo: "AM_MANAUS/2025-11-21_S60_04312641000132-1-000097-2025"
    """
    # Padrão: _{CNPJ}-{CODIGO}-{SEQUENCIAL}-{ANO}
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
    """
    Busca o JSON COMPLETO da API do PNCP.
    Endpoint: https://pncp.gov.br/api/consulta/v1/orgaos/{cnpj}/compras/{ano}/{sequencial}
    """
    url = f"https://pncp.gov.br/api/consulta/v1/orgaos/{cnpj}/compras/{ano}/{sequencial}"

    try:
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        }
        response = requests.get(url, headers=headers, timeout=10)
        response.raise_for_status()
        return response.json()
    except Exception as e:
        print(f"  [AVISO] Erro ao buscar API PNCP: {e}")
        return None

def extrair_data_abertura_proposta(json_completo: Dict) -> Optional[str]:
    """
    Extrai dataAberturaProposta do JSON completo e converte para formato BR.
    Formato da API: "2026-01-15T08:00:00" (ISO 8601)
    Formato retornado: "15/01/2026"
    """
    data_iso = json_completo.get('dataAberturaProposta')

    if not data_iso:
        return None

    # Converter ISO 8601 para DD/MM/YYYY
    try:
        match = re.match(r'^(\d{4})-(\d{2})-(\d{2})', str(data_iso))
        if match:
            ano, mes, dia = match.groups()
            return f"{dia}/{mes}/{ano}"
    except:
        pass

    return None

def processar_edital_com_api(pasta_edital: Path) -> Optional[str]:
    """
    Processa um edital e retorna a data_leilao extraída da API completa do PNCP.
    """
    # Extrair componentes do caminho
    path_str = str(pasta_edital)
    componentes = extrair_componentes_do_path(path_str)

    if not componentes:
        print(f"  [ERRO] Não foi possível extrair CNPJ/ANO/SEQUENCIAL de: {path_str}")
        return None

    cnpj = componentes['cnpj']
    ano = componentes['ano']
    sequencial = componentes['sequencial']

    print(f"  [API] Buscando {cnpj}/{ano}/{sequencial}...")

    # Buscar JSON completo da API
    json_completo = buscar_json_completo_pncp(cnpj, ano, sequencial)

    if not json_completo:
        return None

    # Extrair dataAberturaProposta
    data_leilao = extrair_data_abertura_proposta(json_completo)

    if data_leilao:
        print(f"  [OK] Data encontrada: {data_leilao}")
    else:
        print(f"  [AVISO] Campo dataAberturaProposta não encontrado no JSON")

    return data_leilao

if __name__ == "__main__":
    import pandas as pd

    print("="*80)
    print("BUSCANDO DATAS DA API COMPLETA DO PNCP")
    print("="*80)

    # Ler CSV atual
    df = pd.read_csv('analise_editais_v12.csv', encoding='utf-8-sig')
    print(f"\\n[INFO] Total de editais: {len(df)}")

    # Filtrar editais SEM data
    sem_data = df[df['data_leilao'] == 'N/D'].copy()
    print(f"[INFO] Editais sem data_leilao: {len(sem_data)}")

    # Testar nos primeiros 10
    print(f"\\n[INFO] Testando nos primeiros 10 editais sem data...")
    print("="*80)

    sucessos = 0
    for idx, row in sem_data.head(10).iterrows():
        arquivo_origem = row['arquivo_origem']
        print(f"\\n[{idx+1}] {arquivo_origem}")

        # Construir caminho completo
        pasta_edital = Path("ACHE_SUCATAS_DB") / arquivo_origem

        if not pasta_edital.exists():
            print(f"  [ERRO] Pasta não existe: {pasta_edital}")
            continue

        # Processar
        data_leilao = processar_edital_com_api(pasta_edital)

        if data_leilao:
            sucessos += 1
            # Atualizar DataFrame
            df.at[idx, 'data_leilao'] = data_leilao

    print(f"\\n{'='*80}")
    print(f"RESULTADO DO TESTE: {sucessos}/10 editais com data extraída da API!")
    print("="*80)

    if sucessos > 0:
        print(f"\\n[INFO] A API funciona! Agora vamos processar TODOS os {len(sem_data)} editais sem data...")

        resposta = input("\\nContinuar com todos? (s/n): ")

        if resposta.lower() == 's':
            total_sucessos = 0

            for idx, row in sem_data.iterrows():
                arquivo_origem = row['arquivo_origem']
                pasta_edital = Path("ACHE_SUCATAS_DB") / arquivo_origem

                if pasta_edital.exists():
                    data_leilao = processar_edital_com_api(pasta_edital)
                    if data_leilao:
                        df.at[idx, 'data_leilao'] = data_leilao
                        total_sucessos += 1

            # Salvar CSV atualizado
            df.to_csv('analise_editais_v12.csv', index=False, encoding='utf-8-sig')
            print(f"\\n[OK] CSV atualizado com {total_sucessos} novas datas!")
            print(f"[OK] Taxa final: {((len(df) - len(sem_data) + total_sucessos) / len(df) * 100):.1f}%")
