#!/usr/bin/env python3
"""
03_collect_candidates.py - Coleta e enriquece URLs candidatas

Entrada: inputs/manual_candidates.txt
Saida: outputs/candidates_enriched.csv

Funcoes:
    - Normaliza URLs
    - Remove duplicados
    - Checa status HTTP
    - Extrai titulo da pagina
    - Detecta keywords no conteudo
"""

import csv
import json
import re
import time
import hashlib
from pathlib import Path
from datetime import datetime
from urllib.parse import urlparse, urljoin
from html.parser import HTMLParser

# Tentar importar requests, fallback para urllib
try:
    import requests
    HAS_REQUESTS = True
except ImportError:
    import urllib.request
    import urllib.error
    HAS_REQUESTS = False
    print("AVISO: requests nao disponivel, usando urllib (funcionalidade limitada)")

# Paths
BASE_DIR = Path(__file__).parent.parent
CONFIG_DIR = BASE_DIR / "config"
INPUTS_DIR = BASE_DIR / "inputs"
OUTPUTS_DIR = BASE_DIR / "outputs"
CACHE_DIR = OUTPUTS_DIR / "http_cache"

# Config
TIMEOUT = 15
MAX_RETRIES = 3
RETRY_BACKOFF = 2  # segundos base
RATE_LIMIT = 1.0   # segundos entre requests por dominio
USER_AGENT = "DiscoveryBot/1.0 (+leiloes-gov-discovery; contato: projeto-ache-sucatas)"

# Cache de timestamps por dominio (rate limiting)
domain_last_request: dict[str, float] = {}


class TitleParser(HTMLParser):
    """Parser simples para extrair <title>"""
    def __init__(self):
        super().__init__()
        self.in_title = False
        self.title = ""

    def handle_starttag(self, tag, attrs):
        if tag.lower() == "title":
            self.in_title = True

    def handle_endtag(self, tag):
        if tag.lower() == "title":
            self.in_title = False

    def handle_data(self, data):
        if self.in_title:
            self.title += data


