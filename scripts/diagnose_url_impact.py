#!/usr/bin/env python3
"""
FASE 1: Diagnóstico de Impacto - URLs Inventadas

Este script:
1. Coleta amostra de URLs do Supabase (leiloeiro_lotes com /lote/)
2. Testa cada URL com HEAD request (follow_redirects=True)
3. Gera relatórios CSV e resumo

Uso:
    python scripts/diagnose_url_impact.py

Saída:
    - tmp/url_sample.csv (amostra do banco)
    - tmp/url_http_report.csv (resultado dos testes HTTP)
    - Resumo no terminal

Requer:
    - SUPABASE_URL e SUPABASE_SERVICE_KEY no .env
    - pip install httpx supabase python-dotenv
"""

import csv
import os
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Tuple

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

try:
    import httpx
except ImportError:
    print("ERRO: httpx não instalado. Execute: pip install httpx")
    sys.exit(1)

try:
    from supabase import create_client
except ImportError:
    print("ERRO: supabase não instalado. Execute: pip install supabase")
    sys.exit(1)

try:
    from dotenv import load_dotenv
    load_dotenv(project_root / ".env")
except ImportError:
    pass


# ============================================================================
# CONFIGURAÇÃO
# ============================================================================

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_SERVICE_KEY")

OUTPUT_DIR = project_root / "tmp"
SAMPLE_FILE = OUTPUT_DIR / "url_sample.csv"
HTTP_REPORT_FILE = OUTPUT_DIR / "url_http_report.csv"

# Rate limiting
REQUESTS_PER_SECOND = 3.0
REQUEST_TIMEOUT = 15

# Domínios alvo
TARGET_DOMAINS = ["leiloesjudiciais.com.br", "rioleiloes.com.br"]


# ============================================================================
# FASE 1.1: COLETAR AMOSTRA DO BANCO
# ============================================================================

def collect_sample() -> List[Dict]:
    """
    Coleta amostra de URLs do Supabase.

    Query: URLs de leiloeiro_lotes que contêm '/lote/' no path
    (indicando que foram construídas pelo bug).
    """
    print("=" * 60)
    print("FASE 1.1: COLETAR AMOSTRA DO BANCO")
    print("=" * 60)

    if not SUPABASE_URL or not SUPABASE_KEY:
        print("ERRO: SUPABASE_URL e SUPABASE_SERVICE_KEY não configurados no .env")
        sys.exit(1)

    client = create_client(SUPABASE_URL, SUPABASE_KEY)

    # Query para URLs que contêm /lote/ (padrão inventado)
    # Busca em leiloeiro_lotes.link_leiloeiro
    print("\nExecutando query no Supabase...")

    samples = []

    # Buscar leiloesjudiciais
    for domain in TARGET_DOMAINS:
        try:
            result = client.table("leiloeiro_lotes") \
                .select("id, id_interno, link_leiloeiro, created_at") \
                .ilike("link_leiloeiro", f"%{domain}%") \
                .ilike("link_leiloeiro", "%/lote/%") \
                .limit(50) \
                .execute()

            for row in result.data:
                samples.append({
                    "id": row.get("id"),
                    "id_interno": row.get("id_interno"),
                    "url_no_banco": row.get("link_leiloeiro"),
                    "dominio": domain,
                    "created_at": row.get("created_at"),
                })

            print(f"  {domain}: {len(result.data)} registros encontrados")

        except Exception as e:
            print(f"  AVISO: Erro ao buscar {domain}: {e}")

    # Se não encontrou nada em leiloeiro_lotes, tenta raw.leiloes
    if not samples:
        print("\nNenhum registro em leiloeiro_lotes, tentando raw.leiloes...")
        try:
            # Tentar schema raw
            result = client.schema("raw").table("leiloes") \
                .select("id, id_interno, link_leiloeiro, created_at") \
                .ilike("link_leiloeiro", "%leiloesjudiciais%") \
                .ilike("link_leiloeiro", "%/lote/%") \
                .limit(50) \
                .execute()

            for row in result.data:
                samples.append({
                    "id": row.get("id"),
                    "id_interno": row.get("id_interno"),
                    "url_no_banco": row.get("link_leiloeiro"),
                    "dominio": "leiloesjudiciais.com.br",
                    "created_at": row.get("created_at"),
                })

            print(f"  raw.leiloes: {len(result.data)} registros")

        except Exception as e:
            print(f"  ERRO raw.leiloes: {e}")

    # Contagem total
    print(f"\nTotal de amostras coletadas: {len(samples)}")

    # Salvar CSV
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    with open(SAMPLE_FILE, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=["id", "id_interno", "url_no_banco", "dominio", "created_at"])
        writer.writeheader()
        writer.writerows(samples)

    print(f"Amostra salva em: {SAMPLE_FILE}")

    # Mostrar primeiros 10
    print("\nPrimeiros 10 exemplos:")
    for s in samples[:10]:
        print(f"  {s['url_no_banco'][:80]}...")

    return samples


