#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Validação V12 usando CSV - Para quando o Excel estiver aberto
"""

import pandas as pd
from pathlib import Path

csv_file = Path('analise_editais_v12.csv')

if not csv_file.exists():
    print('[ERRO] analise_editais_v12.csv não encontrado!')
    exit(1)

print('='*80)
print('VALIDACAO ACHE SUCATAS DaaS - AUDITOR V12 (via CSV)')
print('='*80)

# Ler dados
df = pd.read_csv(csv_file, encoding='utf-8-sig')

print(f'\n[OK] Arquivo: {csv_file}')
print(f'[OK] Total de registros: {len(df)}')
print(f'[OK] Total de colunas: {len(df.columns)}')

# Verificar se as novas colunas V12 existem
colunas_v12 = ['modalidade_leilao', 'valor_estimado', 'quantidade_itens', 'nome_leiloeiro']
print('\n' + '='*80)
print('VERIFICACAO DE NOVOS CAMPOS V12')
print('='*80)

for col in colunas_v12:
    if col in df.columns:
        preenchidos = ((df[col] != 'N/D') & df[col].notna() & (df[col] != '')).sum()
        taxa = (preenchidos / len(df) * 100) if len(df) > 0 else 0
        status = '[OK]' if preenchidos > 0 else '[VAZIO]'
        print(f'{status} {col}: {preenchidos}/{len(df)} ({taxa:.1f}%) preenchidos')
    else:
        print(f'[ERRO] Coluna {col} NAO EXISTE!')

# Verificar correções de bugs
print('\n' + '='*80)
print('VERIFICACAO DE CORRECOES CRITICAS (BUGS)')
print('='*80)

# BUG #1: Datas não devem estar todas N/D
datas_leilao_ok = ((df['data_leilao'] != 'N/D') & df['data_leilao'].notna()).sum()
datas_atual_ok = ((df['data_atualizacao'] != 'N/D') & df['data_atualizacao'].notna()).sum()
print(f'[BUG #1] data_leilao com cascata: {datas_leilao_ok}/{len(df)} ({datas_leilao_ok/len(df)*100:.1f}%)')
print(f'[BUG #1] data_atualizacao com cascata: {datas_atual_ok}/{len(df)} ({datas_atual_ok/len(df)*100:.1f}%)')

# BUG #2: link_leiloeiro não deve conter emails
links_validos = df['link_leiloeiro'].notna() & (df['link_leiloeiro'] != 'N/D')
emails_invalidos = df[links_validos]['link_leiloeiro'].astype(str).str.contains(
    'hotmail|yahoo|gmail|outlook', case=False, na=False
).sum()
presenciais = (df['link_leiloeiro'] == 'PRESENCIAL').sum()
print(f'[BUG #2] Links com emails invalidos: {emails_invalidos} (deve ser 0)')
print(f'[BUG #2] Leiloes PRESENCIAIS detectados: {presenciais}')

# BUG #3: link_pncp deve estar no formato /CNPJ/ANO/SEQUENCIAL
links_pncp_ok = df['link_pncp'].notna() & (df['link_pncp'] != 'N/D')
formato_correto = df[links_pncp_ok]['link_pncp'].astype(str).str.contains(
    r'/editais/\d{14}/\d{4}/\d+', regex=True, na=False
).sum()
print(f'[BUG #3] link_pncp no formato correto: {formato_correto}/{links_pncp_ok.sum()}')

# BUG #4: tags não devem ser apenas "veiculos_gerais"
tags_validas = df['tags'].notna() & (df['tags'] != 'N/D') & (df['tags'] != '')
tags_inteligentes = df[tags_validas]['tags'].astype(str).apply(
    lambda x: x != 'veiculos_gerais' and x != 'sem_classificacao'
).sum()
tags_com_virgula = df[tags_validas]['tags'].astype(str).str.contains(',', na=False).sum()
print(f'[BUG #4] Tags inteligentes (nao genericas): {tags_inteligentes}/{tags_validas.sum()}')
print(f'[BUG #4] Tags com multiplas categorias: {tags_com_virgula}')

# BUG #5: titulo não deve ser apenas "Edital nº..."
titulos_validos = df['titulo'].notna() & (df['titulo'] != 'N/D') & (df['titulo'] != '')
titulos_genericos = df[titulos_validos]['titulo'].astype(str).str.match(r'^Edital n[ºo°]\s*\d', na=False).sum()
print(f'[BUG #5] Titulos inteligentes (nao genericos): {titulos_validos.sum() - titulos_genericos}/{titulos_validos.sum()}')

# Estatísticas gerais
print('\n' + '='*80)
print('ESTATISTICAS GERAIS DE PREENCHIMENTO')
print('='*80)
print(f'{"[CAMPO]":<30} {"[PREENCHIDOS]":<20} {"[TAXA]":<10}')
print('-'*80)

campos_criticos = [
    'id_interno', 'orgao', 'uf', 'cidade', 'n_pncp', 'n_edital',
    'data_publicacao', 'data_atualizacao', 'data_leilao', 'titulo',
    'descricao', 'tags', 'link_pncp', 'link_leiloeiro', 'objeto_resumido',
    'modalidade_leilao', 'valor_estimado', 'quantidade_itens', 'nome_leiloeiro'
]

for campo in campos_criticos:
    if campo in df.columns:
        total = len(df)
        filled = ((df[campo] != 'N/D') & df[campo].notna() & (df[campo] != '')).sum()
        taxa = (filled / total * 100) if total > 0 else 0

        if taxa >= 80:
            status = '[EXCELENTE]'
        elif taxa >= 50:
            status = '[BOM]     '
        elif taxa >= 20:
            status = '[PARCIAL] '
        else:
            status = '[BAIXO]   '

        print(f'{campo:<30} {filled:3d}/{total:3d} ({taxa:5.1f}%)    {status}')
    else:
        print(f'{campo:<30} [COLUNA NAO EXISTE]')

# Amostras
print('\n' + '='*80)
print('AMOSTRAS DE DADOS (primeiros 3 registros)')
print('='*80)

campos_amostra = ['orgao', 'cidade', 'tags', 'modalidade_leilao', 'link_leiloeiro']
for campo in campos_amostra:
    if campo in df.columns:
        print(f'\n{campo}:')
        for i, val in enumerate(df[campo].head(3), 1):
            val_str = str(val)[:60] + ('...' if len(str(val)) > 60 else '')
            print(f'  {i}. {val_str}')

print('\n' + '='*80)
print('VALIDACAO CONCLUIDA')
print('='*80)
print(f'\nARQUIVO: {csv_file.absolute()}')
print(f'REGISTROS: {len(df)}')
print('\nPARA GERAR EXCEL:')
print('  1. Feche RESULTADO_FINAL.xlsx se estiver aberto')
print('  2. Execute: python regenerar_excel.py')
print('='*80)
