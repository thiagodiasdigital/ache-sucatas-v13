#!/usr/bin/env python3
"""
DETRAN-MG Scraper - Coleta de leiloes de veiculos

Fonte: https://leilao.detran.mg.gov.br/
Frequencia recomendada: 1x/dia
Rate limit: 1 req/seg

Estrutura do site:
- Pagina inicial lista leiloes ativos (cards com edital, cidade, status)
- Cada leilao tem URL: /lotes/lista-lotes/{ID}/{ANO}
- Lotes paginados: ?page=N
- Campos: lote, categoria (Sucata/Conservado), marca/modelo, ano, valor
"""

import re
import time
import json
import hashlib
from pathlib import Path
from datetime import datetime, timezone
from dataclasses import dataclass, asdict, field
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

BASE_URL = "https://leilao.detran.mg.gov.br"
USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
RATE_LIMIT = 1.0  # segundos entre requests
TIMEOUT = 30
MAX_RETRIES = 3
MAX_PAGES_PER_AUCTION = 50  # Limite de seguranca


# ============================================================
# DATA CONTRACT
# ============================================================

@dataclass
class VeiculoLeilao:
    """Contrato canonico para veiculo de leilao"""
    # Identificacao
    id_fonte: str                    # Hash unico: fonte + edital + lote
    fonte: str = "DETRAN-MG"

    # Leilao
    edital: str = ""
    cidade: str = ""
    data_encerramento: Optional[str] = None
    status_leilao: str = ""          # Publicado, Em Andamento, Finalizado

    # Veiculo
    lote: int = 0
    categoria: str = ""              # Sucata, Conservado
    marca_modelo: str = ""
    ano: Optional[int] = None
    placa: Optional[str] = None      # Nem sempre disponivel
    valor_inicial: float = 0.0

    # Metadados
    url_lote: str = ""
    url_imagem: Optional[str] = None
    coletado_em: str = ""

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class LeilaoInfo:
    """Informacoes de um leilao"""
    lotes_id: str
    ano: str
    edital: str = ""
    cidade: str = ""
    status: str = ""
    encerramento: str = ""
    url: str = ""


# ============================================================
# SCRAPER
# ============================================================

