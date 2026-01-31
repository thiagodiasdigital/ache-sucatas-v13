#!/usr/bin/env python3
"""
PRF Scraper - Coleta de editais de leilões da Polícia Rodoviária Federal

Fonte: https://www.gov.br/prf/pt-br/assuntos/leiloes-prf
Frequência recomendada: 1x/dia
Rate limit: 1 req/seg (site governamental)

Estrutura do site:
- Página principal lista leilões recentes
- Cada estado tem sua própria página: /leiloes-prf/{estado}
- Editais linkam para leiloeiros terceirizados

Dados coletados:
- Editais de leilão por estado
- Datas de leilão
- Links para editais e leiloeiros
"""

import re
import time
import json
import hashlib
from pathlib import Path
from datetime import datetime, timezone
from dataclasses import dataclass, asdict
from typing import Optional, List

try:
    import requests
    HAS_REQUESTS = True
except ImportError:
    import urllib.request
    HAS_REQUESTS = False

# ============================================================
# CONFIGURACAO
# ============================================================

BASE_URL = "https://www.gov.br/prf/pt-br/assuntos/leiloes-prf"
USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
RATE_LIMIT = 1.0  # segundos entre requests
TIMEOUT = 30
MAX_RETRIES = 3

# Estados/Regionais da PRF
ESTADOS = [
    "acre", "alagoas", "amapa", "amazonas", "bahia", "ceara",
    "distrito-federal", "espirito-santo", "goias", "maranhao",
    "mato-grosso", "mato-grosso-do-sul", "minas-gerais", "para",
    "paraiba", "parana", "pernambuco", "piaui", "rio-de-janeiro",
    "rio-grande-do-norte", "rio-grande-do-sul", "rondonia", "roraima",
    "santa-catarina", "sao-paulo", "sergipe", "tocantins"
]

# Mapeamento de siglas
SIGLAS_ESTADOS = {
    "acre": "AC", "alagoas": "AL", "amapa": "AP", "amazonas": "AM",
    "bahia": "BA", "ceara": "CE", "distrito-federal": "DF",
    "espirito-santo": "ES", "goias": "GO", "maranhao": "MA",
    "mato-grosso": "MT", "mato-grosso-do-sul": "MS", "minas-gerais": "MG",
    "para": "PA", "paraiba": "PB", "parana": "PR", "pernambuco": "PE",
    "piaui": "PI", "rio-de-janeiro": "RJ", "rio-grande-do-norte": "RN",
    "rio-grande-do-sul": "RS", "rondonia": "RO", "roraima": "RR",
    "santa-catarina": "SC", "sao-paulo": "SP", "sergipe": "SE",
    "tocantins": "TO"
}


# ============================================================
# DATA CONTRACT
# ============================================================

@dataclass
class EditalLeilao:
    """Contrato para edital de leilão PRF"""
    id_fonte: str
    fonte: str = "PRF"

    # Identificação
    estado: str = ""
    sigla_uf: str = ""
    numero_edital: str = ""
    titulo: str = ""

    # Datas
    data_leilao: Optional[str] = None
    data_publicacao: Optional[str] = None

    # Links
    url_edital: str = ""
    url_leiloeiro: str = ""
    nome_leiloeiro: str = ""

    # Informações extras
    quantidade_lotes: Optional[int] = None
    tipo_leilao: str = ""  # Conservados, Sucatas, Misto
    modalidade: str = ""   # Online, Presencial

    # Metadados
    coletado_em: str = ""

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class VeiculoLeilao:
    """Contrato canônico para veículo (compatível com outros scrapers)"""
    id_fonte: str
    fonte: str = "PRF"

    edital: str = ""
    cidade: str = ""
    data_encerramento: Optional[str] = None
    status_leilao: str = ""

    lote: int = 0
    categoria: str = ""
    marca_modelo: str = ""
    ano: Optional[int] = None
    placa: Optional[str] = None
    valor_inicial: float = 0.0

    url_lote: str = ""
    url_imagem: Optional[str] = None
    coletado_em: str = ""

    # Extras PRF
    estado: str = ""
    chassi: Optional[str] = None
    situacao: str = ""  # Conservado, Sucata, Aproveitável

    def to_dict(self) -> dict:
        return asdict(self)


