#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Diagnóstico: Testar RPC get_lotes_by_id_interno e estado dos dados
"""

import os
import sys
from dotenv import load_dotenv

# Carregar .env da raiz
load_dotenv()

from supabase import create_client

def main():
    url = os.getenv("SUPABASE_URL")
    key = os.getenv("SUPABASE_SERVICE_KEY")

    if not url or not key:
        print("ERRO: SUPABASE_URL ou SUPABASE_SERVICE_KEY não configurados")
        return

    client = create_client(url, key)

    print("=" * 70)
    print("DIAGNÓSTICO COMPLETO: Lotes, View e RPC")
    print("=" * 70)

    # 1. Total de lotes
    print("\n[1] Total de lotes em lotes_leilao:")
    try:
        res = client.table("lotes_leilao").select("id", count="exact").limit(1).execute()
        total_lotes = res.count if res.count else 0
        print(f"    Total: {total_lotes} lotes")
    except Exception as e:
        print(f"    ERRO: {e}")
        total_lotes = 0

    # 2. Editais distintos com lotes
    print("\n[2] Editais com lotes:")
    try:
        res = client.table("lotes_leilao").select("edital_id").execute()
        edital_ids = set(r["edital_id"] for r in res.data) if res.data else set()
        print(f"    {len(edital_ids)} editais distintos têm lotes")
    except Exception as e:
        print(f"    ERRO: {e}")
        edital_ids = set()

    # 3. Verificar VIEW - primeiros 5 editais
    print("\n[3] Primeiros 5 registros da VIEW (pub.v_auction_discovery):")
    try:
        # Simular o que o frontend faz
        res = client.rpc("fetch_auctions_paginated", {
            "p_page": 1,
            "p_page_size": 5,
            "p_temporalidade": "todos"
        }).execute()

        if res.data and res.data.get("data"):
            auctions = res.data["data"]
            print(f"    Retornados: {len(auctions)} auctions")
            print(f"\n    ID | id_interno | tem_lotes?")
            print("    " + "-" * 60)

            for a in auctions[:5]:
                aid = a.get("id")
                id_interno = a.get("id_interno", "N/A")
                tem_lotes = aid in edital_ids
                status = "SIM" if tem_lotes else "NAO"
                print(f"    {aid} | {id_interno[:40]}... | {status}")
        else:
            print("    VIEW vazia ou RPC não retornou dados")
    except Exception as e:
        print(f"    ERRO: {e}")

    # 4. Testar RPC com id_interno de edital que TEM lotes
    print("\n[4] Testando RPC com edital que TEM lotes:")
    if edital_ids:
        try:
            # Pegar id_interno do primeiro edital com lotes
            test_edital_id = list(edital_ids)[0]
            res = client.table("editais_leilao").select("id_interno").eq("id", test_edital_id).execute()

            if res.data:
                test_id_interno = res.data[0]["id_interno"]
                print(f"    Testando id_interno: {test_id_interno[:50]}...")

                # Chamar RPC
                res_rpc = client.rpc("get_lotes_by_id_interno", {"p_id_interno": test_id_interno}).execute()

                if res_rpc.data:
                    print(f"    RPC retornou: {len(res_rpc.data)} lotes")
                else:
                    print(f"    RPC retornou: 0 lotes (PROBLEMA!)")
            else:
                print(f"    edital_id={test_edital_id} não encontrado")
        except Exception as e:
            print(f"    ERRO: {e}")

    # 5. Verificar se VIEW retorna editais que têm lotes
    print("\n[5] Cruzamento: Editais na VIEW que têm lotes:")
    try:
        res = client.rpc("fetch_auctions_paginated", {
            "p_page": 1,
            "p_page_size": 100,
            "p_temporalidade": "todos"
        }).execute()

        if res.data and res.data.get("data"):
            auctions = res.data["data"]
            view_ids = set(a.get("id") for a in auctions)

            com_lotes_na_view = view_ids & edital_ids

            print(f"    Total na VIEW: {len(view_ids)}")
            print(f"    Total com lotes: {len(edital_ids)}")
            print(f"    Na VIEW E com lotes: {len(com_lotes_na_view)}")

            if com_lotes_na_view:
                print(f"\n    Exemplos de editais na VIEW que têm lotes:")
                for eid in list(com_lotes_na_view)[:3]:
                    auction = next((a for a in auctions if a.get("id") == eid), None)
                    if auction:
                        print(f"      - {auction.get('titulo', 'Sem título')[:50]}...")
                        print(f"        id_interno: {auction.get('id_interno', 'N/A')[:50]}...")
            else:
                print(f"\n    [!] NENHUM edital na VIEW tem lotes!")
                print(f"    [!] Isso pode significar que:")
                print(f"        - Os lotes foram extraídos de editais antigos")
                print(f"        - Os editais com lotes estão filtrados (data passada)")
    except Exception as e:
        print(f"    ERRO: {e}")

    print("\n" + "=" * 70)
    print("DIAGNÓSTICO CONCLUÍDO")
    print("=" * 70)

if __name__ == "__main__":
    main()
