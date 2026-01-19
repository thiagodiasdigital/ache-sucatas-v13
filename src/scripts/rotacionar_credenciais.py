#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
ROTAÇÃO DE CREDENCIAIS - ACHE SUCATAS
Execute este script após gerar novas credenciais no Supabase Dashboard.

IMPORTANTE: As credenciais antigas foram COMPROMETIDAS e devem ser rotacionadas.

Passos:
1. Acesse o Dashboard do Supabase
2. Gere novas credenciais (service key e senha do banco)
3. Execute este script para atualizar o .env
4. Atualize os GitHub Secrets
"""
import sys
import os
import re
from pathlib import Path
from datetime import datetime

if sys.platform == 'win32':
    sys.stdout.reconfigure(encoding='utf-8')

print("=" * 60)
print("ROTAÇÃO DE CREDENCIAIS - ACHE SUCATAS")
print("=" * 60)
print(f"\nData: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

# Verificar se .env existe
env_file = Path(".env")
if not env_file.exists():
    print("\n[ERRO] Arquivo .env não encontrado!")
    print("Copie .env.example para .env primeiro.")
    sys.exit(1)

print("\n" + "=" * 60)
print("PASSO 1: GERAR NOVAS CREDENCIAIS NO SUPABASE")
print("=" * 60)

print("""
Acesse o Dashboard do Supabase e siga estes passos:

1. SERVICE ROLE KEY (Nova):
   - Vá em: Settings → API → service_role key
   - Clique em "Regenerate" se disponível
   - OU crie um novo projeto (mais seguro)

2. SENHA DO BANCO (Nova):
   - Vá em: Settings → Database → Database password
   - Clique em "Reset database password"
   - Copie a nova senha

3. URL DO PROJETO:
   - Se criou novo projeto, copie a nova URL
""")

print("\n" + "=" * 60)
print("PASSO 2: INSERIR NOVAS CREDENCIAIS")
print("=" * 60)

# Solicitar novas credenciais
print("\nDigite as NOVAS credenciais (ou pressione Enter para manter atual):\n")

new_url = input("Nova SUPABASE_URL (https://xxx.supabase.co): ").strip()
new_service_key = input("Nova SUPABASE_SERVICE_KEY: ").strip()
new_db_password = input("Nova SUPABASE_DB_PASSWORD: ").strip()

if not any([new_url, new_service_key, new_db_password]):
    print("\n[INFO] Nenhuma credencial fornecida. Saindo...")
    sys.exit(0)

# Ler .env atual
print("\n[INFO] Lendo .env atual...")
with open(env_file, 'r', encoding='utf-8') as f:
    env_content = f.read()

# Fazer backup
backup_file = env_file.with_suffix(f'.env.backup_{datetime.now().strftime("%Y%m%d_%H%M%S")}')
with open(backup_file, 'w', encoding='utf-8') as f:
    f.write(env_content)
print(f"[OK] Backup criado: {backup_file}")

# Atualizar credenciais
changes_made = []

if new_url:
    if "SUPABASE_URL=" in env_content:
        env_content = re.sub(
            r'SUPABASE_URL=.*',
            f'SUPABASE_URL={new_url}',
            env_content
        )
        changes_made.append("SUPABASE_URL")
    else:
        env_content += f"\nSUPABASE_URL={new_url}\n"
        changes_made.append("SUPABASE_URL (adicionado)")

if new_service_key:
    if "SUPABASE_SERVICE_KEY=" in env_content:
        env_content = re.sub(
            r'SUPABASE_SERVICE_KEY=.*',
            f'SUPABASE_SERVICE_KEY={new_service_key}',
            env_content
        )
        changes_made.append("SUPABASE_SERVICE_KEY")
    else:
        env_content += f"\nSUPABASE_SERVICE_KEY={new_service_key}\n"
        changes_made.append("SUPABASE_SERVICE_KEY (adicionado)")

if new_db_password:
    if "SUPABASE_DB_PASSWORD=" in env_content:
        env_content = re.sub(
            r'SUPABASE_DB_PASSWORD=.*',
            f'SUPABASE_DB_PASSWORD={new_db_password}',
            env_content
        )
        changes_made.append("SUPABASE_DB_PASSWORD")
    else:
        env_content += f"\nSUPABASE_DB_PASSWORD={new_db_password}\n"
        changes_made.append("SUPABASE_DB_PASSWORD (adicionado)")

# Salvar .env atualizado
# nosec B602 - This script's purpose is to write credentials to .env file
# CodeQL: clear-text-storage-sensitive-data - Intentional: .env is gitignored
with open(env_file, 'w', encoding='utf-8') as f:
    f.write(env_content)

print(f"\n[OK] .env atualizado com: {', '.join(changes_made)}")

print("\n" + "=" * 60)
print("PASSO 3: ATUALIZAR GITHUB SECRETS")
print("=" * 60)

print("""
Execute os seguintes comandos para atualizar os GitHub Secrets:
""")

if new_url:
    print(f'gh secret set SUPABASE_URL --body "{new_url}"')
if new_service_key:
    print(f'gh secret set SUPABASE_SERVICE_KEY --body "{new_service_key}"')

print("\n" + "=" * 60)
print("PASSO 4: TESTAR CONEXÃO")
print("=" * 60)

print("""
Execute para testar a conexão:

  python -c "from supabase_repository import SupabaseRepository; r = SupabaseRepository(); print(f'OK: {r.contar_editais()} editais')"
""")

print("\n" + "=" * 60)
print("PASSO 5: LIMPAR HISTÓRICO GIT (CRÍTICO!)")
print("=" * 60)

print("""
As credenciais antigas estão no histórico do Git!
Para um projeto novo/pequeno, recomendo criar um novo repositório:

  1. Crie um novo repo no GitHub (privado)
  2. Copie os arquivos (sem a pasta .git)
  3. git init && git add . && git commit -m "Initial commit (clean)"
  4. git remote add origin <novo-repo-url>
  5. git push -u origin master
  6. Delete o repo antigo

OU use BFG Repo Cleaner para limpar o histórico:
  https://rtyley.github.io/bfg-repo-cleaner/
""")

print("\n" + "=" * 60)
print("ROTAÇÃO CONCLUÍDA")
print("=" * 60)
print(f"""
Credenciais atualizadas: {len(changes_made)}
Backup salvo em: {backup_file}

PRÓXIMOS PASSOS OBRIGATÓRIOS:
1. [ ] Atualizar GitHub Secrets (comandos acima)
2. [ ] Testar conexão
3. [ ] Limpar histórico Git ou criar novo repo
4. [ ] Disparar workflow para testar: gh workflow run ache-sucatas.yml
""")
