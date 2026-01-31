"""
Scraper com Playwright para leiloesjudiciais.com.br

Como a API REST está bugada (só retorna imóveis), este módulo usa
Playwright para renderizar JavaScript e extrair dados de veículos.

Estratégia:
1. Interceptar requests de API que o site faz
2. Navegar para /veiculos e capturar dados
3. Paginar automaticamente
4. Extrair dados completos (valores, datas, imagens)

Uso:
    python -m connectors.leiloesjudiciais.playwright_scraper --max-pages 5
"""

import json
import logging
import re
import time
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Callable

from playwright.sync_api import sync_playwright, Page, Response, Browser

logger = logging.getLogger(__name__)


@dataclass
class ScrapedLot:
    """Lote extraído via Playwright."""
    # IDs
    lote_id: int
    leilao_id: int

    # Dados básicos
    titulo: str
    descricao: Optional[str] = None
    cidade: Optional[str] = None
    uf: Optional[str] = None

    # Valores
    valor_avaliacao: Optional[float] = None
    valor_lance_minimo: Optional[float] = None

    # Datas
    dt_fechamento: Optional[str] = None  # ISO 8601

    # Categoria
    id_categoria: int = 1  # 1=Veículos
    nm_categoria: str = "Veículos"

    # URLs
    url_lote: Optional[str] = None
    url_leiloeiro: Optional[str] = None
    imagens: List[str] = field(default_factory=list)

    # Leiloeiro
    nome_leiloeiro: Optional[str] = None

    # Metadados
    raw_data: Optional[Dict] = None
    scraped_at: str = field(default_factory=lambda: datetime.utcnow().isoformat())


@dataclass
class ScrapeStats:
    """Estatísticas de scraping."""
    pages_scraped: int = 0
    total_items: int = 0
    vehicles_found: int = 0
    api_calls_intercepted: int = 0
    errors: List[str] = field(default_factory=list)
    started_at: Optional[str] = None
    finished_at: Optional[str] = None
    duration_seconds: float = 0.0


