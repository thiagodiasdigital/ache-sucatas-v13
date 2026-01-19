#!/usr/bin/env python3
"""Monitor migration progress"""
from supabase_repository import SupabaseRepository
import time

print("="*60)
print("MONITORANDO MIGRACAO V13")
print("="*60)

repo = SupabaseRepository(enable_supabase=True)

if not repo.enable_supabase:
    print("[ERRO] Supabase nao conectado")
    exit(1)

print(f"\n[INFO] Checando progresso a cada 30 segundos...")
print(f"[INFO] Pressione Ctrl+C para parar o monitor\n")

count_anterior = repo.contar_editais()
print(f"[{time.strftime('%H:%M:%S')}] Editais no banco: {count_anterior}")

try:
    while True:
        time.sleep(30)
        count_atual = repo.contar_editais()

        if count_atual != count_anterior:
            diferenca = count_atual - count_anterior
            print(f"[{time.strftime('%H:%M:%S')}] Editais no banco: {count_atual} (+{diferenca})")
            count_anterior = count_atual
        else:
            print(f"[{time.strftime('%H:%M:%S')}] Editais no banco: {count_atual} (sem mudanca)")

        # Se chegou em 198+, migration complete
        if count_atual >= 198:
            print(f"\n[OK] MIGRACAO COMPLETA! Total: {count_atual}")
            break

except KeyboardInterrupt:
    print(f"\n[INFO] Monitor interrompido")
    count_final = repo.contar_editais()
    print(f"[INFO] Editais no banco: {count_final}")
