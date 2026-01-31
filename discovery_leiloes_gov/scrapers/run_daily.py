#!/usr/bin/env python3
"""
Run Daily - Executa todos os scrapers ativos diariamente

Uso:
    python scrapers/run_daily.py [--dry-run] [--persist]

Flags:
    --dry-run: Apenas mostra o que seria executado
    --persist: Salva no Supabase (requer SUPABASE_URL e SUPABASE_SERVICE_KEY)
"""

import os
import sys
import json
import argparse
from pathlib import Path
from datetime import datetime, timezone

# Adicionar diretorio ao path
sys.path.insert(0, str(Path(__file__).parent))

from detran_mg import DetranMGScraper, VeiculoLeilao

# Import condicional para Sodré Santoro (requer playwright)
try:
    from sodre_santoro import SodreSantoroScraper
    HAS_SODRE_SANTORO = True
except ImportError:
    HAS_SODRE_SANTORO = False

# Import para PRF
try:
    from prf import PRFScraper
    HAS_PRF = True
except ImportError:
    HAS_PRF = False

# Import para João Emílio (requer playwright)
try:
    from joao_emilio import JoaoEmilioScraper
    HAS_JOAO_EMILIO = True
except ImportError:
    HAS_JOAO_EMILIO = False

# ============================================================
# CONFIGURACAO
# ============================================================

OUTPUT_DIR = Path(__file__).parent.parent / "outputs"
SCRAPERS_ENABLED = ["detran_mg", "sodre_santoro", "prf", "joao_emilio"]  # Scrapers ativos


# ============================================================
# SUPABASE (opcional)
# ============================================================

def get_supabase_client():
    """Retorna cliente Supabase se configurado"""
    url = os.getenv("SUPABASE_URL")
    key = os.getenv("SUPABASE_SERVICE_KEY")

    if not url or not key:
        return None

    try:
        from supabase import create_client
        return create_client(url, key)
    except ImportError:
        print("AVISO: supabase-py nao instalado")
        return None


def persist_to_supabase(veiculos: list[VeiculoLeilao], table: str = "discovery_veiculos"):
    """Persiste veiculos no Supabase com upsert"""
    client = get_supabase_client()
    if not client:
        print("AVISO: Supabase nao configurado, pulando persistencia")
        return 0

    # Converter para dicts
    records = [v.to_dict() for v in veiculos]

    # Upsert usando id_fonte como chave
    try:
        result = client.table(table).upsert(
            records,
            on_conflict="id_fonte"
        ).execute()

        inserted = len(result.data) if result.data else 0
        print(f"Supabase: {inserted} registros upserted")
        return inserted

    except Exception as e:
        print(f"ERRO Supabase: {e}")
        return 0


# ============================================================
# RUNNER
# ============================================================

def run_detran_mg(dry_run: bool = False, persist: bool = False) -> dict:
    """Executa scraper DETRAN-MG"""
    print("\n" + "=" * 60)
    print("DETRAN-MG")
    print("=" * 60)

    if dry_run:
        print("[DRY-RUN] Scraper DETRAN-MG seria executado")
        return {"scraper": "detran_mg", "status": "dry_run", "veiculos": 0}

    output_dir = OUTPUT_DIR / "detran_mg"
    scraper = DetranMGScraper(output_dir=output_dir)

    try:
        veiculos = scraper.run()

        result = {
            "scraper": "detran_mg",
            "status": "success",
            "veiculos": len(veiculos),
            "leiloes": scraper.metrics["leiloes_found"],
            "requests": scraper.metrics["requests_made"],
            "errors": len(scraper.metrics["errors"])
        }

        # Persistir se solicitado
        if persist and veiculos:
            result["persisted"] = persist_to_supabase(veiculos)

        return result

    except Exception as e:
        return {
            "scraper": "detran_mg",
            "status": "error",
            "error": str(e)
        }


def run_sodre_santoro(dry_run: bool = False, persist: bool = False) -> dict:
    """Executa scraper Sodré Santoro"""
    import asyncio

    print("\n" + "=" * 60)
    print("SODRÉ SANTORO")
    print("=" * 60)

    if not HAS_SODRE_SANTORO:
        print("[SKIP] Playwright não instalado - pulando Sodré Santoro")
        print("       Instale com: pip install playwright && playwright install chromium")
        return {"scraper": "sodre_santoro", "status": "skipped", "reason": "playwright not installed"}

    if dry_run:
        print("[DRY-RUN] Scraper Sodré Santoro seria executado")
        return {"scraper": "sodre_santoro", "status": "dry_run", "veiculos": 0}

    output_dir = OUTPUT_DIR / "sodre_santoro"
    scraper = SodreSantoroScraper(output_dir=output_dir, headless=True)

    try:
        # Executar async
        veiculos = asyncio.run(scraper.run())

        result = {
            "scraper": "sodre_santoro",
            "status": "success",
            "veiculos": len(veiculos),
            "veiculos_cat": scraper.metrics.get("veiculos_found", 0),
            "sucatas_cat": scraper.metrics.get("sucatas_found", 0),
            "leiloes": scraper.metrics.get("leiloes_found", 0),
            "requests": scraper.metrics["requests_made"],
            "errors": len(scraper.metrics["errors"])
        }

        # Persistir se solicitado
        if persist and veiculos:
            result["persisted"] = persist_to_supabase(veiculos)

        return result

    except Exception as e:
        import traceback
        traceback.print_exc()
        return {
            "scraper": "sodre_santoro",
            "status": "error",
            "error": str(e)
        }


