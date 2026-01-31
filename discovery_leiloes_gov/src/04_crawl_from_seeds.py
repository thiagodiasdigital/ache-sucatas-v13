#!/usr/bin/env python3
"""
04_crawl_from_seeds.py - Crawl conservador a partir de seeds conhecidas

Entrada: config/seeds.json (seeds confirmadas)
Saida: outputs/crawl_hits.csv, outputs/crawl_graph.json

Funcoes:
    - Crawl somente em dominios/paths proximos
    - Limite de profundidade (depth=2)
    - Limite de paginas por seed (300)
    - Coleta links internos com keywords
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
from collections import deque

# Tentar importar requests
try:
    import requests
    HAS_REQUESTS = True
except ImportError:
    import urllib.request
    import urllib.error
    HAS_REQUESTS = False
    print("AVISO: requests nao disponivel, usando urllib")

# Paths
BASE_DIR = Path(__file__).parent.parent
CONFIG_DIR = BASE_DIR / "config"
OUTPUTS_DIR = BASE_DIR / "outputs"
CACHE_DIR = OUTPUTS_DIR / "http_cache"

# Config
TIMEOUT = 15
MAX_RETRIES = 2
RATE_LIMIT = 1.5  # segundos entre requests
MAX_DEPTH = 2
MAX_PAGES_PER_SEED = 300
USER_AGENT = "DiscoveryBot/1.0 (+leiloes-gov-discovery; contato: projeto-ache-sucatas)"

# Cache de timestamps por dominio
domain_last_request: dict[str, float] = {}


class LinkExtractor(HTMLParser):
    """Extrai links e titulo de HTML"""
    def __init__(self, base_url: str):
        super().__init__()
        self.base_url = base_url
        self.links = []
        self.in_title = False
        self.title = ""

    def handle_starttag(self, tag, attrs):
        if tag.lower() == "title":
            self.in_title = True
        elif tag.lower() == "a":
            for name, value in attrs:
                if name.lower() == "href" and value:
                    # Normalizar URL
                    full_url = urljoin(self.base_url, value)
                    self.links.append(full_url)

    def handle_endtag(self, tag):
        if tag.lower() == "title":
            self.in_title = False

    def handle_data(self, data):
        if self.in_title:
            self.title += data


def load_keywords() -> list[str]:
    """Carrega keywords"""
    keywords_file = CONFIG_DIR / "keywords.txt"
    if not keywords_file.exists():
        return ["leilao", "leilão", "veiculos", "veículos", "sucata", "edital"]

    keywords = []
    with open(keywords_file, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith("#"):
                keywords.append(line.lower())
    return keywords


def load_confirmed_seeds() -> list[str]:
    """Carrega seeds confirmadas de seeds.json"""
    seeds_file = CONFIG_DIR / "seeds.json"
    if not seeds_file.exists():
        print(f"ERRO: {seeds_file} nao encontrado")
        return []

    with open(seeds_file, "r", encoding="utf-8") as f:
        data = json.load(f)

    urls = []
    for cat_name, cat_data in data.get("categories", {}).items():
        for seed in cat_data.get("seeds", []):
            url = seed.get("url")
            status = seed.get("status")
            if url and status == "confirmed":
                urls.append(url)

    return urls


def get_cache_path(url: str) -> Path:
    """Gera path de cache"""
    url_hash = hashlib.md5(url.encode()).hexdigest()
    return CACHE_DIR / f"{url_hash}.json"


def rate_limit_wait(domain: str) -> None:
    """Espera rate limit"""
    now = time.time()
    last = domain_last_request.get(domain, 0)
    wait_time = RATE_LIMIT - (now - last)
    if wait_time > 0:
        time.sleep(wait_time)
    domain_last_request[domain] = time.time()


def fetch_page(url: str) -> dict:
    """Faz request e extrai links"""
    # Verificar cache
    cache_path = get_cache_path(url)
    if cache_path.exists():
        with open(cache_path, "r", encoding="utf-8") as f:
            data = json.load(f)
            if "links" in data:  # Cache valido
                return data

    parsed = urlparse(url)
    domain = parsed.netloc

    result = {
        "url": url,
        "status_code": None,
        "title": "",
        "links": [],
        "error": None
    }

    for attempt in range(MAX_RETRIES):
        try:
            rate_limit_wait(domain)

            if HAS_REQUESTS:
                headers = {"User-Agent": USER_AGENT}
                resp = requests.get(url, headers=headers, timeout=TIMEOUT, allow_redirects=True)
                result["status_code"] = resp.status_code

                if resp.status_code == 200:
                    content = resp.text[:100000]
                    parser = LinkExtractor(url)
                    try:
                        parser.feed(content)
                        result["title"] = parser.title.strip()[:200]
                        result["links"] = parser.links
                    except:
                        pass
            else:
                req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
                with urllib.request.urlopen(req, timeout=TIMEOUT) as resp:
                    result["status_code"] = resp.status
                    content = resp.read().decode("utf-8", errors="ignore")[:100000]
                    parser = LinkExtractor(url)
                    try:
                        parser.feed(content)
                        result["title"] = parser.title.strip()[:200]
                        result["links"] = parser.links
                    except:
                        pass

            # Salvar cache
            CACHE_DIR.mkdir(parents=True, exist_ok=True)
            with open(cache_path, "w", encoding="utf-8") as f:
                json.dump(result, f, ensure_ascii=False)

            return result

        except Exception as e:
            result["error"] = str(e)
            if attempt < MAX_RETRIES - 1:
                time.sleep(2 ** attempt)

    return result


def is_same_domain(url1: str, url2: str) -> bool:
    """Verifica se URLs sao do mesmo dominio"""
    d1 = urlparse(url1).netloc.lower()
    d2 = urlparse(url2).netloc.lower()
    # Comparar dominio principal (ignora subdominio www)
    d1 = d1.replace("www.", "")
    d2 = d2.replace("www.", "")
    return d1 == d2


def is_valid_link(url: str, seed_url: str) -> bool:
    """Verifica se link e valido para crawl"""
    if not url or not url.startswith(("http://", "https://")):
        return False

    # Ignorar arquivos binarios
    lower_url = url.lower()
    skip_extensions = [".pdf", ".jpg", ".jpeg", ".png", ".gif", ".mp4", ".mp3", ".zip", ".doc", ".xls"]
    if any(lower_url.endswith(ext) for ext in skip_extensions):
        return False

    # Verificar mesmo dominio
    if not is_same_domain(url, seed_url):
        return False

    return True


def has_keywords(url: str, title: str, keywords: list[str]) -> list[str]:
    """Verifica se URL ou titulo contem keywords"""
    text = f"{url} {title}".lower()
    found = [kw for kw in keywords if kw in text]
    return found


def crawl_seed(seed_url: str, keywords: list[str], max_pages: int = MAX_PAGES_PER_SEED, max_depth: int = MAX_DEPTH) -> dict:
    """Crawl conservador a partir de uma seed"""
    print(f"\n[CRAWL] {seed_url}")
    print(f"  Max depth: {max_depth}, Max pages: {max_pages}")

    visited = set()
    hits = []  # Paginas com keywords
    graph = {}  # Grafo de links

    # BFS com profundidade
    queue = deque([(seed_url, 0)])  # (url, depth)

    while queue and len(visited) < max_pages:
        url, depth = queue.popleft()

        if url in visited:
            continue
        if depth > max_depth:
            continue

        visited.add(url)

        # Fetch page
        data = fetch_page(url)

        if data.get("status_code") != 200:
            continue

        # Registrar no grafo
        graph[url] = {
            "title": data.get("title", ""),
            "depth": depth,
            "links_count": len(data.get("links", []))
        }

        # Verificar keywords
        found_kws = has_keywords(url, data.get("title", ""), keywords)
        if found_kws:
            hits.append({
                "url": url,
                "title": data.get("title", ""),
                "depth": depth,
                "keywords": found_kws,
                "seed": seed_url
            })
            print(f"  [HIT] depth={depth}: {url[:60]}")

        # Adicionar links a fila
        for link in data.get("links", []):
            if link not in visited and is_valid_link(link, seed_url):
                queue.append((link, depth + 1))

    print(f"  Visitadas: {len(visited)}, Hits: {len(hits)}")

    return {
        "seed": seed_url,
        "visited": len(visited),
        "hits": hits,
        "graph": graph
    }


def main():
    print("=" * 60)
    print("CRAWL FROM SEEDS - Descoberta em profundidade")
    print("=" * 60)

    # Carregar dados
    keywords = load_keywords()
    print(f"Keywords: {len(keywords)}")

    seeds = load_confirmed_seeds()
    print(f"Seeds confirmadas: {len(seeds)}")

    if not seeds:
        print("Nenhuma seed confirmada. Marque seeds como 'confirmed' em seeds.json")
        return

    # Crawl cada seed
    all_hits = []
    all_graphs = {}

    for seed in seeds:
        result = crawl_seed(seed, keywords)
        all_hits.extend(result["hits"])
        all_graphs[seed] = result["graph"]

    # Salvar hits
    OUTPUTS_DIR.mkdir(exist_ok=True)

    hits_file = OUTPUTS_DIR / "crawl_hits.csv"
    fieldnames = ["url", "title", "seed", "depth", "keywords"]

    with open(hits_file, "w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for hit in all_hits:
            hit["keywords"] = "|".join(hit.get("keywords", []))
            writer.writerow(hit)

    print(f"\nHits salvos: {hits_file}")

    # Salvar grafo
    graph_file = OUTPUTS_DIR / "crawl_graph.json"
    with open(graph_file, "w", encoding="utf-8") as f:
        json.dump(all_graphs, f, ensure_ascii=False, indent=2)

    print(f"Grafo salvo: {graph_file}")

    # Estatisticas
    print("\n" + "=" * 60)
    print("RESUMO")
    print("=" * 60)
    print(f"Seeds processadas: {len(seeds)}")
    print(f"Total de hits com keywords: {len(all_hits)}")

    # Top keywords
    keyword_counts = {}
    for hit in all_hits:
        for kw in hit.get("keywords", "").split("|"):
            if kw:
                keyword_counts[kw] = keyword_counts.get(kw, 0) + 1

    if keyword_counts:
        print("\nTop keywords encontradas:")
        for kw, count in sorted(keyword_counts.items(), key=lambda x: -x[1])[:10]:
            print(f"  {kw}: {count}")


if __name__ == "__main__":
    main()
