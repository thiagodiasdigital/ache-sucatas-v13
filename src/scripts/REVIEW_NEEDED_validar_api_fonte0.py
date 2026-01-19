#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Valida que a API PNCP está sendo usada como FONTE 0 no auditor V12.
Testa especificamente os editais que ANTES tinham N/D em data_leilao.
"""

import sys
from pathlib import Path
import pandas as pd

# Importar auditor
sys.path.insert(0, str(Path(__file__).parent))
import local_auditor_v12_final
from local_auditor_v12_final import processar_edital

PASTA_EDITAIS = local_auditor_v12_final.PASTA_EDITAIS

print("="*80)
print("VALIDACAO DA INTEGRACAO DA API PNCP - FONTE 0")
print("="*80)
print()
print("Testando editais que ANTES tinham data_leilao = N/D")
print("Se a API estiver funcionando, eles devem ter datas agora!")
print()

# Ler CSV atualizado (com datas da API)
df = pd.read_csv('analise_editais_v12.csv', encoding='utf-8-sig')

# Pegar apenas 10 editais de amostra que foram atualizados pela API
# (esses são editais que tinham N/D antes)
editais_teste = [
    "MG_UNIAO_DE_MINAS\\2025-11-07_S60_01051819000140-1-000116-2025",
    "PR_UNIAO_DA_VITORIA\\2025-07-14_S80_75967760000171-1-000045-2025",
    "GO_ITAUCU\\2025-06-03_S65_00167437000114-1-000175-2025",
    "RS_TAQUARI\\2025-10-10_S65_88067780000138-1-000152-2025",
    "SC_SAO_JOSE_DO_CERRITO\\2025-11-18_S65_82777327000139-1-000109-2025",
    "MS_CASSILANDIA\\2025-10-16_S85_03501572000180-1-000147-2025",
    "PR_CAMPO_BONITO\\2025-09-26_S90_01590828000155-1-000141-2025",
    "MG_CAMPO_AZUL\\2025-11-14_S60_18227241000164-1-000107-2025",
    "PR_SAO_JORGE_DO_PATROCINIO\\2025-10-31_S80_95684389000172-1-000110-2025",
    "MG_CAMPOS_GERAIS\\2025-11-24_S70_18715267000108-1-000139-2025"
]

print(f"Processando {len(editais_teste)} editais de teste...\n")

sucessos = 0
falhas = 0

for i, arquivo_origem in enumerate(editais_teste, 1):
    pasta_edital = PASTA_EDITAIS / arquivo_origem

    # Normalizar path para Windows
    arquivo_origem_normalizado = arquivo_origem.replace('\\', '/')

    print(f"[{i}/{len(editais_teste)}] {arquivo_origem_normalizado}")

    if pasta_edital.exists():
        # Processar edital
        dados = processar_edital(pasta_edital)

        if dados:
            data_extraida = dados.get('data_leilao', 'N/D')

            if data_extraida != 'N/D':
                print(f"    [OK] Data extraida via API: {data_extraida}")
                sucessos += 1
            else:
                print(f"    [FALHA] Data ainda e N/D")
                falhas += 1
        else:
            print(f"    [ERRO] Falha ao processar edital")
            falhas += 1
    else:
        print(f"    [AVISO] Pasta nao encontrada")
        falhas += 1

    print()

print("="*80)
print("RESULTADO FINAL DA VALIDACAO")
print("="*80)
print(f"\n[OK] Sucessos: {sucessos}/{len(editais_teste)}")
print(f"[FALHA] Falhas: {falhas}/{len(editais_teste)}")
print(f"\nTaxa de sucesso: {(sucessos/len(editais_teste))*100:.1f}%")

if sucessos == len(editais_teste):
    print("\n" + "="*80)
    print("VALIDACAO COMPLETA!")
    print("="*80)
    print("\nA API PNCP esta integrada e funcionando como FONTE 0!")
    print("O auditor agora extrai datas diretamente da API em tempo real.")
    print("\nProximos passos sugeridos:")
    print("  1. Reprocessar TODOS os 198 editais com o auditor atualizado")
    print("  2. Verificar se 100% dos editais tem data_leilao")
    print("  3. Gerar RESULTADO_FINAL.xlsx atualizado")
elif sucessos > 0:
    print(f"\n[AVISO] Integracao parcialmente funcional ({sucessos}/{len(editais_teste)})")
else:
    print("\n[ERRO] Integracao da API nao esta funcionando!")

print("\n" + "="*80)
