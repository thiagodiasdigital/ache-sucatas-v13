#!/usr/bin/env python3
"""
Phase 3: Extraction Proof Script

This script demonstrates that data CAN be extracted from the HTML
of leiloesjudiciais.com.br lot pages.

It:
1. Fetches 3 real lot URLs from the sitemap
2. Saves the HTML to out/leiloesjudiciais/html/
3. Extracts data from the HTML
4. Generates a proof report at out/leiloesjudiciais/reports/extraction_proof.md

LIMITATION: The site is a SPA (Vue.js), so values/dates are NOT available
in the static HTML. Only title (vehicle + location) can be extracted.
"""

import sys
from datetime import datetime
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from connectors.leiloesjudiciais.config import config
from connectors.leiloesjudiciais.discover import LeilaoDiscovery
from connectors.leiloesjudiciais.fetch import LeilaoFetcher, FetchStatus
from connectors.leiloesjudiciais.parse import LeilaoParser


def run_extraction_proof(num_samples: int = 3):
    """
    Run extraction proof for Phase 3.

    Args:
        num_samples: Number of lot pages to sample (default 3)
    """
    print("=" * 70)
    print("PHASE 3: EXTRACTION PROOF")
    print("=" * 70)
    print(f"Timestamp: {datetime.utcnow().isoformat()}")
    print()

    # Initialize components
    discovery = LeilaoDiscovery(config)
    fetcher = LeilaoFetcher(config)
    parser = LeilaoParser(config, html_output_dir="out/leiloesjudiciais/html")

    # Create output directories
    Path("out/leiloesjudiciais/html").mkdir(parents=True, exist_ok=True)
    Path("out/leiloesjudiciais/reports").mkdir(parents=True, exist_ok=True)

    # Step 1: Discover lots from sitemap
    print("[1/4] Discovering lots from sitemap...")
    lots, discovery_report = discovery.discover_from_sitemap(
        filter_vehicles_only=False,  # Get all to find valid ones
        max_lots=50  # Fetch more to find valid ones (many are 410 gone)
    )
    print(f"  Found {len(lots)} lot URLs in sitemap")

    if not lots:
        print("ERROR: No lots found in sitemap")
        return

    # Step 2: Fetch sample lot pages
    print(f"\n[2/4] Fetching {num_samples} sample lot pages...")
    samples = []
    attempts = 0
    max_attempts = min(len(lots), 20)  # Try up to 20 URLs to find 3 valid ones

    for lot in lots:
        if len(samples) >= num_samples:
            break
        if attempts >= max_attempts:
            break

        attempts += 1
        result = fetcher.fetch(lot.url)

        if result.status == FetchStatus.SUCCESS:
            samples.append((lot, result))
            print(f"  [{len(samples)}/{num_samples}] OK: {lot.url}")
        else:
            print(f"  SKIP ({result.status.value}): {lot.url}")

    print(f"  Collected {len(samples)} valid samples after {attempts} attempts")

    if not samples:
        print("ERROR: Could not fetch any valid lot pages")
        return

    # Step 3: Parse and extract data
    print(f"\n[3/4] Parsing and extracting data from {len(samples)} samples...")
    extraction_results = []

    for lot, fetch_result in samples:
        parsed = parser.parse(fetch_result.url, fetch_result.content, save_html=True)

        extraction_results.append({
            "url": lot.url,
            "leilao_id": lot.leilao_id,
            "lote_id": lot.lote_id,
            "titulo_completo": parsed.titulo_completo,
            "descricao_veiculo": parsed.descricao_veiculo,
            "cidade": parsed.cidade,
            "uf": parsed.uf,
            "og_title": parsed.og_title,
            "og_description": parsed.og_description,
            "og_image": parsed.og_image,
            "valor_avaliacao": parsed.valor_avaliacao,
            "data_leilao": parsed.data_leilao,
            "imagens": parsed.imagens[:3] if parsed.imagens else [],
            "confidence": parsed.extraction_confidence,
            "warnings": parsed.warnings,
        })

        print(f"  Parsed: {parsed.descricao_veiculo or 'N/A'} - {parsed.cidade}/{parsed.uf}")

    # Step 4: Generate proof report
    print("\n[4/4] Generating extraction proof report...")
    report_path = generate_proof_report(extraction_results, parser.get_saved_htmls())
    print(f"  Report saved to: {report_path}")

    print("\n" + "=" * 70)
    print("EXTRACTION PROOF COMPLETE")
    print("=" * 70)

    return extraction_results