# ============================================================
# SCRAPER
# ============================================================

class PRFScraper:
    """Scraper para leilões da PRF"""

    def __init__(self, output_dir: Path = None):
        self.base_url = BASE_URL
        self.session = requests.Session() if HAS_REQUESTS else None
        if self.session:
            self.session.headers.update({
                "User-Agent": USER_AGENT,
                "Accept": "text/html,application/xhtml+xml",
                "Accept-Language": "pt-BR,pt;q=0.9",
            })
        self.last_request_time = 0
        self.output_dir = output_dir or Path("outputs/prf")
        self.output_dir.mkdir(parents=True, exist_ok=True)

        # Métricas
        self.metrics = {
            "started_at": datetime.now(timezone.utc).isoformat(),
            "requests_made": 0,
            "estados_coletados": 0,
            "editais_found": 0,
            "errors": []
        }

    def _rate_limit(self):
        """Respeita rate limit"""
        elapsed = time.time() - self.last_request_time
        if elapsed < RATE_LIMIT:
            time.sleep(RATE_LIMIT - elapsed)
        self.last_request_time = time.time()

    def _fetch(self, url: str) -> str:
        """Faz request com retry"""
        self._rate_limit()

        for attempt in range(MAX_RETRIES):
            try:
                self.metrics["requests_made"] += 1

                if HAS_REQUESTS:
                    resp = self.session.get(url, timeout=TIMEOUT)
                    resp.raise_for_status()
                    return resp.text
                else:
                    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
                    with urllib.request.urlopen(req, timeout=TIMEOUT) as resp:
                        return resp.read().decode("utf-8", errors="ignore")

            except Exception as e:
                if attempt < MAX_RETRIES - 1:
                    time.sleep(2 ** attempt)
                else:
                    self.metrics["errors"].append({"url": url, "error": str(e)})
                    raise

        return ""

    def get_editais_estado(self, estado: str) -> List[EditalLeilao]:
        """Busca editais de um estado específico"""
        url = f"{self.base_url}/{estado}"
        sigla = SIGLAS_ESTADOS.get(estado, estado.upper()[:2])

        try:
            html = self._fetch(url)
            editais = self._parse_editais(html, estado, sigla)
            return editais

        except Exception as e:
            print(f"  [ERRO] {estado}: {e}")
            return []

    def _parse_editais(self, html: str, estado: str, sigla: str) -> List[EditalLeilao]:
        """Extrai editais do HTML"""
        editais = []
        matches = []

        # Padrão principal: <a class="summary url" href="URL">TÍTULO</a>
        # Este é o formato usado pelo gov.br para listar os editais
        summary_pattern = r'<a[^>]*class="[^"]*summary[^"]*url[^"]*"[^>]*href="([^"]+)"[^>]*>([^<]+)</a>'
        summary_matches = re.findall(summary_pattern, html, re.IGNORECASE)

        for url_path, titulo in summary_matches:
            # Filtrar apenas editais do estado atual
            if f'/leiloes-prf/{estado}/' in url_path.lower():
                matches.append((url_path, titulo.strip()))

        # Padrão alternativo: href seguido de título em outro elemento
        # <a href="URL"><img...></a>...<a class="summary url" href="URL">TÍTULO</a>
        alt_pattern = r'href="(https://www\.gov\.br/prf/pt-br/assuntos/leiloes-prf/' + estado + r'/[^"]+)"[^>]*title="collective\.nitf\.content">([^<]+)</a>'
        alt_matches = re.findall(alt_pattern, html, re.IGNORECASE)
        matches.extend(alt_matches)

        # Padrão para pegar descrições também
        desc_pattern = r'<span[^>]*class="[^"]*description[^"]*"[^>]*>([^<]+)</span>'
        descriptions = re.findall(desc_pattern, html, re.IGNORECASE)

        # Processar matches únicos
        seen_urls = set()
        for url_path, titulo in matches:
            # Filtrar apenas editais do estado atual
            if estado not in url_path.lower():
                continue

            # Ignorar duplicados
            if url_path in seen_urls:
                continue
            seen_urls.add(url_path)

            # Ignorar links de navegação
            if any(skip in url_path.lower() for skip in ['todos-leiloes', 'folder_contents', '@@']):
                continue

            # Extrair número do edital
            edital_num = ""
            num_match = re.search(r'edital[^\d]*(\d+[/-]\d{4})', titulo, re.IGNORECASE)
            if num_match:
                edital_num = num_match.group(1)
            else:
                num_match = re.search(r'(\d+[/-]20\d{2})', titulo)
                if num_match:
                    edital_num = num_match.group(1)

            # Extrair data do leilão do título
            data_leilao = None
            data_match = re.search(r'(\d{2}[/-]\d{2}[/-]\d{4})', titulo)
            if data_match:
                data_leilao = data_match.group(1).replace('-', '/')

            # Detectar tipo de leilão
            tipo = "Misto"
            titulo_lower = titulo.lower()
            if "sucata" in titulo_lower and "conservad" not in titulo_lower:
                tipo = "Sucatas"
            elif "conservad" in titulo_lower and "sucata" not in titulo_lower:
                tipo = "Conservados"

            # Gerar ID único
            id_raw = f"PRF|{sigla}|{edital_num or url_path}"
            id_fonte = hashlib.md5(id_raw.encode()).hexdigest()[:16]

            # URL completa
            if url_path.startswith('/'):
                full_url = f"https://www.gov.br{url_path}"
            else:
                full_url = url_path

            edital = EditalLeilao(
                id_fonte=id_fonte,
                fonte="PRF",
                estado=estado.replace('-', ' ').title(),
                sigla_uf=sigla,
                numero_edital=edital_num,
                titulo=titulo.strip(),
                data_leilao=data_leilao,
                url_edital=full_url,
                tipo_leilao=tipo,
                modalidade="Online",  # Maioria é online
                coletado_em=datetime.now(timezone.utc).isoformat()
            )
            editais.append(edital)

        return editais

    def get_editais_pagina_principal(self) -> List[EditalLeilao]:
        """Busca editais da página principal (destaques)"""
        print("[PRF] Buscando editais da página principal...")

        try:
            html = self._fetch(self.base_url)
            editais = []

            # Procurar por cards de destaque
            # Padrão: tile-content com link e título
            card_pattern = r'<div[^>]*class="[^"]*tile-content[^"]*"[^>]*>.*?<a[^>]*href="([^"]+)"[^>]*>.*?<span[^>]*>([^<]+)</span>'
            matches = re.findall(card_pattern, html, re.IGNORECASE | re.DOTALL)

            for url_path, titulo in matches:
                # Extrair estado da URL
                estado_match = re.search(r'/leiloes-prf/([^/]+)/', url_path)
                if not estado_match:
                    continue

                estado = estado_match.group(1)
                sigla = SIGLAS_ESTADOS.get(estado, estado.upper()[:2])

                # Processar como edital
                edital_num = ""
                num_match = re.search(r'(\d+[/-]20\d{2})', titulo)
                if num_match:
                    edital_num = num_match.group(1)

                id_raw = f"PRF|{sigla}|{edital_num or url_path}"
                id_fonte = hashlib.md5(id_raw.encode()).hexdigest()[:16]

                if url_path.startswith('/'):
                    full_url = f"https://www.gov.br{url_path}"
                else:
                    full_url = url_path

                edital = EditalLeilao(
                    id_fonte=id_fonte,
                    fonte="PRF",
                    estado=estado.replace('-', ' ').title(),
                    sigla_uf=sigla,
                    numero_edital=edital_num,
                    titulo=titulo.strip(),
                    url_edital=full_url,
                    coletado_em=datetime.now(timezone.utc).isoformat()
                )
                editais.append(edital)

            print(f"[PRF] {len(editais)} editais em destaque")
            return editais

        except Exception as e:
            print(f"[ERRO] Página principal: {e}")
            return []

    def run(self, estados: List[str] = None, max_estados: int = None) -> List[EditalLeilao]:
        """Executa coleta completa"""
        print("=" * 60)
        print("PRF SCRAPER - Iniciando coleta de editais")
        print("=" * 60)

        all_editais = []

        # Determinar estados a coletar
        estados_to_scrape = estados or ESTADOS
        if max_estados:
            estados_to_scrape = estados_to_scrape[:max_estados]

        # 1. Coletar página principal (destaques)
        editais_destaque = self.get_editais_pagina_principal()
        all_editais.extend(editais_destaque)

        # 2. Coletar cada estado
        print(f"\n[PRF] Coletando {len(estados_to_scrape)} estados...")

        for i, estado in enumerate(estados_to_scrape, 1):
            sigla = SIGLAS_ESTADOS.get(estado, estado[:2].upper())
            print(f"  [{i}/{len(estados_to_scrape)}] {sigla} ({estado})...", end=" ")

            try:
                editais = self.get_editais_estado(estado)
                all_editais.extend(editais)
                self.metrics["estados_coletados"] += 1
                print(f"{len(editais)} editais")

            except Exception as e:
                print(f"ERRO: {e}")

        # Remover duplicados por ID
        seen_ids = set()
        unique_editais = []
        for e in all_editais:
            if e.id_fonte not in seen_ids:
                seen_ids.add(e.id_fonte)
                unique_editais.append(e)

        self.metrics["editais_found"] = len(unique_editais)
        self.metrics["finished_at"] = datetime.now(timezone.utc).isoformat()

        # Salvar resultados
        self._save_results(unique_editais)

        print("\n" + "=" * 60)
        print(f"RESULTADO: {len(unique_editais)} editais coletados de {self.metrics['estados_coletados']} estados")
        print("=" * 60)

        return unique_editais

    def _save_results(self, editais: List[EditalLeilao]):
        """Salva resultados em JSONL e métricas"""
        timestamp = datetime.now().strftime("%Y%m%dT%H%M%S")

        # Salvar editais em JSONL
        editais_file = self.output_dir / f"editais_{timestamp}.jsonl"
        with open(editais_file, "w", encoding="utf-8") as f:
            for e in editais:
                f.write(json.dumps(e.to_dict(), ensure_ascii=False) + "\n")
        print(f"Editais salvos: {editais_file}")

        # Salvar métricas
        metrics_file = self.output_dir / f"metrics_{timestamp}.json"
        with open(metrics_file, "w", encoding="utf-8") as f:
            json.dump(self.metrics, f, ensure_ascii=False, indent=2)
        print(f"Métricas salvas: {metrics_file}")

        # Atualizar arquivo "latest"
        latest_file = self.output_dir / "latest.jsonl"
        with open(latest_file, "w", encoding="utf-8") as f:
            for e in editais:
                f.write(json.dumps(e.to_dict(), ensure_ascii=False) + "\n")

        # Gerar resumo por estado
        resumo = {}
        for e in editais:
            uf = e.sigla_uf
            if uf not in resumo:
                resumo[uf] = {"total": 0, "editais": []}
            resumo[uf]["total"] += 1
            resumo[uf]["editais"].append(e.numero_edital or e.titulo[:30])

        resumo_file = self.output_dir / "resumo_estados.json"
        with open(resumo_file, "w", encoding="utf-8") as f:
            json.dump(resumo, f, ensure_ascii=False, indent=2)


