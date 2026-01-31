#!/usr/bin/env python3
"""
Palácio dos Leilões Scraper - Coleta de leilões de veículos

Fonte: https://www.palaciodosleiloes.com.br/site/
Frequência recomendada: 3x/dia
Rate limit: 1.5-2 seg entre requests

Estrutura do site:
- Página principal: /site/index.php
- Leilões veículos: /site/leilao.php?subcategoria_pesquisa=1 (carros)
- Lotes carregados via AJAX em div#div_lotes
- Editais PDF: /site/documents/leiloes/{codigo}.pdf

Requer: playwright (pip install playwright && playwright install chromium)
"""

import re
import json
import hashlib
import asyncio
import random
from pathlib import Path
from datetime import datetime, timezone
from dataclasses import dataclass, asdict
from typing import Optional, List

# ============================================================
# CONFIGURACAO
# ============================================================

BASE_URL = "https://www.palaciodosleiloes.com.br"
RATE_LIMIT = 1.5  # segundos entre requests
TIMEOUT = 30000  # ms
MAX_PAGES = 20  # Limite de segurança por subcategoria
MAX_RETRIES = 3

# Subcategorias de veículos (parâmetro subcategoria_pesquisa)
SUBCATEGORIAS = {
    1: "Carros",
    2: "Motos",
    3: "Caminhões",
    4: "Ônibus/Vans",
    5: "Tratores/Máquinas",
}

# Palavras-chave para filtrar veículos/sucatas
CATEGORIAS_VEICULOS = [
    "CARRO", "CARROS", "VEICULO", "VEÍCULO", "VEICULOS", "VEÍCULOS",
    "MOTO", "MOTOS", "MOTOCICLETA", "MOTOCICLETAS",
    "CAMINHÃO", "CAMINHAO", "CAMINHÕES", "CAMINHOES",
    "ONIBUS", "ÔNIBUS", "VAN", "VANS",
    "TRATOR", "TRATORES", "MÁQUINA", "MAQUINA",
    "SUCATA", "SUCATAS", "SINISTRADO", "SINISTRADOS",
    "ALLIANZ", "SEGUROS", "SEGURADORA",
]


# ============================================================
# DATA CONTRACT (compatível com outros scrapers)
# ============================================================

@dataclass
class VeiculoLeilao:
    """Contrato canônico para veículo de leilão"""
    id_fonte: str
    fonte: str = "PALACIO-LEILOES"

    # Leilão
    edital: str = ""
    cidade: str = ""
    data_encerramento: Optional[str] = None
    status_leilao: str = ""

    # Veículo
    lote: int = 0
    categoria: str = ""
    marca_modelo: str = ""
    ano: Optional[int] = None
    placa: Optional[str] = None
    valor_inicial: float = 0.0

    # Metadados
    url_lote: str = ""
    url_imagem: Optional[str] = None
    coletado_em: str = ""

    # Campos extras Palácio
    patio: str = ""
    leilao_codigo: str = ""
    comitente: str = ""
    subcategoria: str = ""

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class LoteInfo:
    """Informações de um lote"""
    lote_id: str
    numero: int = 0
    descricao: str = ""
    marca_modelo: str = ""
    ano: Optional[int] = None
    placa: Optional[str] = None
    valor: float = 0.0
    url: str = ""
    imagem: Optional[str] = None
    status: str = ""
    subcategoria: str = ""
    leilao_codigo: str = ""


# ============================================================
# SCRAPER COM PLAYWRIGHT
# ============================================================

