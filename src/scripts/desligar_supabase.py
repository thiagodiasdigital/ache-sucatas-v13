#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
KILL SWITCH - Desliga Supabase imediatamente
Usar em emergência se detectar custos
"""
import sys
if sys.platform == 'win32':
    sys.stdout.reconfigure(encoding='utf-8')

from pathlib import Path

print("=" * 60)
print("KILL SWITCH - DESLIGANDO SUPABASE")
print("=" * 60)

# Modificar .env para desabilitar Supabase
env_file = Path(".env")

if not env_file.exists():
    print("\n[ERRO] Arquivo .env nao encontrado")
    sys.exit(1)

print("\n[1] Lendo .env atual...")
with open(env_file, 'r', encoding='utf-8') as f:
    linhas = f.readlines()

print("[2] Desabilitando Supabase...")
novas_linhas = []
supabase_desabilitado = False

for linha in linhas:
    if linha.startswith("ENABLE_SUPABASE"):
        novas_linhas.append("ENABLE_SUPABASE=false\n")
        supabase_desabilitado = True
    else:
        novas_linhas.append(linha)

# Se não existir a linha, adicionar
if not supabase_desabilitado:
    novas_linhas.append("\n# DESABILITADO POR KILL SWITCH\n")
    novas_linhas.append("ENABLE_SUPABASE=false\n")

# Salvar
with open(env_file, 'w', encoding='utf-8') as f:
    f.writelines(novas_linhas)

print("[OK] ENABLE_SUPABASE=false setado no .env")

# Criar flag de emergência
flag_file = Path("SUPABASE_DISABLED.flag")
with open(flag_file, 'w', encoding='utf-8') as f:
    from datetime import datetime
    f.write(f"Supabase desabilitado em: {datetime.now().isoformat()}\n")
    f.write("Motivo: Kill switch ativado (limite de custo)\n")
    f.write("\nPara reativar:\n")
    f.write("1. Verifique custos no Dashboard\n")
    f.write("2. Execute: python reativar_supabase.py\n")

print(f"[OK] Flag criada: {flag_file}")

print("\n" + "=" * 60)
print("SUPABASE DESABILITADO COM SUCESSO")
print("=" * 60)
print("\nProximos passos:")
print("1. Verificar custos no Dashboard do Supabase")
print("2. Auditor V13 vai continuar salvando apenas em CSV/XLSX")
print("3. Para reativar: python reativar_supabase.py")
print("\n[INFO] Modo LOCAL ONLY ativado")
print("=" * 60)