def generate_proof_report(results: list, saved_htmls: list) -> str:
    """Generate the extraction_proof.md report."""

    report_lines = [
        "# Extraction Proof Report - Leilões Judiciais",
        "",
        f"**Generated:** {datetime.utcnow().isoformat()}Z",
        f"**Samples:** {len(results)}",
        "",
        "---",
        "",
        "## Summary",
        "",
        "This report documents the extraction capabilities from leiloesjudiciais.com.br.",
        "",
        "### Site Characteristics",
        "",
        "- **Type:** Single Page Application (Vue.js)",
        "- **Data Loading:** Dynamic via JavaScript/API",
        "- **HTML Content:** Limited static content",
        "",
        "### Extractable Fields",
        "",
        "| Field | Available in HTML | Extraction Method |",
        "|-------|------------------|-------------------|",
        "| Vehicle Description | YES | `<title>` tag parsing |",
        "| City | YES | `<title>` tag parsing |",
        "| State (UF) | YES | `<title>` tag parsing |",
        "| Lot URL | YES | Sitemap + URL parsing |",
        "| OG Title | YES | Meta tag |",
        "| OG Description | PARTIAL | Meta tag |",
        "| OG Image | PARTIAL | Meta tag |",
        "| Valuation Amount | NO | Requires JavaScript |",
        "| Minimum Bid | NO | Requires JavaScript |",
        "| Auction Date | NO | Requires JavaScript |",
        "| Current Bid | NO | Requires JavaScript |",
        "| Full Images | NO | Requires JavaScript |",
        "",
        "---",
        "",
        "## Sample Extractions",
        "",
    ]

    for i, result in enumerate(results, 1):
        report_lines.extend([
            f"### Sample {i}: {result['leilao_id']}/{result['lote_id']}",
            "",
            f"**URL:** `{result['url']}`",
            "",
            "#### Extracted Data",
            "",
            f"| Field | Value |",
            f"|-------|-------|",
            f"| Title (full) | {result['titulo_completo'] or 'N/A'} |",
            f"| Vehicle Description | {result['descricao_veiculo'] or 'N/A'} |",
            f"| City | {result['cidade'] or 'N/A'} |",
            f"| UF (State) | {result['uf'] or 'N/A'} |",
            f"| OG Title | {result['og_title'] or 'N/A'} |",
            f"| Valuation | {'R$ ' + str(result['valor_avaliacao']) if result['valor_avaliacao'] else 'NOT IN HTML'} |",
            f"| Auction Date | {result['data_leilao'] or 'NOT IN HTML'} |",
            f"| Confidence Score | {result['confidence']}% |",
            "",
        ])

        if result['warnings']:
            report_lines.append("#### Warnings")
            report_lines.append("")
            for warning in result['warnings']:
                report_lines.append(f"- {warning}")
            report_lines.append("")

        report_lines.append("---")
        report_lines.append("")

    # HTML Evidence section
    report_lines.extend([
        "## HTML Evidence Files",
        "",
        "The following HTML files were saved as evidence:",
        "",
    ])

    for html_info in saved_htmls:
        report_lines.append(f"- `{html_info['filepath']}` (Lote {html_info['leilao_id']}/{html_info['lote_id']})")

    report_lines.extend([
        "",
        "---",
        "",
        "## Selectors Used",
        "",
        "```python",
        "# Title pattern: 'DESCRIPTION - CITY/UF - Leilões Judiciais'",
        "TITLE_PATTERN = r'^(.+?)\\s*-\\s*([A-Za-zÀ-ÿ\\s]+)/([A-Z]{2})\\s*-\\s*Leilões Judiciais'",
        "",
        "# Meta tags",
        "og:title = soup.find('meta', property='og:title')['content']",
        "og:description = soup.find('meta', property='og:description')['content']",
        "og:image = soup.find('meta', property='og:image')['content']",
        "```",
        "",
        "---",
        "",
        "## Conclusion",
        "",
        "The extraction successfully retrieves vehicle description and location from the HTML.",
        "However, **valuation amounts and auction dates are NOT available in the static HTML**.",
        "",
        "### Recommendations",
        "",
        "1. **API Investigation:** The site likely has a REST API that returns lot details.",
        "2. **Playwright Fallback:** Use browser automation to render JavaScript and extract data.",
        "3. **Accept Partial Data:** For now, emit items with available fields (title, location, URL).",
        "",
        "---",
        "",
        "*Report generated by extraction_proof.py*",
    ])

    report_content = "\n".join(report_lines)

    # Save report
    report_path = "out/leiloesjudiciais/reports/extraction_proof.md"
    with open(report_path, 'w', encoding='utf-8') as f:
        f.write(report_content)

    return report_path


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Generate extraction proof for Phase 3")
    parser.add_argument("--samples", type=int, default=3, help="Number of samples to extract")
    args = parser.parse_args()

    run_extraction_proof(args.samples)
