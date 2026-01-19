#!/usr/bin/env python3
"""
Executa Schema SQL no Supabase
Cria todas as tabelas, índices, views e RLS
"""
import os
from dotenv import load_dotenv

load_dotenv()

print("=" * 60)
print("EXECUTANDO SCHEMA SQL NO SUPABASE")
print("=" * 60)

# Validar credenciais
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_SERVICE_KEY")

if not SUPABASE_URL or not SUPABASE_KEY:
    print("[ERRO] Credenciais não encontradas no .env")
    exit(1)

print(f"\n[OK] Supabase URL: {SUPABASE_URL}")

# Importar supabase
try:
    from supabase import create_client, Client
except ImportError:
    print("[ERRO] Biblioteca supabase não instalada")
    print("Instalar com: pip install supabase")
    exit(1)

# Criar cliente
print(f"\n[1] Conectando ao Supabase...")
supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)
print("[OK] Conectado")

# Ler schema SQL
print(f"\n[2] Lendo schema SQL...")
try:
    with open("schemas_v13_supabase.sql", "r", encoding="utf-8") as f:
        sql_script = f.read()
    print(f"[OK] Schema lido ({len(sql_script)} bytes)")
except FileNotFoundError:
    print("[ERRO] Arquivo schemas_v13_supabase.sql não encontrado")
    exit(1)

# Executar SQL via API
print(f"\n[3] Executando SQL no Supabase...")
print("[AVISO] Use o SQL Editor do Supabase Dashboard para executar o schema")
print(f"\nPasso a passo:")
print("1. Acesse: {}/project/_/sql".format(SUPABASE_URL.replace("https://", "https://supabase.com/dashboard/project/")))
print("2. Clique em 'SQL Editor' → 'New query'")
print("3. Cole o conteúdo de 'schemas_v13_supabase.sql'")
print("4. Clique em 'Run' (botão verde)")
print("5. Verifique se apareceu 'Success' sem erros")
print("\nArquivo SQL: schemas_v13_supabase.sql")
print(f"\nDepois execute novamente: python testar_supabase_conexao.py")

print("\n" + "=" * 60)
print("AGUARDANDO EXECUÇÃO MANUAL DO SCHEMA")
print("=" * 60)
