#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Reprocessa todos os 198 editais com as APIs integradas:
- data_leilao via API PNCP
- valor_estimado via API PNCP
"""

import shutil
from datetime import datetime
from pathlib import Path
import subprocess
import sys

print("="*80)
print("REPROCESSAMENTO COM APIS INTEGRADAS")
print("="*80)
print()

# 1. Fazer backup dos arquivos atuais
print("[1/3] Fazendo backup dos arquivos atuais...")

timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
backup_dir = Path(f"backup_antes_reprocessamento_{timestamp}")
backup_dir.mkdir(exist_ok=True)

arquivos_backup = [
    'analise_editais_v12.csv',
    'RESULTADO_FINAL.xlsx'
]

for arquivo in arquivos_backup:
    if Path(arquivo).exists():
        shutil.copy2(arquivo, backup_dir / arquivo)
        print(f"  [OK] {arquivo} -> {backup_dir / arquivo}")

print(f"\nBackup criado em: {backup_dir}")
print()

# 2. Confirmar com usuário
print("="*80)
print("CONFIRMACAO")
print("="*80)
print()
print("Voce esta prestes a reprocessar TODOS os 198 editais.")
print()
print("Melhorias esperadas:")
print("  - data_leilao:     100% -> 100% (mantido via API)")
print("  - valor_estimado:  9.6% -> 100% (via API)")
print()
print("Tempo estimado: 20-25 minutos")
print("(~1 requisicao API por edital)")
print()

resposta = input("Deseja continuar? (s/n): ").strip().lower()

if resposta != 's':
    print("\n[CANCELADO] Reprocessamento cancelado pelo usuario.")
    sys.exit(0)

print()
print("="*80)
print("[2/3] Reprocessando editais...")
print("="*80)
print()

# 3. Executar auditor
try:
    resultado = subprocess.run(
        [sys.executable, 'local_auditor_v12_final.py'],
        capture_output=False,
        text=True,
        timeout=1800  # 30 minutos timeout
    )

    if resultado.returncode == 0:
        print()
        print("="*80)
        print("[3/3] Reprocessamento CONCLUIDO!")
        print("="*80)
        print()
        print("Arquivos gerados:")
        print("  - analise_editais_v12.csv (atualizado)")
        print("  - RESULTADO_FINAL.xlsx (atualizado)")
        print()
        print(f"Backup dos arquivos antigos: {backup_dir}")
        print()
        print("="*80)
    else:
        print()
        print(f"[ERRO] Auditor finalizou com codigo {resultado.returncode}")

except subprocess.TimeoutExpired:
    print()
    print("[ERRO] Timeout - processo levou mais de 30 minutos")
except KeyboardInterrupt:
    print()
    print("[CANCELADO] Reprocessamento interrompido pelo usuario")
except Exception as e:
    print()
    print(f"[ERRO] {str(e)}")