def run_prf(dry_run: bool = False, persist: bool = False) -> dict:
    """Executa scraper PRF (editais de leilão)"""
    print("\n" + "=" * 60)
    print("PRF - POLÍCIA RODOVIÁRIA FEDERAL")
    print("=" * 60)

    if not HAS_PRF:
        print("[SKIP] Módulo PRF não encontrado")
        return {"scraper": "prf", "status": "skipped", "reason": "module not found"}

    if dry_run:
        print("[DRY-RUN] Scraper PRF seria executado")
        return {"scraper": "prf", "status": "dry_run", "editais": 0}

    output_dir = OUTPUT_DIR / "prf"
    scraper = PRFScraper(output_dir=output_dir)

    try:
        editais = scraper.run()

        result = {
            "scraper": "prf",
            "status": "success",
            "editais": len(editais),
            "estados": scraper.metrics.get("estados_coletados", 0),
            "requests": scraper.metrics["requests_made"],
            "errors": len(scraper.metrics["errors"])
        }

        # PRF coleta editais, não veículos diretamente
        # Persistência seria diferente (tabela de editais)
        if persist and editais:
            # TODO: Implementar persistência de editais
            print("[INFO] Persistência de editais PRF não implementada ainda")

        return result

    except Exception as e:
        import traceback
        traceback.print_exc()
        return {
            "scraper": "prf",
            "status": "error",
            "error": str(e)
        }


def run_joao_emilio(dry_run: bool = False, persist: bool = False) -> dict:
    """Executa scraper João Emílio (leiloeiro privado)"""
    import asyncio

    print("\n" + "=" * 60)
    print("JOÃO EMÍLIO")
    print("=" * 60)

    if not HAS_JOAO_EMILIO:
        print("[SKIP] Playwright não instalado - pulando João Emílio")
        print("       Instale com: pip install playwright && playwright install chromium")
        return {"scraper": "joao_emilio", "status": "skipped", "reason": "playwright not installed"}

    if dry_run:
        print("[DRY-RUN] Scraper João Emílio seria executado")
        return {"scraper": "joao_emilio", "status": "dry_run", "veiculos": 0}

    output_dir = OUTPUT_DIR / "joao_emilio"
    scraper = JoaoEmilioScraper(output_dir=output_dir, headless=True)

    try:
        # Executar async
        veiculos = asyncio.run(scraper.run())

        result = {
            "scraper": "joao_emilio",
            "status": "success",
            "veiculos": len(veiculos),
            "leiloes": scraper.metrics.get("leiloes_found", 0),
            "requests": scraper.metrics["requests_made"],
            "errors": len(scraper.metrics["errors"])
        }

        # Persistir se solicitado
        if persist and veiculos:
            result["persisted"] = persist_to_supabase(veiculos)

        return result

    except Exception as e:
        import traceback
        traceback.print_exc()
        return {
            "scraper": "joao_emilio",
            "status": "error",
            "error": str(e)
        }


def main():
    parser = argparse.ArgumentParser(description="Run Daily Scrapers")
    parser.add_argument("--dry-run", action="store_true",
                        help="Apenas mostra o que seria executado")
    parser.add_argument("--persist", action="store_true",
                        help="Salva no Supabase")
    parser.add_argument("--scrapers", type=str, default=None,
                        help="Lista de scrapers separados por virgula (default: todos)")
    args = parser.parse_args()

    # Determinar scrapers a executar
    scrapers_to_run = args.scrapers.split(",") if args.scrapers else SCRAPERS_ENABLED

    print("=" * 60)
    print("DISCOVERY SCRAPERS - Execucao Diaria")
    print(f"Data: {datetime.now(timezone.utc).isoformat()}")
    print(f"Scrapers: {', '.join(scrapers_to_run)}")
    print(f"Dry-run: {args.dry_run}")
    print(f"Persist: {args.persist}")
    print("=" * 60)

    results = []

    # Executar cada scraper
    for scraper_name in scrapers_to_run:
        if scraper_name == "detran_mg":
            result = run_detran_mg(dry_run=args.dry_run, persist=args.persist)
            results.append(result)
        elif scraper_name == "sodre_santoro":
            result = run_sodre_santoro(dry_run=args.dry_run, persist=args.persist)
            results.append(result)
        elif scraper_name == "prf":
            result = run_prf(dry_run=args.dry_run, persist=args.persist)
            results.append(result)
        elif scraper_name == "joao_emilio":
            result = run_joao_emilio(dry_run=args.dry_run, persist=args.persist)
            results.append(result)
        else:
            print(f"AVISO: Scraper '{scraper_name}' nao implementado")

    # Resumo final
    print("\n" + "=" * 60)
    print("RESUMO FINAL")
    print("=" * 60)

    total_veiculos = 0
    for r in results:
        status_icon = "OK" if r["status"] == "success" else "!!" if r["status"] == "error" else "--"
        veiculos = r.get("veiculos", 0)
        total_veiculos += veiculos
        print(f"  [{status_icon}] {r['scraper']}: {veiculos} veiculos")

        if r["status"] == "error":
            print(f"      Erro: {r.get('error', 'N/A')}")

    print(f"\nTotal: {total_veiculos} veiculos coletados")

    # Salvar relatorio
    report_file = OUTPUT_DIR / "daily_report.json"
    report = {
        "executed_at": datetime.now(timezone.utc).isoformat(),
        "dry_run": args.dry_run,
        "persist": args.persist,
        "results": results,
        "total_veiculos": total_veiculos
    }

    OUTPUT_DIR.mkdir(exist_ok=True)
    with open(report_file, "w", encoding="utf-8") as f:
        json.dump(report, f, ensure_ascii=False, indent=2)

    print(f"\nRelatorio salvo: {report_file}")

    # Exit code
    has_error = any(r["status"] == "error" for r in results)
    sys.exit(1 if has_error else 0)


if __name__ == "__main__":
    main()
