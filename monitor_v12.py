#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Monitor V12 - Acompanhamento em tempo real do processamento
"""

import re
import time
from datetime import datetime, timedelta
from pathlib import Path

def monitor():
    log_file = Path('auditor_v12.log')

    if not log_file.exists():
        print("[ERRO] auditor_v12.log não encontrado!")
        return

    print("\n" + "="*70)
    print("MONITOR V12 - PROCESSAMENTO EM TEMPO REAL")
    print("="*70)

    try:
        with open(log_file, 'r', encoding='utf-8', errors='ignore') as f:
            content = f.read()

        # Contar editais processados
        matches = re.findall(r'\[(\d+)/198\]', content)
        if matches:
            processed = int(matches[-1])
        else:
            processed = 0

        total = 198
        percent = (processed / total) * 100
        remaining = total - processed

        # Calcular tempo estimado
        avg_time_per_edital = 20  # segundos
        remaining_seconds = remaining * avg_time_per_edital
        remaining_minutes = remaining_seconds / 60
        eta = datetime.now() + timedelta(seconds=remaining_seconds)

        # Barra de progresso
        bar_length = 50
        filled = int(bar_length * processed / total)
        bar = '#' * filled + '-' * (bar_length - filled)

        print(f"\n[PROGRESSO GERAL]")
        print(f"   [{bar}] {percent:.1f}%")
        print(f"   {processed}/{total} editais processados")
        print(f"\n[ESTIMATIVAS]")
        print(f"   Restantes:     {remaining} editais")
        print(f"   Tempo medio:   ~{avg_time_per_edital}s por edital")
        print(f"   ETA:           {eta.strftime('%H:%M:%S')} ({int(remaining_minutes)} min)")

        # Mostrar últimos 5 processados
        all_matches = re.findall(r'\[(\d+)/198\] \[INFO\] Processando: (.+)', content)
        if all_matches:
            print(f"\n[ULTIMOS PROCESSADOS]")
            for num, path in all_matches[-5:]:
                estado = path.split('\\')[0].split('_')[0]
                print(f"   [{num:>3}/198] {estado}: {path.split(chr(92))[-1][:50]}")

        # Verificar se concluiu
        if 'PROCESSAMENTO CONCLUIDO' in content:
            print(f"\n[OK] PROCESSAMENTO CONCLUIDO!")
            print(f"\n[PROXIMO PASSO] Execute 'python validar_v12.py'")
        else:
            print(f"\n[INFO] Processamento em andamento...")

        print("="*70)

    except Exception as e:
        print(f"[ERRO] {e}")

if __name__ == '__main__':
    monitor()