# ============================================================
# CLI
# ============================================================

def main():
    import argparse
    parser = argparse.ArgumentParser(description="PRF Leilões Scraper")
    parser.add_argument("--max-estados", type=int, default=None,
                        help="Limitar número de estados (para teste)")
    parser.add_argument("--estados", type=str, default=None,
                        help="Lista de estados separados por vírgula (ex: parana,sao-paulo)")
    parser.add_argument("--output-dir", type=str, default=None,
                        help="Diretório de saída")
    args = parser.parse_args()

    output_dir = Path(args.output_dir) if args.output_dir else None
    estados = args.estados.split(",") if args.estados else None

    scraper = PRFScraper(output_dir=output_dir)
    editais = scraper.run(estados=estados, max_estados=args.max_estados)

    # Resumo
    print(f"\nResumo:")
    print(f"  Requests: {scraper.metrics['requests_made']}")
    print(f"  Estados: {scraper.metrics['estados_coletados']}")
    print(f"  Editais: {len(editais)}")
    print(f"  Erros: {len(scraper.metrics['errors'])}")

    if editais:
        print(f"\nExemplos (primeiros 5):")
        for e in editais[:5]:
            print(f"  - [{e.sigla_uf}] {e.titulo[:50]}...")


if __name__ == "__main__":
    main()
