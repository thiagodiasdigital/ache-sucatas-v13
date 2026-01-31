#!/usr/bin/env python3
"""
Sodré Santoro Scraper - Coleta de leilões de veículos e sucatas

Fonte: https://www.sodresantoro.com.br/
Frequência recomendada: 1x/dia
Rate limit: 2-3 seg entre requests (site com proteção anti-bot)

Estrutura do site:
- /veiculos/lotes - Lista de veículos
- /sucatas/lotes - Lista de sucatas
- Paginação via ?page=N
- Filtros: lot_category, lot_location, order

Requer: playwright (pip install playwright && playwright install chromium)
"""

import re
import time
import json
import hashlib
import asyncio
from pathlib import Path
from datetime import datetime, timezone
from dataclasses import dataclass, asdict
from typing import Optional, List

# ============================================================
# CONFIGURACAO
# ============================================================

BASE_URL = "https://www.sodresantoro.com.br"
RATE_LIMIT = 2.5  # segundos entre requests (site com proteção)
TIMEOUT = 30000  # ms
MAX_PAGES = 100  # Limite de segurança
MAX_RETRIES = 3

# Categorias a coletar
CATEGORIAS = [
    {"tipo": "veiculos", "path": "/veiculos/lotes"},
    {"tipo": "sucatas", "path": "/sucatas/lotes"},
]


# ============================================================
# DATA CONTRACT (mesmo do DETRAN-MG para compatibilidade)
# ============================================================

@dataclass
class VeiculoLeilao:
    """Contrato canônico para veículo de leilão"""
    id_fonte: str
    fonte: str = "SODRE-SANTORO"

    # Leilão
    edital: str = ""
    cidade: str = ""
    data_encerramento: Optional[str] = None
    status_leilao: str = ""

    # Veículo
    lote: int = 0
    categoria: str = ""  # Sucata, Conservado, etc
    marca_modelo: str = ""
    ano: Optional[int] = None
    placa: Optional[str] = None
    valor_inicial: float = 0.0

    # Metadados
    url_lote: str = ""
    url_imagem: Optional[str] = None
    coletado_em: str = ""

    # Campos extras Sodré Santoro
    patio: str = ""
    combustivel: str = ""
    cor: str = ""

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class LeilaoInfo:
    """Informações de um leilão/evento"""
    id_leilao: str
    nome: str = ""
    data: str = ""
    local: str = ""
    url: str = ""
    status: str = ""


# ============================================================
# SCRAPER COM PLAYWRIGHT
# ============================================================