def load_keywords() -> list[str]:
    """Carrega keywords do arquivo de config"""
    keywords_file = CONFIG_DIR / "keywords.txt"
    if not keywords_file.exists():
        print(f"AVISO: {keywords_file} nao encontrado, usando keywords padrao")
        return ["leilao", "leilão", "veiculos", "veículos", "sucata", "edital"]

    keywords = []
    with open(keywords_file, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith("#"):
                keywords.append(line.lower())
    return keywords


def load_candidates() -> list[str]:
    """Carrega URLs do arquivo de candidatos"""
    candidates_file = INPUTS_DIR / "manual_candidates.txt"
    if not candidates_file.exists():
        print(f"ERRO: {candidates_file} nao encontrado")
        return []

    urls = []
    with open(candidates_file, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith("#"):
                # Normalizar URL
                if not line.startswith(("http://", "https://")):
                    line = "https://" + line
                urls.append(line)

    return list(set(urls))  # Remove duplicados


def get_cache_path(url: str) -> Path:
    """Gera path de cache para URL"""
    url_hash = hashlib.md5(url.encode()).hexdigest()
    return CACHE_DIR / f"{url_hash}.json"


def get_cached_response(url: str) -> dict | None:
    """Retorna resposta cacheada se existir e for recente (< 24h)"""
    cache_path = get_cache_path(url)
    if cache_path.exists():
        with open(cache_path, "r", encoding="utf-8") as f:
            data = json.load(f)
            cached_at = datetime.fromisoformat(data.get("cached_at", "2000-01-01"))
            if (datetime.now() - cached_at).total_seconds() < 86400:  # 24h
                return data
    return None


def save_cache(url: str, data: dict) -> None:
    """Salva resposta no cache"""
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    cache_path = get_cache_path(url)
    data["cached_at"] = datetime.now().isoformat()
    with open(cache_path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def rate_limit_wait(domain: str) -> None:
    """Espera rate limit por dominio"""
    now = time.time()
    last = domain_last_request.get(domain, 0)
    wait_time = RATE_LIMIT - (now - last)
    if wait_time > 0:
        time.sleep(wait_time)
    domain_last_request[domain] = time.time()


def fetch_url(url: str) -> dict:
    """Faz request com retries e rate limiting"""
    # Verificar cache
    cached = get_cached_response(url)
    if cached:
        cached["from_cache"] = True
        return cached

    parsed = urlparse(url)
    domain = parsed.netloc

    result = {
        "url": url,
        "status_code": None,
        "title": "",
        "content_snippet": "",
        "error": None,
        "from_cache": False
    }

    for attempt in range(MAX_RETRIES):
        try:
            rate_limit_wait(domain)

            if HAS_REQUESTS:
                headers = {"User-Agent": USER_AGENT}
                resp = requests.get(url, headers=headers, timeout=TIMEOUT, allow_redirects=True)
                result["status_code"] = resp.status_code

                if resp.status_code == 200:
                    # Extrair titulo
                    content = resp.text[:50000]  # Limitar para performance
                    parser = TitleParser()
                    try:
                        parser.feed(content)
                        result["title"] = parser.title.strip()[:200]
                    except:
                        pass

                    # Extrair snippet (primeiros 1000 chars de texto)
                    text = re.sub(r'<[^>]+>', ' ', content)
                    text = re.sub(r'\s+', ' ', text).strip()
                    result["content_snippet"] = text[:1000]
            else:
                # Fallback para urllib
                req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
                with urllib.request.urlopen(req, timeout=TIMEOUT) as resp:
                    result["status_code"] = resp.status
                    content = resp.read().decode("utf-8", errors="ignore")[:50000]

                    parser = TitleParser()
                    try:
                        parser.feed(content)
                        result["title"] = parser.title.strip()[:200]
                    except:
                        pass

                    text = re.sub(r'<[^>]+>', ' ', content)
                    text = re.sub(r'\s+', ' ', text).strip()
                    result["content_snippet"] = text[:1000]

            # Sucesso - salvar cache e retornar
            save_cache(url, result)
            return result

        except Exception as e:
            result["error"] = str(e)
            if attempt < MAX_RETRIES - 1:
                wait = RETRY_BACKOFF * (2 ** attempt)
                print(f"  Retry {attempt + 1}/{MAX_RETRIES} em {wait}s: {e}")
                time.sleep(wait)

    return result


def detect_keywords(text: str, keywords: list[str]) -> list[str]:
    """Detecta keywords no texto"""
    text_lower = text.lower()
    found = []
    for kw in keywords:
        if kw in text_lower:
            found.append(kw)
    return found


def main():
    print("=" * 60)
    print("COLLECT CANDIDATES - Enriquecimento de URLs")
    print("=" * 60)

    # Carregar dados
    keywords = load_keywords()
    print(f"Keywords carregadas: {len(keywords)}")

    candidates = load_candidates()
    print(f"Candidatos carregados: {len(candidates)}")

    if not candidates:
        print("Nenhum candidato para processar. Adicione URLs em inputs/manual_candidates.txt")
        return

    # Processar cada URL
    results = []
    for i, url in enumerate(candidates, 1):
        print(f"\n[{i}/{len(candidates)}] {url[:60]}...")

        data = fetch_url(url)

        if data.get("from_cache"):
            print(f"  (cache) Status: {data['status_code']}")
        else:
            print(f"  Status: {data['status_code']}")

        if data.get("error"):
            print(f"  ERRO: {data['error'][:50]}")
        elif data.get("title"):
            print(f"  Titulo: {data['title'][:50]}")

        # Detectar keywords
        full_text = f"{data.get('title', '')} {data.get('content_snippet', '')}"
        found_keywords = detect_keywords(full_text, keywords)
        data["keywords_found"] = found_keywords
        data["keywords_count"] = len(found_keywords)

        if found_keywords:
            print(f"  Keywords: {', '.join(found_keywords[:5])}")

        # Detectar dominio .gov.br
        parsed = urlparse(url)
        data["domain"] = parsed.netloc
        data["is_gov_br"] = ".gov.br" in parsed.netloc.lower()
        data["is_detran"] = "detran" in parsed.netloc.lower()

        results.append(data)

    # Salvar resultados
    OUTPUTS_DIR.mkdir(exist_ok=True)
    output_file = OUTPUTS_DIR / "candidates_enriched.csv"

    fieldnames = [
        "url", "domain", "status_code", "title", "is_gov_br", "is_detran",
        "keywords_count", "keywords_found", "error", "from_cache"
    ]

    with open(output_file, "w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        for r in results:
            r["keywords_found"] = "|".join(r.get("keywords_found", []))
            writer.writerow(r)

    print("\n" + "=" * 60)
    print(f"RESULTADO: {len(results)} URLs processadas")
    print(f"Salvo em: {output_file}")
    print("=" * 60)

    # Estatisticas
    ok_count = sum(1 for r in results if r.get("status_code") == 200)
    gov_count = sum(1 for r in results if r.get("is_gov_br"))
    with_keywords = sum(1 for r in results if r.get("keywords_count", 0) > 0)

    print(f"\nEstatisticas:")
    print(f"  - HTTP 200: {ok_count}")
    print(f"  - Dominios .gov.br: {gov_count}")
    print(f"  - Com keywords: {with_keywords}")


if __name__ == "__main__":
    main()
