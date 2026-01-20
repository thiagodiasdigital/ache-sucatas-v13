#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Diagnostico da tabela raw.leiloes via RPC
"""

import os
import sys

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

try:
    from supabase import create_client, Client
except ImportError:
    print("[ERRO] Biblioteca supabase nao instalada.")
    sys.exit(1)


def main():
    print("=" * 80)
    print("DIAGNOSTICO - raw.leiloes vs editais_leilao")
    print("=" * 80)
    print()

    supabase_url = os.getenv("SUPABASE_URL")
    supabase_key = os.getenv("SUPABASE_SERVICE_KEY")

    if not supabase_url or not supabase_key:
        print("[ERRO] Variaveis SUPABASE_URL e SUPABASE_SERVICE_KEY nao encontradas.")
        sys.exit(1)

    print("[1/4] Conectando ao Supabase...")
    supabase: Client = create_client(supabase_url, supabase_key)
    print("  [OK] Conectado")

    # 1. Verificar editais_leilao (public)
    print()
    print("[2/4] Verificando public.editais_leilao...")
    try:
        response = supabase.table("editais_leilao").select("id", count="exact").limit(0).execute()
        count_editais = response.count
        print(f"  Total: {count_editais} registros")
    except Exception as e:
        print(f"  [ERRO] {e}")
        count_editais = 0

    # 2. Verificar via RPC fetch_auctions_paginated (como o frontend faz)
    print()
    print("[3/4] Verificando via RPC fetch_auctions_paginated...")
    try:
        # Buscar primeira pagina para ver total
        response = supabase.rpc("fetch_auctions_paginated", {
            "p_limit": 1,
            "p_offset": 0
        }).execute()
        if response.data:
            # A RPC retorna um objeto com total_count
            print(f"  RPC funcionando")
        count_view = "N/A (via RPC)"
    except Exception as e:
        print(f"  [ERRO] RPC: {e}")
        count_view = 0

    # 3. Buscar TODOS os dados via RPC para analise
    print()
    print("[4/4] Analisando dados via RPC (como o frontend ve)...")
    try:
        # Buscar todos os dados (limite alto)
        response = supabase.rpc("fetch_auctions_paginated", {
            "p_limit": 1000,
            "p_offset": 0
        }).execute()
        leiloes = response.data if response.data else []

        print(f"  Total de leiloes na view: {len(leiloes)}")

        # Estatisticas
        stats = {
            "total": len(leiloes),
            "com_tag_sync": 0,
            "sem_link_leiloeiro": 0,
            "url_na_descricao": 0,
            "data_2024": 0,
            "data_passada": 0,
            "sem_data": 0,
        }

        from datetime import datetime, date
        hoje = date.today()

        for leilao in leiloes:
            # Verificar tags
            tags = leilao.get("tags", [])
            if tags:
                tags_str = str(tags).lower()
                if "sync" in tags_str or "leilao" in tags_str or "leilão" in tags_str:
                    stats["com_tag_sync"] += 1

            # Verificar link_leiloeiro
            link = leilao.get("link_leiloeiro")
            if not link or link in ["N/D", "", None]:
                stats["sem_link_leiloeiro"] += 1

                # Verificar se tem URL na descricao
                descricao = leilao.get("descricao", "") or ""
                if "http" in descricao.lower() or "www." in descricao.lower():
                    stats["url_na_descricao"] += 1

            # Verificar data_leilao
            data_leilao = leilao.get("data_leilao")
            if not data_leilao:
                stats["sem_data"] += 1
            else:
                try:
                    # Parse da data
                    if isinstance(data_leilao, str):
                        if "T" in data_leilao:
                            dt = datetime.fromisoformat(data_leilao.replace("Z", "+00:00"))
                        else:
                            dt = datetime.strptime(data_leilao, "%Y-%m-%d")
                        data = dt.date()
                    else:
                        data = data_leilao

                    if data.year == 2024:
                        stats["data_2024"] += 1
                    if data < hoje:
                        stats["data_passada"] += 1
                except:
                    pass

        print()
        print("=" * 80)
        print("RESULTADO DO DIAGNOSTICO (view do frontend)")
        print("=" * 80)
        print()
        print(f"  Total de leiloes na view: {stats['total']}")
        print(f"  ---")
        print(f"  Com tag SYNC/LEILAO: {stats['com_tag_sync']}")
        print(f"  Sem link_leiloeiro: {stats['sem_link_leiloeiro']}")
        print(f"  Com URL na descricao (recuperaveis): {stats['url_na_descricao']}")
        print(f"  ---")
        print(f"  Com data de 2024: {stats['data_2024']}")
        print(f"  Com data PASSADA (antes de hoje): {stats['data_passada']}")
        print(f"  Sem data: {stats['sem_data']}")
        print()

        # Mostrar exemplos de leiloes com tag SYNC
        if stats["com_tag_sync"] > 0:
            print("=" * 80)
            print("EXEMPLOS DE LEILOES COM TAG SYNC:")
            print("=" * 80)
            for leilao in leiloes[:20]:
                tags = leilao.get("tags", [])
                if tags:
                    tags_str = str(tags).lower()
                    if "sync" in tags_str:
                        print(f"  ID: {leilao.get('id_interno', 'N/A')[:50]}")
                        print(f"  Tags: {tags}")
                        print(f"  Orgao: {leilao.get('orgao', 'N/A')[:50]}")
                        print()

        # Mostrar exemplos de leiloes com data 2024
        if stats["data_2024"] > 0:
            print("=" * 80)
            print("EXEMPLOS DE LEILOES COM DATA 2024:")
            print("=" * 80)
            count = 0
            for leilao in leiloes:
                data_leilao = leilao.get("data_leilao")
                if data_leilao and "2024" in str(data_leilao):
                    print(f"  ID: {leilao.get('id_interno', 'N/A')[:50]}")
                    print(f"  Data: {data_leilao}")
                    print(f"  Orgao: {leilao.get('orgao', 'N/A')[:50]}")
                    print()
                    count += 1
                    if count >= 5:
                        break

        # Mostrar exemplos de leiloes sem link mas com URL na descricao
        if stats["url_na_descricao"] > 0:
            print("=" * 80)
            print("EXEMPLOS SEM LINK MAS COM URL NA DESCRICAO:")
            print("=" * 80)
            count = 0
            for leilao in leiloes:
                link = leilao.get("link_leiloeiro")
                if not link or link in ["N/D", "", None]:
                    descricao = leilao.get("descricao", "") or ""
                    if "http" in descricao.lower() or "www." in descricao.lower():
                        print(f"  ID: {leilao.get('id_interno', 'N/A')[:60]}")
                        print(f"  Orgao: {leilao.get('orgao', 'N/A')[:60]}")
                        # Encontrar URL na descricao
                        import re
                        urls = re.findall(r'https?://[^\s<>"\')\]]+|www\.[^\s<>"\')\]]+', descricao)
                        if urls:
                            print(f"  URLs encontradas: {urls[:3]}")
                        print()
                        count += 1
                        if count >= 5:
                            break

    except Exception as e:
        print(f"  [ERRO] {e}")
        import traceback
        traceback.print_exc()

    print("=" * 80)


if __name__ == "__main__":
    main()
