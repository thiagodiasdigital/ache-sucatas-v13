#!/usr/bin/env python3
"""
05_officiality_score.py - Pontua candidatos por oficialidade

Entrada: outputs/candidates_enriched.csv, outputs/crawl_hits.csv
Saida: outputs/sources_ranked.csv, outputs/blocked_or_hard_cases.csv

Criterios de pontuacao (0-100):
    - Dominio .gov.br: +30
    - Dominio DETRAN oficial: +20
    - Presenca de keywords de leilao: +15
    - Referencia a edital/numero: +15
    - Referencia a orgao/comissao: +10
    - HTTPS: +5
    - Status 200: +5
"""

import csv
import json
import re
from pathlib import Path
from datetime import datetime
from urllib.parse import urlparse

# Paths
BASE_DIR = Path(__file__).parent.parent
OUTPUTS_DIR = BASE_DIR / "outputs"

# Pontuacoes
SCORE_GOV_BR = 30
SCORE_DETRAN = 20
SCORE_KEYWORDS = 15
SCORE_EDITAL_REF = 15
SCORE_ORGAO_REF = 10
SCORE_HTTPS = 5
SCORE_HTTP_200 = 5

# Patterns para deteccao
EDITAL_PATTERNS = [
    r'edital\s*n[°ºo]?\s*\d+',
    r'processo\s*n[°ºo]?\s*\d+',
    r'leilao\s*n[°ºo]?\s*\d+',
    r'leilão\s*n[°ºo]?\s*\d+',
    r'pregao\s*n[°ºo]?\s*\d+',
    r'pregão\s*n[°ºo]?\s*\d+',
]

ORGAO_PATTERNS = [
    r'comiss[aã]o\s+de\s+leil[aã]o',
    r'comiss[aã]o\s+permanente',
    r'denatran',
    r'senatran',
    r'secretaria\s+de',
    r'minist[eé]rio\s+',
    r'tribunal\s+',
    r'receita\s+federal',
    r'pol[ií]cia\s+federal',
    r'pol[ií]cia\s+rodovi[aá]ria',
]

# Categorias de dominio
DETRAN_DOMAINS = [
    'detran.sp.gov.br', 'detran.rj.gov.br', 'detran.mg.gov.br',
    'detran.pr.gov.br', 'detran.rs.gov.br', 'detran.sc.gov.br',
    'detran.ba.gov.br', 'detran.pe.gov.br', 'detran.ce.gov.br',
    'detran.go.gov.br', 'detran.df.gov.br', 'detran.es.gov.br',
    'detran.pa.gov.br', 'detran.am.gov.br', 'detran.mt.gov.br',
    'detran.ms.gov.br', 'detran.ma.gov.br', 'detran.pb.gov.br',
    'detran.rn.gov.br', 'detran.pi.gov.br', 'detran.al.gov.br',
    'detran.se.gov.br', 'detran.to.gov.br', 'detran.ro.gov.br',
    'detran.ac.gov.br', 'detran.ap.gov.br', 'detran.rr.gov.br',
]

# Hard cases (bloqueados)
HARD_CASE_INDICATORS = [
    'captcha', 'cloudflare', 'login required', 'acesso negado',
    'javascript required', 'habilite javascript', 'enable javascript',
    '403 forbidden', '401 unauthorized',
]


