#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Testa a integração da API PNCP para extrair valor_estimado.
Compara valores ANTES (CSV atual) e DEPOIS (processamento com API).
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
print("TESTE: INTEGRACAO API PNCP PARA valor_estimado")
print("="*80)
print()

# Ler CSV atual
df = pd.read_csv('analise_editais_v12.csv', encoding='utf-8-sig')

# Calcular cobertura ANTES
total = len(df)
com_valor_antes = (df['valor_estimado'] != 'N/D').sum()
cobertura_antes = (com_valor_antes / total) * 100

print(f"COBERTURA ATUAL (CSV):")
print(f"  valor_estimado: {com_valor_antes}/{total} ({cobertura_antes:.1f}%)")
print()

# Selecionar 10 editais de teste
amostra = df.sample(n=10, random_state=42)

print(f"Testando 10 editais aleatorios...\n")

resultados = []

for i, row in amostra.iterrows():
    arquivo_origem = row['arquivo_origem']
    valor_csv = row['valor_estimado']

    pasta_edital = PASTA_EDITAIS / arquivo_origem

    print(f"[{len(resultados)+1}/10] {arquivo_origem[:50]:50s}")
    print(f"         CSV: {valor_csv}")

    if pasta_edital.exists():
        # Processar edital com API integrada
        dados = processar_edital(pasta_edital)

        if dados:
            valor_api = dados.get('valor_estimado', 'N/D')
            print(f"         API: {valor_api}")

            # Classificar resultado
            if valor_api != 'N/D' and valor_csv == 'N/D':
                status = "[MELHORIA] N/D -> valor extraido via API"
                melhorou = True
            elif valor_api != 'N/D' and valor_csv != 'N/D':
                status = "[OK] Valor mantido/atualizado"
                melhorou = False
            elif valor_api == 'N/D' and valor_csv != 'N/D':
                status = "[AVISO] Tinha valor, agora N/D"
                melhorou = False
            else:
                status = "[N/D] Continua sem valor"
                melhorou = False

            print(f"         {status}")

            resultados.append({
                'arquivo': arquivo_origem,
                'valor_csv': valor_csv,
                'valor_api': valor_api,
                'melhorou': melhorou,
                'status': status
            })
        else:
            print(f"         [ERRO] Falha ao processar")
    else:
        print(f"         [ERRO] Pasta nao encontrada")

    print()

print("="*80)
print("RESUMO DO TESTE")
print("="*80)
print()

df_result = pd.DataFrame(resultados)

if not df_result.empty:
    total_teste = len(df_result)
    com_valor_depois = (df_result['valor_api'] != 'N/D').sum()
    melhorias = df_result['melhorou'].sum()

    cobertura_depois = (com_valor_depois / total_teste) * 100

    print(f"Resultados nos 10 editais testados:")
    print(f"  Cobertura ANTES (CSV): {(df_result['valor_csv'] != 'N/D').sum()}/{total_teste} ({((df_result['valor_csv'] != 'N/D').sum()/total_teste)*100:.1f}%)")
    print(f"  Cobertura DEPOIS (API): {com_valor_depois}/{total_teste} ({cobertura_depois:.1f}%)")
    print(f"  Melhorias (N/D -> valor): {melhorias}")
    print()

    # Projeção para toda a base
    if melhorias > 0:
        # Calcular quantos N/D existem no CSV
        nd_total = (df['valor_estimado'] == 'N/D').sum()

        # Taxa de sucesso da API nos testes
        nd_testados = (df_result['valor_csv'] == 'N/D').sum()
        if nd_testados > 0:
            taxa_sucesso = melhorias / nd_testados
            nd_potencialmente_resolvidos = int(nd_total * taxa_sucesso)

            cobertura_projetada = ((com_valor_antes + nd_potencialmente_resolvidos) / total) * 100

            print("="*80)
            print("PROJECAO PARA TODA A BASE (198 editais)")
            print("="*80)
            print(f"\nCobertura atual:    {com_valor_antes}/{total} ({cobertura_antes:.1f}%)")
            print(f"N/D na base:        {nd_total}")
            print(f"Taxa de sucesso API: {taxa_sucesso*100:.1f}%")
            print(f"N/D resolviveis:    ~{nd_potencialmente_resolvidos}")
            print(f"\nCobertura projetada: ~{com_valor_antes + nd_potencialmente_resolvidos}/{total} ({cobertura_projetada:.1f}%)")
            print()

            if cobertura_projetada >= 80:
                print("[RECOMENDACAO] API pode melhorar significativamente a cobertura!")
                print("Sugestao: Reprocessar todos os editais com auditor atualizado")
            elif cobertura_projetada >= 50:
                print("[OK] API melhora moderadamente a cobertura")
            else:
                print("[INFO] API melhora marginalmente a cobertura")

print("\n" + "="*80)
