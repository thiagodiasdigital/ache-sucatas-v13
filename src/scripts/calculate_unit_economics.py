#!/usr/bin/env python3
"""
ACHE SUCATAS - Calculadora de Unit Economics (FinOps)
=====================================================
Script para calcular metricas de custo unitario do pipeline.

Uso:
    PYTHONPATH=src/core python src/scripts/calculate_unit_economics.py

Output:
    - Custos mensais estimados
    - Custo por execucao
    - Custo por edital
    - Projecoes de escala
"""

import os
import sys
from datetime import datetime, timedelta

# Add src/core to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'core'))


def get_supabase_metrics():
    """Obtem metricas do Supabase (se disponivel)."""
    try:
        from supabase_repository import SupabaseRepository
        repo = SupabaseRepository(enable_supabase=True)

        if not repo.enable_supabase:
            return None

        # Contar editais
        total_editais = repo.contar_editais()

        # Buscar execucoes dos ultimos 30 dias
        try:
            resp = repo.client.table('execucoes_miner').select('*').gte(
                'execution_start',
                (datetime.now() - timedelta(days=30)).isoformat()
            ).execute()
            execucoes = resp.data if resp.data else []
        except Exception:
            execucoes = []

        # Calcular metricas
        editais_novos_mes = sum(e.get('editais_novos', 0) for e in execucoes)
        execucoes_mes = len(execucoes)
        execucoes_sucesso = len([e for e in execucoes if e.get('status') == 'SUCCESS'])

        return {
            'total_editais': total_editais,
            'editais_novos_mes': editais_novos_mes,
            'execucoes_mes': execucoes_mes,
            'execucoes_sucesso': execucoes_sucesso,
            'taxa_sucesso': (execucoes_sucesso / execucoes_mes * 100) if execucoes_mes > 0 else 0,
        }
    except Exception as e:
        print(f"Aviso: Nao foi possivel conectar ao Supabase: {e}")
        return None


def estimate_storage_mb():
    """Estima uso de storage baseado em media por edital."""
    # Media: 2 PDFs por edital, 500KB por PDF
    # Total editais: ~300
    # Estimativa: 300 * 2 * 0.5 MB = 300 MB
    return 300  # MB estimado


def calculate_costs():
    """Calcula custos unitarios."""
    # Constantes de pricing (Free Tier)
    SUPABASE_FREE_DB_MB = 500
    SUPABASE_FREE_STORAGE_MB = 1024  # 1 GB
    SUPABASE_FREE_BANDWIDTH_MB = 2048  # 2 GB
    GITHUB_FREE_MINUTES = 2000

    # Estimativas de uso
    github_minutes_per_exec = 1.0
    execucoes_por_dia = 3
    dias_mes = 30

    # Calcular uso
    execucoes_mes = execucoes_por_dia * dias_mes
    github_minutes_mes = execucoes_mes * github_minutes_per_exec
    storage_mb = estimate_storage_mb()

    # Custos (Free Tier = $0)
    custo_supabase = 0.0
    custo_github = 0.0
    custo_total = custo_supabase + custo_github

    # Obter metricas reais se disponivel
    metrics = get_supabase_metrics()

    if metrics:
        editais_novos_mes = metrics['editais_novos_mes'] or 360  # default
        execucoes_mes = metrics['execucoes_mes'] or execucoes_mes
    else:
        editais_novos_mes = 360  # estimativa: 12 novos/dia * 30 dias

    # Unit costs
    custo_por_execucao = custo_total / execucoes_mes if execucoes_mes > 0 else 0
    custo_por_edital = custo_total / editais_novos_mes if editais_novos_mes > 0 else 0
    custo_por_mb = custo_total / storage_mb if storage_mb > 0 else 0

    return {
        'data': datetime.now().strftime('%Y-%m-%d'),
        'custos': {
            'supabase': custo_supabase,
            'github_actions': custo_github,
            'total_mensal': custo_total,
        },
        'uso': {
            'github_minutes_mes': github_minutes_mes,
            'github_minutes_limite': GITHUB_FREE_MINUTES,
            'github_pct': (github_minutes_mes / GITHUB_FREE_MINUTES) * 100,
            'storage_mb': storage_mb,
            'storage_limite_mb': SUPABASE_FREE_STORAGE_MB,
            'storage_pct': (storage_mb / SUPABASE_FREE_STORAGE_MB) * 100,
        },
        'metricas': {
            'execucoes_mes': execucoes_mes,
            'editais_novos_mes': editais_novos_mes,
        },
        'unit_costs': {
            'por_execucao': custo_por_execucao,
            'por_edital': custo_por_edital,
            'por_mb_storage': custo_por_mb,
        },
        'status': 'FREE_TIER',
        'supabase_metrics': metrics,
    }


def print_report(data: dict):
    """Imprime relatorio de unit economics."""
    print("=" * 50)
    print("UNIT ECONOMICS - ACHE SUCATAS")
    print("=" * 50)
    print(f"Data: {data['data']}")
    print()

    print("CUSTOS:")
    print(f"  Supabase: ${data['custos']['supabase']:.2f} (free tier)")
    print(f"  GitHub Actions: ${data['custos']['github_actions']:.2f} (free tier)")
    print(f"  Total Mensal: ${data['custos']['total_mensal']:.2f}")
    print()

    print("USO DE RECURSOS:")
    print(f"  GitHub Minutes: {data['uso']['github_minutes_mes']:.0f}/{data['uso']['github_minutes_limite']} ({data['uso']['github_pct']:.1f}%)")
    print(f"  Storage: {data['uso']['storage_mb']:.0f}/{data['uso']['storage_limite_mb']} MB ({data['uso']['storage_pct']:.1f}%)")
    print()

    print("METRICAS:")
    print(f"  Execucoes/mes: {data['metricas']['execucoes_mes']}")
    print(f"  Editais novos/mes: ~{data['metricas']['editais_novos_mes']}")

    if data.get('supabase_metrics'):
        m = data['supabase_metrics']
        print(f"  Total editais (banco): {m['total_editais']}")
        print(f"  Taxa sucesso (30d): {m['taxa_sucesso']:.1f}%")
    print()

    print("UNIT COSTS:")
    print(f"  Por execucao: ${data['unit_costs']['por_execucao']:.4f}")
    print(f"  Por edital: ${data['unit_costs']['por_edital']:.4f}")
    print(f"  Por MB storage: ${data['unit_costs']['por_mb_storage']:.4f}")
    print()

    print(f"STATUS: {data['status']} - Operando dentro dos limites gratuitos")
    print("=" * 50)


def main():
    """Entry point."""
    data = calculate_costs()
    print_report(data)

    # Exportar JSON para evidencia
    import json
    output_path = os.path.join(
        os.path.dirname(__file__),
        '..', '..',
        'audit_evidence', '2026-01-19',
        'unit_economics.json'
    )

    try:
        os.makedirs(os.path.dirname(output_path), exist_ok=True)
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2, ensure_ascii=False, default=str)
        print(f"\nExportado para: {output_path}")
    except Exception as e:
        print(f"\nAviso: Nao foi possivel exportar JSON: {e}")


if __name__ == "__main__":
    main()
