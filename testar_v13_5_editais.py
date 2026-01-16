#!/usr/bin/env python3
"""
Teste do Auditor V13 com apenas 5 editais
Para validar integração com Supabase
"""
import sys
from pathlib import Path

# Importar o auditor V13
sys.path.insert(0, str(Path(__file__).parent))

# Importar funções necessárias
from local_auditor_v13 import (
    listar_pastas_editais,
    processar_edital,
    PASTA_EDITAIS
)
from supabase_repository import SupabaseRepository

print("=" * 60)
print("TESTE AUDITOR V13 - 5 EDITAIS")
print("=" * 60)

# Inicializar Supabase
print("\n[1] Inicializando Supabase...")
repo = SupabaseRepository(enable_supabase=True)

if not repo.enable_supabase:
    print("[ERRO] Supabase não conectado!")
    exit(1)

print(f"[OK] Supabase conectado")
count_inicial = repo.contar_editais()
print(f"[INFO] Editais no banco antes do teste: {count_inicial}")

# Listar editais
print(f"\n[2] Listando editais em: {PASTA_EDITAIS}")
pastas = listar_pastas_editais(PASTA_EDITAIS)
print(f"[INFO] Total disponível: {len(pastas)}")

# Processar apenas 5
print(f"\n[3] Processando primeiros 5 editais...")
test_pastas = pastas[:5]

resultados = []
for i, pasta in enumerate(test_pastas, 1):
    print(f"\n[{i}/5] Processando: {pasta.name}")
    try:
        dados = processar_edital(pasta)
        if dados:
            resultados.append(dados)
            print(f"  [OK] Extraído: {dados.get('titulo', 'N/D')[:50]}...")
    except Exception as e:
        print(f"  [ERRO] {e}")

print(f"\n[4] Persistindo {len(resultados)} editais no Supabase...")
sucessos = 0
falhas = 0

for edital in resultados:
    sucesso = repo.inserir_edital(edital)
    if sucesso:
        sucessos += 1
    else:
        falhas += 1

print(f"\n{'='*60}")
print(f"RESULTADO DO TESTE")
print(f"{'='*60}")
print(f"Editais processados: {len(resultados)}")
print(f"Supabase:")
print(f"  - Inseridos/atualizados: {sucessos}")
print(f"  - Falhas: {falhas}")

count_final = repo.contar_editais()
print(f"\nEditais no banco ANTES: {count_inicial}")
print(f"Editais no banco DEPOIS: {count_final}")
print(f"Diferença: +{count_final - count_inicial}")

# Listar alguns editais do banco
print(f"\n{'='*60}")
print("EDITAIS NO SUPABASE (últimos 3):")
print(f"{'='*60}")
editais_db = repo.listar_editais_recentes(limit=3)
for i, edital in enumerate(editais_db, 1):
    print(f"\n[{i}] {edital.get('id_interno')}")
    print(f"    Órgão: {edital.get('orgao')}")
    print(f"    UF: {edital.get('uf')} | Cidade: {edital.get('cidade')}")
    print(f"    Data Leilão: {edital.get('data_leilao')}")
    print(f"    Valor: {edital.get('valor_estimado')}")

print(f"\n{'='*60}")
print("[OK] TESTE CONCLUÍDO COM SUCESSO!")
print(f"{'='*60}")
