#!/usr/bin/env python3
"""Teste rápido V13 - com output imediato"""
import sys
sys.stdout.reconfigure(encoding='utf-8')

print("="*60)
print("TESTE RAPIDO V13")
print("="*60)

# Test 1: Supabase connection
print("\n[1] Testando Supabase...")
try:
    from supabase_repository import SupabaseRepository
    repo = SupabaseRepository(enable_supabase=True)

    if repo.enable_supabase:
        print("  [OK] Conectado")
        count = repo.contar_editais()
        print(f"  [INFO] Editais no banco: {count}")
    else:
        print("  [ERRO] Nao conectado")
        sys.exit(1)
except Exception as e:
    print(f"  [ERRO] {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)

# Test 2: Load editals list
print("\n[2] Listando editais...")
try:
    from local_auditor_v13 import listar_pastas_editais, PASTA_EDITAIS
    pastas = listar_pastas_editais(PASTA_EDITAIS)
    print(f"  [OK] {len(pastas)} editais encontrados")
    print(f"  [INFO] Processando apenas 2 para teste rapido...")
except Exception as e:
    print(f"  [ERRO] {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)

# Test 3: Process 2 editals
print("\n[3] Processando editais...")
test_pastas = pastas[:2]

from local_auditor_v13 import processar_edital

for i, pasta in enumerate(test_pastas, 1):
    print(f"\n  [{i}/2] {pasta.name[:50]}...")
    try:
        dados = processar_edital(pasta)
        if dados:
            print(f"    [OK] Titulo: {dados.get('titulo', 'N/D')[:40]}...")
            print(f"    [OK] Orgao: {dados.get('orgao', 'N/D')}")

            # Try to insert
            print(f"    [DB] Inserindo no Supabase...")
            sucesso = repo.inserir_edital(dados)
            if sucesso:
                print(f"    [OK] Inserido com sucesso")
            else:
                print(f"    [AVISO] Falha ao inserir (pode ja existir)")
        else:
            print(f"    [ERRO] Nao extraiu dados")
    except Exception as e:
        print(f"    [ERRO] {e}")
        import traceback
        traceback.print_exc()

# Final count
print("\n[4] Contagem final...")
count_final = repo.contar_editais()
print(f"  [INFO] Editais no banco agora: {count_final}")

print("\n" + "="*60)
print("[OK] TESTE RAPIDO CONCLUIDO")
print("="*60)