# ============================================================================
# FASE 1.2: TESTAR COMPORTAMENTO HTTP
# ============================================================================

def test_http_urls(samples: List[Dict]) -> List[Dict]:
    """
    Testa cada URL com HEAD request.

    Para cada URL:
    - Faz HEAD com follow_redirects=True
    - Registra status inicial, final e URL final
    """
    print("\n" + "=" * 60)
    print("FASE 1.2: TESTAR COMPORTAMENTO HTTP")
    print("=" * 60)

    results = []
    stats = {
        "total": len(samples),
        "ok": 0,
        "redirect": 0,
        "error_404": 0,
        "error_other": 0,
    }

    # Rate limiter
    min_interval = 1.0 / REQUESTS_PER_SECOND
    last_request_time = 0.0

    print(f"\nTestando {len(samples)} URLs (rate limit: {REQUESTS_PER_SECOND} req/s)...")
    print()

    with httpx.Client(timeout=REQUEST_TIMEOUT, follow_redirects=True) as client:
        for i, sample in enumerate(samples, 1):
            url = sample.get("url_no_banco", "")

            if not url:
                continue

            # Rate limiting
            elapsed = time.time() - last_request_time
            if elapsed < min_interval:
                time.sleep(min_interval - elapsed)

            result = {
                "id": sample.get("id"),
                "url_original": url,
                "status_inicial": None,
                "url_location": None,
                "url_final": None,
                "status_final": None,
                "ok": False,
                "error": None,
            }

            try:
                # Primeiro, tenta sem seguir redirects para capturar status inicial
                with httpx.Client(timeout=REQUEST_TIMEOUT, follow_redirects=False) as client_no_redirect:
                    try:
                        initial_resp = client_no_redirect.head(url)
                        result["status_inicial"] = initial_resp.status_code
                        result["url_location"] = initial_resp.headers.get("location")
                    except Exception:
                        pass

                # Agora segue redirects
                resp = client.head(url)
                last_request_time = time.time()

                result["status_final"] = resp.status_code
                result["url_final"] = str(resp.url)
                result["ok"] = 200 <= resp.status_code < 400

                # Estatísticas
                if result["ok"]:
                    if result["url_final"] != url:
                        stats["redirect"] += 1
                    else:
                        stats["ok"] += 1
                elif resp.status_code == 404:
                    stats["error_404"] += 1
                else:
                    stats["error_other"] += 1

            except httpx.TimeoutException:
                result["error"] = "TIMEOUT"
                stats["error_other"] += 1
            except httpx.RequestError as e:
                result["error"] = str(type(e).__name__)
                stats["error_other"] += 1
            except Exception as e:
                result["error"] = str(e)[:50]
                stats["error_other"] += 1

            results.append(result)

            # Progress
            status_str = f"{result['status_final']}" if result['status_final'] else result.get('error', 'ERR')
            marker = "[OK]" if result["ok"] else "[ER]"
            print(f"  [{i:3d}/{len(samples)}] {marker} {status_str:5} {url[:60]}...")

    # Salvar CSV
    with open(HTTP_REPORT_FILE, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=[
            "id", "url_original", "status_inicial", "url_location",
            "url_final", "status_final", "ok", "error"
        ])
        writer.writeheader()
        writer.writerows(results)

    print(f"\nRelatório salvo em: {HTTP_REPORT_FILE}")

    return results


