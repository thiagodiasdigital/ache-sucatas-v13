#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Executa Schema SQL Diretamente no PostgreSQL do Supabase
"""
import sys
if sys.platform == 'win32':
    sys.stdout.reconfigure(encoding='utf-8')
    sys.stderr.reconfigure(encoding='utf-8')

print("=" * 60)
print("EXECUTANDO SCHEMA SQL NO POSTGRESQL/SUPABASE")
print("=" * 60)

# Importar psycopg2
try:
    import psycopg2
    print("\n[OK] psycopg2 disponivel")
except ImportError:
    print("\n[ERRO] psycopg2 nao instalado")
    exit(1)

# Connection string - NUNCA hardcode credenciais!
# Usar variáveis de ambiente do .env
import os
from dotenv import load_dotenv
load_dotenv()

SUPABASE_URL = os.getenv("SUPABASE_URL", "")
DB_PASSWORD = os.getenv("SUPABASE_DB_PASSWORD", "")

if not SUPABASE_URL or not DB_PASSWORD:
    print("[ERRO] Credenciais não encontradas no .env")
    print("Configure SUPABASE_URL e SUPABASE_DB_PASSWORD no arquivo .env")
    exit(1)

# Extrair project_id da URL
project_id = SUPABASE_URL.replace("https://", "").replace(".supabase.co", "")
DATABASE_URL = f"postgresql://postgres:{DB_PASSWORD}@db.{project_id}.supabase.co:5432/postgres"

print(f"\n[1] Conectando ao PostgreSQL...")
try:
    conn = psycopg2.connect(DATABASE_URL)
    print("[OK] Conectado com sucesso!")
except Exception as e:
    print(f"[ERRO] Falha ao conectar: {e}")
    exit(1)

# Ler schema SQL
print(f"\n[2] Lendo schema SQL...")
try:
    with open("schemas_v13_supabase.sql", "r", encoding="utf-8") as f:
        sql_script = f.read()
    print(f"[OK] Schema lido ({len(sql_script)} bytes)")
except FileNotFoundError:
    print("[ERRO] Arquivo schemas_v13_supabase.sql nao encontrado")
    conn.close()
    exit(1)

# Executar SQL
print(f"\n[3] Executando schema no banco...")
print("    Criando tabelas...")
cursor = conn.cursor()
try:
    # Executar o SQL completo
    cursor.execute(sql_script)
    conn.commit()
    print("[OK] Schema executado com sucesso!")

    # Verificar tabelas criadas
    cursor.execute("""
        SELECT table_name
        FROM information_schema.tables
        WHERE table_schema = 'public'
        AND table_name IN ('editais_leilao', 'execucoes_miner', 'metricas_diarias')
        ORDER BY table_name;
    """)
    tables = cursor.fetchall()

    print(f"\n[4] Tabelas criadas:")
    for table in tables:
        print(f"    - {table[0]}")

    # Verificar RLS
    cursor.execute("""
        SELECT tablename, rowsecurity
        FROM pg_tables
        WHERE schemaname = 'public'
        AND tablename IN ('editais_leilao', 'execucoes_miner', 'metricas_diarias');
    """)
    rls_status = cursor.fetchall()

    print(f"\n[5] RLS (Row Level Security):")
    for table, enabled in rls_status:
        status = "ATIVADO" if enabled else "DESATIVADO"
        print(f"    - {table}: {status}")

except Exception as e:
    print(f"[ERRO] Erro ao executar: {e}")
    print(f"\nDetalhes: {type(e).__name__}")
    conn.rollback()
    cursor.close()
    conn.close()
    exit(1)

cursor.close()
conn.close()

print("\n" + "=" * 60)
print("[OK] SCHEMA CRIADO COM SUCESSO NO SUPABASE!")
print("=" * 60)
print("\nProximas etapas:")
print("1. Validar: python testar_supabase_conexao.py")
print("2. Implementar Auditor V13")
print("3. Migrar 198 editais")
