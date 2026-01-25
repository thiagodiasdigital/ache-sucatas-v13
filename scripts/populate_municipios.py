"""
Script para popular a tabela pub.ref_municipios no Supabase
Executa o arquivo insert_municipios.sql com ~5.600 municípios brasileiros
"""

import os
import sys
import psycopg2
from pathlib import Path

# Configuracao do Supabase (variaveis de ambiente)
SUPABASE_URL = os.getenv("SUPABASE_URL", "")
SUPABASE_DB_PASSWORD = os.getenv("SUPABASE_DB_PASSWORD", "")

# Extrair project ID da URL
SUPABASE_PROJECT = SUPABASE_URL.replace("https://", "").split(".")[0] if SUPABASE_URL else ""

if not SUPABASE_DB_PASSWORD or not SUPABASE_PROJECT:
    print("ERRO: Configure SUPABASE_URL e SUPABASE_DB_PASSWORD no .env")
    sys.exit(1)

# Connection string do Supabase (conexao direta)
DATABASE_URL = f"postgresql://postgres:{SUPABASE_DB_PASSWORD}@db.{SUPABASE_PROJECT}.supabase.co:5432/postgres"

# Caminho do arquivo SQL
SQL_FILE = Path(__file__).parent.parent / "frontend" / "supabase" / "insert_municipios.sql"

def main():
    print("=" * 60)
    print("POPULATE MUNICIPIOS - Ache Sucatas")
    print("=" * 60)

    # Verificar se arquivo existe
    if not SQL_FILE.exists():
        print(f"ERRO: Arquivo SQL nao encontrado: {SQL_FILE}")
        sys.exit(1)

    print(f"Arquivo SQL: {SQL_FILE}")
    print(f"Conectando ao Supabase...")

    try:
        # Conectar ao banco
        conn = psycopg2.connect(DATABASE_URL)
        conn.autocommit = False
        cursor = conn.cursor()

        print("Conexao estabelecida!")

        # Verificar contagem atual
        cursor.execute("SELECT COUNT(*) FROM pub.ref_municipios")
        count_before = cursor.fetchone()[0]
        print(f"Registros antes: {count_before}")

        # Ler e executar o arquivo SQL
        print("Lendo arquivo SQL...")
        with open(SQL_FILE, 'r', encoding='utf-8') as f:
            sql_content = f.read()

        print("Executando SQL (pode demorar alguns segundos)...")
        cursor.execute(sql_content)

        # Commit
        conn.commit()
        print("Commit realizado!")

        # Verificar contagem apos
        cursor.execute("SELECT COUNT(*) FROM pub.ref_municipios")
        count_after = cursor.fetchone()[0]
        print(f"Registros depois: {count_after}")
        print(f"Novos registros: {count_after - count_before}")

        # Verificar amostra de MG
        cursor.execute("""
            SELECT nome_municipio, uf, latitude, longitude
            FROM pub.ref_municipios
            WHERE uf = 'MG'
            LIMIT 5
        """)
        sample = cursor.fetchall()
        print("\nAmostra de municipios de MG:")
        for row in sample:
            print(f"  - {row[0]} ({row[1]}): lat={row[2]}, lng={row[3]}")

        cursor.close()
        conn.close()

        print("\n" + "=" * 60)
        print("SUCESSO! Tabela ref_municipios populada.")
        print("O mapa agora deve exibir as coordenadas corretamente.")
        print("=" * 60)

    except Exception as e:
        print(f"\nERRO: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