class DetranMGScraper:
    """Scraper para DETRAN-MG leiloes"""

    # Marcas conhecidas para deteccao
    MARCAS = [
        "FIAT", "VW", "VOLKSWAGEN", "GM", "CHEVROLET", "FORD", "HONDA", "YAMAHA",
        "TOYOTA", "HYUNDAI", "RENAULT", "NISSAN", "JEEP", "MITSUBISHI",
        "CITROEN", "PEUGEOT", "KIA", "SUZUKI", "BMW", "MERCEDES", "AUDI",
        "DAFRA", "SHINERAY", "HAOJUE", "KASINSKI", "SUNDOWN", "TRAXX"
    ]

    def __init__(self, output_dir: Path = None):
        self.base_url = BASE_URL
        self.session = requests.Session() if HAS_REQUESTS else None
        if self.session:
            self.session.headers.update({"User-Agent": USER_AGENT})
        self.last_request_time = 0
        self.output_dir = output_dir or Path("outputs/detran_mg")
        self.output_dir.mkdir(parents=True, exist_ok=True)

        # Metricas
        self.metrics = {
            "started_at": datetime.now(timezone.utc).isoformat(),
            "requests_made": 0,
            "leiloes_found": 0,
            "veiculos_found": 0,
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

    def get_leiloes_ativos(self) -> List[LeilaoInfo]:
        """Busca lista de leiloes ativos na pagina inicial usando regex"""
        print(f"[DETRAN-MG] Buscando leiloes ativos...")

        html = self._fetch(self.base_url)
        leiloes = []

        # Encontrar todos os links de lotes
        lotes_pattern = r'href="(/lotes/lista-lotes/(\d+)/(\d+))"'
        matches = re.findall(lotes_pattern, html)

        for url, lotes_id, ano in matches:
            # Pegar contexto antes do link para extrair dados
            pos = html.find(url)
            context = html[max(0, pos-2000):pos+100]

            # Extrair edital
            editais = re.findall(r'(\d{3,4}/202[4-6])', context)
            edital = editais[-1] if editais else f"{lotes_id}/{ano}"

            # Extrair status
            status = "Desconhecido"
            if "Publicado" in context[-500:]:
                status = "Publicado"
            elif "Em Andamento" in context[-500:]:
                status = "Em Andamento"
            elif "Finalizado" in context[-500:]:
                status = "Finalizado"

            # Extrair encerramento
            enc = re.search(r'Encerramento:\s*(\d{2}/\d{2}/\d{4}\s*\d{2}:\d{2})', context)
            encerramento = enc.group(1) if enc else ""

            # Extrair cidade (do card-title)
            cidade_match = re.search(r'card-title[^>]*>([^<]+)<', context[-1000:])
            cidade = cidade_match.group(1).strip().title() if cidade_match else ""

            leilao = LeilaoInfo(
                lotes_id=lotes_id,
                ano=ano,
                edital=edital,
                cidade=cidade,
                status=status,
                encerramento=encerramento,
                url=f"{self.base_url}{url}"
            )
            leiloes.append(leilao)

        # Remover duplicados por lotes_id
        seen = set()
        unique_leiloes = []
        for l in leiloes:
            if l.lotes_id not in seen:
                seen.add(l.lotes_id)
                unique_leiloes.append(l)

        self.metrics["leiloes_found"] = len(unique_leiloes)
        print(f"[DETRAN-MG] Encontrados {len(unique_leiloes)} leiloes unicos")

        return unique_leiloes

    def get_lotes_leilao(self, leilao: LeilaoInfo) -> List[dict]:
        """Busca todos os lotes de um leilao (com paginacao)"""
        all_lotes = []
        page = 1

        while page <= MAX_PAGES_PER_AUCTION:
            url = f"{self.base_url}/lotes/lista-lotes/{leilao.lotes_id}/{leilao.ano}?page={page}"

            try:
                html = self._fetch(url)

                # Extrair lotes desta pagina
                lotes = self._parse_lotes_page(html)

                if not lotes:
                    break  # Sem mais lotes

                all_lotes.extend(lotes)

                # Verificar se ha mais paginas
                max_page = self._get_max_page(html)
                if page >= max_page:
                    break

                page += 1

            except Exception as e:
                print(f"  ERRO pagina {page}: {e}")
                break

        return all_lotes

    def _parse_lotes_page(self, html: str) -> List[dict]:
        """Extrai lotes de uma pagina usando regex"""
        lotes = []

        # Padrão para extrair blocos de cada lote
        # Cada lote tem: numero, categoria, marca/modelo, ano, valor

        # Estrategia: encontrar numeros de lote e pegar contexto
        lote_numbers = re.findall(r'<[^>]*>\s*(\d{1,4})\s*</[^>]*>', html)

        # Procurar por padroes de veiculos
        # Formato tipico: "GM/CORSA SUPER" ou "FIAT/PALIO"
        veiculo_pattern = r'(' + '|'.join(self.MARCAS) + r')[/\s]+([A-Z0-9\s\-\.]+)'
        veiculos = re.findall(veiculo_pattern, html, re.IGNORECASE)

        # Procurar categorias
        categorias = re.findall(r'(Sucata|Conservado|Recuperável)', html, re.IGNORECASE)

        # Procurar valores
        valores = re.findall(r'R\$\s*([\d.,]+)', html)

        # Procurar anos
        anos = re.findall(r'\b(19[8-9]\d|20[0-2]\d)\b', html)

        # Montar lotes combinando dados
        # Assumir que aparecem na mesma ordem
        n_lotes = min(len(veiculos), len(valores)) if veiculos else 0

        for i in range(n_lotes):
            marca, modelo = veiculos[i]
            marca_modelo = f"{marca}/{modelo}".strip()

            # Limpar valor
            valor_str = valores[i].replace(".", "").replace(",", ".")
            try:
                valor = float(valor_str)
            except:
                valor = 0.0

            # Pegar ano se disponivel
            ano = int(anos[i]) if i < len(anos) else None

            # Pegar categoria se disponivel
            categoria = categorias[i].title() if i < len(categorias) else ""

            # Numero do lote
            lote_num = i + 1  # Fallback

            lote = {
                "lote": lote_num,
                "categoria": categoria,
                "marca_modelo": marca_modelo,
                "ano": ano,
                "valor": valor
            }
            lotes.append(lote)

        return lotes

    def _get_max_page(self, html: str) -> int:
        """Extrai numero maximo de paginas"""
        pages = re.findall(r'page=(\d+)', html)
        if pages:
            return max(int(p) for p in pages)
        return 1

    def normalizar_veiculo(self, leilao: LeilaoInfo, lote: dict) -> VeiculoLeilao:
        """Normaliza dados para contrato canonico"""

        # Gerar ID unico
        id_raw = f"DETRAN-MG|{leilao.edital}|{lote.get('lote', 0)}"
        id_fonte = hashlib.md5(id_raw.encode()).hexdigest()[:16]

        return VeiculoLeilao(
            id_fonte=id_fonte,
            fonte="DETRAN-MG",
            edital=leilao.edital,
            cidade=leilao.cidade,
            data_encerramento=leilao.encerramento,
            status_leilao=leilao.status,
            lote=lote.get("lote", 0),
            categoria=lote.get("categoria", ""),
            marca_modelo=lote.get("marca_modelo", ""),
            ano=lote.get("ano"),
            valor_inicial=lote.get("valor", 0.0),
            url_lote=leilao.url,
            url_imagem=lote.get("imagem"),
            coletado_em=datetime.now(timezone.utc).isoformat()
        )

    def run(self, max_leiloes: int = None, only_active: bool = True) -> List[VeiculoLeilao]:
        """Executa coleta completa"""
        print("=" * 60)
        print("DETRAN-MG SCRAPER - Iniciando coleta")
        print("=" * 60)

        veiculos = []

        # 1. Buscar leiloes ativos
        leiloes = self.get_leiloes_ativos()

        # Filtrar apenas publicados/em andamento
        if only_active:
            leiloes = [l for l in leiloes if l.status in ["Publicado", "Em Andamento"]]
            print(f"[DETRAN-MG] {len(leiloes)} leiloes ativos (Publicado/Em Andamento)")

        if max_leiloes:
            leiloes = leiloes[:max_leiloes]

        # 2. Para cada leilao, buscar lotes
        for i, leilao in enumerate(leiloes, 1):
            print(f"\n[{i}/{len(leiloes)}] Leilao {leilao.edital} - {leilao.cidade or 'N/A'}")
            print(f"  Status: {leilao.status} | Encerramento: {leilao.encerramento}")

            lotes = self.get_lotes_leilao(leilao)
            print(f"  -> {len(lotes)} lotes encontrados")

            # 3. Normalizar cada lote
            for lote in lotes:
                veiculo = self.normalizar_veiculo(leilao, lote)
                veiculos.append(veiculo)

        self.metrics["veiculos_found"] = len(veiculos)
        self.metrics["finished_at"] = datetime.now(timezone.utc).isoformat()

        # 4. Salvar resultados
        self._save_results(veiculos)

        print("\n" + "=" * 60)
        print(f"RESULTADO: {len(veiculos)} veiculos coletados de {len(leiloes)} leiloes")
        print("=" * 60)

        return veiculos

    def _save_results(self, veiculos: List[VeiculoLeilao]):
        """Salva resultados em JSONL e metricas"""
        timestamp = datetime.now().strftime("%Y%m%dT%H%M%S")

        # Salvar veiculos em JSONL
        veiculos_file = self.output_dir / f"veiculos_{timestamp}.jsonl"
        with open(veiculos_file, "w", encoding="utf-8") as f:
            for v in veiculos:
                f.write(json.dumps(v.to_dict(), ensure_ascii=False) + "\n")
        print(f"Veiculos salvos: {veiculos_file}")

        # Salvar metricas
        metrics_file = self.output_dir / f"metrics_{timestamp}.json"
        with open(metrics_file, "w", encoding="utf-8") as f:
            json.dump(self.metrics, f, ensure_ascii=False, indent=2)
        print(f"Metricas salvas: {metrics_file}")

        # Atualizar arquivo "latest"
        latest_file = self.output_dir / "latest.jsonl"
        with open(latest_file, "w", encoding="utf-8") as f:
            for v in veiculos:
                f.write(json.dumps(v.to_dict(), ensure_ascii=False) + "\n")


# ============================================================
# CLI
# ============================================================

def main():
    import argparse
    parser = argparse.ArgumentParser(description="DETRAN-MG Scraper")
    parser.add_argument("--max-leiloes", type=int, default=None,
                        help="Limitar numero de leiloes (para teste)")
    parser.add_argument("--output-dir", type=str, default=None,
                        help="Diretorio de saida")
    parser.add_argument("--all", action="store_true",
                        help="Incluir leiloes finalizados")
    args = parser.parse_args()

    output_dir = Path(args.output_dir) if args.output_dir else None
    scraper = DetranMGScraper(output_dir=output_dir)

    veiculos = scraper.run(max_leiloes=args.max_leiloes, only_active=not args.all)

    # Resumo
    print(f"\nResumo:")
    print(f"  Requests: {scraper.metrics['requests_made']}")
    print(f"  Leiloes: {scraper.metrics['leiloes_found']}")
    print(f"  Veiculos: {len(veiculos)}")
    print(f"  Erros: {len(scraper.metrics['errors'])}")

    if veiculos:
        print(f"\nExemplos (primeiros 5):")
        for v in veiculos[:5]:
            print(f"  - Lote {v.lote}: {v.marca_modelo} ({v.ano}) - R$ {v.valor_inicial:.2f} - {v.categoria}")


if __name__ == "__main__":
    main()