class PlaywrightScraper:
    """
    Scraper usando Playwright para extrair dados de veículos.

    Funciona interceptando as chamadas de API que o site faz
    quando navega para a página de veículos.
    """

    BASE_URL = "https://www.leiloesjudiciais.com.br"
    VEHICLES_URL = f"{BASE_URL}/veiculos"
    API_PATTERN = re.compile(r"api\.leiloesjudiciais\.com\.br.*get-lotes")

    def __init__(
        self,
        headless: bool = True,
        timeout_ms: int = 30000,
        page_delay_ms: int = 2000,
    ):
        """
        Inicializa o scraper.

        Args:
            headless: Executar sem janela visível
            timeout_ms: Timeout para navegação
            page_delay_ms: Delay entre páginas (rate limiting)
        """
        self.headless = headless
        self.timeout_ms = timeout_ms
        self.page_delay_ms = page_delay_ms
        self.stats = ScrapeStats()
        self._intercepted_data: List[Dict] = []

    def scrape_vehicles(
        self,
        max_pages: Optional[int] = None,
        progress_callback: Optional[Callable[[int, int, int], None]] = None,
    ) -> tuple[List[ScrapedLot], ScrapeStats]:
        """
        Extrai lotes de veículos do site.

        Args:
            max_pages: Limite de páginas (None = todas)
            progress_callback: Callback(page, total_pages, items_so_far)

        Returns:
            Tupla (lista de lotes, estatísticas)
        """
        self.stats = ScrapeStats(started_at=datetime.utcnow().isoformat())
        self._intercepted_data = []
        all_lots: List[ScrapedLot] = []

        logger.info(f"Iniciando scraping com Playwright (headless={self.headless})")

        with sync_playwright() as p:
            browser = p.chromium.launch(headless=self.headless)
            context = browser.new_context(
                viewport={"width": 1920, "height": 1080},
                user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
            )
            page = context.new_page()

            # Interceptar responses da API
            page.on("response", self._handle_response)

            try:
                # Navegar para página de veículos
                logger.info(f"Navegando para {self.VEHICLES_URL}")
                page.goto(self.VEHICLES_URL, timeout=self.timeout_ms)

                # Aguardar carregamento inicial
                page.wait_for_load_state("networkidle", timeout=self.timeout_ms)
                time.sleep(2)  # Extra delay para SPA carregar

                # Processar dados interceptados da primeira página
                lots = self._process_intercepted_data()
                all_lots.extend(lots)
                self.stats.pages_scraped = 1

                if progress_callback and lots:
                    progress_callback(1, self._get_total_pages(), len(all_lots))

                logger.info(f"Página 1: {len(lots)} veículos encontrados")

                # Paginar
                current_page = 1
                total_pages = self._get_total_pages()

                while current_page < total_pages:
                    if max_pages and current_page >= max_pages:
                        logger.info(f"Atingido limite de {max_pages} páginas")
                        break

                    current_page += 1

                    # Limpar dados interceptados
                    self._intercepted_data = []

                    # Clicar no botão de próxima página
                    if not self._click_next_page(page):
                        logger.warning("Não foi possível ir para próxima página")
                        break

                    # Aguardar carregamento
                    time.sleep(self.page_delay_ms / 1000)
                    page.wait_for_load_state("networkidle", timeout=self.timeout_ms)

                    # Processar dados
                    lots = self._process_intercepted_data()
                    all_lots.extend(lots)
                    self.stats.pages_scraped = current_page

                    if progress_callback:
                        progress_callback(current_page, total_pages, len(all_lots))

                    logger.info(f"Página {current_page}/{total_pages}: {len(lots)} veículos")

            except Exception as e:
                logger.error(f"Erro no scraping: {e}")
                self.stats.errors.append(str(e))

            finally:
                browser.close()

        self.stats.finished_at = datetime.utcnow().isoformat()
        self.stats.total_items = len(all_lots)
        self.stats.vehicles_found = len([l for l in all_lots if l.id_categoria == 1])

        if self.stats.started_at and self.stats.finished_at:
            start = datetime.fromisoformat(self.stats.started_at)
            end = datetime.fromisoformat(self.stats.finished_at)
            self.stats.duration_seconds = (end - start).total_seconds()

        logger.info(
            f"Scraping concluído: {len(all_lots)} lotes em "
            f"{self.stats.pages_scraped} páginas "
            f"({self.stats.duration_seconds:.1f}s)"
        )

        return all_lots, self.stats

    def _handle_response(self, response: Response):
        """Intercepta responses da API."""
        url = response.url

        if self.API_PATTERN.search(url):
            self.stats.api_calls_intercepted += 1

            try:
                if response.status == 200:
                    data = response.json()
                    if isinstance(data, dict) and "items" in data:
                        self._intercepted_data.append(data)
                        logger.debug(f"Interceptado: {len(data.get('items', []))} items")
            except Exception as e:
                logger.warning(f"Erro ao processar response: {e}")

    def _process_intercepted_data(self) -> List[ScrapedLot]:
        """Processa dados interceptados e filtra veículos."""
        lots = []

        for data in self._intercepted_data:
            items = data.get("items", [])

            for item in items:
                # Filtrar apenas veículos (id_categoria = 1)
                if item.get("id_categoria") != 1:
                    continue

                lot = self._parse_item(item)
                if lot:
                    lots.append(lot)

        return lots

    def _parse_item(self, item: Dict[str, Any]) -> Optional[ScrapedLot]:
        """Converte item da API para ScrapedLot."""
        try:
            # Extrair IDs
            lote_id = item.get("lote_id") or item.get("id")
            leilao_id = item.get("leilao_id")

            if not lote_id or not leilao_id:
                return None

            # Extrair título
            titulo = (
                item.get("nm_titulo_lote") or
                item.get("titulo") or
                item.get("nm_titulo_leilao") or
                ""
            )

            # Extrair localização
            cidade = item.get("nm_cidade") or item.get("cidade")
            uf = item.get("nm_estado") or item.get("uf") or item.get("estado")

            # Extrair valores
            valor_avaliacao = None
            val_str = item.get("vl_avaliacao") or item.get("valor_avaliacao")
            if val_str:
                try:
                    valor_avaliacao = float(str(val_str).replace(",", "."))
                except ValueError:
                    pass

            valor_lance = None
            lance_str = item.get("vl_lance_minimo") or item.get("lance_minimo")
            if lance_str:
                try:
                    valor_lance = float(str(lance_str).replace(",", "."))
                except ValueError:
                    pass

            # Extrair data
            dt_fechamento = item.get("dt_fechamento") or item.get("data_fechamento")

            # Extrair URLs - CORREÇÃO: Não concatenar URL hardcoded
            # Usa resolução centralizada para obter URL canônica do lote
            from connectors.common.url_resolution import resolve_lote_url, normalize_base_url

            url_leiloeiro_raw = item.get("nm_url_leiloeiro") or item.get("url_leiloeiro")
            url_lote_api = item.get("url_lote") or item.get("nm_url_lote") or item.get("link")

            # Normaliza URL do leiloeiro (adiciona https:// se necessário)
            url_leiloeiro = normalize_base_url(url_leiloeiro_raw)

            # Constrói URL de fallback com padrão correto (se tiver dados suficientes)
            fallback_url = None
            if url_leiloeiro and leilao_id and lote_id:
                # Padrão correto: /leilao/index/leilao_id/{leilao_id}/lote/{lote_id}
                fallback_url = f"{url_leiloeiro}/leilao/index/leilao_id/{leilao_id}/lote/{lote_id}"

            # Resolve URL do lote usando estratégia em cascata
            url_result = resolve_lote_url(
                candidate_urls=[url_lote_api, url_leiloeiro],  # Usa url_leiloeiro normalizada
                candidate_labels=["api_canonical", "api_canonical"],  # Dados interceptados da API
                fallback_constructed=fallback_url,  # Fallback com padrão correto
                validate_http=False,
            )

            url_lote = url_result.final_url

            # Extrair imagens
            imagens = []
            img = item.get("imagem") or item.get("nm_imagem")
            if img:
                if not img.startswith("http"):
                    img = f"https://cdn.leiloesjudiciais.com.br/{img}"
                imagens.append(img)

            # Leiloeiro
            nome_leiloeiro = item.get("nm_leiloeiro") or item.get("leiloeiro")

            return ScrapedLot(
                lote_id=int(lote_id),
                leilao_id=int(leilao_id),
                titulo=titulo,
                descricao=item.get("nm_descricao") or item.get("descricao"),
                cidade=cidade,
                uf=uf,
                valor_avaliacao=valor_avaliacao,
                valor_lance_minimo=valor_lance,
                dt_fechamento=dt_fechamento,
                id_categoria=item.get("id_categoria", 1),
                nm_categoria=item.get("nm_categoria", "Veículos"),
                url_lote=url_lote,
                url_leiloeiro=url_leiloeiro,
                imagens=imagens,
                nome_leiloeiro=nome_leiloeiro,
                raw_data=item,
            )

        except Exception as e:
            logger.warning(f"Erro ao parsear item: {e}")
            return None

    def _get_total_pages(self) -> int:
        """Obtém total de páginas dos dados interceptados."""
        for data in self._intercepted_data:
            total = data.get("totalPages")
            if total:
                return int(total)
        return 1

    def _click_next_page(self, page: Page) -> bool:
        """Clica no botão de próxima página."""
        try:
            # Tentar diferentes seletores para botão de próxima página
            selectors = [
                "button.p-paginator-next",
                ".p-paginator-next",
                "[aria-label='Next Page']",
                "button:has-text('>')",
                ".pagination-next",
            ]

            for selector in selectors:
                try:
                    btn = page.locator(selector).first
                    if btn.is_visible() and btn.is_enabled():
                        btn.click()
                        return True
                except Exception:
                    continue

            # Fallback: tentar scroll para carregar mais
            page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
            return False

        except Exception as e:
            logger.warning(f"Erro ao clicar próxima página: {e}")
            return False


