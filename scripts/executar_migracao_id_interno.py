#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Executa migração de id_interno para formato padrão ID_XXXXXXXXXXXX

Este script:
1. Busca todos os registros com formato errado
2. Gera novos IDs no formato correto
3. Atualiza editais_leilao via API
4. Gera SQL para raw.leiloes (precisa ser executado manualmente)
"""

import os
import sys
import uuid
import json
from datetime import datetime
from dotenv import load_dotenv

load_dotenv()

from supabase import create_client


def gerar_novo_id() -> str:
    """Gera id_interno no formato padrão: ID_XXXXXXXXXXXX"""
    return f"ID_{uuid.uuid4().hex[:12].upper()}"


def main():
    url = os.getenv("SUPABASE_URL")
    key = os.getenv("SUPABASE_SERVICE_KEY")

    if not url or not key:
        print("ERRO: Variáveis de ambiente não configuradas")
        return False

    client = create_client(url, key)

    print("=" * 70)
    print("MIGRAÇÃO: id_interno -> formato ID_XXXXXXXXXXXX")
    print(f"Iniciado: {datetime.now().isoformat()}")
    print("=" * 70)

    # 1. Buscar registros com formato errado
    print("\n[1] Buscando registros em editais_leilao...")

    res = client.table("editais_leilao").select("id, id_interno").execute()

    if not res.data:
        print("    Nenhum registro encontrado")
        return False

    # Filtrar apenas os que NÃO começam com ID_
    registros_errados = [
        r for r in res.data
        if r['id_interno'] and not r['id_interno'].startswith('ID_')
    ]

    print(f"    Total: {len(res.data)}")
    print(f"    Com formato errado: {len(registros_errados)}")

    if not registros_errados:
        print("\n    Todos os registros já estão no formato correto!")
        return True

    # 2. Gerar mapeamento
    print("\n[2] Gerando novos IDs...")

    mapeamento = {}
    for r in registros_errados:
        old_id = r['id_interno']
        new_id = gerar_novo_id()
        mapeamento[old_id] = {
            'db_id': r['id'],
            'new_id': new_id
        }

    print(f"    {len(mapeamento)} IDs gerados")

    # 3. Atualizar editais_leilao
    print("\n[3] Atualizando editais_leilao...")

    sucesso = 0
    erros = []

    for i, (old_id, info) in enumerate(mapeamento.items()):
        try:
            client.table("editais_leilao").update({
                "id_interno": info['new_id']
            }).eq("id", info['db_id']).execute()

            sucesso += 1

            if (i + 1) % 25 == 0:
                print(f"    Progresso: {i + 1}/{len(mapeamento)}")

        except Exception as e:
            erros.append(f"id={info['db_id']}: {e}")

    print(f"    Concluído: {sucesso} atualizados, {len(erros)} erros")

    if erros:
        print(f"\n    Erros:")
        for e in erros[:5]:
            print(f"      - {e}")

    # 4. Gerar SQL para raw.leiloes
    print("\n[4] Gerando SQL para raw.leiloes...")

    sql_file = "migration_raw_leiloes_id_interno.sql"
    with open(sql_file, "w", encoding="utf-8") as f:
        f.write("-- ============================================\n")
        f.write("-- MIGRAÇÃO: Atualizar id_interno em raw.leiloes\n")
        f.write(f"-- Gerado: {datetime.now().isoformat()}\n")
        f.write("-- IMPORTANTE: Execute este SQL no Supabase SQL Editor\n")
        f.write("-- ============================================\n\n")
        f.write("BEGIN;\n\n")

        for old_id, info in mapeamento.items():
            old_escaped = old_id.replace("'", "''")
            f.write(f"UPDATE raw.leiloes SET id_interno = '{info['new_id']}' WHERE id_interno = '{old_escaped}';\n")

        f.write("\nCOMMIT;\n")
        f.write("\n-- Verificar resultado:\n")
        f.write("-- SELECT id_interno FROM raw.leiloes WHERE id_interno NOT LIKE 'ID_%' LIMIT 10;\n")

    print(f"    SQL salvo em: {sql_file}")

    # 5. Salvar mapeamento
    map_file = f"id_mapping_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    with open(map_file, "w", encoding="utf-8") as f:
        json.dump(mapeamento, f, indent=2, ensure_ascii=False)

    print(f"\n[5] Mapeamento salvo em: {map_file}")

    # Resumo
    print("\n" + "=" * 70)
    print("RESUMO DA MIGRAÇÃO")
    print("=" * 70)
    print(f"  editais_leilao: {sucesso} atualizados")
    print(f"  raw.leiloes: Execute o arquivo {sql_file} no Supabase SQL Editor")
    print("=" * 70)

    return True


if __name__ == "__main__":
    main()
