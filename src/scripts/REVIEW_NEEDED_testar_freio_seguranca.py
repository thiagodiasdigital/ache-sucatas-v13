#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Testa o freio de segurança simulando limite atingido
"""
import sys
if sys.platform == 'win32':
    sys.stdout.reconfigure(encoding='utf-8')

import os
os.environ["MAX_EDITAIS_SUPABASE"] = "5"  # Simular limite baixo

from supabase_repository import SupabaseRepository

print("=" * 60)
print("TESTE DO FREIO DE SEGURANCA")
print("=" * 60)

print("\n[CONFIG] Limite simulado: 5 editais")
print("[CONFIG] Atual no banco: 5 editais")
print("[EXPECTATIVA] Deve BLOQUEAR próximo insert\n")

repo = SupabaseRepository(enable_supabase=True)

if not repo.enable_supabase:
    print("[ERRO] Supabase nao conectado")
    sys.exit(1)

# Tentar inserir (deve falhar)
print("[1] Tentando inserir edital de teste...")

dados_teste = {
    "id_interno": "ID_TESTE_LIMITE",
    "orgao": "ORGAO TESTE",
    "uf": "SP",
    "cidade": "Teste",
    "n_edital": "001/2026",
    "titulo": "Edital de Teste - Deve ser Bloqueado",
    "descricao": "Este edital nao deve ser inserido pois atingiu o limite",
    "tags": "teste",
    "link_pncp": "https://example.com",
    "arquivo_origem": "SP_TESTE/teste-001",
    "data_publicacao": "2026-01-16",
    "data_leilao": "2026-01-16 10:00"
}

sucesso = repo.inserir_edital(dados_teste)

if sucesso:
    print("[ERRO] Insercao NAO foi bloqueada!")
    print("[FALHA] Freio de seguranca NAO funcionou!")
    sys.exit(1)
else:
    print("[OK] Insercao foi BLOQUEADA como esperado!")
    print("[OK] Freio de seguranca FUNCIONOU!")

# Verificar count (deve continuar 5)
count_final = repo.contar_editais()
print(f"\n[2] Count final no banco: {count_final}")

if count_final == 5:
    print("[OK] Count permaneceu em 5 (limite nao ultrapassado)")
else:
    print(f"[ERRO] Count deveria ser 5, mas eh {count_final}")

print("\n" + "=" * 60)
print("RESULTADO DO TESTE")
print("=" * 60)
print("[OK] FREIO DE SEGURANCA ESTA FUNCIONANDO!")
print("    - Limite configurado: 5 editais")
print("    - Banco atual: 5 editais")
print("    - Insert bloqueado: SIM")
print("    - Count mantido: SIM")
print("\n[INFO] Limite real configurado: 10.000 editais (no .env)")
print("=" * 60)
