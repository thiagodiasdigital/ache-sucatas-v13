#!/usr/bin/env python3
"""
Executa Schema SQL Diretamente no Supabase via psycopg2
"""
import os
from dotenv import load_dotenv

load_dotenv()

print("=" * 60)
print("EXECUTANDO SCHEMA SQL DIRETAMENTE NO SUPABASE")
print("=" * 60)

# Tentar via psycopg2 (conexão direta PostgreSQL)
try:
    import psycopg2
    print("\n[OK] psycopg2 instalado")
except ImportError:
    print("\n[INSTALANDO] psycopg2...")
    import subprocess
    subprocess.check_call(["pip", "install", "psycopg2-binary"])
    import psycopg2
    print("[OK] psycopg2 instalado")

# Construir connection string
SUPABASE_URL = os.getenv("SUPABASE_URL")
project_id = SUPABASE_URL.replace("https://", "").replace(".supabase.co", "")

# Connection string para Supabase
# Formato: postgresql://postgres:[PASSWORD]@db.[PROJECT_ID].supabase.co:5432/postgres
print(f"\n[INFO] Project ID: {project_id}")
print("[AVISO] Preciso da senha do banco de dados PostgreSQL")
print("\nPara obter a senha:")
print("1. Acesse: https://supabase.com/dashboard/project/{}/settings/database".format(project_id))
print("2. Em 'Connection String' → clique em 'Show'")
print("3. Copie apenas a SENHA (depois de 'postgres:' e antes de '@')")
print("\nOu informe a senha agora:")

# Tentar usar a service key como senha (às vezes funciona)
SERVICE_KEY = os.getenv("SUPABASE_SERVICE_KEY")
DB_PASSWORD = SERVICE_KEY  # Tentar primeiro

# Construir connection string
conn_string = f"postgresql://postgres.{project_id}:{DB_PASSWORD}@aws-0-sa-east-1.pooler.supabase.com:6543/postgres"

print(f"\n[1] Tentando conectar ao PostgreSQL...")
try:
    conn = psycopg2.connect(conn_string)
    print("[OK] Conectado ao PostgreSQL!")
except Exception as e:
    print(f"[ERRO] Falha ao conectar: {e}")
    print("\nTentando connection string alternativa...")

    # Tentar formato alternativo
    conn_string_alt = f"postgresql://postgres:{DB_PASSWORD}@db.{project_id}.supabase.co:5432/postgres"
    try:
        conn = psycopg2.connect(conn_string_alt)
        print("[OK] Conectado ao PostgreSQL (formato alternativo)!")
    except Exception as e2:
        print(f"[ERRO] Também falhou: {e2}")
        print("\n[SOLUCAO] Precisamos da senha do banco PostgreSQL")
        print("Acesse: https://supabase.com/dashboard/project/{}/settings/database".format(project_id))
        print("Copie a senha e execute:")
        print("  export DB_PASSWORD='sua-senha-aqui'")
        print("  python executar_schema_direto.py")
        exit(1)

# Ler schema SQL
print(f"\n[2] Lendo schema SQL...")
with open("schemas_v13_supabase.sql", "r", encoding="utf-8") as f:
    sql_script = f.read()
print(f"[OK] Schema lido ({len(sql_script)} bytes)")

# Executar SQL
print(f"\n[3] Executando schema no banco...")
cursor = conn.cursor()
try:
    cursor.execute(sql_script)
    conn.commit()
    print("[OK] Schema executado com sucesso!")
except Exception as e:
    print(f"[ERRO] Erro ao executar: {e}")
    conn.rollback()
    exit(1)
finally:
    cursor.close()
    conn.close()

print("\n" + "=" * 60)
print("[OK] SCHEMA CRIADO COM SUCESSO!")
print("=" * 60)
print("\nValidar com: python testar_supabase_conexao.py")