def load_enriched_candidates() -> list[dict]:
    """Carrega candidatos enriquecidos"""
    file_path = OUTPUTS_DIR / "candidates_enriched.csv"
    if not file_path.exists():
        return []

    candidates = []
    with open(file_path, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            candidates.append(row)
    return candidates


def load_crawl_hits() -> list[dict]:
    """Carrega hits do crawl"""
    file_path = OUTPUTS_DIR / "crawl_hits.csv"
    if not file_path.exists():
        return []

    hits = []
    with open(file_path, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            hits.append(row)
    return hits


def detect_pattern(text: str, patterns: list[str]) -> bool:
    """Verifica se texto contem algum pattern"""
    text_lower = text.lower()
    for pattern in patterns:
        if re.search(pattern, text_lower):
            return True
    return False


def is_hard_case(error: str, title: str) -> bool:
    """Verifica se e um hard case (bloqueado/JS pesado)"""
    full_text = f"{error or ''} {title or ''}".lower()
    return any(indicator in full_text for indicator in HARD_CASE_INDICATORS)


def categorize_domain(domain: str) -> str:
    """Categoriza dominio"""
    domain_lower = domain.lower()

    if any(d in domain_lower for d in DETRAN_DOMAINS):
        return "DETRAN"
    if "receita.fazenda.gov.br" in domain_lower or "gov.br/receitafederal" in domain_lower:
        return "FEDERAL_RFB"
    if "gov.br/pf" in domain_lower or "gov.br/prf" in domain_lower:
        return "FEDERAL_POLICIA"
    if "pncp.gov.br" in domain_lower or "compras.gov.br" in domain_lower:
        return "FEDERAL_COMPRAS"
    if ".gov.br" in domain_lower:
        return "GOV_BR_OUTRO"
    if "in.gov.br" in domain_lower or "imprensaoficial" in domain_lower:
        return "DIARIO_OFICIAL"
    if "leiloesjudiciais" in domain_lower:
        return "LEILOEIRA_OFICIAL"

    return "OUTRO"


def extract_uf(url: str, domain: str) -> str:
    """Tenta extrair UF da URL/dominio"""
    # Pattern: detran.XX.gov.br
    match = re.search(r'detran\.([a-z]{2})\.gov\.br', domain.lower())
    if match:
        return match.group(1).upper()

    # Pattern: .XX.gov.br
    match = re.search(r'\.([a-z]{2})\.gov\.br', domain.lower())
    if match:
        uf = match.group(1).upper()
        if uf in ['SP', 'RJ', 'MG', 'PR', 'RS', 'SC', 'BA', 'PE', 'CE', 'GO',
                   'DF', 'ES', 'PA', 'AM', 'MT', 'MS', 'MA', 'PB', 'RN', 'PI',
                   'AL', 'SE', 'TO', 'RO', 'AC', 'AP', 'RR']:
            return uf

    return ""


def score_candidate(candidate: dict) -> dict:
    """Calcula score de oficialidade"""
    url = candidate.get("url", "")
    domain = candidate.get("domain", "")
    title = candidate.get("title", "")
    keywords = candidate.get("keywords_found", "")
    status_code = candidate.get("status_code", "")
    error = candidate.get("error", "")

    # Iniciar score
    score = 0
    score_breakdown = []

    # HTTPS
    if url.startswith("https://"):
        score += SCORE_HTTPS
        score_breakdown.append(f"HTTPS:+{SCORE_HTTPS}")

    # HTTP 200
    if str(status_code) == "200":
        score += SCORE_HTTP_200
        score_breakdown.append(f"HTTP200:+{SCORE_HTTP_200}")

    # Dominio .gov.br
    if ".gov.br" in domain.lower():
        score += SCORE_GOV_BR
        score_breakdown.append(f"GOV_BR:+{SCORE_GOV_BR}")

    # DETRAN oficial
    if any(d in domain.lower() for d in DETRAN_DOMAINS):
        score += SCORE_DETRAN
        score_breakdown.append(f"DETRAN:+{SCORE_DETRAN}")

    # Keywords
    if keywords:
        score += SCORE_KEYWORDS
        score_breakdown.append(f"KEYWORDS:+{SCORE_KEYWORDS}")

    # Referencia a edital/numero
    full_text = f"{url} {title}"
    if detect_pattern(full_text, EDITAL_PATTERNS):
        score += SCORE_EDITAL_REF
        score_breakdown.append(f"EDITAL_REF:+{SCORE_EDITAL_REF}")

    # Referencia a orgao
    if detect_pattern(full_text, ORGAO_PATTERNS):
        score += SCORE_ORGAO_REF
        score_breakdown.append(f"ORGAO_REF:+{SCORE_ORGAO_REF}")

    # Construir resultado
    result = {
        "url": url,
        "domain": domain,
        "title": title,
        "score": min(score, 100),  # Cap at 100
        "score_breakdown": "|".join(score_breakdown),
        "category": categorize_domain(domain),
        "uf": extract_uf(url, domain),
        "keywords": keywords,
        "status_code": status_code,
        "is_hard_case": is_hard_case(error, title),
        "error": error,
    }

    return result


def generate_report(ranked: list[dict], hard_cases: list[dict]) -> str:
    """Gera conteudo do REPORT.md"""
    now = datetime.now().isoformat()

    # Estatisticas
    total = len(ranked)
    approved = [r for r in ranked if r["score"] >= 70]
    by_category = {}
    for r in ranked:
        cat = r["category"]
        by_category[cat] = by_category.get(cat, 0) + 1

    report = f"""# Discovery Report - Leiloes de Veiculos Governamentais

**Gerado em:** {now}

## Resumo Executivo

| Metrica | Valor |
|---------|-------|
| Total URLs analisadas | {total} |
| Aprovadas (score >= 70) | {len(approved)} |
| Hard cases (bloqueados) | {len(hard_cases)} |

## Distribuicao por Categoria

| Categoria | Quantidade |
|-----------|------------|
"""
    for cat, count in sorted(by_category.items(), key=lambda x: -x[1]):
        report += f"| {cat} | {count} |\n"

    report += """
## Top 30 Fontes (por score)

| Rank | Score | Categoria | UF | URL | Evidencia |
|------|-------|-----------|----|----|-----------|
"""
    for i, r in enumerate(ranked[:30], 1):
        url_short = r["url"][:50] + "..." if len(r["url"]) > 50 else r["url"]
        report += f"| {i} | {r['score']} | {r['category']} | {r['uf'] or '-'} | {url_short} | {r['score_breakdown'][:30]} |\n"

    report += """
## Hard Cases (requerem tratamento especial)

Estas URLs apresentaram bloqueios que impedem coleta automatica:
- Captcha
- Cloudflare protection
- Login obrigatorio
- JavaScript pesado

| URL | Erro/Indicador |
|-----|----------------|
"""
    for hc in hard_cases[:20]:
        url_short = hc["url"][:50] + "..." if len(hc["url"]) > 50 else hc["url"]
        report += f"| {url_short} | {hc.get('error', 'JS/Captcha')[:40]} |\n"

    report += """
## Proximos Passos

### Prontas para Extracao (score >= 70)
Estas fontes podem ser convertidas em pipelines de extracao:

1. **Avaliar estrutura HTML** - Verificar se dados sao extraiveis via BeautifulSoup
2. **Definir contrato de dados** - Schema de saida normalizado
3. **Implementar extrator** - Usando patterns do projeto existente

### Hard Cases - Recomendacoes

| Tipo | Solucao Sugerida |
|------|------------------|
| Captcha | Considerar servico de resolucao ou acesso manual periodico |
| Cloudflare | Playwright com fingerprint rotation |
| Login | Verificar se ha API publica ou dados abertos |
| JS pesado | Playwright headless com wait conditions |

**IMPORTANTE:** Qualquer automacao deve respeitar rate limits e ToS dos sites.

---

*Gerado automaticamente pelo Discovery Pipeline*
"""

    return report


def main():
    print("=" * 60)
    print("OFFICIALITY SCORE - Pontuacao de Fontes")
    print("=" * 60)

    # Carregar dados
    candidates = load_enriched_candidates()
    crawl_hits = load_crawl_hits()

    print(f"Candidatos enriquecidos: {len(candidates)}")
    print(f"Crawl hits: {len(crawl_hits)}")

    # Combinar todos
    all_urls = {}

    for c in candidates:
        url = c.get("url")
        if url:
            all_urls[url] = c

    for h in crawl_hits:
        url = h.get("url")
        if url and url not in all_urls:
            # Converter hit para formato de candidato
            all_urls[url] = {
                "url": url,
                "domain": urlparse(url).netloc,
                "title": h.get("title", ""),
                "status_code": "200",  # Se veio do crawl, funcionou
                "keywords_found": h.get("keywords", ""),
                "error": "",
            }

    print(f"Total unico de URLs: {len(all_urls)}")

    # Pontuar
    ranked = []
    hard_cases = []

    for url, data in all_urls.items():
        scored = score_candidate(data)
        if scored["is_hard_case"]:
            hard_cases.append(scored)
        else:
            ranked.append(scored)

    # Ordenar por score
    ranked.sort(key=lambda x: -x["score"])

    # Salvar ranked
    OUTPUTS_DIR.mkdir(exist_ok=True)

    ranked_file = OUTPUTS_DIR / "sources_ranked.csv"
    fieldnames = ["url", "score", "category", "uf", "domain", "title", "keywords",
                  "score_breakdown", "status_code"]

    with open(ranked_file, "w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        for r in ranked:
            writer.writerow(r)

    print(f"\nRanked salvo: {ranked_file}")

    # Salvar hard cases
    hard_file = OUTPUTS_DIR / "blocked_or_hard_cases.csv"
    with open(hard_file, "w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=["url", "domain", "error", "category"],
                                extrasaction="ignore")
        writer.writeheader()
        for hc in hard_cases:
            writer.writerow(hc)

    print(f"Hard cases salvo: {hard_file}")

    # Gerar report
    report_content = generate_report(ranked, hard_cases)
    report_file = BASE_DIR / "REPORT.md"
    with open(report_file, "w", encoding="utf-8") as f:
        f.write(report_content)

    print(f"Report gerado: {report_file}")

    # Log do run
    log_file = OUTPUTS_DIR / "run_log.jsonl"
    log_entry = {
        "timestamp": datetime.now().isoformat(),
        "total_urls": len(all_urls),
        "ranked": len(ranked),
        "hard_cases": len(hard_cases),
        "approved_70plus": len([r for r in ranked if r["score"] >= 70]),
    }
    with open(log_file, "a", encoding="utf-8") as f:
        f.write(json.dumps(log_entry, ensure_ascii=False) + "\n")

    # Resumo final
    print("\n" + "=" * 60)
    print("RESUMO FINAL")
    print("=" * 60)
    approved = [r for r in ranked if r["score"] >= 70]
    print(f"Total URLs analisadas: {len(all_urls)}")
    print(f"Fontes aprovadas (score >= 70): {len(approved)}")
    print(f"Hard cases: {len(hard_cases)}")

    if approved:
        print("\nTop 5 fontes:")
        for i, r in enumerate(approved[:5], 1):
            print(f"  {i}. [{r['score']}] {r['category']}: {r['url'][:50]}")


if __name__ == "__main__":
    main()
