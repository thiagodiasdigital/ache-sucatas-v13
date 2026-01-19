#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Monitora o progresso do reprocessamento.
"""

import time
from pathlib import Path
import sys

print("="*80)
print("MONITORAMENTO DO REPROCESSAMENTO")
print("="*80)
print()

csv_path = Path('analise_editais_v12.csv')
log_path = Path('auditor_v12.log')

if not csv_path.exists():
    print("[AVISO] CSV ainda nao foi criado. Aguardando inicio...")
    print()

print("Monitorando progresso a cada 30 segundos...")
print("Pressione Ctrl+C para sair (o processamento continuara)")
print()

tamanho_anterior = 0
ultima_modificacao = None

try:
    while True:
        # Verificar tamanho do CSV
        if csv_path.exists():
            stat = csv_path.stat()
            tamanho_atual = stat.st_size
            mod_time = stat.st_mtime

            if tamanho_atual != tamanho_anterior:
                # Contar linhas no CSV
                try:
                    with open(csv_path, 'r', encoding='utf-8-sig') as f:
                        linhas = sum(1 for _ in f)
                    editais_processados = linhas - 1  # Menos o cabeçalho

                    print(f"[{time.strftime('%H:%M:%S')}] Progresso: {editais_processados}/198 editais processados ({tamanho_atual:,} bytes)")

                    tamanho_anterior = tamanho_atual
                    ultima_modificacao = mod_time
                except:
                    print(f"[{time.strftime('%H:%M:%S')}] CSV em processo de escrita...")

        # Verificar log se existir
        if log_path.exists():
            try:
                with open(log_path, 'r', encoding='utf-8') as f:
                    linhas = f.readlines()
                    if linhas:
                        ultima_linha = linhas[-1].strip()
                        if ultima_linha:
                            print(f"  Log: {ultima_linha[:70]}")
            except:
                pass

        time.sleep(30)

except KeyboardInterrupt:
    print()
    print("="*80)
    print("Monitoramento encerrado.")
    print("O reprocessamento continua em execucao.")
    print("="*80)
