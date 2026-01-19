#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Regenerar Excel - Cria RESULTADO_FINAL.xlsx a partir do CSV V12
"""

import pandas as pd
from pathlib import Path

csv_file = Path('analise_editais_v12.csv')
xlsx_file = Path('RESULTADO_FINAL.xlsx')

if not csv_file.exists():
    print(f"[ERRO] {csv_file} não encontrado!")
    exit(1)

print(f"[INFO] Lendo {csv_file}...")
df = pd.read_csv(csv_file, encoding='utf-8-sig')

print(f"[OK] {len(df)} registros carregados")
print(f"[OK] {len(df.columns)} colunas")

# Ordem correta das colunas
ordem_colunas = [
    'id_interno', 'n_pncp', 'n_edital', 'data_publicacao', 'data_atualizacao',
    'data_leilao', 'titulo', 'descricao', 'objeto_resumido', 'orgao', 'uf',
    'cidade', 'tags', 'link_pncp', 'link_leiloeiro', 'modalidade_leilao',
    'valor_estimado', 'quantidade_itens', 'nome_leiloeiro', 'arquivo_origem'
]

# Reordenar colunas (manter todas, adicionar faltantes no final)
colunas_existentes = [c for c in ordem_colunas if c in df.columns]
colunas_extras = [c for c in df.columns if c not in ordem_colunas]
df_ordenado = df[colunas_existentes + colunas_extras]

print(f"\n[INFO] Salvando {xlsx_file}...")
print(f"[INFO] IMPORTANTE: Feche o arquivo Excel se estiver aberto!")

try:
    df_ordenado.to_excel(xlsx_file, index=False, engine='openpyxl')
    print(f"[OK] Arquivo criado com sucesso!")
    print(f"[OK] Tamanho: {xlsx_file.stat().st_size / 1024:.1f} KB")

    print(f"\n[PROXIMOS PASSOS]")
    print(f"  1. Verificar {xlsx_file}")
    print(f"  2. Executar: python validar_v12.py")

except PermissionError:
    print(f"\n[ERRO] Permissão negada!")
    print(f"[SOLUCAO] Feche o arquivo {xlsx_file} se estiver aberto no Excel")
    print(f"          e execute este script novamente.")
    exit(1)

except Exception as e:
    print(f"\n[ERRO] {type(e).__name__}: {e}")
    exit(1)
