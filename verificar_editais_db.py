#!/usr/bin/env python3
"""Verificar qualidade dos dados no Supabase"""
from supabase_repository import SupabaseRepository

print("="*60)
print("VERIFICACAO DE DADOS NO SUPABASE")
print("="*60)

repo = SupabaseRepository(enable_supabase=True)

if not repo.enable_supabase:
    print("[ERRO] Supabase nao conectado")
    exit(1)

count = repo.contar_editais()
print(f"\n[INFO] Total de editais no banco: {count}")

print(f"\n{'='*60}")
print("EDITAIS CADASTRADOS:")
print(f"{'='*60}")

editais = repo.listar_editais_recentes(limit=5)

for i, edital in enumerate(editais, 1):
    print(f"\n[{i}] ID Interno: {edital.get('id_interno')}")
    print(f"    PNCP ID: {edital.get('pncp_id')}")
    print(f"    Orgao: {edital.get('orgao')}")
    print(f"    UF: {edital.get('uf')} | Cidade: {edital.get('cidade')}")
    print(f"    N. Edital: {edital.get('n_edital')}")
    print(f"    Data Publicacao: {edital.get('data_publicacao')}")
    print(f"    Data Leilao: {edital.get('data_leilao')}")
    print(f"    Titulo: {edital.get('titulo', '')[:60]}...")
    print(f"    Descricao: {edital.get('descricao', '')[:80]}...")
    print(f"    Tags: {edital.get('tags', [])}")
    print(f"    Link PNCP: {edital.get('link_pncp', '')[:60]}...")
    print(f"    Link Leiloeiro: {edital.get('link_leiloeiro', 'N/A')}")
    print(f"    Modalidade: {edital.get('modalidade_leilao', 'N/A')}")
    print(f"    Valor Estimado: R$ {edital.get('valor_estimado', 'N/A')}")
    print(f"    Qtd Itens: {edital.get('quantidade_itens', 'N/A')}")
    print(f"    Leiloeiro: {edital.get('nome_leiloeiro', 'N/A')}")
    print(f"    Versao: {edital.get('versao_auditor')}")
    print(f"    Created: {edital.get('created_at', '')[:19]}")

print(f"\n{'='*60}")
print("[OK] VERIFICACAO CONCLUIDA")
print(f"{'='*60}")

# Estatisticas
print(f"\nESTATISTICAS:")
tags_all = []
for e in editais:
    tags_all.extend(e.get('tags', []))

print(f"  - Total de editais: {count}")
print(f"  - UFs representadas: {len(set(e.get('uf') for e in editais))}")
print(f"  - Tags unicas (amostra): {len(set(tags_all))}")
print(f"  - Editais com valor estimado: {sum(1 for e in editais if e.get('valor_estimado'))}")
print(f"  - Editais com link leiloeiro: {sum(1 for e in editais if e.get('link_leiloeiro'))}")
