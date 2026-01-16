#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Check Completion - Verifica se o processamento V12 foi concluído
"""

import re
from pathlib import Path

def check_completion():
    log_file = Path('auditor_v12.log')
    xlsx_file = Path('RESULTADO_FINAL.xlsx')
    csv_file = Path('analise_editais_v12.csv')

    print("\n" + "="*70)
    print("VERIFICAÇÃO DE CONCLUSÃO - AUDITOR V12")
    print("="*70)

    # Verificar log
    if not log_file.exists():
        print("\n[ERRO] auditor_v12.log não encontrado!")
        print("O processamento pode não ter iniciado.")
        return False

    with open(log_file, 'r', encoding='utf-8', errors='ignore') as f:
        content = f.read()

    # Verificar mensagem de conclusão
    if 'PROCESSAMENTO CONCLUIDO' in content:
        print("\n[OK] Processamento concluído com sucesso!")

        # Contar editais processados
        matches = re.findall(r'\[(\d+)/198\]', content)
        if matches:
            processed = int(matches[-1])
            print(f"[OK] Total processado: {processed}/198 editais")

        # Verificar arquivos de saída
        print("\n[ARQUIVOS DE SAÍDA]")

        if xlsx_file.exists():
            size_kb = xlsx_file.stat().st_size / 1024
            print(f"  [OK] RESULTADO_FINAL.xlsx ({size_kb:.1f} KB)")
        else:
            print(f"  [AVISO] RESULTADO_FINAL.xlsx não encontrado")

        if csv_file.exists():
            size_kb = csv_file.stat().st_size / 1024
            print(f"  [OK] analise_editais_v12.csv ({size_kb:.1f} KB)")
        else:
            print(f"  [AVISO] analise_editais_v12.csv não encontrado")

        print("\n" + "="*70)
        print("PRÓXIMO PASSO: Execute 'python validar_v12.py'")
        print("="*70)

        return True

    else:
        # Processamento ainda em andamento
        matches = re.findall(r'\[(\d+)/198\]', content)
        if matches:
            processed = int(matches[-1])
            percent = (processed / 198) * 100
            remaining = 198 - processed

            print(f"\n[INFO] Processamento em andamento...")
            print(f"  Progresso: {processed}/198 editais ({percent:.1f}%)")
            print(f"  Restantes: {remaining} editais")
            print(f"  Tempo estimado: ~{remaining * 20 // 60} minutos")

            # Última linha processada
            last_lines = content.strip().split('\n')[-3:]
            print(f"\n[ÚLTIMAS LINHAS DO LOG]")
            for line in last_lines:
                if line.strip():
                    print(f"  {line[:68]}")

        else:
            print("\n[INFO] Processamento iniciando...")

        print("\n" + "="*70)
        print("Execute novamente este script para verificar o status.")
        print("="*70)

        return False

if __name__ == '__main__':
    check_completion()