class PalacioLeiloesScraper:
    """Scraper para Palácio dos Leilões usando Playwright"""

    def __init__(self, output_dir: Path = None, headless: bool = True):
        self.base_url = BASE_URL
        self.headless = headless
        self.output_dir = output_dir or Path("outputs/palacio_leiloes")
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.browser = None
        self.page = None

        # Métricas
        self.metrics = {
            "started_at": datetime.now(timezone.utc).isoformat(),
            "requests_made": 0,
            "leiloes_found": 0,
            "veiculos_found": 0,
            "errors": []
        }

    async def _init_browser(self):
        """Inicializa navegador Playwright"""
        try:
            from playwright.async_api import async_playwright
        except ImportError:
            raise ImportError(
                "Playwright não instalado. Execute:\n"
                "  pip install playwright\n"
                "  playwright install chromium"
            )

        # Tentar importar stealth
        try:
            from playwright_stealth import stealth_async
            self.has_stealth = True
        except ImportError:
            print("[WARN] playwright-stealth não instalado")
            self.has_stealth = False

        self.playwright = await async_playwright().start()
        self.browser = await self.playwright.chromium.launch(
            headless=self.headless,
            args=[
                "--disable-blink-features=AutomationControlled",
                "--disable-dev-shm-usage",
                "--no-sandbox",
            ]
        )
        self.context = await self.browser.new_context(
            viewport={"width": 1920, "height": 1080},
            user_agent=(
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/131.0.0.0 Safari/537.36"
            ),
            locale="pt-BR",
            timezone_id="America/Sao_Paulo",
        )
        self.page = await self.context.new_page()

        # Aplicar stealth patches
        if self.has_stealth:
            from playwright_stealth import stealth_async
            await stealth_async(self.page)
            print("[PALACIO] Stealth mode ativado")

        # Bloquear tracking
        await self.page.route("**/analytics**", lambda route: route.abort())
        await self.page.route("**/tracking**", lambda route: route.abort())
        await self.page.route("**google-analytics**", lambda route: route.abort())

        print("[PALACIO] Navegador inicializado")

    async def _close_browser(self):
        """Fecha navegador"""
        if self.browser:
            await self.browser.close()
        if self.playwright:
            await self.playwright.stop()

    async def _navigate(self, url: str) -> str:
        """Navega para URL com retry e rate limit"""
        # Rate limit
        await asyncio.sleep(RATE_LIMIT + random.uniform(0.3, 0.8))

        for attempt in range(MAX_RETRIES):
            try:
                self.metrics["requests_made"] += 1

                response = await self.page.goto(url, timeout=TIMEOUT, wait_until="domcontentloaded")

                # Aguardar conteúdo dinâmico
                await asyncio.sleep(random.uniform(1.0, 2.0))

                # Esperar div_lotes carregar (se existir)
                try:
                    await self.page.wait_for_selector("#div_lotes", timeout=5000)
                    # Aguardar conteúdo aparecer
                    await asyncio.sleep(2)
                except:
                    pass

                # Scroll para carregar lazy content
                await self._human_scroll()

                try:
                    await self.page.wait_for_load_state("networkidle", timeout=10000)
                except:
                    pass

                return await self.page.content()

            except Exception as e:
                if attempt < MAX_RETRIES - 1:
                    print(f"  [RETRY] {e}")
                    await asyncio.sleep(2 * (attempt + 1))
                else:
                    self.metrics["errors"].append({"url": url, "error": str(e)})
                    raise

        return ""

    async def _human_scroll(self):
        """Simula scroll humano para carregar conteúdo lazy"""
        try:
            # Scroll mais agressivo para carregar mais lotes
            for _ in range(random.randint(8, 12)):
                await self.page.mouse.wheel(0, random.randint(500, 800))
                await asyncio.sleep(random.uniform(0.2, 0.4))

            # Aguardar carregamento
            await asyncio.sleep(1)

            # Scroll para cima e para baixo para garantir carregamento
            for _ in range(3):
                await self.page.mouse.wheel(0, -1000)
                await asyncio.sleep(0.3)
            for _ in range(5):
                await self.page.mouse.wheel(0, 1000)
                await asyncio.sleep(0.3)
        except:
            pass

    async def get_lotes_subcategoria(self, subcat_id: int, subcat_nome: str) -> List[LoteInfo]:
        """Busca lotes de uma subcategoria específica"""
        url = f"{self.base_url}/site/leilao.php?subcategoria_pesquisa={subcat_id}"
        print(f"  Carregando {subcat_nome}...")

        lotes = []

        try:
            html = await self._navigate(url)
            if not html:
                return lotes

            # Debug: salvar HTML
            debug_file = self.output_dir / f"debug_subcat_{subcat_id}.html"
            debug_file.write_text(html, encoding="utf-8")

            # Extrair lotes do HTML renderizado
            lotes = self._parse_lotes_html(html, subcat_nome)
            print(f"    Encontrados: {len(lotes)} lotes")

            # Verificar paginação
            page = 2
            while page <= MAX_PAGES:
                # Tentar próxima página
                next_url = f"{url}&paginacao={page}"
                html = await self._navigate(next_url)

                if not html:
                    break

                novos_lotes = self._parse_lotes_html(html, subcat_nome)
                if not novos_lotes:
                    break

                # Verificar se são lotes novos (evitar duplicatas)
                ids_existentes = {l.lote_id for l in lotes}
                novos = [l for l in novos_lotes if l.lote_id not in ids_existentes]

                if not novos:
                    break

                lotes.extend(novos)
                print(f"    Página {page}: +{len(novos)} lotes")
                page += 1

        except Exception as e:
            print(f"  [ERRO] Falha ao buscar subcategoria {subcat_id}: {e}")
            self.metrics["errors"].append({
                "subcategoria": subcat_id,
                "error": str(e)
            })

        return lotes

    def _parse_lotes_html(self, html: str, subcategoria: str) -> List[LoteInfo]:
        """Extrai lotes do HTML renderizado"""
        lotes = []

        # Padrão principal: onclick="exibir_lote(lote_id, leilao_id)"
        # Exemplo: onclick="exibir_lote(1490421,8242)"
        lote_pattern = r'exibir_lote\((\d+)\s*,\s*(\d+)\)'
        matches = re.findall(lote_pattern, html)

        print(f"    IDs encontrados: {len(matches)}")

        seen_ids = set()
        for lote_id, leilao_id in matches:
            if lote_id in seen_ids:
                continue
            seen_ids.add(lote_id)

            lote = self._extract_lote_from_card(html, lote_id, leilao_id, subcategoria)
            if lote:
                lotes.append(lote)

        return lotes

    def _extract_lote_from_card(self, html: str, lote_id: str, leilao_id: str, subcategoria: str) -> Optional[LoteInfo]:
        """Extrai informações de um lote do card HTML"""
        # Estrutura do card:
        # <div class="col-md-3 ...">
        #   <div class="shadow mb-4">
        #     <div class="i-c" onclick="exibir_lote(lote_id,leilao_id)">
        #       <img src="imagens_lote/...">
        #     </div>
        #     <div class="card-body ...">
        #       <div class="quebraln mt-3 mb-0 h6"> MARCA/MODELO</div>
        #       <div class="my-0 h6">2022 2023</div>
        #       <div class="mt-0 small mb-2">sucata (grande monta)</div>
        #       <div class="inf small">Leilão <div class="float-right">8242</div></div>
        #       <div class="inf small">Salvador <div class="float-right">05/02/26</div></div>
        #       <div class="h3 mt-3 text-center">...4.697,00...</div>
        #     </div>
        #   </div>
        # </div>

        # Localizar o card pelo onclick
        pattern = rf'exibir_lote\({lote_id}\s*,\s*{leilao_id}\)'
        match = re.search(pattern, html)
        if not match:
            return None

        # Extrair o card inteiro (aproximadamente 1500 chars após o onclick)
        start = max(0, match.start() - 200)
        end = min(len(html), match.end() + 1500)
        card_html = html[start:end]

        lote = LoteInfo(
            lote_id=lote_id,
            leilao_codigo=leilao_id,
            url=f"{self.base_url}/site/lotem.php?cod_lote={lote_id}",
            subcategoria=subcategoria,
        )

        # Imagem (primeiro img após o onclick)
        img_pattern = r'<img\s+src=["\']([^"\']+)["\']'
        img_match = re.search(img_pattern, card_html)
        if img_match:
            img_url = img_match.group(1)
            # Ignorar imagens de logo/preparação
            if 'preparacao' not in img_url.lower() and 'logo' not in img_url.lower():
                if not img_url.startswith('http'):
                    img_url = f"{self.base_url}/site/{img_url}"
                lote.imagem = img_url

        # Marca/Modelo (div com classe quebraln h6)
        # Formato: " CHEV/ONIX 10MT LT2" ou "<i class='fab fa-youtube'></i> FORD/FIESTA"
        marca_patterns = [
            r'class=["\']quebraln[^"\']*h6["\'][^>]*>(?:<[^>]+>\s*)*([A-Z][^<]+)</div>',
            r'<div[^>]*h6[^>]*>(?:<[^>]+>\s*)*([A-Z][A-Z0-9/\s\-\.]+)</div>',
        ]
        for pattern in marca_patterns:
            marca_match = re.search(pattern, card_html)
            if marca_match:
                marca_modelo = marca_match.group(1).strip()
                if marca_modelo and len(marca_modelo) > 3:
                    lote.marca_modelo = marca_modelo
                    lote.descricao = marca_modelo
                    break

        # Ano (div com my-0 h6 contendo "2022 2023")
        ano_pattern = r'class=["\']my-0\s+h6["\'][^>]*>(\d{4})\s*(\d{4})?</div>'
        ano_match = re.search(ano_pattern, card_html)
        if ano_match:
            try:
                # Pegar o ano mais recente (segundo, se existir)
                ano1 = int(ano_match.group(1))
                ano2 = int(ano_match.group(2)) if ano_match.group(2) else ano1
                lote.ano = max(ano1, ano2)
            except:
                pass

        # Categoria/status (sucata, pequena monta, etc)
        cat_pattern = r'class=["\']mt-0\s+small\s+mb-2["\'][^>]*>([^<]+)</div>'
        cat_match = re.search(cat_pattern, card_html)
        if cat_match:
            lote.status = cat_match.group(1).strip()

        # Valor (padrão: 4.697,00 ou 13.972,00)
        valor_pattern = r'<i\s+class=["\']fas\s+fa-gavel[^"\']*["\'][^>]*></i>\s*([\d.,]+)'
        valor_match = re.search(valor_pattern, card_html)
        if valor_match:
            valor_str = valor_match.group(1).replace('.', '').replace(',', '.')
            try:
                lote.valor = float(valor_str)
            except:
                pass

        return lote

    def _generate_id(self, lote: LoteInfo) -> str:
        """Gera ID único para o lote"""
        key = f"PALACIO-{lote.lote_id}"
        return hashlib.md5(key.encode()).hexdigest()[:16]

    def _lote_to_veiculo(self, lote: LoteInfo) -> VeiculoLeilao:
        """Converte LoteInfo para VeiculoLeilao"""
        coletado_em = datetime.now(timezone.utc).isoformat()

        return VeiculoLeilao(
            id_fonte=self._generate_id(lote),
            fonte="PALACIO-LEILOES",
            edital=f"Leilão {lote.leilao_codigo}" if lote.leilao_codigo else "",
            cidade="",
            data_encerramento=None,
            status_leilao=lote.status,
            lote=lote.numero,
            categoria=lote.subcategoria,
            marca_modelo=lote.marca_modelo or lote.descricao,
            ano=lote.ano,
            placa=lote.placa,
            valor_inicial=lote.valor,
            url_lote=lote.url,
            url_imagem=lote.imagem,
            coletado_em=coletado_em,
            patio="",
            leilao_codigo=lote.leilao_codigo,
            comitente="",
            subcategoria=lote.subcategoria,
        )

    async def run(self) -> List[VeiculoLeilao]:
        """Executa coleta completa"""
        print("\n" + "=" * 60)
        print("PALÁCIO DOS LEILÕES - Iniciando coleta")
        print("=" * 60)

        veiculos = []

        try:
            await self._init_browser()

            # Buscar lotes de cada subcategoria
            for subcat_id, subcat_nome in SUBCATEGORIAS.items():
                lotes = await self.get_lotes_subcategoria(subcat_id, subcat_nome)

                for lote in lotes:
                    veiculo = self._lote_to_veiculo(lote)
                    veiculos.append(veiculo)

            self.metrics["veiculos_found"] = len(veiculos)
            self.metrics["leiloes_found"] = len(set(v.leilao_codigo for v in veiculos if v.leilao_codigo))

            print(f"\n[PALACIO] Total: {len(veiculos)} veículos coletados")

            # Salvar resultados
            if veiculos:
                await self._save_results(veiculos)

            return veiculos

        finally:
            await self._close_browser()

            # Salvar métricas
            self.metrics["finished_at"] = datetime.now(timezone.utc).isoformat()
            self._save_metrics()

    async def _save_results(self, veiculos: List[VeiculoLeilao]):
        """Salva veículos em JSONL"""
        timestamp = datetime.now().strftime("%Y%m%dT%H%M%S")
        output_file = self.output_dir / f"veiculos_{timestamp}.jsonl"

        with open(output_file, "w", encoding="utf-8") as f:
            for v in veiculos:
                f.write(json.dumps(v.to_dict(), ensure_ascii=False) + "\n")

        print(f"[PALACIO] Resultados salvos: {output_file}")

    def _save_metrics(self):
        """Salva métricas da execução"""
        timestamp = datetime.now().strftime("%Y%m%dT%H%M%S")
        metrics_file = self.output_dir / f"metrics_{timestamp}.json"

        with open(metrics_file, "w", encoding="utf-8") as f:
            json.dump(self.metrics, f, ensure_ascii=False, indent=2)

        print(f"[PALACIO] Métricas salvas: {metrics_file}")


# ============================================================
# CLI
# ============================================================

async def main():
    """Executa scraper standalone"""
    import argparse

    parser = argparse.ArgumentParser(description="Palácio dos Leilões Scraper")
    parser.add_argument("--output", "-o", type=str, default="outputs/palacio_leiloes",
                        help="Diretório de saída")
    parser.add_argument("--headless", action="store_true", default=True,
                        help="Executar sem interface gráfica")
    parser.add_argument("--visible", action="store_true",
                        help="Executar com interface gráfica visível")
    args = parser.parse_args()

    headless = not args.visible

    scraper = PalacioLeiloesScraper(output_dir=Path(args.output), headless=headless)
    veiculos = await scraper.run()

    print(f"\nTotal: {len(veiculos)} veículos")

    # Mostrar amostra
    if veiculos:
        print("\nAmostra (primeiros 5):")
        for v in veiculos[:5]:
            print(f"  - Lote {v.lote}: {v.marca_modelo} ({v.ano}) - R$ {v.valor_inicial:.2f}")


if __name__ == "__main__":
    asyncio.run(main())
