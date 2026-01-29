#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
ACHE SUCATAS - Diagnostico de Qualidade de Links
================================================
Script para gerar relatorio de qualidade dos links de leiloeiros.

Uso:
    python scripts/diagnostico_qualidade_links.py

Output:
    - Estatisticas gerais (total, com_link, sem_link, validos, invalidos)
    - Distribuicao por origem_tipo
    - Lista dos 5 links invalidos
    - Lista dos 11 sem link
    - Recomendacoes de acao

Data: 2026-01-27
"""

import os
import sys
from datetime import datetime
from pathlib import Path

# Adicionar path do projeto
sys.path.insert(0, str(Path(__file__).parent.parent / "src" / "core"))

from dotenv import load_dotenv
load_dotenv()


def main():
    """Executa diagnostico de qualidade de links."""
    print("=" * 70)
    print("ACHE SUCATAS - DIAGNOSTICO DE QUALIDADE DE LINKS")
    print(f"Data: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 70)
    print()

    # Conectar ao Supabase
    supabase_url = os.environ.get("SUPABASE_URL")
    supabase_key = os.environ.get("SUPABASE_SERVICE_KEY", os.environ.get("SUPABASE_KEY"))

    if not supabase_url or not supabase_key:
        print("[ERRO] Credenciais Supabase nao configuradas")
        print("       Configure SUPABASE_URL e SUPABASE_SERVICE_KEY no .env")
        return 1

    try:
        from supabase import create_client
        client = create_client(supabase_url, supabase_key)
    except Exception as e:
        print(f"[ERRO] Falha ao conectar Supabase: {e}")
        return 1

    print("[1/5] ESTATISTICAS GERAIS")
    print("-" * 70)

    # Query principal de estatisticas
    try:
        total_resp = client.table("editais_leilao").select("id", count="exact").execute()
        total = total_resp.count

        com_link_resp = client.table("editais_leilao").select("id", count="exact").not_.is_("link_leiloeiro", "null").neq("link_leiloeiro", "N/D").execute()
        com_link = com_link_resp.count

        sem_link = total - com_link

        com_link_valido_resp = client.table("editais_leilao").select("id", count="exact").eq("link_leiloeiro_valido", True).execute()
        com_link_valido = com_link_valido_resp.count

        links_invalidos = com_link - com_link_valido

        print(f"   Total de editais:      {total:4d}")
        print(f"   Com link_leiloeiro:    {com_link:4d} ({100*com_link/total:.1f}%)")
        print(f"   Sem link_leiloeiro:    {sem_link:4d} ({100*sem_link/total:.1f}%)")
        print(f"   Links validos:         {com_link_valido:4d} ({100*com_link_valido/total:.1f}%)")
        print(f"   Links invalidos:       {links_invalidos:4d} ({100*links_invalidos/total:.1f}%)")
        print()

    except Exception as e:
        print(f"[ERRO] Falha ao obter estatisticas: {e}")
        return 1

    print("[2/5] DISTRIBUICAO POR ORIGEM_TIPO")
    print("-" * 70)

    try:
        # Buscar todos os editais para calcular distribuicao
        editais_resp = client.table("editais_leilao").select("link_leiloeiro_origem_tipo").execute()
        editais = editais_resp.data

        # Contar por origem
        origem_counts = {}
        for e in editais:
            origem = e.get("link_leiloeiro_origem_tipo") or "NULL"
            origem_counts[origem] = origem_counts.get(origem, 0) + 1

        # Ordenar por contagem
        for origem, count in sorted(origem_counts.items(), key=lambda x: -x[1]):
            pct = 100 * count / total
            print(f"   {origem:25s}  {count:4d}  ({pct:5.1f}%)")

        origem_unknown = origem_counts.get("unknown", 0) + origem_counts.get("NULL", 0)
        print()
        print(f"   [!] origem_unknown + NULL = {origem_unknown} (meta: <= {sem_link + 10})")

    except Exception as e:
        print(f"[ERRO] Falha ao obter distribuicao: {e}")

    print()
    print("[3/5] LINKS INVALIDOS (link preenchido mas invalido)")
    print("-" * 70)

    try:
        invalidos_resp = client.table("editais_leilao").select(
            "id_interno, pncp_id, link_leiloeiro, link_leiloeiro_valido, link_leiloeiro_origem_tipo, link_leiloeiro_confianca"
        ).not_.is_("link_leiloeiro", "null").neq("link_leiloeiro", "N/D").neq("link_leiloeiro_valido", True).limit(20).execute()

        invalidos = invalidos_resp.data
        print(f"   Encontrados: {len(invalidos)} links invalidos")
        print()

        if invalidos:
            for i, inv in enumerate(invalidos, 1):
                print(f"   {i}. ID Interno: {inv.get('id_interno', '?')}")
                print(f"      PNCP ID: {inv.get('pncp_id', '?')}")
                print(f"      Link: {inv.get('link_leiloeiro', '?')[:60]}...")
                print(f"      Valido: {inv.get('link_leiloeiro_valido')}")
                print(f"      Origem: {inv.get('link_leiloeiro_origem_tipo')}")
                print(f"      Confianca: {inv.get('link_leiloeiro_confianca')}")
                print()
        else:
            print("   Nenhum link invalido encontrado!")

    except Exception as e:
        print(f"[ERRO] Falha ao obter links invalidos: {e}")

    print()
    print("[4/5] EDITAIS SEM LINK")
    print("-" * 70)

    try:
        sem_link_resp = client.table("editais_leilao").select(
            "id_interno, pncp_id, data_leilao, orgao, uf, auditor_v19_result"
        ).or_("link_leiloeiro.is.null,link_leiloeiro.eq.N/D").limit(20).execute()

        sem_links = sem_link_resp.data
        print(f"   Encontrados: {len(sem_links)} editais sem link")
        print()

        if sem_links:
            for i, sl in enumerate(sem_links, 1):
                print(f"   {i}. ID Interno: {sl.get('id_interno', '?')}")
                print(f"      PNCP ID: {sl.get('pncp_id', '?')}")
                print(f"      Data Leilao: {sl.get('data_leilao', '?')}")
                print(f"      Orgao: {(sl.get('orgao') or '?')[:50]}")
                print(f"      UF: {sl.get('uf', '?')}")
                print(f"      Auditor Result: {sl.get('auditor_v19_result', 'N/A')}")
                print()
        else:
            print("   Nenhum edital sem link encontrado!")

    except Exception as e:
        print(f"[ERRO] Falha ao obter editais sem link: {e}")

    print()
    print("[5/5] RECOMENDACOES")
    print("-" * 70)

    print("""
   ACOES RECOMENDADAS:

   1. Para links INVALIDOS:
      - Verificar se sao falsos positivos (TLD colado)
      - Aplicar normalizacao (adicionar https://) se aplicavel
      - Marcar para revisao manual se necessario

   2. Para editais SEM LINK:
      - Confirmar que PDF nao contem link (auditoria manual)
      - Registrar como 'pdf_sem_link' no backlog
      - Considerar busca em outras fontes

   3. Para LINEAGE (origem_tipo):
      - Executar migration 006 para backfill
      - Verificar que origem_unknown <= sem_link + margem

   COMANDOS UTEIS:

   # Executar Auditor V19 com force (reprocessar)
   python src/core/cloud_auditor_v19.py --force --limite 50

   # Aplicar migration de backfill
   # (executar no Supabase Dashboard ou via psql)
   # sql/migrations/006_backfill_link_leiloeiro_origem.sql
""")

    print("=" * 70)
    print("DIAGNOSTICO CONCLUIDO")
    print("=" * 70)

    return 0


if __name__ == "__main__":
    sys.exit(main())
