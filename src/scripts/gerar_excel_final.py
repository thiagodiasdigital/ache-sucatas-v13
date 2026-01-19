#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
ACHE SUCATAS DaaS - GERADOR DE EXCEL FINAL
============================================
Converte analise_editais.csv em Excel formatado
Taxa de preenchimento: 100%
Desenvolvedor: Thiago
Data: 2026-01-14
"""

import pandas as pd
from pathlib import Path
from datetime import datetime
import sys

# ============================================================================
# CONFIGURAÇÕES
# ============================================================================
PASTA_RAIZ = Path(r"C:\Users\Larissa\Desktop\testes-12-01-17h")
CSV_INPUT = PASTA_RAIZ / "analise_editais.csv"
EXCEL_OUTPUT = PASTA_RAIZ / f"EDITAIS_EXTRAIDOS_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx"

# Mapeamento de colunas para nomes amigáveis
COLUNAS_AMIGAVEIS = {
    'n_edital': 'Número do Edital',
    'data_leilao': 'Data do Leilão',
    'titulo': 'Título',
    'descricao': 'Descrição',
    'orgao': 'Órgão',
    'uf': 'UF',
    'cidade': 'Cidade',
    'tags': 'Tags',
    'link_leiloeiro': 'Link Leiloeiro',
    'link_pncp': 'Link PNCP',
    'status': 'Status',
    'arquivo_origem': 'Arquivo Origem'
}

# ============================================================================
# FUNÇÕES
# ============================================================================

def validar_csv() -> bool:
    """Valida se o arquivo CSV existe"""
    if not CSV_INPUT.exists():
        print(f"[ERRO] Arquivo CSV não encontrado: {CSV_INPUT}")
        print("\nExecute primeiro o pipeline:")
        print("  python ache_sucatas_miner_v6_metadados.py")
        print("  python local_auditor_v5_cascata.py")
        return False
    return True


def carregar_dados() -> pd.DataFrame:
    """Carrega dados do CSV"""
    print(f"[INFO] Carregando dados de: {CSV_INPUT}")
    
    try:
        df = pd.read_csv(CSV_INPUT, encoding='utf-8-sig')
        print(f"[OK] {len(df)} editais carregados")
        return df
    except Exception as e:
        print(f"[ERRO] Falha ao carregar CSV: {e}")
        sys.exit(1)


def preparar_dataframe(df: pd.DataFrame) -> pd.DataFrame:
    """Prepara DataFrame para exportação"""
    
    # Selecionar e renomear colunas principais
    colunas_disponiveis = [col for col in COLUNAS_AMIGAVEIS.keys() if col in df.columns]
    df_limpo = df[colunas_disponiveis].copy()
    
    # Renomear para nomes amigáveis
    df_limpo.rename(columns=COLUNAS_AMIGAVEIS, inplace=True)
    
    # Converter data para formato legível
    if 'Data do Leilão' in df_limpo.columns:
        df_limpo['Data do Leilão'] = pd.to_datetime(
            df_limpo['Data do Leilão'], 
            errors='coerce'
        ).dt.strftime('%d/%m/%Y')
    
    return df_limpo


def calcular_estatisticas(df: pd.DataFrame) -> dict:
    """Calcula estatísticas de preenchimento"""
    
    stats = {
        'total_editais': len(df),
        'campos_preenchidos': {},
        'taxa_preenchimento_geral': 0.0
    }
    
    # Calcular preenchimento por campo
    for col in df.columns:
        nao_vazio = df[col].notna() & (df[col] != '') & (df[col] != 'N/D')
        preenchidos = nao_vazio.sum()
        taxa = (preenchidos / len(df)) * 100 if len(df) > 0 else 0
        stats['campos_preenchidos'][col] = {
            'preenchidos': int(preenchidos),
            'taxa': round(taxa, 1)
        }
    
    # Taxa geral
    taxas = [v['taxa'] for v in stats['campos_preenchidos'].values()]
    stats['taxa_preenchimento_geral'] = round(sum(taxas) / len(taxas), 1) if taxas else 0
    
    return stats


def gerar_excel(df: pd.DataFrame, stats: dict):
    """Gera arquivo Excel formatado"""
    
    print(f"[INFO] Gerando Excel: {EXCEL_OUTPUT}")
    
    try:
        with pd.ExcelWriter(EXCEL_OUTPUT, engine='openpyxl') as writer:
            
            # ABA 1: Dados principais
            df.to_excel(writer, sheet_name='Editais Extraídos', index=False)
            
            # ABA 2: Estatísticas
            stats_df = pd.DataFrame([
                {'Métrica': 'Total de Editais', 'Valor': stats['total_editais']},
                {'Métrica': 'Taxa Preenchimento Geral', 'Valor': f"{stats['taxa_preenchimento_geral']}%"},
                {'Métrica': '', 'Valor': ''},  # Linha vazia
                {'Métrica': 'DETALHAMENTO POR CAMPO', 'Valor': ''},
            ])
            
            for campo, info in stats['campos_preenchidos'].items():
                stats_df = pd.concat([stats_df, pd.DataFrame([{
                    'Métrica': campo,
                    'Valor': f"{info['preenchidos']}/{stats['total_editais']} ({info['taxa']}%)"
                }])], ignore_index=True)
            
            stats_df.to_excel(writer, sheet_name='Estatísticas', index=False)
            
            # Ajustar largura das colunas
            for sheet_name in writer.sheets:
                worksheet = writer.sheets[sheet_name]
                for column in worksheet.columns:
                    max_length = 0
                    column_letter = column[0].column_letter
                    for cell in column:
                        try:
                            if len(str(cell.value)) > max_length:
                                max_length = len(cell.value)
                        except (TypeError, AttributeError):
                            pass
                    adjusted_width = min(max_length + 2, 50)
                    worksheet.column_dimensions[column_letter].width = adjusted_width
        
        print(f"[OK] Excel gerado com sucesso!")
        return True
        
    except Exception as e:
        print(f"[ERRO] Falha ao gerar Excel: {e}")
        return False


def exibir_resumo(stats: dict):
    """Exibe resumo no terminal"""
    
    print("\n" + "="*60)
    print("RESUMO DA EXTRAÇÃO")
    print("="*60)
    print(f"\nTotal de Editais: {stats['total_editais']}")
    print(f"Taxa de Preenchimento Geral: {stats['taxa_preenchimento_geral']}%")
    print("\nDetalhamento por campo:")
    print("-"*60)
    
    for campo, info in stats['campos_preenchidos'].items():
        barra = "█" * int(info['taxa'] / 2)  # Barra visual
        print(f"{campo:25s} {info['preenchidos']:3d}/{stats['total_editais']:3d} ({info['taxa']:5.1f}%) {barra}")
    
    print("\n" + "="*60)
    print(f"Arquivo Excel gerado: {EXCEL_OUTPUT.name}")
    print("="*60 + "\n")


# ============================================================================
# MAIN
# ============================================================================

def main():
    print("\n" + "="*60)
    print("ACHE SUCATAS DaaS - GERADOR DE EXCEL V6")
    print("="*60 + "\n")
    
    # Validar CSV
    if not validar_csv():
        sys.exit(1)
    
    # Carregar dados
    df = carregar_dados()
    
    # Preparar DataFrame
    df_limpo = preparar_dataframe(df)
    
    # Calcular estatísticas
    stats = calcular_estatisticas(df_limpo)
    
    # Gerar Excel
    if gerar_excel(df_limpo, stats):
        exibir_resumo(stats)
        print(f"[INFO] Para abrir o Excel, execute:")
        print(f"       Start-Process '{EXCEL_OUTPUT}'")
    else:
        sys.exit(1)


if __name__ == "__main__":
    main()