class SodreSantoroScraper:
    """Scraper para Sodré Santoro usando Playwright"""

    def __init__(self, output_dir: Path = None, headless: bool = True):
        self.base_url = BASE_URL
        self.headless = headless
        self.output_dir = output_dir or Path("outputs/sodre_santoro")
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.browser = None
        self.page = None

        # Métricas
        self.metrics = {
            "started_at": datetime.now(timezone.utc).isoformat(),
            "requests_made": 0,
            "leiloes_found": 0,
            "veiculos_found": 0,
            "sucatas_found": 0,
            "errors": []
        }

    async def _init_browser(self):
        """Inicializa navegador Playwright com stealth mode"""
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
            print("[WARN] playwright-stealth não instalado. Execute: pip install playwright-stealth")
            self.has_stealth = False

        self.playwright = await async_playwright().start()
        self.browser = await self.playwright.chromium.launch(
            headless=self.headless,
            args=[
                "--disable-blink-features=AutomationControlled",
                "--disable-dev-shm-usage",
                "--no-sandbox",
                "--disable-setuid-sandbox",
                "--disable-accelerated-2d-canvas",
                "--disable-gpu",
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
            geolocation={"latitude": -23.5505, "longitude": -46.6333},
            permissions=["geolocation"],
        )
        self.page = await self.context.new_page()

        # Aplicar stealth patches
        if self.has_stealth:
            from playwright_stealth import stealth_async
            await stealth_async(self.page)
            print("[SODRE] Stealth mode ativado")

        # NÃO bloquear imagens - pode ser detectado como bot
        # Apenas bloquear tracking
        await self.page.route("**/analytics**", lambda route: route.abort())
        await self.page.route("**/tracking**", lambda route: route.abort())
        await self.page.route("**google-analytics**", lambda route: route.abort())

        print("[SODRE] Navegador inicializado")

    async def _close_browser(self):
        """Fecha navegador"""
        if self.browser:
            await self.browser.close()
        if self.playwright:
            await self.playwright.stop()

    async def _navigate(self, url: str) -> str:
        """Navega para URL com retry, rate limit e bypass de Cloudflare"""
        import random

        # Rate limit com variação para parecer humano
        await asyncio.sleep(RATE_LIMIT + random.uniform(0.5, 1.5))

        for attempt in range(MAX_RETRIES):
            try:
                self.metrics["requests_made"] += 1

                # Navegar
                response = await self.page.goto(url, timeout=TIMEOUT, wait_until="domcontentloaded")

                # Aguardar um pouco (comportamento humano)
                await asyncio.sleep(random.uniform(1.0, 2.0))

                # Verificar se tem Cloudflare challenge
                html = await self.page.content()
                if "challenge" in html.lower() or "cf-browser-verification" in html:
                    print(f"  [CF] Cloudflare challenge detectado - aguardando resolução...")
                    # Aguardar mais tempo para o challenge resolver
                    await asyncio.sleep(8)

                    # Tentar aguardar o challenge terminar
                    try:
                        await self.page.wait_for_function(
                            "() => !document.body.innerHTML.includes('challenge')",
                            timeout=15000
                        )
                    except:
                        pass

                    html = await self.page.content()

                if response and response.status == 403:
                    print(f"  [WARN] 403 Forbidden - tentativa {attempt + 1}")
                    await asyncio.sleep(5 * (attempt + 1))
                    continue

                # Simular scroll humano
                await self._human_scroll()

                # Aguardar conteúdo carregar
                try:
                    await self.page.wait_for_load_state("networkidle", timeout=10000)
                except:
                    pass  # Timeout ok, conteúdo pode já estar carregado

                return await self.page.content()

            except Exception as e:
                if attempt < MAX_RETRIES - 1:
                    print(f"  [RETRY] {e} - aguardando...")
                    await asyncio.sleep(3 * (attempt + 1))
                else:
                    self.metrics["errors"].append({"url": url, "error": str(e)})
                    raise

        return ""

    async def _human_scroll(self):
        """Simula scroll humano na página"""
        import random
        try:
            # Scroll para baixo algumas vezes
            for _ in range(random.randint(2, 4)):
                await self.page.mouse.wheel(0, random.randint(100, 300))
                await asyncio.sleep(random.uniform(0.2, 0.5))
        except:
            pass

    async def _detect_blocked(self, html: str) -> bool:
        """Detecta se fomos bloqueados"""
        html_lower = html.lower()

        # Indicadores de bloqueio
        blocked_indicators = [
            "cf-browser-verification",
            "challenge-running",
            "just a moment",
            "checking your browser",
            "ray id",
        ]

        # Se encontrar indicadores de bloqueio
        if any(ind in html_lower for ind in blocked_indicators):
            # Mas verificar se também tem conteúdo real
            content_indicators = [
                "sodresantoro",
                "leilão",
                "leilao",
                "veículo",
                "veiculo",
                "lote",
            ]
            # Se tiver conteúdo real, não está bloqueado
            if any(ind in html_lower for ind in content_indicators):
                return False
            return True

        return False

    async def get_lotes_pagina(self, categoria: dict, page_num: int = 1) -> List[dict]:
        """Extrai lotes de uma página da categoria"""
        url = f"{self.base_url}{categoria['path']}?page={page_num}"
        print(f"  Coletando {categoria['tipo']} página {page_num}...")

        try:
            html = await self._navigate(url)

            if await self._detect_blocked(html):
                print("  [ERRO] Página bloqueada (Cloudflare/CAPTCHA)")
                return []

            # Extrair lotes do HTML
            lotes = await self._parse_lotes(html, categoria["tipo"])
            return lotes

        except Exception as e:
            print(f"  [ERRO] {e}")
            return []

    async def _parse_lotes(self, html: str, tipo_categoria: str) -> List[dict]:
        """Extrai dados dos lotes do HTML"""
        lotes = []

        # Lista de marcas conhecidas
        marcas = [
            "FIAT", "VW", "VOLKSWAGEN", "GM", "CHEVROLET", "FORD", "HONDA",
            "YAMAHA", "TOYOTA", "HYUNDAI", "RENAULT", "NISSAN", "JEEP",
            "MITSUBISHI", "CITROEN", "PEUGEOT", "KIA", "SUZUKI", "BMW",
            "MERCEDES", "AUDI", "DAFRA", "SHINERAY", "HAOJUE", "CAOA CHERY",
            "JAC", "LIFAN", "CHERY", "TROLLER", "LAND ROVER", "VOLVO",
            "IVECO", "SCANIA", "MAN", "DAF", "AGRALE"
        ]

        # Padrão para marca/modelo com ano no formato XX/XX ou XXXX
        # Ex: "FIAT siena essence 1.6 13/14" ou "VOLKSWAGEN gol 2019"
        marcas_pattern = r'\b(' + '|'.join(marcas) + r')\s+([A-Za-z0-9][A-Za-z0-9\s\-/\.]+?)(?:\s+(\d{2}/\d{2}|\d{4}))?\s*(?:<|$|\n)'
        modelo_matches = re.findall(marcas_pattern, html, re.IGNORECASE)

        # Padrão para valor (R$ XX.XXX,XX)
        valor_pattern = r'R\$\s*([\d.]+,\d{2})'
        valor_matches = re.findall(valor_pattern, html)

        # Padrão para categoria
        cat_pattern = r'\b(Sucata|Conservado|Recuperável|Sinistrado|Alienação|Aproveitável)\b'
        cat_matches = re.findall(cat_pattern, html, re.IGNORECASE)

        # Padrão para URLs de lotes individuais
        url_pattern = r'href="(/(?:veiculos|sucatas)/lote/(\d+))"'
        url_matches = re.findall(url_pattern, html)

        # Padrão para imagens
        img_pattern = r'src="(https?://[^"]+\.(?:jpg|jpeg|png|webp)[^"]*)"'
        img_matches = re.findall(img_pattern, html, re.IGNORECASE)

        # Padrão para pátios/locais
        patio_pattern = r'(?:Pátio|patio)[:\s]*([A-Za-zÀ-ú\s]+?)(?:\s*[-|<]|$)'
        patio_matches = re.findall(patio_pattern, html, re.IGNORECASE)

        # Quantidade de lotes a processar
        n_lotes = len(modelo_matches)

        for i in range(n_lotes):
            marca, modelo_raw, ano_str = modelo_matches[i]
            modelo = modelo_raw.strip()

            # Limpar modelo de caracteres extras
            modelo = re.sub(r'\s+', ' ', modelo).strip()

            # Extrair ano do formato XX/XX ou XXXX
            ano = None
            if ano_str:
                if '/' in ano_str:
                    # Formato 14/15 -> usar o segundo (ano atual)
                    parts = ano_str.split('/')
                    ano_suffix = int(parts[1])
                    # Converter para ano completo
                    ano = 2000 + ano_suffix if ano_suffix < 50 else 1900 + ano_suffix
                else:
                    ano = int(ano_str)
            else:
                # Tentar extrair ano do modelo
                ano_in_modelo = re.search(r'(\d{2})/(\d{2})', modelo)
                if ano_in_modelo:
                    ano_suffix = int(ano_in_modelo.group(2))
                    ano = 2000 + ano_suffix if ano_suffix < 50 else 1900 + ano_suffix
                    # Remover ano do modelo
                    modelo = re.sub(r'\s*\d{2}/\d{2}\s*', '', modelo).strip()

            # Marca/Modelo formatado
            marca_modelo = f"{marca.upper()} {modelo}"

            # Valor
            if i < len(valor_matches):
                valor_str = valor_matches[i].replace(".", "").replace(",", ".")
                try:
                    valor = float(valor_str)
                except:
                    valor = 0.0
            else:
                valor = 0.0

            # Categoria
            categoria = cat_matches[i].title() if i < len(cat_matches) else tipo_categoria.title()

            # Pátio
            patio = ""
            if i < len(patio_matches):
                patio = patio_matches[i].strip()
                # Limpar pátio de fragmentos inválidos
                if len(patio) < 3 or patio.lower() in ['do', 'de', 'da', 'lote', 'do lote']:
                    patio = ""

            # URL e ID do lote
            lote_num = i + 1
            url_lote = ""
            if i < len(url_matches):
                url_path, lote_id = url_matches[i]
                url_lote = f"{self.base_url}{url_path}"
                lote_num = int(lote_id)

            # Imagem
            url_imagem = img_matches[i] if i < len(img_matches) else None

            lote = {
                "lote": lote_num,
                "marca_modelo": marca_modelo,
                "ano": ano,
                "valor": valor,
                "categoria": categoria,
                "patio": patio,
                "url_lote": url_lote,
                "url_imagem": url_imagem,
            }

            # Só adicionar se tiver marca/modelo válido
            if marca_modelo and len(modelo) > 1:
                lotes.append(lote)

        return lotes

    async def _get_max_page(self, html: str) -> int:
        """Extrai número máximo de páginas"""
        pages = re.findall(r'page=(\d+)', html)
        if pages:
            return max(int(p) for p in pages)
        return 1

    async def get_leiloes_agenda(self) -> List[LeilaoInfo]:
        """Busca leilões na agenda"""
        url = f"{self.base_url}/leilao"
        print("[SODRE] Buscando agenda de leilões...")

        try:
            html = await self._navigate(url)

            if await self._detect_blocked(html):
                print("[ERRO] Agenda bloqueada")
                return []

            leiloes = []

            # Extrair informações de leilões
            # Padrão para datas de leilão
            data_pattern = r'(\d{2}/\d{2}/\d{4})\s*(?:às|-)?\s*(\d{2}:\d{2})?'
            datas = re.findall(data_pattern, html)

            # Padrão para locais/pátios
            local_pattern = r'(?:Pátio|Local)[:\s]+([^<\n]+)'
            locais = re.findall(local_pattern, html, re.IGNORECASE)

            # Padrão para links de leilões
            leilao_url_pattern = r'href="(/leilao/\d+)"'
            urls = re.findall(leilao_url_pattern, html)

            for i, url_match in enumerate(urls):
                leilao = LeilaoInfo(
                    id_leilao=re.search(r'/leilao/(\d+)', url_match).group(1),
                    data=f"{datas[i][0]} {datas[i][1]}" if i < len(datas) else "",
                    local=locais[i].strip() if i < len(locais) else "",
                    url=f"{self.base_url}{url_match}",
                    status="Agendado"
                )
                leiloes.append(leilao)

            self.metrics["leiloes_found"] = len(leiloes)
            print(f"[SODRE] {len(leiloes)} leilões encontrados na agenda")
            return leiloes

        except Exception as e:
            print(f"[ERRO] Agenda: {e}")
            return []

    def normalizar_veiculo(self, lote: dict) -> VeiculoLeilao:
        """Normaliza dados para contrato canônico"""

        # Gerar ID único
        id_raw = f"SODRE-SANTORO|{lote.get('url_lote', '')}|{lote.get('lote', 0)}"
        id_fonte = hashlib.md5(id_raw.encode()).hexdigest()[:16]

        return VeiculoLeilao(
            id_fonte=id_fonte,
            fonte="SODRE-SANTORO",
            edital="",  # Sodré Santoro não usa edital
            cidade=lote.get("patio", ""),
            data_encerramento=None,
            status_leilao="Disponível",
            lote=lote.get("lote", 0),
            categoria=lote.get("categoria", ""),
            marca_modelo=lote.get("marca_modelo", ""),
            ano=lote.get("ano"),
            valor_inicial=lote.get("valor", 0.0),
            url_lote=lote.get("url_lote", ""),
            url_imagem=lote.get("url_imagem"),
            patio=lote.get("patio", ""),
            coletado_em=datetime.now(timezone.utc).isoformat()
        )

    async def run(self, max_pages: int = None, categorias: List[str] = None) -> List[VeiculoLeilao]:
        """Executa coleta completa"""
        print("=" * 60)
        print("SODRÉ SANTORO SCRAPER - Iniciando coleta")
        print("=" * 60)

        veiculos = []

        try:
            await self._init_browser()

            # Filtrar categorias se especificado
            cats_to_scrape = CATEGORIAS
            if categorias:
                cats_to_scrape = [c for c in CATEGORIAS if c["tipo"] in categorias]

            # Para cada categoria
            for categoria in cats_to_scrape:
                print(f"\n[{categoria['tipo'].upper()}] Iniciando coleta...")

                page = 1
                max_pg = max_pages or MAX_PAGES
                lotes_categoria = []

                while page <= max_pg:
                    lotes = await self.get_lotes_pagina(categoria, page)

                    if not lotes:
                        print(f"  Página {page}: sem lotes, finalizando categoria")
                        break

                    lotes_categoria.extend(lotes)
                    print(f"  Página {page}: {len(lotes)} lotes extraídos")

                    # Verificar se há mais páginas
                    html = await self.page.content()
                    max_page_found = await self._get_max_page(html)

                    if page >= max_page_found:
                        break

                    page += 1

                print(f"[{categoria['tipo'].upper()}] Total: {len(lotes_categoria)} lotes")

                # Atualizar métricas
                if categoria["tipo"] == "veiculos":
                    self.metrics["veiculos_found"] = len(lotes_categoria)
                else:
                    self.metrics["sucatas_found"] = len(lotes_categoria)

                # Normalizar lotes
                for lote in lotes_categoria:
                    veiculo = self.normalizar_veiculo(lote)
                    veiculos.append(veiculo)

            # Buscar agenda de leilões (informativo)
            await self.get_leiloes_agenda()

        finally:
            await self._close_browser()

        self.metrics["finished_at"] = datetime.now(timezone.utc).isoformat()

        # Salvar resultados
        self._save_results(veiculos)

        print("\n" + "=" * 60)
        print(f"RESULTADO: {len(veiculos)} veículos/sucatas coletados")
        print("=" * 60)

        return veiculos

    def _save_results(self, veiculos: List[VeiculoLeilao]):
        """Salva resultados em JSONL e métricas"""
        timestamp = datetime.now().strftime("%Y%m%dT%H%M%S")

        # Salvar veículos em JSONL
        veiculos_file = self.output_dir / f"veiculos_{timestamp}.jsonl"
        with open(veiculos_file, "w", encoding="utf-8") as f:
            for v in veiculos:
                f.write(json.dumps(v.to_dict(), ensure_ascii=False) + "\n")
        print(f"Veículos salvos: {veiculos_file}")

        # Salvar métricas
        metrics_file = self.output_dir / f"metrics_{timestamp}.json"
        with open(metrics_file, "w", encoding="utf-8") as f:
            json.dump(self.metrics, f, ensure_ascii=False, indent=2)
        print(f"Métricas salvas: {metrics_file}")

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
    parser = argparse.ArgumentParser(description="Sodré Santoro Scraper")
    parser.add_argument("--max-pages", type=int, default=None,
                        help="Limitar número de páginas por categoria (para teste)")
    parser.add_argument("--output-dir", type=str, default=None,
                        help="Diretório de saída")
    parser.add_argument("--categorias", type=str, default=None,
                        help="Categorias a coletar (veiculos,sucatas)")
    parser.add_argument("--headless", action="store_true", default=True,
                        help="Executar sem interface gráfica (padrão)")
    parser.add_argument("--visible", action="store_true",
                        help="Executar com navegador visível (debug)")
    args = parser.parse_args()

    output_dir = Path(args.output_dir) if args.output_dir else None
    categorias = args.categorias.split(",") if args.categorias else None
    headless = not args.visible

    scraper = SodreSantoroScraper(output_dir=output_dir, headless=headless)

    # Executar async
    veiculos = asyncio.run(scraper.run(max_pages=args.max_pages, categorias=categorias))

    # Resumo
    print(f"\nResumo:")
    print(f"  Requests: {scraper.metrics['requests_made']}")
    print(f"  Veículos: {scraper.metrics['veiculos_found']}")
    print(f"  Sucatas: {scraper.metrics['sucatas_found']}")
    print(f"  Erros: {len(scraper.metrics['errors'])}")

    if veiculos:
        print(f"\nExemplos (primeiros 5):")
        for v in veiculos[:5]:
            print(f"  - Lote {v.lote}: {v.marca_modelo} ({v.ano}) - R$ {v.valor_inicial:.2f} - {v.categoria}")


if __name__ == "__main__":
    main()
