#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Corrige leilao com UF invalida (XX -> MG para Carmo de Minas).

Uso:
    python corrigir_uf_invalida.py
"""

import os
import sys
from dotenv import load_dotenv

load_dotenv()


def get_supabase_client():
    """Cria cliente Supabase."""
    from supabase import create_client

    url = os.getenv("SUPABASE_URL")
    key = os.getenv("SUPABASE_SERVICE_KEY") or os.getenv("SUPABASE_SERVICE_ROLE_KEY")

    if not url or not key:
        print("ERRO: SUPABASE_URL e SUPABASE_SERVICE_KEY necessarios no .env")
        sys.exit(1)

    return create_client(url, key)


def main():
    print("=" * 60)
    print("CORRECAO DE UF INVALIDA")
    print("=" * 60)
    print()

    supabase = get_supabase_client()

    # 1. Buscar leilao com UF = XX e cidade = Carmo de Minas
    print("[1/3] Buscando leilao com UF invalida...")

    response = supabase.table("editais_leilao").select(
        "id, id_interno, pncp_id, cidade, uf, orgao, titulo"
    ).eq("uf", "XX").execute()

    leiloes = response.data or []

    if not leiloes:
        print("      Nenhum leilao com UF = 'XX' encontrado.")
        print("      Ja pode ter sido corrigido anteriormente.")
        return 0

    print(f"      Encontrado(s) {len(leiloes)} leilao(es) com UF invalida:")
    print()

    for l in leiloes:
        print(f"      ID: {l['id']}")
        print(f"      ID Interno: {l['id_interno']}")
        print(f"      PNCP ID: {l['pncp_id']}")
        print(f"      Cidade: {l['cidade']}")
        print(f"      UF atual: {l['uf']}")
        print(f"      Orgao: {l['orgao'][:60]}..." if l.get('orgao') and len(l.get('orgao', '')) > 60 else f"      Orgao: {l.get('orgao')}")
        print()

    # 2. Confirmar que Carmo de Minas e de MG
    print("[2/3] Verificando UF correta para 'Carmo de Minas'...")

    # Carmo de Minas e um municipio de Minas Gerais (MG)
    # Codigo IBGE: 3114105
    uf_correta = "MG"
    print(f"      Carmo de Minas -> UF correta: {uf_correta}")
    print()

    # 3. Corrigir
    print("[3/3] Aplicando correcao...")

    for l in leiloes:
        if l['cidade'] and 'carmo' in l['cidade'].lower() and 'minas' in l['cidade'].lower():
            # Corrigir UF
            update_resp = supabase.table("editais_leilao").update({
                "uf": uf_correta
            }).eq("id", l['id']).execute()

            if update_resp.data:
                print(f"      [OK] Leilao ID {l['id']} corrigido: XX -> {uf_correta}")

                # Tambem atualizar o id_interno se necessario
                if l['id_interno'] and l['id_interno'].startswith('XX_'):
                    novo_id_interno = l['id_interno'].replace('XX_', f'{uf_correta}_', 1)
                    supabase.table("editais_leilao").update({
                        "id_interno": novo_id_interno
                    }).eq("id", l['id']).execute()
                    print(f"      [OK] ID interno atualizado: {novo_id_interno}")
            else:
                print(f"      [ERRO] Falha ao corrigir leilao ID {l['id']}")
        else:
            print(f"      [SKIP] Leilao ID {l['id']} - cidade '{l['cidade']}' nao e Carmo de Minas")

    print()
    print("=" * 60)
    print("CORRECAO CONCLUIDA")
    print("=" * 60)

    return 0


if __name__ == "__main__":
    sys.exit(main())