def scrape_vehicles(
    max_pages: int = 10,
    headless: bool = True,
    output_file: Optional[str] = None,
) -> tuple[List[ScrapedLot], ScrapeStats]:
    """
    Função de conveniência para scraping.

    Args:
        max_pages: Máximo de páginas
        headless: Executar sem janela
        output_file: Arquivo para salvar resultados (JSONL)

    Returns:
        Tupla (lotes, estatísticas)
    """
    scraper = PlaywrightScraper(headless=headless)

    def progress(page, total, items):
        print(f"  Página {page}/{total}: {items} veículos coletados")

    lots, stats = scraper.scrape_vehicles(
        max_pages=max_pages,
        progress_callback=progress
    )

    # Salvar resultados
    if output_file and lots:
        Path(output_file).parent.mkdir(parents=True, exist_ok=True)

        with open(output_file, "w", encoding="utf-8") as f:
            for lot in lots:
                # Converter para dict
                lot_dict = {
                    "lote_id": lot.lote_id,
                    "leilao_id": lot.leilao_id,
                    "titulo": lot.titulo,
                    "descricao": lot.descricao,
                    "cidade": lot.cidade,
                    "uf": lot.uf,
                    "valor_avaliacao": lot.valor_avaliacao,
                    "valor_lance_minimo": lot.valor_lance_minimo,
                    "dt_fechamento": lot.dt_fechamento,
                    "id_categoria": lot.id_categoria,
                    "nm_categoria": lot.nm_categoria,
                    "url_lote": lot.url_lote,
                    "url_leiloeiro": lot.url_leiloeiro,
                    "imagens": lot.imagens,
                    "nome_leiloeiro": lot.nome_leiloeiro,
                    "scraped_at": lot.scraped_at,
                }
                f.write(json.dumps(lot_dict, ensure_ascii=False) + "\n")

        print(f"Resultados salvos em: {output_file}")

    return lots, stats