def print_summary(results: List[Dict]):
    """Imprime resumo dos resultados."""
    print("\n" + "=" * 60)
    print("RESUMO DO DIAGNÓSTICO")
    print("=" * 60)

    total = len(results)
    if total == 0:
        print("Nenhum resultado para analisar.")
        return

    ok_same = sum(1 for r in results if r["ok"] and r["url_final"] == r["url_original"])
    ok_redirect = sum(1 for r in results if r["ok"] and r["url_final"] != r["url_original"])
    error_404 = sum(1 for r in results if r["status_final"] == 404)
    error_other = sum(1 for r in results if not r["ok"] and r["status_final"] != 404)

    print(f"""
+----------------------------------------+
|           RESULTADO DO TESTE           |
+----------------------------------------+
| Total de URLs testadas: {total:14} |
+----------------------------------------+
| [OK] URL correta      : {ok_same:5} ({ok_same*100/total:5.1f}%) |
| [OK] Com redirect     : {ok_redirect:5} ({ok_redirect*100/total:5.1f}%) |
| [ER] Erro 404         : {error_404:5} ({error_404*100/total:5.1f}%) |
| [ER] Outros erros     : {error_other:5} ({error_other*100/total:5.1f}%) |
+----------------------------------------+
""")

    # URLs que deram 404
    urls_404 = [r for r in results if r["status_final"] == 404]
    if urls_404:
        print("\nExemplos de URLs com 404:")
        for r in urls_404[:5]:
            print(f"  - {r['url_original']}")

    # URLs que redirecionaram
    urls_redirect = [r for r in results if r["ok"] and r["url_final"] != r["url_original"]]
    if urls_redirect:
        print("\nExemplos de URLs que redirecionaram:")
        for r in urls_redirect[:5]:
            print(f"  - {r['url_original'][:50]}...")
            print(f"    -> {r['url_final'][:50]}...")

        # Top 10 destinos de redirect (dominios/paths)
        from urllib.parse import urlparse
        from collections import Counter
        destinations = []
        for r in urls_redirect:
            try:
                parsed = urlparse(r["url_final"])
                # Pega dominio + primeiro segmento do path
                path_parts = parsed.path.strip("/").split("/")
                dest = f"{parsed.netloc}/{path_parts[0]}" if path_parts else parsed.netloc
                destinations.append(dest)
            except Exception:
                pass
        if destinations:
            print("\nTop 10 destinos de redirect:")
            for dest, count in Counter(destinations).most_common(10):
                print(f"  {count:3d}x  {dest}")

    # Conclusão
    print("\n" + "=" * 60)
    print("CONCLUSÃO")
    print("=" * 60)

    total_errors = error_404 + error_other
    if total_errors > 0:
        print(f"""
[WARN] IMPACTO CONFIRMADO: {total_errors} URLs ({total_errors*100/total:.1f}%) retornam erro

Detalhes:
- 404 Not Found: {error_404} ({error_404*100/total:.1f}%)
- Outros erros (400, 500, timeout): {error_other} ({error_other*100/total:.1f}%)

Causa raiz: URLs sendo construidas por concatenacao hardcoded
(ex: /lote/{{leilao_id}}/{{lote_id}}) que nao existem no servidor.

Proximos passos:
1. Remover concatenacao hardcoded
2. Usar URL canonica da API ou href real
3. Backfill dos registros existentes
""")
    else:
        print("[OK] Todas as URLs retornaram status OK (200-399)")

    # Recomendacao de backfill
    print("\n" + "=" * 60)
    print("RECOMENDACAO DE BACKFILL")
    print("=" * 60)
    ok_total = ok_same + ok_redirect
    if total > 0:
        ok_pct = ok_total * 100 / total
        err_pct = (error_404 + error_other) * 100 / total

        if ok_pct >= 50 and ok_redirect > 0:
            print(f"""
[SIM] PODE EXECUTAR BACKFILL COM SEGURANCA

Evidencia:
- {ok_redirect} URLs ({ok_redirect*100/total:.1f}%) redirecionam para URLs validas
- O site suporta redirecionamento de URLs antigas para novas
- Backfill pode resolver URLs via HEAD request

Comando:
  python scripts/backfill_fix_urls.py --dry-run
  python scripts/backfill_fix_urls.py --execute
""")
        elif error_404 == total:
            print(f"""
[NAO] NAO RECOMENDADO EXECUTAR BACKFILL

Evidencia:
- 100% das URLs retornaram 404
- O site nao suporta o padrao /lote/{{id}}/{{id}}
- URLs precisam vir diretamente da API

Acao necessaria:
  Verificar se a API retorna campo url_lote ou nm_url_lote
""")
        else:
            print(f"""
[TALVEZ] AVALIACAO MANUAL NECESSARIA

Estatisticas:
- OK: {ok_pct:.1f}%
- Erro: {err_pct:.1f}%

Recomendacao:
  Executar --dry-run primeiro e analisar resultados
""")


# ============================================================================
# MAIN
# ============================================================================

def main():
    print("=" * 60)
    print("DIAGNÓSTICO DE IMPACTO - URLs INVENTADAS")
    print(f"Data: {datetime.now().isoformat()}")
    print("=" * 60)

    # Fase 1.1: Coletar amostra
    samples = collect_sample()

    if not samples:
        print("\n⚠️ Nenhuma amostra encontrada. Verifique:")
        print("  1. Conexão com Supabase")
        print("  2. Se existem dados em leiloeiro_lotes ou raw.leiloes")
        return

    # Fase 1.2: Testar URLs
    results = test_http_urls(samples)

    # Resumo
    print_summary(results)

    print("\nArquivos gerados:")
    print(f"  - {SAMPLE_FILE}")
    print(f"  - {HTTP_REPORT_FILE}")


if __name__ == "__main__":
    main()
