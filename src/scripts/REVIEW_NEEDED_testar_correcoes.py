#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Testar Correções V12 - Processar 5 editais para validar
"""

import sys
sys.path.insert(0, '.')

import local_auditor_v12_final as v12

print("="*70)
print("TESTE DE CORREÇÕES CRÍTICAS V12")
print("="*70)

# Listar editais
editais = v12.listar_pastas_editais(v12.PASTA_EDITAIS)
print(f"\n[INFO] Total de editais: {len(editais)}")
print(f"[INFO] Testando primeiros 5 editais...\n")

resultados = []
for i, pasta in enumerate(editais[:5], 1):
    print(f"\n{'='*70}")
    print(f"[{i}/5] Processando: {pasta.relative_to(v12.PASTA_EDITAIS)}")
    print(f"{'='*70}")

    try:
        resultado = v12.processar_edital(pasta)

        if resultado:
            resultados.append(resultado)

            # Mostrar campos críticos
            print(f"\n[RESULTADOS]")
            print(f"  data_leilao: {resultado.get('data_leilao', 'N/D')}")
            print(f"  link_pncp: {resultado.get('link_pncp', 'N/D')}")
            print(f"  tags: {resultado.get('tags', 'N/D')[:60]}")
            print(f"  modalidade: {resultado.get('modalidade_leilao', 'N/D')}")

            # Validar link_pncp format
            link = resultado.get('link_pncp', '')
            if '/editais/' in link:
                partes = link.split('/editais/')[1].split('/')
                if len(partes) == 3:
                    print(f"  [OK] link_pncp no formato correto: /{partes[0]}/{partes[1]}/{partes[2]}")
                else:
                    print(f"  [ERRO] link_pncp formato incorreto")

    except Exception as e:
        print(f"[ERRO] {type(e).__name__}: {e}")
        import traceback
        traceback.print_exc()

# Estatísticas
print(f"\n{'='*70}")
print(f"ESTATÍSTICAS DO TESTE")
print(f"{'='*70}")

datas_ok = sum(1 for r in resultados if r.get('data_leilao', 'N/D') != 'N/D')
links_ok = sum(1 for r in resultados if '/editais/' in r.get('link_pncp', '') and
               len(r.get('link_pncp', '').split('/editais/')[1].split('/')) == 3)

print(f"Editais processados: {len(resultados)}/5")
print(f"data_leilao preenchida: {datas_ok}/{len(resultados)} ({datas_ok/len(resultados)*100:.1f}%)")
print(f"link_pncp formato correto: {links_ok}/{len(resultados)} ({links_ok/len(resultados)*100:.1f}%)")

if datas_ok >= 4:
    print(f"\n[OK] data_leilao: CORREÇÃO FUNCIONANDO! ({datas_ok}/5)")
else:
    print(f"\n[AVISO] data_leilao: Ainda precisa melhorias ({datas_ok}/5)")

if links_ok >= 4:
    print(f"[OK] link_pncp: CORREÇÃO FUNCIONANDO! ({links_ok}/5)")
else:
    print(f"[AVISO] link_pncp: Ainda precisa melhorias ({links_ok}/5)")

print("="*70)

if datas_ok >= 4 and links_ok >= 4:
    print("\n[SUCESSO] Correções validadas! Pode reprocessar todos os editais.")
    print("[COMANDO] python local_auditor_v12_final.py")
else:
    print("\n[ATENÇÃO] Correções precisam de ajustes antes do reprocessamento completo.")
