"""
Diagnóstico Forense de Quarentena - Ache Sucatas
=================================================
Script para analisar registros quarentenados e identificar causas raiz.

Autor: Claude (Auditoria Forense)
Data: 2026-01-29
"""

import os
import json
from datetime import datetime, timedelta
from pathlib import Path
from collections import Counter
from dotenv import load_dotenv

load_dotenv()

# Supabase
from supabase import create_client

SUPABASE_URL = os.environ.get("SUPABASE_URL")
SUPABASE_KEY = os.environ.get("SUPABASE_SERVICE_KEY")

if not SUPABASE_URL or not SUPABASE_KEY:
    print("ERRO: Configure SUPABASE_URL e SUPABASE_SERVICE_KEY no .env")
    exit(1)

client = create_client(SUPABASE_URL, SUPABASE_KEY)


def get_run_reports(limit: int = 20):
    """Obtém os últimos relatórios de execução."""
    result = client.table("pipeline_run_reports").select("*").order(
        "created_at", desc=True
    ).limit(limit).execute()
    return result.data


def get_quarantine_records(run_id: str = None, limit: int = 100):
    """Obtém registros quarentenados."""
    query = client.table("dataset_rejections").select("*")
    if run_id:
        query = query.eq("run_id", run_id)
    query = query.order("created_at", desc=True).limit(limit)
    result = query.execute()
    return result.data


def analyze_missing_fields(records: list) -> dict:
    """Analisa campos faltantes nos registros."""
    field_counts = Counter()
    error_codes = Counter()

    for rec in records:
        errors = rec.get("errors", [])
        if isinstance(errors, str):
            try:
                errors = json.loads(errors)
            except:
                errors = []

        for err in errors:
            code = err.get("code", "unknown")
            field = err.get("field", "unknown")
            error_codes[code] += 1
            if code == "missing_required_field":
                field_counts[field] += 1

    return {
        "missing_fields": dict(field_counts.most_common()),
        "error_codes": dict(error_codes.most_common()),
    }


def extract_sample_records(records: list, count: int = 10) -> list:
    """Extrai amostra de registros com detalhes relevantes."""
    samples = []
    for rec in records[:count]:
        raw = rec.get("raw_record", {})
        if isinstance(raw, str):
            try:
                raw = json.loads(raw)
            except:
                raw = {}

        errors = rec.get("errors", [])
        if isinstance(errors, str):
            try:
                errors = json.loads(errors)
            except:
                errors = []

        sample = {
            "id_interno": rec.get("id_interno"),
            "status": rec.get("status"),
            "run_id": rec.get("run_id"),
            "errors": errors,
            "missing_fields": [
                e.get("field") for e in errors
                if e.get("code") == "missing_required_field"
            ],
            "raw_record_keys": list(raw.keys()) if raw else [],
            "raw_record_sample": {
                k: (str(v)[:100] if v else None)
                for k, v in raw.items()
            } if raw else {},
        }
        samples.append(sample)

    return samples


def main():
    print("=" * 70)
    print("DIAGNÓSTICO FORENSE DE QUARENTENA - ACHE SUCATAS")
    print("=" * 70)
    print(f"Executado em: {datetime.now().isoformat()}")
    print()

    # 1. Obter relatórios recentes
    print("[1] RELATÓRIOS DE EXECUÇÃO RECENTES")
    print("-" * 70)
    reports = get_run_reports(20)

    target_runs = [
        "20260129T085904Z_993dc64e",
        "20260129T083054Z_b0f94720",
        "20260129T012107Z_b3537670",
        "20260128T162822Z_6b1837d1",
    ]

    print(f"Total de relatórios encontrados: {len(reports)}")
    print()

    for rep in reports:
        run_id = rep.get("run_id", "")
        is_target = any(t in run_id for t in target_runs)
        marker = " <<< TARGET" if is_target else ""

        total = rep.get("total", 0)
        com_link = rep.get("com_link", 0)
        sem_link = rep.get("sem_link", 0)

        print(f"  - {run_id}")
        print(f"    Created: {rep.get('created_at')}")
        print(f"    Total: {total}, Com Link: {com_link}, Sem Link: {sem_link}{marker}")
        print()

    # 2. Buscar registros quarentenados
    print()
    print("[2] REGISTROS QUARENTENADOS (TODOS)")
    print("-" * 70)

    quarantine_all = get_quarantine_records(limit=500)
    print(f"Total de registros em quarentena: {len(quarantine_all)}")

    # Agrupar por run_id
    by_run = {}
    for rec in quarantine_all:
        rid = rec.get("run_id", "unknown")
        if rid not in by_run:
            by_run[rid] = []
        by_run[rid].append(rec)

    print(f"Runs com quarentena: {len(by_run)}")
    print()

    for rid, recs in sorted(by_run.items(), key=lambda x: -len(x[1]))[:10]:
        is_target = any(t in rid for t in target_runs)
        marker = " <<< TARGET" if is_target else ""
        print(f"  - {rid}: {len(recs)} registros{marker}")

    # 3. Análise de campos faltantes
    print()
    print("[3] ANÁLISE DE CAMPOS FALTANTES (GLOBAL)")
    print("-" * 70)

    analysis = analyze_missing_fields(quarantine_all)

    print("Campos faltantes (missing_required_field):")
    for field, count in analysis["missing_fields"].items():
        print(f"  - {field}: {count}")

    print()
    print("Códigos de erro:")
    for code, count in analysis["error_codes"].items():
        print(f"  - {code}: {count}")

    # 4. Amostras detalhadas
    print()
    print("[4] AMOSTRAS DE REGISTROS QUARENTENADOS")
    print("-" * 70)

    samples = extract_sample_records(quarantine_all, 10)

    for i, sample in enumerate(samples, 1):
        print(f"\n--- Amostra {i} ---")
        print(f"ID: {sample['id_interno']}")
        print(f"Status: {sample['status']}")
        print(f"Run: {sample['run_id']}")
        print(f"Campos faltantes: {sample['missing_fields']}")
        print(f"Campos presentes no raw_record: {sample['raw_record_keys']}")
        print("Valores do raw_record:")
        for k, v in sample['raw_record_sample'].items():
            print(f"  - {k}: {v}")

    # 5. Análise por run específico (se disponível)
    print()
    print("[5] ANÁLISE DOS RUNS ALVO")
    print("-" * 70)

    for target in target_runs:
        matching_runs = [rid for rid in by_run.keys() if target in rid]
        if matching_runs:
            for rid in matching_runs:
                print(f"\nRun: {rid}")
                recs = by_run[rid]
                analysis = analyze_missing_fields(recs)
                print(f"  Registros: {len(recs)}")
                print(f"  Campos faltantes:")
                for field, count in analysis["missing_fields"].items():
                    print(f"    - {field}: {count}")
        else:
            print(f"\nRun {target}: NÃO ENCONTRADO na tabela dataset_rejections")

    # 6. Exportar para JSON
    output_dir = Path(__file__).parent.parent / "docs"
    output_dir.mkdir(parents=True, exist_ok=True)

    output = {
        "timestamp": datetime.now().isoformat(),
        "total_quarantine_records": len(quarantine_all),
        "runs_with_quarantine": len(by_run),
        "global_analysis": analysis,
        "samples": samples,
        "run_reports": reports,
    }

    output_path = output_dir / "forensic_quarantine_analysis.json"
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(output, f, ensure_ascii=False, indent=2, default=str)

    print()
    print(f"[6] RESULTADO EXPORTADO PARA: {output_path}")
    print("=" * 70)


if __name__ == "__main__":
    main()
