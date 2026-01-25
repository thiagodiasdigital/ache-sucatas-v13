"""
Script para executar o FIX_PAGINACAO_PUBLIC.sql no Supabase
Cria a função fetch_auctions_paginated com todos os parâmetros necessários
"""

import os
import sys
import psycopg2
from pathlib import Path

# Configuracao via variaveis de ambiente
SUPABASE_URL = os.getenv("SUPABASE_URL", "")
SUPABASE_DB_PASSWORD = os.getenv("SUPABASE_DB_PASSWORD", "")
SUPABASE_PROJECT = SUPABASE_URL.replace("https://", "").split(".")[0] if SUPABASE_URL else ""

if not SUPABASE_DB_PASSWORD or not SUPABASE_PROJECT:
    print("ERRO: Configure SUPABASE_URL e SUPABASE_DB_PASSWORD no .env")
    sys.exit(1)

DATABASE_URL = f"postgresql://postgres:{SUPABASE_DB_PASSWORD}@db.{SUPABASE_PROJECT}.supabase.co:5432/postgres"

SQL_FILE = Path(__file__).parent.parent / "FIX_PAGINACAO_PUBLIC.sql"

def main():
    print("=" * 60)
    print("EXECUTAR FIX_PAGINACAO_PUBLIC.sql")
    print("=" * 60)

    if not SQL_FILE.exists():
        print(f"ERRO: Arquivo não encontrado: {SQL_FILE}")
        return

    print(f"Arquivo: {SQL_FILE}")
    print("Conectando ao Supabase...")

    try:
        conn = psycopg2.connect(DATABASE_URL)
        conn.autocommit = True
        cursor = conn.cursor()

        print("Conexão estabelecida!")
        print("Lendo arquivo SQL...")

        with open(SQL_FILE, 'r', encoding='utf-8') as f:
            sql_content = f.read()

        print("Executando SQL...")
        cursor.execute(sql_content)
        print("SQL executado com sucesso!")

        # Testar a função
        print("\n" + "=" * 60)
        print("TESTANDO A FUNÇÃO")
        print("=" * 60)

        cursor.execute("""
            SELECT
                (public.fetch_auctions_paginated(
                    'MG'::TEXT, NULL, NULL, NULL, NULL, NULL, NULL, NULL,
                    1, 20, 'proximos'::TEXT, 'futuros'::TEXT
                )::json->>'total')::int as total_futuros_mg
        """)
        result = cursor.fetchone()
        print(f"MG com temporalidade='futuros': {result[0]} leilões")

        cursor.execute("""
            SELECT
                (public.fetch_auctions_paginated(
                    'MG'::TEXT, NULL, NULL, NULL, NULL, NULL, NULL, NULL,
                    1, 20, 'proximos'::TEXT, 'todos'::TEXT
                )::json->>'total')::int as total_todos_mg
        """)
        result = cursor.fetchone()
        print(f"MG com temporalidade='todos': {result[0]} leilões")

        # Verificar se latitude/longitude estão sendo retornados
        cursor.execute("""
            SELECT json_array_length(
                (public.fetch_auctions_paginated(
                    'MG'::TEXT, NULL, NULL, NULL, NULL, NULL, NULL, NULL,
                    1, 5, 'proximos'::TEXT, 'futuros'::TEXT
                )::json->'data')
            ) as count_data
        """)
        result = cursor.fetchone()
        print(f"Quantidade de leilões no array 'data': {result[0]}")

        if result[0] and result[0] > 0:
            cursor.execute("""
                SELECT
                    public.fetch_auctions_paginated(
                        'MG'::TEXT, NULL, NULL, NULL, NULL, NULL, NULL, NULL,
                        1, 2, 'proximos'::TEXT, 'futuros'::TEXT
                    )::json->'data'->0->>'cidade' as cidade,
                    public.fetch_auctions_paginated(
                        'MG'::TEXT, NULL, NULL, NULL, NULL, NULL, NULL, NULL,
                        1, 2, 'proximos'::TEXT, 'futuros'::TEXT
                    )::json->'data'->0->>'latitude' as latitude,
                    public.fetch_auctions_paginated(
                        'MG'::TEXT, NULL, NULL, NULL, NULL, NULL, NULL, NULL,
                        1, 2, 'proximos'::TEXT, 'futuros'::TEXT
                    )::json->'data'->0->>'longitude' as longitude
            """)
            result = cursor.fetchone()
            print(f"\nPrimeiro resultado: {result[0]}")
            print(f"  latitude: {result[1]}")
            print(f"  longitude: {result[2]}")

        cursor.close()
        conn.close()

        print("\n" + "=" * 60)
        print("SUCESSO! Função criada e testada.")
        print("=" * 60)
        print("\nPróximos passos:")
        print("1. Recarregue o dashboard no navegador")
        print("2. Selecione UF=MG e temporalidade='todos' para ver todos os 55 leilões")
        print("3. Ou mantenha 'futuros' para ver os 2 leilões com data futura")

    except Exception as e:
        print(f"\nERRO: {e}")

if __name__ == "__main__":
    main()
