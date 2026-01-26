#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Migração: Padronizar id_interno para formato ID_XXXXXXXXXXXX

Problema: Existem dois formatos de id_interno:
  - Formato CORRETO: ID_FFC584EA30FA (12 chars hex)
  - Formato ERRADO: UF_CIDADE_CNPJ-...

Solução: Converter todos para o formato ID_XXXX usando UUID.

Tabelas afetadas:
  - editais_leilao (public)
  - raw.leiloes (via SQL direto)

IMPORTANTE: Mantém mapeamento old_id -> new_id para rastreabilidade.
"""

import os
import sys
import uuid
from datetime import datetime
from dotenv import load_dotenv

load_dotenv()

from supabase import create_client


def gerar_novo_id_interno() -> str:
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
    print("MIGRAÇÃO: Padronizar id_interno para formato ID_XXXXXXXXXXXX")
    print(f"Executado em: {datetime.now().isoformat()}")
    print("=" * 70)

    # 1. Buscar todos os registros com formato errado em editais_leilao
    print("\n[1] Buscando registros com formato incorreto em editais_leilao...")

    res = client.table("editais_leilao").select("id, id_interno").execute()

    if not res.data:
        print("    Nenhum registro encontrado")
        return False

    # Filtrar apenas os que NÃO começam com ID_
    registros_errados = [
        r for r in res.data
        if r['id_interno'] and not r['id_interno'].startswith('ID_')
    ]

    print(f"    Total de registros: {len(res.data)}")
    print(f"    Registros com formato incorreto: {len(registros_errados)}")

    if not registros_errados:
        print("    Nenhum registro precisa ser migrado!")
        return True

    # 2. Gerar mapeamento old -> new
    print("\n[2] Gerando novos id_interno...")

    mapeamento = {}
    for r in registros_errados:
        old_id = r['id_interno']
        new_id = gerar_novo_id_interno()
        mapeamento[old_id] = {
            'db_id': r['id'],
            'new_id_interno': new_id
        }

    print(f"    Gerados {len(mapeamento)} novos IDs")

    # Mostrar amostra
    print("\n    Amostra do mapeamento:")
    for old_id, info in list(mapeamento.items())[:3]:
        print(f"      {old_id[:40]}... -> {info['new_id_interno']}")

    # 3. Confirmar execução
    print("\n" + "=" * 70)
    print("ATENÇÃO: Esta operação irá atualizar:")
    print(f"  - {len(registros_errados)} registros em editais_leilao")
    print(f"  - {len(registros_errados)} registros em raw.leiloes (via SQL)")
    print("=" * 70)

    confirmacao = input("\nDigite 'MIGRAR' para confirmar: ")
    if confirmacao != "MIGRAR":
        print("Operação cancelada pelo usuário")
        return False

    # 4. Executar migração em editais_leilao
    print("\n[3] Atualizando editais_leilao...")

    sucesso = 0
    erros = 0

    for old_id, info in mapeamento.items():
        try:
            client.table("editais_leilao").update({
                "id_interno": info['new_id_interno']
            }).eq("id", info['db_id']).execute()

            sucesso += 1
            if sucesso % 50 == 0:
                print(f"    Progresso: {sucesso}/{len(mapeamento)}")

        except Exception as e:
            print(f"    ERRO ao atualizar id={info['db_id']}: {e}")
            erros += 1

    print(f"    Concluído: {sucesso} atualizados, {erros} erros")

    # 5. Executar migração em raw.leiloes via SQL direto
    print("\n[4] Atualizando raw.leiloes via SQL...")

    # Construir SQL para atualização em batch
    sucesso_raw = 0
    erros_raw = 0

    for old_id, info in mapeamento.items():
        try:
            # Usar RPC ou query direta para raw schema
            client.rpc("update_raw_leiloes_id_interno", {
                "p_old_id": old_id,
                "p_new_id": info['new_id_interno']
            }).execute()

            sucesso_raw += 1
            if sucesso_raw % 50 == 0:
                print(f"    Progresso raw.leiloes: {sucesso_raw}/{len(mapeamento)}")

        except Exception as e:
            # Se RPC não existe, tentar via postgREST direto
            # Note: raw schema pode não ser acessível via API
            erros_raw += 1

    if erros_raw > 0:
        print(f"\n    AVISO: raw.leiloes precisa ser atualizado via SQL direto.")
        print(f"    Execute o SQL abaixo no Supabase SQL Editor:\n")

        # Gerar SQL para execução manual
        print("    -- SQL para atualizar raw.leiloes")
        for old_id, info in list(mapeamento.items())[:5]:
            sql = f"UPDATE raw.leiloes SET id_interno = '{info['new_id_interno']}' WHERE id_interno = '{old_id}';"
            print(f"    {sql}")
        print("    -- ... (mais registros)")

        # Salvar SQL completo em arquivo
        sql_file = "migration_raw_leiloes.sql"
        with open(sql_file, "w", encoding="utf-8") as f:
            f.write("-- Migração de id_interno para raw.leiloes\n")
            f.write(f"-- Gerado em: {datetime.now().isoformat()}\n\n")
            f.write("BEGIN;\n\n")
            for old_id, info in mapeamento.items():
                # Escapar aspas simples
                old_id_escaped = old_id.replace("'", "''")
                f.write(f"UPDATE raw.leiloes SET id_interno = '{info['new_id_interno']}' WHERE id_interno = '{old_id_escaped}';\n")
            f.write("\nCOMMIT;\n")

        print(f"\n    SQL completo salvo em: {sql_file}")

    # 6. Salvar mapeamento para referência
    import json
    mapping_file = f"id_interno_mapping_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    with open(mapping_file, "w", encoding="utf-8") as f:
        json.dump(mapeamento, f, indent=2, ensure_ascii=False)

    print(f"\n[5] Mapeamento salvo em: {mapping_file}")

    print("\n" + "=" * 70)
    print("MIGRAÇÃO CONCLUÍDA")
    print(f"  - editais_leilao: {sucesso} atualizados")
    print(f"  - raw.leiloes: Executar SQL manualmente se necessário")
    print("=" * 70)

    return True


if __name__ == "__main__":
    main()
