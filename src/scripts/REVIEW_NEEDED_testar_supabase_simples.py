#!/usr/bin/env python3
"""Test Supabase connection only"""
from supabase_repository import SupabaseRepository

print("Testing Supabase connection...")
repo = SupabaseRepository(enable_supabase=True)

if not repo.enable_supabase:
    print("[ERRO] Not connected")
    exit(1)

print("[OK] Connected")

count = repo.contar_editais()
print(f"[INFO] Count: {count}")

editais = repo.listar_editais_recentes(limit=3)
print(f"[INFO] Recent editals: {len(editais)}")

for i, e in enumerate(editais, 1):
    print(f"  [{i}] {e.get('id_interno', 'N/A')}")
    print(f"      Titulo: {e.get('titulo', 'N/A')[:50]}...")

print("[OK] Test complete")
