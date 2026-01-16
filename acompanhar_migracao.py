#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Acompanha progresso da migração em tempo real
"""
import sys
if sys.platform == 'win32':
    sys.stdout.reconfigure(encoding='utf-8')

import time
from supabase_repository import SupabaseRepository

print("=" * 60)
print("ACOMPANHAMENTO MIGRACAO V13")
print("=" * 60)
print("\nMonitorando insercoes no Supabase a cada 20 segundos...")
print("Pressione Ctrl+C para parar\n")

repo = SupabaseRepository(enable_supabase=True)

if not repo.enable_supabase:
    print("[ERRO] Supabase nao conectado")
    sys.exit(1)

count_anterior = repo.contar_editais()
inicio = time.time()

print(f"[{time.strftime('%H:%M:%S')}] Inicio: {count_anterior} editais")

try:
    while True:
        time.sleep(20)
        count_atual = repo.contar_editais()

        if count_atual != count_anterior:
            diferenca = count_atual - count_anterior
            progresso_pct = (count_atual / 198) * 100
            tempo_decorrido = int(time.time() - inicio)

            # Estimar tempo restante
            if count_atual > count_anterior:
                taxa = count_atual / tempo_decorrido  # editais/segundo
                restantes = 198 - count_atual
                tempo_restante_seg = int(restantes / taxa) if taxa > 0 else 0
                tempo_restante_min = tempo_restante_seg // 60

                print(f"[{time.strftime('%H:%M:%S')}] {count_atual}/198 ({progresso_pct:.1f}%) | +{diferenca} | ETA: ~{tempo_restante_min}min")

            count_anterior = count_atual

            # Se chegou em 198, concluiu
            if count_atual >= 198:
                print(f"\n[OK] MIGRACAO COMPLETA!")
                print(f"Total: {count_atual} editais")
                print(f"Tempo total: {tempo_decorrido//60}min {tempo_decorrido%60}s")
                break
        else:
            # Sem mudança
            print(f"[{time.strftime('%H:%M:%S')}] {count_atual}/198 ({(count_atual/198)*100:.1f}%) - processando...")

except KeyboardInterrupt:
    print(f"\n[INFO] Monitor interrompido")
    count_final = repo.contar_editais()
    tempo_total = int(time.time() - inicio)
    print(f"[INFO] Progresso atual: {count_final}/198 ({(count_final/198)*100:.1f}%)")
    print(f"[INFO] Tempo decorrido: {tempo_total//60}min {tempo_total%60}s")
