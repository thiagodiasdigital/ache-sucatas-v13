#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Testa a integração da API PNCP no auditor V12.
Processa 5 editais de amostra e verifica se a API está sendo usada.
"""

import sys
from pathlib import Path
import pandas as pd

# Importar funções do auditor
sys.path.insert(0, str(Path(__file__).parent))
import local_auditor_v12_final
from local_auditor_v12_final import processar_edital

# Usar a mesma PASTA_EDITAIS do auditor
PASTA_EDITAIS = local_auditor_v12_final.PASTA_EDITAIS

# Ler CSV para obter editais de teste
df = pd.read_csv('analise_editais_v12.csv', encoding='utf-8-sig')

print("="*80)
print("TESTE DE INTEGRAÇÃO DA API PNCP NO AUDITOR V12")
print("="*80)
print()
print("Testando 5 editais aleatórios para verificar se a API está funcionando...")
print()

# Selecionar 5 editais de teste
amostra = df.sample(n=5, random_state=42)

resultados = []

for idx, row in amostra.iterrows():
    arquivo_origem = row['arquivo_origem']
    data_esperada = row['data_leilao']

    # Construir path do edital
    pasta_edital = PASTA_EDITAIS / arquivo_origem

    print(f"[{len(resultados)+1}/5] Processando: {arquivo_origem}")
    print(f"      Data esperada: {data_esperada}")

    if pasta_edital.exists():
        # Processar edital
        dados = processar_edital(pasta_edital)

        if dados:
            data_extraida = dados.get('data_leilao', 'N/D')
            print(f"      Data extraída: {data_extraida}")

            if data_extraida == data_esperada:
                print(f"      [OK] SUCESSO!")
            elif data_extraida != 'N/D':
                print(f"      [OK] Data diferente, mas valida")
            else:
                print(f"      [FALHA] N/D")

            resultados.append({
                'arquivo': arquivo_origem,
                'esperada': data_esperada,
                'extraida': data_extraida,
                'sucesso': data_extraida != 'N/D'
            })
        else:
            print(f"      [ERRO] ao processar edital")
    else:
        print(f"      [ERRO] Pasta nao encontrada")

    print()

print("="*80)
print("RESUMO DO TESTE")
print("="*80)

df_resultado = pd.DataFrame(resultados)
if not df_resultado.empty:
    sucessos = df_resultado['sucesso'].sum()
    total = len(df_resultado)

    print(f"\nResultados: {sucessos}/{total} editais com data extraída")
    print(f"Taxa de sucesso: {(sucessos/total)*100:.1f}%")

    print("\nDetalhes:")
    for i, r in df_resultado.iterrows():
        status = "[OK]  " if r['sucesso'] else "[FALHA]"
        print(f"  {status} {r['arquivo'][:40]:40s} | {r['extraida']}")
else:
    print("\nNenhum resultado para exibir")

print("\n" + "="*80)
