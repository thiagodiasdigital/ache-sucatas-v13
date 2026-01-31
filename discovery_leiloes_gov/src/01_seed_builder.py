#!/usr/bin/env python3
"""
01_seed_builder.py - Gera/valida estrutura de seeds para discovery

Uso:
    python src/01_seed_builder.py [--validate] [--export-urls]

Funcoes:
    - Valida estrutura do seeds.json
    - Lista seeds por categoria
    - Exporta URLs para arquivo de entrada
"""

import json
import sys
from pathlib import Path
from datetime import datetime

# Paths
BASE_DIR = Path(__file__).parent.parent
CONFIG_DIR = BASE_DIR / "config"
SEEDS_FILE = CONFIG_DIR / "seeds.json"
OUTPUTS_DIR = BASE_DIR / "outputs"


def load_seeds() -> dict:
    """Carrega seeds.json"""
    if not SEEDS_FILE.exists():
        print(f"ERRO: {SEEDS_FILE} nao encontrado")
        sys.exit(1)

    with open(SEEDS_FILE, "r", encoding="utf-8") as f:
        return json.load(f)


def validate_seeds(data: dict) -> list:
    """Valida estrutura e retorna lista de problemas"""
    issues = []

    if "metadata" not in data:
        issues.append("Falta secao 'metadata'")

    if "categories" not in data:
        issues.append("Falta secao 'categories'")
        return issues

    for cat_name, cat_data in data["categories"].items():
        if "seeds" not in cat_data:
            issues.append(f"Categoria '{cat_name}': falta lista 'seeds'")
            continue

        for i, seed in enumerate(cat_data["seeds"]):
            # Verificar campos obrigatorios
            if "status" not in seed:
                issues.append(f"{cat_name}[{i}]: falta campo 'status'")

            # Verificar se URL e valida (quando presente)
            url = seed.get("url")
            if url and not url.startswith(("http://", "https://")):
                issues.append(f"{cat_name}[{i}]: URL invalida: {url}")

    return issues


def list_seeds(data: dict) -> None:
    """Lista seeds por categoria"""
    print("=" * 60)
    print("SEEDS CADASTRADAS")
    print("=" * 60)

    total = 0
    confirmed = 0
    needs_discovery = 0

    for cat_name, cat_data in data.get("categories", {}).items():
        seeds = cat_data.get("seeds", [])
        print(f"\n[{cat_name.upper()}] - {len(seeds)} seeds")
        print("-" * 40)

        for seed in seeds:
            status = seed.get("status", "unknown")
            url = seed.get("url", "N/A")
            nome = seed.get("nome") or seed.get("cidade") or seed.get("uf", "")

            status_icon = "OK" if status == "confirmed" else "?" if status == "needs_discovery" else "X"
            print(f"  [{status_icon}] {nome}: {url}")

            total += 1
            if status == "confirmed":
                confirmed += 1
            elif status == "needs_discovery":
                needs_discovery += 1

    print("\n" + "=" * 60)
    print(f"TOTAL: {total} seeds")
    print(f"  - Confirmadas: {confirmed}")
    print(f"  - Precisam discovery: {needs_discovery}")
    print("=" * 60)


def export_urls(data: dict) -> None:
    """Exporta URLs confirmadas para arquivo de entrada"""
    OUTPUTS_DIR.mkdir(exist_ok=True)
    output_file = OUTPUTS_DIR / "seeds_urls.txt"

    urls = []
    for cat_name, cat_data in data.get("categories", {}).items():
        for seed in cat_data.get("seeds", []):
            url = seed.get("url")
            status = seed.get("status")
            if url and status == "confirmed":
                urls.append(url)

    with open(output_file, "w", encoding="utf-8") as f:
        f.write(f"# URLs exportadas de seeds.json em {datetime.now().isoformat()}\n")
        f.write(f"# Total: {len(urls)} URLs confirmadas\n\n")
        for url in urls:
            f.write(url + "\n")

    print(f"Exportadas {len(urls)} URLs para: {output_file}")


def main():
    import argparse
    parser = argparse.ArgumentParser(description="Seed Builder - Gerencia seeds de discovery")
    parser.add_argument("--validate", action="store_true", help="Valida estrutura do seeds.json")
    parser.add_argument("--export-urls", action="store_true", help="Exporta URLs confirmadas")
    args = parser.parse_args()

    print(f"Carregando: {SEEDS_FILE}")
    data = load_seeds()

    # Sempre validar
    issues = validate_seeds(data)
    if issues:
        print("\nPROBLEMAS ENCONTRADOS:")
        for issue in issues:
            print(f"  - {issue}")
    else:
        print("Validacao OK: nenhum problema estrutural")

    # Listar seeds
    list_seeds(data)

    # Exportar se solicitado
    if args.export_urls:
        export_urls(data)


if __name__ == "__main__":
    main()
