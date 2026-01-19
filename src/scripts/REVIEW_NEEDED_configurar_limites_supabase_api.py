#!/usr/bin/env python3
"""
Tentar configurar limites de custo via Supabase Management API
"""
import os
import requests
from dotenv import load_dotenv

load_dotenv()

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_SERVICE_KEY")

# Extrair project_id da URL
# Exemplo: https://xxx.supabase.co → xxx
project_id = SUPABASE_URL.replace("https://", "").split(".")[0]

print("="*60)
print("TENTANDO CONFIGURAR LIMITES VIA API")
print("="*60)
print(f"\nProject ID: {project_id}")

# Tentar acessar Management API
# https://supabase.com/docs/reference/api/introduction
management_api_base = "https://api.supabase.com/v1"

headers = {
    "Authorization": f"Bearer {SUPABASE_KEY}",
    "Content-Type": "application/json"
}

# Tentar obter informações do projeto
print(f"\n[1] Tentando acessar informações do projeto...")
try:
    response = requests.get(
        f"{management_api_base}/projects/{project_id}",
        headers=headers,
        timeout=10
    )
    print(f"    Status: {response.status_code}")

    if response.status_code == 200:
        data = response.json()
        print(f"    [OK] Projeto encontrado: {data.get('name', 'N/A')}")
        print(f"    Plan: {data.get('subscription_tier', 'N/A')}")
    elif response.status_code == 401:
        print(f"    [ERRO] Service key não tem permissão para Management API")
        print(f"    [INFO] Precisa de Personal Access Token do Dashboard")
    elif response.status_code == 404:
        print(f"    [ERRO] Projeto não encontrado")
    else:
        print(f"    [AVISO] Resposta inesperada: {response.text[:200]}")
except Exception as e:
    print(f"    [ERRO] {e}")

# Tentar acessar billing info
print(f"\n[2] Tentando acessar informações de billing...")
try:
    response = requests.get(
        f"{management_api_base}/projects/{project_id}/billing",
        headers=headers,
        timeout=10
    )
    print(f"    Status: {response.status_code}")

    if response.status_code == 200:
        data = response.json()
        print(f"    [OK] Billing info:")
        print(f"    {data}")
    else:
        print(f"    [AVISO] Não conseguiu acessar billing via API")
except Exception as e:
    print(f"    [ERRO] {e}")

# Tentar verificar usage/quotas via API interna
print(f"\n[3] Tentando verificar usage via API do projeto...")
try:
    # API interna do Supabase (pode não estar exposta)
    response = requests.get(
        f"{SUPABASE_URL}/rest/v1/",
        headers={
            "apikey": SUPABASE_KEY,
            "Authorization": f"Bearer {SUPABASE_KEY}"
        },
        timeout=10
    )
    print(f"    Status: {response.status_code}")
    print(f"    [INFO] REST API está ativa (usada para dados)")
except Exception as e:
    print(f"    [ERRO] {e}")

print("\n" + "="*60)
print("CONCLUSÃO")
print("="*60)
print("""
❌ Management API requer Personal Access Token do Dashboard
   (Service Key só dá acesso aos dados, não ao billing)

✅ SOLUÇÃO:
   1. Você precisa criar Personal Access Token no Dashboard:
      https://supabase.com/dashboard/account/tokens

   2. Adicionar no .env:
      SUPABASE_ACCESS_TOKEN=sbp_xxxxxxxxxxxxx

   3. Re-executar este script com o token

OU (mais simples):
   Configurar manualmente no Dashboard conforme FREIO_SEGURANCA_CUSTOS.md
""")
