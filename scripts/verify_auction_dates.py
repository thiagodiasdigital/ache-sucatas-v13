"""
Script para verificar as datas dos leilões de MG
Hipótese: Todos os leilões estão no passado, por isso o mapa mostra "sem dados"
"""

import os
import psycopg2
from datetime import datetime

SUPABASE_PROJECT = os.getenv("SUPABASE_PROJECT", "")
SUPABASE_DB_PASSWORD = os.getenv("SUPABASE_DB_PASSWORD", "")

if not SUPABASE_DB_PASSWORD:
    raise ValueError("SUPABASE_DB_PASSWORD nao configurada no .env")

DATABASE_URL = f"postgresql://postgres:{SUPABASE_DB_PASSWORD}@db.{SUPABASE_PROJECT}.supabase.co:5432/postgres"

def main():
    print("=" * 60)
    print("VERIFICAÇÃO DE DATAS DOS LEILÕES")
    print("=" * 60)
    print(f"Data atual: {datetime.now().strftime('%Y-%m-%d')}")

    try:
        conn = psycopg2.connect(DATABASE_URL)
        cursor = conn.cursor()

        # Verificar datas dos leilões de MG
        cursor.execute("""
            SELECT
                cidade,
                data_leilao,
                latitude,
                longitude,
                CASE WHEN data_leilao >= CURRENT_DATE THEN 'FUTURO' ELSE 'PASSADO' END as status
            FROM pub.v_auction_discovery
            WHERE uf = 'MG'
            ORDER BY data_leilao DESC
            LIMIT 20
        """)

        rows = cursor.fetchall()
        print(f"\nLeilões de MG (últimos 20):")
        print("-" * 80)
        for row in rows:
            cidade, data_leilao, lat, lng, status = row
            print(f"  {cidade}: {data_leilao} - {status} | lat={lat}, lng={lng}")

        # Contar futuros vs passados
        cursor.execute("""
            SELECT
                CASE WHEN data_leilao >= CURRENT_DATE THEN 'FUTURO' ELSE 'PASSADO' END as status,
                COUNT(*) as total
            FROM pub.v_auction_discovery
            WHERE uf = 'MG'
            GROUP BY status
        """)

        counts = cursor.fetchall()
        print(f"\n{'='*60}")
        print("RESUMO MG:")
        for status, total in counts:
            print(f"  {status}: {total} leilões")

        # Verificar o que a função retorna com filtro 'futuros'
        cursor.execute("""
            SELECT
                (public.fetch_auctions_paginated(
                    'MG', NULL, NULL, NULL, NULL, NULL, NULL, NULL,
                    1, 20, 'proximos', 'futuros'
                )::json->>'total')::int as total_futuros_mg
        """)

        result = cursor.fetchone()
        print(f"\nResultado da função fetch_auctions_paginated(MG, futuros): {result[0]} leilões")

        # Verificar com 'todos'
        cursor.execute("""
            SELECT
                (public.fetch_auctions_paginated(
                    'MG', NULL, NULL, NULL, NULL, NULL, NULL, NULL,
                    1, 20, 'proximos', 'todos'
                )::json->>'total')::int as total_todos_mg
        """)

        result = cursor.fetchone()
        print(f"Resultado da função fetch_auctions_paginated(MG, todos): {result[0]} leilões")

        cursor.close()
        conn.close()

        print(f"\n{'='*60}")
        print("DIAGNÓSTICO:")
        print("Se 'futuros' retorna 0 e 'todos' retorna 55, o problema é que")
        print("todos os leilões de MG estão no PASSADO!")
        print("O mapa usa p_temporalidade='futuros' por padrão.")
        print("="*60)

    except Exception as e:
        print(f"\nERRO: {e}")

if __name__ == "__main__":
    main()
