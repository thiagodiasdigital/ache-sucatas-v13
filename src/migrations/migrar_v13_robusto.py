#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Migração V13 ROBUSTA - continua mesmo com erros
"""
import sys
if sys.platform == 'win32':
    sys.stdout.reconfigure(encoding='utf-8')

from pathlib import Path
from local_auditor_v13 import (
    listar_pastas_editais,
    processar_edital,
    PASTA_EDITAIS,
    salvar_csv,
    salvar_resultado_final
)
from supabase_repository import SupabaseRepository

print("=" * 60)
print("MIGRACAO V13 ROBUSTA - COM TRATAMENTO DE ERROS")
print("=" * 60)

# Inicializar Supabase
print("\n[1] Inicializando Supabase...")
repo = SupabaseRepository(enable_supabase=True)

if not repo.enable_supabase:
    print("[ERRO] Supabase nao conectado!")
    sys.exit(1)

print(f"[OK] Supabase conectado")
count_inicial = repo.contar_editais()
print(f"[INFO] Editais no banco antes: {count_inicial}")

# Listar editais
print(f"\n[2] Listando editais em: {PASTA_EDITAIS}")
pastas = listar_pastas_editais(PASTA_EDITAIS)
print(f"[INFO] Total disponivel: {len(pastas)}")

# Processar COM tratamento de erro
print(f"\n[3] Processando {len(pastas)} editais...")

resultados = []
erros = []

for i, pasta in enumerate(pastas, 1):
    print(f"\n[{i}/{len(pastas)}] {pasta.name[:60]}...")

    try:
        dados = processar_edital(pasta)

        if dados:
            resultados.append(dados)
            print(f"  [OK] Extraido: {dados.get('titulo', 'N/D')[:50]}...")
        else:
            print(f"  [AVISO] Sem dados extraidos")
            erros.append((i, pasta.name, "Sem dados"))

    except KeyboardInterrupt:
        print(f"\n[INFO] Interrompido pelo usuario")
        break

    except Exception as e:
        print(f"  [ERRO] {type(e).__name__}: {str(e)[:100]}")
        erros.append((i, pasta.name, str(e)[:200]))
        # CONTINUAR para proximo edital

print(f"\n[4] Processamento concluido!")
print(f"  - Sucesso: {len(resultados)}")
print(f"  - Erros: {len(erros)}")

# Persistir no Supabase
if repo.enable_supabase and resultados:
    print(f"\n[5] Persistindo {len(resultados)} editais no Supabase...")

    sucessos = 0
    falhas = 0

    for i, edital in enumerate(resultados, 1):
        try:
            sucesso = repo.inserir_edital(edital)

            if sucesso:
                sucessos += 1
            else:
                falhas += 1

            if i % 20 == 0:
                print(f"  [{i}/{len(resultados)}] OK: {sucessos}, Falhas: {falhas}")

        except KeyboardInterrupt:
            print(f"\n[INFO] Persistencia interrompida")
            break

        except Exception as e:
            print(f"  [ERRO ao persistir] {edital.get('id_interno')}: {e}")
            falhas += 1
            # CONTINUAR

    print(f"\n[OK] Supabase:")
    print(f"  - Inseridos/atualizados: {sucessos}")
    print(f"  - Falhas: {falhas}")

# Salvar backup local
print(f"\n[6] Salvando backups locais...")
try:
    salvar_csv(resultados)
    print(f"  [OK] CSV salvo")
except Exception as e:
    print(f"  [ERRO CSV] {e}")

try:
    salvar_resultado_final(resultados)
    print(f"  [OK] XLSX salvo")
except Exception as e:
    print(f"  [ERRO XLSX] {e}")

# Resultado final
count_final = repo.contar_editais()

print(f"\n{'='*60}")
print("RESULTADO DA MIGRACAO")
print(f"{'='*60}")
print(f"Editais processados: {len(resultados)}")
print(f"Erros durante processamento: {len(erros)}")
print(f"\nSupabase:")
print(f"  - Antes: {count_inicial}")
print(f"  - Depois: {count_final}")
print(f"  - Diferenca: +{count_final - count_inicial}")

# Listar erros (se houver)
if erros:
    print(f"\n{'='*60}")
    print("EDITAIS COM ERRO:")
    print(f"{'='*60}")
    for idx, nome, erro in erros[:10]:  # Mostrar primeiro 10
        print(f"[{idx}] {nome}")
        print(f"    Erro: {erro[:100]}...")

    if len(erros) > 10:
        print(f"\n... e mais {len(erros) - 10} erros")

print(f"\n{'='*60}")
print("[OK] MIGRACAO CONCLUIDA!")
print(f"{'='*60}")
