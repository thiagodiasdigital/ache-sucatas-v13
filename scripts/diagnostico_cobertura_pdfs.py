#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
DIAGNOSTICO DE COBERTURA DE PDFs

Objetivo: Entender por que 269/274 editais estao marcados como no_link.

Autor: Claude Code
Data: 2026-01-27
"""

import os
import sys
import json
from pathlib import Path
from datetime import datetime
from collections import Counter

PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from dotenv import load_dotenv
load_dotenv()

def conectar_supabase():
    """Conecta ao Supabase."""
    SUPABASE_URL = os.getenv("SUPABASE_URL")
    SUPABASE_KEY = os.getenv("SUPABASE_SERVICE_KEY") or os.getenv("SUPABASE_KEY")

    if not SUPABASE_URL or not SUPABASE_KEY:
        print("[X] Credenciais Supabase nao encontradas")
        sys.exit(1)

    from supabase import create_client
    return create_client(SUPABASE_URL, SUPABASE_KEY)


def query_1_cobertura_pdfs(client):
    """
    QUERY 1: Cobertura de PDFs/anexos por edital

    Colunas reais:
    - arquivo_origem (path local)
    - storage_path (Supabase Storage)
    - pdf_hash (SHA256)
    """
    print("\n" + "="*70)
    print("QUERY 1: COBERTURA DE PDFs/ANEXOS POR EDITAL")
    print("="*70)

    # Total
    total = client.table("editais_leilao").select("id", count="exact").execute()
    total_count = total.count
    print(f"\n[TOTAL] Total de editais: {total_count}")

    # Com storage_path
    with_storage = client.table("editais_leilao")\
        .select("id", count="exact")\
        .not_.is_("storage_path", "null")\
        .neq("storage_path", "")\
        .execute()
    storage_count = with_storage.count or 0

    # Com pdf_hash
    with_hash = client.table("editais_leilao")\
        .select("id", count="exact")\
        .not_.is_("pdf_hash", "null")\
        .neq("pdf_hash", "")\
        .execute()
    hash_count = with_hash.count or 0

    # Com arquivo_origem
    with_arquivo = client.table("editais_leilao")\
        .select("id", count="exact")\
        .not_.is_("arquivo_origem", "null")\
        .neq("arquivo_origem", "")\
        .execute()
    arquivo_count = with_arquivo.count or 0

    print(f"\n[FILES] Cobertura de campos de PDF:")
    print(f"   - arquivo_origem (path local):   {arquivo_count:4d} ({100*arquivo_count/total_count:.1f}%)")
    print(f"   - storage_path (Supabase):       {storage_count:4d} ({100*storage_count/total_count:.1f}%)")
    print(f"   - pdf_hash (SHA256):             {hash_count:4d} ({100*hash_count/total_count:.1f}%)")

    return {
        "total": total_count,
        "com_arquivo_origem": arquivo_count,
        "com_storage_path": storage_count,
        "com_pdf_hash": hash_count,
    }


def query_2_arquivos_processados(client):
    """
    QUERY 2: Status dos arquivos processados (lotes)
    """
    print("\n" + "="*70)
    print("QUERY 2: ARQUIVOS PROCESSADOS (LOTES)")
    print("="*70)

    try:
        result = client.table("arquivos_processados_lotes")\
            .select("tipo_detectado, status")\
            .execute()

        if not result.data:
            print("\n[WARN] Tabela arquivos_processados_lotes esta vazia")
            return {"total": 0}

        tipos = Counter(r["tipo_detectado"] for r in result.data)
        status = Counter(r["status"] for r in result.data)

        print(f"\n[PDF] Total de arquivos processados: {len(result.data)}")
        print(f"\n   Por tipo detectado:")
        for tipo, count in tipos.most_common():
            print(f"   - {tipo or 'NULL'}: {count}")

        print(f"\n   Por status:")
        for st, count in status.most_common():
            print(f"   - {st or 'NULL'}: {count}")

        return {
            "total": len(result.data),
            "por_tipo": dict(tipos),
            "por_status": dict(status),
        }
    except Exception as e:
        print(f"\n[WARN] Erro ao consultar arquivos_processados_lotes: {e}")
        return {"error": str(e)}


def query_3_amostra_no_link(client, limite: int = 20):
    """
    QUERY 3: Amostra forense de editais no_link
    """
    print("\n" + "="*70)
    print(f"QUERY 3: AMOSTRA FORENSE DE {limite} EDITAIS NO_LINK")
    print("="*70)

    result = client.table("editais_leilao")\
        .select("id_interno, link_pncp, arquivo_origem, storage_path, pdf_hash, link_leiloeiro, link_leiloeiro_valido, link_leiloeiro_origem_tipo, auditor_v19_result")\
        .eq("auditor_v19_result", "no_link")\
        .limit(limite)\
        .execute()

    if not result.data:
        print("\n[WARN] Nenhum edital com no_link encontrado")
        return []

    print(f"\n[LIST] Amostra de {len(result.data)} editais no_link:")
    print("-" * 70)

    analise = []
    for i, row in enumerate(result.data, 1):
        tem_arquivo = bool(row.get("arquivo_origem"))
        tem_storage = bool(row.get("storage_path"))
        tem_hash = bool(row.get("pdf_hash"))
        link = row.get("link_leiloeiro")
        tem_link = bool(link and link != "N/D")
        link_valido = row.get("link_leiloeiro_valido")
        origem_tipo = row.get("link_leiloeiro_origem_tipo")

        # Classificar causa provavel
        if tem_link and link_valido:
            causa = "TEM_LINK_VALIDO"  # Estranho - deveria ser found_link
        elif tem_link and not link_valido:
            causa = "LINK_INVALIDO"
        elif not tem_arquivo and not tem_storage:
            causa = "SEM_PDF"
        elif tem_storage:
            causa = "PDF_SEM_LINK"
        else:
            causa = "APENAS_LOCAL"

        print(f"\n{i}. {row.get('id_interno', 'N/A')[:50]}")
        print(f"   [ATTACH] arquivo_origem: {'[OK]' if tem_arquivo else '[X]'}")
        print(f"   [CLOUD]  storage_path:   {'[OK]' if tem_storage else '[X]'}")
        print(f"   [HASH]   pdf_hash:       {'[OK]' if tem_hash else '[X]'}")
        print(f"   [TAG]    link_leiloeiro: {link[:40] if link else '[X]'}")
        print(f"   [VALID]  valido:         {link_valido}")
        print(f"   [TYPE]   origem_tipo:    {origem_tipo}")
        print(f"   [LOC]    Causa provavel: {causa}")

        analise.append({
            "id_interno": row.get("id_interno"),
            "link_pncp": row.get("link_pncp"),
            "tem_arquivo": tem_arquivo,
            "tem_storage": tem_storage,
            "tem_hash": tem_hash,
            "link_leiloeiro": link,
            "link_valido": link_valido,
            "origem_tipo": origem_tipo,
            "causa_provavel": causa,
        })

    # Resumo das causas
    causas = Counter(a["causa_provavel"] for a in analise)
    print("\n" + "-" * 70)
    print("[STATS] RESUMO DAS CAUSAS:")
    for causa, count in causas.most_common():
        print(f"   - {causa}: {count} ({100*count/len(analise):.0f}%)")

    # Resumo das origens
    origens = Counter(a["origem_tipo"] for a in analise)
    print("\n[STATS] RESUMO DAS ORIGENS DO LINK:")
    for origem, count in origens.most_common():
        print(f"   - {origem or 'NULL'}: {count} ({100*count/len(analise):.0f}%)")

    return analise


def query_4_detalhes_pdf(client, limite: int = 5):
    """
    QUERY 4: Detalhes de PDFs para investigacao manual
    """
    print("\n" + "="*70)
    print(f"QUERY 4: URLs DE PDFs PARA INVESTIGACAO MANUAL ({limite} primeiros)")
    print("="*70)

    result = client.table("editais_leilao")\
        .select("id_interno, link_pncp, storage_path, arquivo_origem")\
        .eq("auditor_v19_result", "no_link")\
        .not_.is_("storage_path", "null")\
        .limit(limite)\
        .execute()

    if not result.data:
        print("\n[WARN] Nenhum edital no_link com PDF disponivel")
        return []

    # Obter URL base do storage
    supabase_url = os.getenv("SUPABASE_URL", "")
    storage_base = f"{supabase_url}/storage/v1/object/public/editais-pdf/"

    print(f"\n[SEARCH] PDFs para investigacao manual:")
    print("-" * 70)

    urls = []
    for i, row in enumerate(result.data, 1):
        id_interno = row.get("id_interno", "N/A")
        storage = row.get("storage_path")
        arquivo = row.get("arquivo_origem")
        link_pncp = row.get("link_pncp")

        pdf_url = f"{storage_base}{storage}" if storage else None

        print(f"\n{i}. {id_interno[:60]}")
        print(f"   PNCP: {link_pncp or 'N/A'}")
        if pdf_url:
            print(f"   PDF URL: {pdf_url}")
        else:
            print(f"   Arquivo Local: {arquivo}")

        urls.append({
            "id_interno": id_interno,
            "link_pncp": link_pncp,
            "pdf_url": pdf_url or arquivo,
            "storage_path": storage,
        })

    return urls


def query_5_analise_link_leiloeiro(client):
    """
    QUERY 5: Analise do campo link_leiloeiro
    """
    print("\n" + "="*70)
    print("QUERY 5: ANALISE DO CAMPO link_leiloeiro")
    print("="*70)

    # Total
    total_result = client.table("editais_leilao").select("id", count="exact").execute()
    total = total_result.count

    # NULL
    null_result = client.table("editais_leilao")\
        .select("id", count="exact")\
        .is_("link_leiloeiro", "null")\
        .execute()
    null_count = null_result.count or 0

    # N/D
    nd_result = client.table("editais_leilao")\
        .select("id", count="exact")\
        .eq("link_leiloeiro", "N/D")\
        .execute()
    nd_count = nd_result.count or 0

    # Vazio
    empty_result = client.table("editais_leilao")\
        .select("id", count="exact")\
        .eq("link_leiloeiro", "")\
        .execute()
    empty_count = empty_result.count or 0

    # Com link (nem NULL, nem N/D, nem vazio)
    com_link = total - null_count - nd_count - empty_count

    print(f"\n[STATS] Distribuicao de link_leiloeiro (total: {total}):")
    print(f"   - NULL:     {null_count:4d} ({100*null_count/total:.1f}%)")
    print(f"   - 'N/D':    {nd_count:4d} ({100*nd_count/total:.1f}%)")
    print(f"   - '':       {empty_count:4d} ({100*empty_count/total:.1f}%)")
    print(f"   - Com link: {com_link:4d} ({100*com_link/total:.1f}%)")

    # Analise de link_leiloeiro_valido
    valido_result = client.table("editais_leilao")\
        .select("id", count="exact")\
        .eq("link_leiloeiro_valido", True)\
        .execute()
    valido_count = valido_result.count or 0

    invalido_result = client.table("editais_leilao")\
        .select("id", count="exact")\
        .eq("link_leiloeiro_valido", False)\
        .execute()
    invalido_count = invalido_result.count or 0

    print(f"\n[STATS] Distribuicao de link_leiloeiro_valido:")
    print(f"   - True:  {valido_count:4d}")
    print(f"   - False: {invalido_count:4d}")
    print(f"   - NULL:  {total - valido_count - invalido_count:4d}")

    # Analise de link_leiloeiro_origem_tipo
    origens_result = client.table("editais_leilao")\
        .select("link_leiloeiro_origem_tipo")\
        .execute()

    if origens_result.data:
        origens = Counter(r["link_leiloeiro_origem_tipo"] for r in origens_result.data)
        print(f"\n[STATS] Distribuicao de link_leiloeiro_origem_tipo:")
        for origem, count in origens.most_common():
            print(f"   - {origem or 'NULL'}: {count} ({100*count/total:.1f}%)")

    # Exemplos de links validos
    if com_link > 0:
        exemplos = client.table("editais_leilao")\
            .select("link_leiloeiro")\
            .eq("link_leiloeiro_valido", True)\
            .limit(10)\
            .execute()

        if exemplos.data:
            print(f"\n[LINK] Exemplos de links validos encontrados:")
            dominios = Counter()
            for row in exemplos.data:
                link = row.get("link_leiloeiro", "")
                if link:
                    try:
                        from urllib.parse import urlparse
                        parsed = urlparse(link)
                        dominio = parsed.netloc or "sem_dominio"
                    except:
                        dominio = "parse_error"
                    dominios[dominio] += 1
                    print(f"   - {link[:70]}")

            if dominios:
                print(f"\n[LOC] Dominios encontrados:")
                for dom, count in dominios.most_common():
                    print(f"   - {dom}: {count}")

    return {
        "total": total,
        "null": null_count,
        "nd": nd_count,
        "empty": empty_count,
        "com_link": com_link,
        "valido_true": valido_count,
        "valido_false": invalido_count,
    }


def query_6_auditor_v19_results(client):
    """
    QUERY 6: Resultados do Auditor V19
    """
    print("\n" + "="*70)
    print("QUERY 6: RESULTADOS DO AUDITOR V19")
    print("="*70)

    result = client.table("editais_leilao")\
        .select("auditor_v19_result")\
        .execute()

    if not result.data:
        print("\n[WARN] Nenhum dado encontrado")
        return {}

    resultados = Counter(r["auditor_v19_result"] for r in result.data)
    total = len(result.data)

    print(f"\n[STATS] Distribuicao de auditor_v19_result (total: {total}):")
    for res, count in resultados.most_common():
        print(f"   - {res or 'NULL'}: {count} ({100*count/total:.1f}%)")

    return dict(resultados)


def main():
    print("=" * 70)
    print("DIAGNOSTICO COMPLETO DE COBERTURA DE PDFs")
    print(f"Data: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 70)

    client = conectar_supabase()

    resultados = {}

    # Query 1: Cobertura de PDFs
    resultados["cobertura_pdfs"] = query_1_cobertura_pdfs(client)

    # Query 2: Arquivos processados
    resultados["arquivos_processados"] = query_2_arquivos_processados(client)

    # Query 5: Analise link_leiloeiro (antes da amostra para contexto)
    resultados["analise_link_leiloeiro"] = query_5_analise_link_leiloeiro(client)

    # Query 6: Resultados V19
    resultados["auditor_v19_results"] = query_6_auditor_v19_results(client)

    # Query 3: Amostra forense
    resultados["amostra_no_link"] = query_3_amostra_no_link(client, limite=20)

    # Query 4: URLs para investigacao
    resultados["urls_investigacao"] = query_4_detalhes_pdf(client, limite=5)

    # Salvar relatorio
    reports_dir = PROJECT_ROOT / "reports" / "diagnostico"
    reports_dir.mkdir(parents=True, exist_ok=True)

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filepath = reports_dir / f"cobertura_pdfs_{timestamp}.json"

    with open(filepath, "w", encoding="utf-8") as f:
        json.dump(resultados, f, ensure_ascii=False, indent=2, default=str)

    print("\n" + "=" * 70)
    print("CONCLUSAO")
    print("=" * 70)
    print(f"\n[STATS] Relatorio salvo em: {filepath}")

    # Analise final
    cobertura = resultados.get("cobertura_pdfs", {})
    total = cobertura.get("total", 0)
    com_storage = cobertura.get("com_storage_path", 0)

    link_info = resultados.get("analise_link_leiloeiro", {})
    com_link = link_info.get("com_link", 0)
    valido = link_info.get("valido_true", 0)

    v19 = resultados.get("auditor_v19_results", {})
    found_link = v19.get("found_link", 0)
    no_link = v19.get("no_link", 0)

    print(f"\n[CHART] RESUMO EXECUTIVO:")
    print(f"   - Total de editais:        {total}")
    print(f"   - Com PDF no Storage:      {com_storage} ({100*com_storage/total if total else 0:.1f}%)")
    print(f"   - Com link_leiloeiro:      {com_link} ({100*com_link/total if total else 0:.1f}%)")
    print(f"   - Com link_leiloeiro_valido: {valido} ({100*valido/total if total else 0:.1f}%)")
    print(f"   - V19 found_link:          {found_link} ({100*found_link/total if total else 0:.1f}%)")
    print(f"   - V19 no_link:             {no_link} ({100*no_link/total if total else 0:.1f}%)")

    print("\n[TARGET] ANALISE:")
    if com_link > no_link:
        print(f"   INSIGHT: {com_link} editais TEM link_leiloeiro mas V19 marcou {no_link} como no_link")
        print("   CAUSA: Os links existentes vieram de WHITELIST, nao de extracao de PDF")
        print("   O V19 marca no_link quando nao ENCONTRA link no PDF, mesmo que exista link de outra fonte")


if __name__ == "__main__":
    main()
