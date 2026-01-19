#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Instala hooks de segurança no repositório Git.
Detecta automaticamente secrets antes de cada commit.
"""
import sys
import os
import subprocess
from pathlib import Path

if sys.platform == 'win32':
    sys.stdout.reconfigure(encoding='utf-8')

print("=" * 60)
print("INSTALAÇÃO DE HOOKS DE SEGURANÇA")
print("=" * 60)

# Verificar se é um repositório Git
if not Path(".git").exists():
    print("\n[ERRO] Este diretório não é um repositório Git!")
    sys.exit(1)

# Verificar se o hook existe
hook_file = Path(".githooks/pre-commit")
if not hook_file.exists():
    print(f"\n[ERRO] Arquivo {hook_file} não encontrado!")
    sys.exit(1)

# Configurar o diretório de hooks
print("\n[1] Configurando hooks path...")
try:
    subprocess.run(
        ["git", "config", "core.hooksPath", ".githooks"],
        check=True,
        capture_output=True
    )
    print("[OK] core.hooksPath configurado para .githooks")
except subprocess.CalledProcessError as e:
    print(f"[ERRO] Falha ao configurar hooks: {e}")
    sys.exit(1)

# No Windows, o hook precisa de permissão de execução
# No Unix, tornar executável
if sys.platform != 'win32':
    print("\n[2] Tornando hook executável...")
    try:
        # CodeQL: overly-permissive-file - 0o755 required for Git hooks (must be executable by Git)
        # Using 0o700 would break hooks when Git runs under different user context
        os.chmod(hook_file, 0o755)  # nosec B103
        print(f"[OK] {hook_file} agora é executável")
    except Exception as e:
        print(f"[AVISO] Não foi possível tornar executável: {e}")

print("\n" + "=" * 60)
print("HOOKS DE SEGURANÇA INSTALADOS!")
print("=" * 60)

print("""
O hook pre-commit agora irá:

1. Verificar TODOS os arquivos antes de cada commit
2. BLOQUEAR commits com possíveis secrets:
   - Supabase service keys
   - Senhas de banco de dados
   - JWT tokens
   - Outras credenciais

3. Padrões detectados:
   - SUPABASE_SERVICE_KEY=...
   - SUPABASE_DB_PASSWORD=...
   - sb_secret_...
   - postgresql://user:password@...
   - eyJ... (JWT tokens)

IMPORTANTE:
- O hook NÃO bloqueia .env.example (usa placeholders)
- Para bypass emergencial: git commit --no-verify
- Arquivos binários são ignorados

Para testar:
  echo "SUPABASE_SERVICE_KEY=sb_secret_teste123" > teste.txt
  git add teste.txt
  git commit -m "teste"  # Deve ser bloqueado!
  rm teste.txt
""")

# Verificar configuração
print("\n[INFO] Verificando configuração atual...")
result = subprocess.run(
    ["git", "config", "--get", "core.hooksPath"],
    capture_output=True,
    text=True
)
print(f"[OK] core.hooksPath = {result.stdout.strip()}")
