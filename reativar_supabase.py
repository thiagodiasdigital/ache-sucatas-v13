#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Reativa Supabase após kill switch
Só usar após confirmar que custos estão OK
"""
import sys
if sys.platform == 'win32':
    sys.stdout.reconfigure(encoding='utf-8')

from pathlib import Path

print("=" * 60)
print("REATIVANDO SUPABASE")
print("=" * 60)

# Verificar se foi desabilitado
flag_file = Path("SUPABASE_DISABLED.flag")

if not flag_file.exists():
    print("\n[INFO] Supabase nao estava desabilitado")
    print("[INFO] Nada a fazer")
    sys.exit(0)

print("\n[AVISO] Supabase foi desabilitado anteriormente")
print("\n" + flag_file.read_text(encoding='utf-8'))

# Confirmar reativação
print("\n" + "=" * 60)
print("CONFIRMACAO OBRIGATORIA")
print("=" * 60)
print("\nAntes de reativar, confirme:")
print("1. Verificou custos no Dashboard do Supabase?")
print("2. Database esta dentro do limite (< 500 MB)?")
print("3. Custo mensal esta em $0.00?")

resposta = input("\nDigite 'SIM' para reativar: ").strip().upper()

if resposta != "SIM":
    print("\n[INFO] Reativacao cancelada")
    sys.exit(0)

# Modificar .env
env_file = Path(".env")

print("\n[1] Lendo .env...")
with open(env_file, 'r', encoding='utf-8') as f:
    linhas = f.readlines()

print("[2] Habilitando Supabase...")
novas_linhas = []

for linha in linhas:
    if linha.startswith("ENABLE_SUPABASE"):
        novas_linhas.append("ENABLE_SUPABASE=true\n")
    else:
        novas_linhas.append(linha)

# Salvar
with open(env_file, 'w', encoding='utf-8') as f:
    f.writelines(novas_linhas)

print("[OK] ENABLE_SUPABASE=true setado no .env")

# Remover flag
flag_file.unlink()
print(f"[OK] Flag removida: {flag_file}")

# Testar conexão
print("\n[3] Testando conexao...")
try:
    from supabase_repository import SupabaseRepository
    repo = SupabaseRepository(enable_supabase=True)

    if repo.enable_supabase:
        count = repo.contar_editais()
        print(f"[OK] Conectado! Editais no banco: {count}")
    else:
        print("[ERRO] Nao conseguiu conectar")
        sys.exit(1)
except Exception as e:
    print(f"[ERRO] {e}")
    sys.exit(1)

print("\n" + "=" * 60)
print("SUPABASE REATIVADO COM SUCESSO")
print("=" * 60)
print("\nRecomendacoes:")
print("1. Monitore uso diariamente: python monitorar_uso_supabase.py")
print("2. Configure alertas no Dashboard do Supabase")
print("3. Mantenha spending cap em $50")
print("=" * 60)
