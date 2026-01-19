#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Script de validação V12 - Verifica se todas as correções foram aplicadas
"""

import pandas as pd
from pathlib import Path

print('='*80)
print('VALIDAÇÃO ACHE SUCATAS DaaS - AUDITOR V12')
print('='*80)

# Verificar arquivos de saída
csv_file = Path('analise_editais_v12.csv')
xlsx_file = Path('RESULTADO_FINAL.xlsx')

if not xlsx_file.exists():
    print('\n[ERRO] RESULTADO_FINAL.xlsx não encontrado!')
    print('O processamento pode não ter sido concluído.')
    exit(1)

print(f'\n[OK] Arquivo encontrado: {xlsx_file}')

# Ler dados
df = pd.read_excel(xlsx_file)

print(f'[OK] Total de registros: {len(df)}')
print(f'[OK] Total de colunas: {len(df.columns)}')

# Verificar se as novas colunas V12 existem
colunas_v12 = ['modalidade_leilao', 'valor_estimado', 'quantidade_itens', 'nome_leiloeiro']
print('\n' + '='*80)
print('VERIFICAÇÃO DE NOVOS CAMPOS V12')
print('='*80)

for col in colunas_v12:
    if col in df.columns:
        preenchidos = ((df[col] != 'N/D') & df[col].notna() & (df[col] != '')).sum()
        taxa = (preenchidos / len(df) * 100) if len(df) > 0 else 0
        status = '[OK]' if preenchidos > 0 else '[VAZIO]'
        print(f'{status} {col}: {preenchidos}/{len(df)} ({taxa:.1f}%) preenchidos')
    else:
        print(f'[ERRO] Coluna {col} NÃO EXISTE!')

# Verificar correções de bugs
print('\n' + '='*80)
print('VERIFICAÇÃO DE CORREÇÕES CRÍTICAS (BUGS)')
print('='*80)

# BUG #1: Datas não devem estar todas N/D
datas_leilao_ok = ((df['data_leilao'] != 'N/D') & df['data_leilao'].notna()).sum()
datas_atual_ok = ((df['data_atualizacao'] != 'N/D') & df['data_atualizacao'].notna()).sum()
print(f'[BUG #1] data_leilao com cascata: {datas_leilao_ok}/{len(df)} ({datas_leilao_ok/len(df)*100:.1f}%)')
print(f'[BUG #1] data_atualizacao com cascata: {datas_atual_ok}/{len(df)} ({datas_atual_ok/len(df)*100:.1f}%)')

# BUG #2: link_leiloeiro não deve conter emails
links_validos = df['link_leiloeiro'].notna() & (df['link_leiloeiro'] != 'N/D')
emails_invalidos = df[links_validos]['link_leiloeiro'].str.contains(
    'hotmail|yahoo|gmail|outlook', case=False, na=False
).sum()
presenciais = (df['link_leiloeiro'] == 'PRESENCIAL').sum()
print(f'[BUG #2] Links com emails inválidos: {emails_invalidos} (deve ser 0)')
print(f'[BUG #2] Leilões PRESENCIAIS detectados: {presenciais}')

# BUG #3: link_pncp deve estar no formato /CNPJ/ANO/SEQUENCIAL
links_pncp_ok = df['link_pncp'].notna() & (df['link_pncp'] != 'N/D')
formato_correto = df[links_pncp_ok]['link_pncp'].str.contains(
    r'/editais/\d{14}/\d{4}/\d+', regex=True, na=False
).sum()
print(f'[BUG #3] link_pncp no formato correto: {formato_correto}/{links_pncp_ok.sum()}')

# BUG #4: tags não devem ser apenas "veiculos_gerais"
tags_inteligentes = df['tags'].notna() & (df['tags'] != 'N/D') & (df['tags'] != 'veiculos_gerais')
tags_com_virgula = df[tags_inteligentes]['tags'].str.contains(',', na=False).sum()
print(f'[BUG #4] Tags inteligentes (não genéricas): {tags_inteligentes.sum()}/{len(df)}')
print(f'[BUG #4] Tags com múltiplas categorias: {tags_com_virgula}')

# BUG #5: titulo não deve ser apenas "Edital nº..."
titulos_inteligentes = df['titulo'].notna() & (df['titulo'] != 'N/D')
titulos_genericos = df[titulos_inteligentes]['titulo'].str.match(r'^Edital n[ºo°]\s*\d', na=False).sum()
print(f'[BUG #5] Títulos inteligentes (não genéricos): {titulos_inteligentes.sum() - titulos_genericos}/{titulos_inteligentes.sum()}')

# Estatísticas gerais
print('\n' + '='*80)
print('ESTATÍSTICAS GERAIS DE PREENCHIMENTO')
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
        print(f'{campo:<30} [COLUNA NÃO EXISTE]')

# Amostras
print('\n' + '='*80)
print('AMOSTRAS DE DADOS (primeiros 3 registros)')
print('='*80)

campos_amostra = ['orgao', 'cidade', 'titulo', 'tags', 'modalidade_leilao', 'link_leiloeiro']
print(df[campos_amostra].head(3).to_string(index=False))

print('\n' + '='*80)
print('VALIDAÇÃO CONCLUÍDA')
print('='*80)
print(f'\nARQUIVO: {xlsx_file.absolute()}')
print(f'REGISTROS: {len(df)}')
print(f'DATA DE PROCESSAMENTO: {pd.Timestamp.now().strftime("%d/%m/%Y %H:%M:%S")}')
print('='*80)