# CLI
if __name__ == "__main__":
    import argparse

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(message)s"
    )

    parser = argparse.ArgumentParser(
        description="Scraper Playwright para leiloesjudiciais.com.br"
    )
    parser.add_argument(
        "--max-pages",
        type=int,
        default=5,
        help="Máximo de páginas a processar (default: 5)"
    )
    parser.add_argument(
        "--no-headless",
        action="store_true",
        help="Mostrar janela do navegador"
    )
    parser.add_argument(
        "--output",
        type=str,
        default="out/leiloesjudiciais/vehicles_playwright.jsonl",
        help="Arquivo de saída (JSONL)"
    )

    args = parser.parse_args()

    print("=" * 60)
    print("SCRAPER PLAYWRIGHT - LEILÕES JUDICIAIS")
    print("=" * 60)
    print()
    print(f"Max páginas: {args.max_pages}")
    print(f"Headless: {not args.no_headless}")
    print(f"Output: {args.output}")
    print()

    lots, stats = scrape_vehicles(
        max_pages=args.max_pages,
        headless=not args.no_headless,
        output_file=args.output,
    )

    print()
    print("=" * 60)
    print("RESULTADO")
    print("=" * 60)
    print(f"Páginas processadas: {stats.pages_scraped}")
    print(f"Veículos encontrados: {stats.vehicles_found}")
    print(f"API calls interceptados: {stats.api_calls_intercepted}")
    print(f"Duração: {stats.duration_seconds:.1f}s")

    if stats.errors:
        print(f"Erros: {len(stats.errors)}")
        for e in stats.errors[:5]:
            print(f"  - {e}")
