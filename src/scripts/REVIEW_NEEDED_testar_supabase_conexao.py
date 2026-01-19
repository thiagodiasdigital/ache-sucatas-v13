#!/usr/bin/env python3
"""
Teste de Conexão com Supabase
Valida credenciais e acesso ao banco de dados
"""
import os
from dotenv import load_dotenv

# Carregar .env
load_dotenv()

print("=" * 60)
print("TESTE DE CONEXÃO SUPABASE - ACHE SUCATAS DaaS V13")
print("=" * 60)

# Validar credenciais
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_SERVICE_KEY")

print(f"\n[1] Validando credenciais...")
if not SUPABASE_URL:
    print("[ERRO] SUPABASE_URL nao encontrada no .env")
    exit(1)

if not SUPABASE_KEY:
    print("[ERRO] SUPABASE_SERVICE_KEY nao encontrada no .env")
    exit(1)

print(f"[OK] SUPABASE_URL: {SUPABASE_URL}")
print(f"[OK] SUPABASE_SERVICE_KEY: [CONFIGURADA - {len(SUPABASE_KEY)} caracteres]")

# Importar supabase
print(f"\n[2] Importando biblioteca supabase...")
try:
    from supabase import create_client, Client
    print("[OK] Biblioteca supabase importada com sucesso")
except ImportError as e:
    print(f"[ERRO] Erro ao importar supabase: {e}")
    print("\nInstalar com: pip install supabase")
    exit(1)

# Criar cliente
print(f"\n[3] Criando cliente Supabase...")
try:
    supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)
    print("[OK] Cliente Supabase criado com sucesso")
except Exception as e:
    print(f"[ERRO] Erro ao criar cliente: {e}")
    exit(1)

# Testar conexão (listar tabelas)
print(f"\n[4] Testando conexao (listando tabelas)...")
try:
    # Tentar uma query simples
    response = supabase.table("editais_leilao").select("id", count="exact").limit(0).execute()
    print(f"[OK] Conexao estabelecida com sucesso!")
    print(f"   Tabela 'editais_leilao' existe (count: {response.count})")
except Exception as e:
    error_msg = str(e)
    if "relation" in error_msg.lower() and "does not exist" in error_msg.lower():
        print(f"[AVISO] Tabela 'editais_leilao' nao existe ainda")
        print(f"   (Isso e normal - sera criada na proxima etapa)")
    else:
        print(f"[ERRO] Erro ao conectar: {e}")
        exit(1)

# Sucesso
print("\n" + "=" * 60)
print("[OK] TESTE COMPLETO - CONEXAO SUPABASE OK")
print("=" * 60)
print("\nPróximo passo: Criar schemas SQL no banco")
