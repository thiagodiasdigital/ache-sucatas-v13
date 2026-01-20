#!/usr/bin/env python3
"""
Executa os scripts SQL no Supabase para criar a infraestrutura do frontend.
"""
import os
import sys

# Adicionar pasta pai ao path para importar dotenv
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv

# Carregar .env da pasta pai (raiz do projeto)
load_dotenv(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), '.env'))

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_SERVICE_KEY")

if not SUPABASE_URL or not SUPABASE_KEY:
    print("ERRO: SUPABASE_URL ou SUPABASE_SERVICE_KEY não configurados no .env")
    sys.exit(1)

try:
    from supabase import create_client
except ImportError:
    print("Instalando supabase-py...")
    os.system("pip install supabase")
    from supabase import create_client

print(f"Conectando ao Supabase: {SUPABASE_URL}")
client = create_client(SUPABASE_URL, SUPABASE_KEY)

def execute_sql_file(filepath: str, description: str):
    """Executa um arquivo SQL no Supabase."""
    print(f"\n{'='*60}")
    print(f"Executando: {description}")
    print(f"Arquivo: {filepath}")
    print('='*60)

    if not os.path.exists(filepath):
        print(f"ERRO: Arquivo não encontrado: {filepath}")
        return False

    with open(filepath, 'r', encoding='utf-8') as f:
        sql_content = f.read()

    # Dividir em statements (por segurança, executar em blocos menores)
    # Para o arquivo de infraestrutura, executar tudo de uma vez
    try:
        result = client.postgrest.rpc('', {}).execute()
    except:
        pass

    # Usar a função SQL do Supabase via REST API
    import requests

    headers = {
        "apikey": SUPABASE_KEY,
        "Authorization": f"Bearer {SUPABASE_KEY}",
        "Content-Type": "application/json",
        "Prefer": "return=minimal"
    }

    # Executar via endpoint SQL do Supabase
    sql_url = f"{SUPABASE_URL}/rest/v1/rpc/exec_sql"

    # Tentar via pg_net ou diretamente
    # Na verdade, vamos usar o método mais simples: psycopg2 direto

    print("Tentando executar SQL via conexão direta...")

    # Extrair host do URL
    import re
    match = re.search(r'https://([^.]+)\.supabase\.co', SUPABASE_URL)
    if not match:
        print("ERRO: Não foi possível extrair o project_ref do URL")
        return False

    project_ref = match.group(1)
    db_host = f"db.{project_ref}.supabase.co"
    db_password = os.getenv("SUPABASE_DB_PASSWORD")

    if not db_password:
        print("ERRO: SUPABASE_DB_PASSWORD não configurado no .env")
        print("Adicione a senha do banco no .env para executar SQL direto")
        return False

    try:
        import psycopg2
    except ImportError:
        print("Instalando psycopg2-binary...")
        os.system("pip install psycopg2-binary")
        import psycopg2

    conn_string = f"postgresql://postgres:{db_password}@{db_host}:5432/postgres"

    try:
        print(f"Conectando ao banco: {db_host}...")
        conn = psycopg2.connect(conn_string)
        conn.autocommit = True
        cursor = conn.cursor()

        print("Executando SQL...")
        cursor.execute(sql_content)

        print("SQL executado com sucesso!")

        cursor.close()
        conn.close()
        return True

    except Exception as e:
        print(f"ERRO ao executar SQL: {e}")
        return False

def main():
    print("="*60)
    print("ACHE SUCATAS - Configuração do Supabase")
    print("="*60)

    supabase_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'supabase')

    # 1. Executar infraestrutura
    infra_sql = os.path.join(supabase_dir, 'supabase_infrastructure.sql')
    if not execute_sql_file(infra_sql, "Infraestrutura (schemas, tabelas, views, RPCs)"):
        print("\nERRO na infraestrutura. Abortando.")
        return

    # 2. Executar municípios
    municipios_sql = os.path.join(supabase_dir, 'insert_municipios.sql')
    if not execute_sql_file(municipios_sql, "Dados dos Municípios (IBGE)"):
        print("\nERRO nos municípios.")
        return

    print("\n" + "="*60)
    print("SUCESSO! Infraestrutura do Supabase configurada.")
    print("="*60)

if __name__ == "__main__":
    main()
