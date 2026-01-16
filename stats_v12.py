#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Estatísticas V12 - Análise dos campos extraídos durante o processamento
"""

import re
from pathlib import Path
from collections import Counter

def analyze_log():
    log_file = Path('auditor_v12.log')

    if not log_file.exists():
        print("[ERRO] auditor_v12.log não encontrado!")
        return

    print("\n" + "="*70)
    print("ESTATÍSTICAS DE EXTRAÇÃO V12")
    print("="*70)

    with open(log_file, 'r', encoding='utf-8', errors='ignore') as f:
        content = f.read()

    # Contar editais processados
    matches = re.findall(r'\[(\d+)/198\]', content)
    if matches:
        processed = int(matches[-1])
    else:
        processed = 0

    print(f"\n[PROCESSAMENTO]")
    print(f"  Editais processados: {processed}/198 ({processed/198*100:.1f}%)")

    # Analisar campos extraídos
    extraction_lines = re.findall(r'\[OK\] Extraido: (.+)', content)

    if not extraction_lines:
        print("\n[INFO] Nenhuma extração registrada ainda.")
        return

    # Contar fontes de extração
    all_fields = []
    for line in extraction_lines:
        fields = line.split(', ')
        for field in fields:
            if '(' in field:
                field_name = field.split('(')[0]
                source = field.split('(')[1].rstrip(')').rstrip('...')
                all_fields.append((field_name, source))

    # Estatísticas por campo
    field_counter = Counter([f[0] for f in all_fields])
    source_counter = Counter([f[1] for f in all_fields])

    print(f"\n[CAMPOS MAIS EXTRAÍDOS]")
    print(f"  {'Campo':<25} {'Extrações':<10} {'Taxa':<10}")
    print(f"  {'-'*45}")
    for field, count in field_counter.most_common(10):
        taxa = (count / processed * 100) if processed > 0 else 0
        print(f"  {field:<25} {count:<10} {taxa:>5.1f}%")

    print(f"\n[FONTES DE DADOS]")
    print(f"  {'Fonte':<15} {'Extrações':<10} {'Percentual':<10}")
    print(f"  {'-'*35}")
    total_extractions = sum(source_counter.values())
    for source, count in source_counter.most_common():
        percent = (count / total_extractions * 100) if total_extractions > 0 else 0
        print(f"  {source:<15} {count:<10} {percent:>5.1f}%")

    # Análise de estados
    state_matches = re.findall(r'Processando: ([A-Z]{2})_', content)
    if state_matches:
        state_counter = Counter(state_matches)
        print(f"\n[ESTADOS PROCESSADOS]")
        print(f"  {'UF':<5} {'Editais':<10}")
        print(f"  {'-'*15}")
        for state, count in sorted(state_counter.items()):
            print(f"  {state:<5} {count:<10}")

    print("\n" + "="*70)

if __name__ == '__main__':
    analyze_log()
