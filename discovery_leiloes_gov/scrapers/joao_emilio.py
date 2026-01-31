#!/usr/bin/env python3
"""
João Emílio Scraper - Coleta de leilões de veículos

Fonte: https://www.joaoemilio.com.br/
Frequência recomendada: 3x/dia
Rate limit: 2-3 seg entre requests (site com proteção Cloudflare)

Estrutura do site:
- Página principal: lista de leilões ativos
- /leilao/{id}/lotes?page=N - Lotes de um leilão
- Tipos: MULTIMARCAS, FAB, PRF, TRIBUNAL DE JUSTIÇA

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

BASE_URL = "https://www.joaoemilio.com.br"
RATE_LIMIT = 2.5  # segundos entre requests
TIMEOUT = 30000  # ms
MAX_PAGES = 50  # Limite de segurança por leilão
MAX_RETRIES = 3


# ============================================================
# DATA CONTRACT (compatível com outros scrapers)
# ============================================================

@dataclass
class VeiculoLeilao:
    """Contrato canônico para veículo de leilão"""
    id_fonte: str
    fonte: str = "JOAO-EMILIO"

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

    # Campos extras João Emílio
    patio: str = ""
    leilao_nome: str = ""
    leilao_id: str = ""

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class LeilaoInfo:
    """Informações de um leilão/evento"""
    id_leilao: str
    nome: str = ""
    data: str = ""
    hora: str = ""
    status: str = ""
    tipo: str = ""
    url: str = ""
    total_lotes: int = 0


# ============================================================
# SCRAPER COM PLAYWRIGHT
# ============================================================

class JoaoEmilioScraper:
    """Scraper para João Emílio Leilões usando Playwright"""

    def __init__(self, output_dir: Path = None, headless: bool = True):
        self.base_url = BASE_URL
        self.headless = headless
        self.output_dir = output_dir or Path("outputs/joao_emilio")
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
            print("[WARN] playwright-stealth não instalado")
            self.has_stealth = False

        self.playwright = await async_playwright().start()
        self.browser = await self.playwright.chromium.launch(
            headless=self.headless,
            args=[
                "--disable-blink-features=AutomationControlled",
                "--disable-dev-shm-usage",
                "--no-sandbox",
                "--disable-setuid-sandbox",
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
            print("[JOAO-EMILIO] Stealth mode ativado")

        # Bloquear tracking
        await self.page.route("**/analytics**", lambda route: route.abort())
        await self.page.route("**/tracking**", lambda route: route.abort())
        await self.page.route("**google-analytics**", lambda route: route.abort())

        print("[JOAO-EMILIO] Navegador inicializado")

    async def _close_browser(self):
        """Fecha navegador"""
        if self.browser:
            await self.browser.close()
        if self.playwright:
            await self.playwright.stop()

    async def _navigate(self, url: str) -> str:
        """Navega para URL com retry, rate limit e bypass de Cloudflare"""
        # Rate limit com variação humana
        await asyncio.sleep(RATE_LIMIT + random.uniform(0.5, 1.5))

        for attempt in range(MAX_RETRIES):
            try:
                self.metrics["requests_made"] += 1

                response = await self.page.goto(url, timeout=TIMEOUT, wait_until="domcontentloaded")

                # Comportamento humano
                await asyncio.sleep(random.uniform(1.0, 2.0))

                # Verificar Cloudflare challenge
                html = await self.page.content()
                if "challenge" in html.lower() or "cf-browser-verification" in html or "just a moment" in html.lower():
                    print(f"  [CF] Cloudflare challenge - aguardando resolução...")

                    # Aguardar o challenge resolver (até 30 segundos)
                    for wait in range(6):
                        await asyncio.sleep(5)
                        html = await self.page.content()

                        # Verificar se o conteúdo real carregou
                        if "joaoemilio" in html.lower() and "leilao" in html.lower():
                            print(f"  [CF] Challenge resolvido após {(wait+1)*5}s")
                            break

                    # Esperar mais um pouco para carregar completamente
                    await asyncio.sleep(2)
                    html = await self.page.content()

                if response and response.status == 403:
                    print(f"  [WARN] 403 Forbidden - tentativa {attempt + 1}")
                    await asyncio.sleep(5 * (attempt + 1))
                    continue

                if response and response.status == 404:
                    print(f"  [INFO] 404 - leilão não encontrado ou encerrado")
                    return ""

                # Simular scroll
                await self._human_scroll()

                try:
                    await self.page.wait_for_load_state("networkidle", timeout=10000)
                except:
                    pass

                return await self.page.content()

            except Exception as e:
                if attempt < MAX_RETRIES - 1:
                    print(f"  [RETRY] {e}")
                    await asyncio.sleep(3 * (attempt + 1))
                else:
                    self.metrics["errors"].append({"url": url, "error": str(e)})
                    raise

        return ""

    async def _human_scroll(self):
        """Simula scroll humano"""
        try:
            for _ in range(random.randint(2, 4)):
                await self.page.mouse.wheel(0, random.randint(100, 300))
                await asyncio.sleep(random.uniform(0.2, 0.5))
        except:
            pass

    async def _detect_blocked(self, html: str) -> bool:
        """Detecta se fomos bloqueados"""
        html_lower = html.lower()

        blocked_indicators = [
            "cf-browser-verification",
            "challenge-running",
            "just a moment",
            "checking your browser",
        ]

        if any(ind in html_lower for ind in blocked_indicators):
            content_indicators = ["joaoemilio", "leilão", "leilao", "veículo", "lote"]
            if any(ind in html_lower for ind in content_indicators):
                return False
            return True

        return False

    async def get_leiloes_ativos(self) -> List[LeilaoInfo]:
        """Busca leilões ativos na página principal"""
        url = self.base_url
        print("[JOAO-EMILIO] Buscando leilões ativos...")

        try:
            html = await self._navigate(url)

            if await self._detect_blocked(html):
                print("[ERRO] Página bloqueada (Cloudflare)")
                return []

            leiloes = []

            # Categorias de veículos que queremos coletar
            CATEGORIAS_VEICULOS = [
                "MULTIMARCAS", "VEICULO", "VEÍCULO", "VEICULOS", "VEÍCULOS",
                "MOTO", "MOTOS", "MOTOCICLETA", "MOTOCICLETAS",
                "FAB", "PRF", "DETRAN", "RECEITA FEDERAL",
                "TRIBUNAL", "JUDICIAL", "SUCATA"
            ]

            # Padrão para extrair leilões: links absolutos ou relativos
            # Formato: href="https://www.joaoemilio.com.br/leilao/5745/lotes" ou href="/leilao/5745/lotes"
            leilao_pattern = r'href="(?:https?://www\.joaoemilio\.com\.br)?(/leilao/(\d+)/lotes)"[^>]*>'
            url_matches = re.findall(leilao_pattern, html)

            # Padrão para títulos dos cards
            titulo_pattern = r'<h6[^>]*class="card-title[^"]*"[^>]*>([^<]+)</h6>'
            titulos = re.findall(titulo_pattern, html)

            # Padrão para datas
            data_pattern = r'<strong>Data:</strong>\s*(\d{2}/\d{2}/\d{4})'
            datas = re.findall(data_pattern, html)

            # Padrão para horários
            hora_pattern = r'leilão às[^>]*</strong>\s*(\d{2}:\d{2})'
            horas = re.findall(hora_pattern, html, re.IGNORECASE)

            # Padrão para status
            status_pattern = r'<div class="[^"]*label_leilao[^"]*">([^<]+)</div>'
            status_list = re.findall(status_pattern, html)

            seen_ids = set()
            leilao_idx = 0

            for url_path, leilao_id in url_matches:
                # Evitar duplicados
                if leilao_id in seen_ids:
                    continue
                seen_ids.add(leilao_id)

                # Pegar título correspondente
                nome = titulos[leilao_idx] if leilao_idx < len(titulos) else ""
                nome = nome.strip()

                # Filtrar apenas categorias de veículos
                is_veiculo = any(cat.lower() in nome.lower() for cat in CATEGORIAS_VEICULOS)

                # Verificar também na descrição (próximos elementos)
                if not is_veiculo and leilao_idx < len(titulos):
                    # Procurar descrição "VEÍCULOS" nos próximos 500 chars após o título
                    start_idx = html.find(nome)
                    if start_idx > 0:
                        desc_area = html[start_idx:start_idx + 500]
                        if any(cat.lower() in desc_area.lower() for cat in CATEGORIAS_VEICULOS):
                            is_veiculo = True

                if not is_veiculo:
                    leilao_idx += 1
                    continue

                # Pegar data e hora
                data = datas[leilao_idx] if leilao_idx < len(datas) else ""
                hora = horas[leilao_idx] if leilao_idx < len(horas) else ""
                status = status_list[leilao_idx] if leilao_idx < len(status_list) else "Ativo"

                leilao = LeilaoInfo(
                    id_leilao=leilao_id,
                    nome=nome,
                    data=data,
                    hora=hora,
                    status=status.strip(),
                    url=f"{self.base_url}{url_path}"
                )
                leiloes.append(leilao)
                leilao_idx += 1

            self.metrics["leiloes_found"] = len(leiloes)
            print(f"[JOAO-EMILIO] {len(leiloes)} leilões encontrados")
            return leiloes

        except Exception as e:
            print(f"[ERRO] Buscar leilões: {e}")
            return []

    async def get_lotes_leilao(self, leilao: LeilaoInfo) -> List[dict]:
        """Extrai todos os lotes de um leilão"""
        all_lotes = []
        page = 1

        print(f"\n[LEILÃO {leilao.id_leilao}] {leilao.nome}")

        while page <= MAX_PAGES:
            url = f"{self.base_url}/leilao/{leilao.id_leilao}/lotes?page={page}"
            print(f"  Página {page}...")

            try:
                html = await self._navigate(url)

                if not html or await self._detect_blocked(html):
                    break

                # Verificar se há lotes na página
                lotes = self._parse_lotes(html, leilao)

                if not lotes:
                    print(f"  Página {page}: sem lotes")
                    break

                all_lotes.extend(lotes)
                print(f"  Página {page}: {len(lotes)} lotes")

                # Verificar paginação
                max_page = self._get_max_page(html)
                if page >= max_page:
                    break

                page += 1

            except Exception as e:
                print(f"  [ERRO] Página {page}: {e}")
                break

        return all_lotes

    def _parse_lotes(self, html: str, leilao: LeilaoInfo) -> List[dict]:
        """Extrai dados dos lotes do HTML"""
        lotes = []

        # Padrão para encontrar blocos de lotes
        # Estrutura: <a href="/item/{id}/detalhes">...<h5>descrição</h5>...</a>
        item_pattern = r'href="(https?://www\.joaoemilio\.com\.br/item/(\d+)/detalhes[^"]*)"[^>]*>.*?<h5>([^<]+)</h5>'
        items = re.findall(item_pattern, html, re.DOTALL | re.IGNORECASE)

        # Padrão para imagens dos lotes (background-url no estilo)
        img_pattern = r"background:\s*url\('([^']+)'\)"
        img_matches = re.findall(img_pattern, html)

        # Padrão para Marca/Modelo separado
        marca_modelo_pattern = r'<b>Marca/Modelo:</b>\s*([^<\n]+)'
        marca_modelo_matches = re.findall(marca_modelo_pattern, html)

        # Padrão para valor de avaliação/lance inicial
        valor_pattern = r'Lance\s+Inicial.*?R\$\s*([\d.,]+)'
        valor_matches = re.findall(valor_pattern, html, re.DOTALL | re.IGNORECASE)

        # Processar cada item encontrado
        for i, (url, item_id, descricao) in enumerate(items):
            descricao = descricao.strip()

            # Verificar se é veículo (não equipamento/móvel)
            desc_lower = descricao.lower()
            is_veiculo = any(kw in desc_lower for kw in [
                'veículo', 'veiculo', 'moto', 'motocicleta', 'carro',
                'sucata', 'caminhão', 'caminhao', 'ônibus', 'onibus',
                'automóvel', 'automovel', 'fiat', 'volkswagen', 'vw',
                'chevrolet', 'ford', 'honda', 'yamaha', 'toyota', 'hyundai'
            ])

            if not is_veiculo:
                continue

            # Extrair marca e modelo da descrição
            # Formato: "MARCA {marca} MODELO {modelo}, ANO {ano}"
            marca = ""
            modelo = ""
            ano = None
            placa = None
            categoria = ""

            # Extrair marca
            marca_match = re.search(r'MARCA\s+(\w+)', descricao, re.IGNORECASE)
            if marca_match:
                marca = marca_match.group(1).upper()

            # Extrair modelo
            modelo_match = re.search(r'MODELO\s+([^,]+)', descricao, re.IGNORECASE)
            if modelo_match:
                modelo = modelo_match.group(1).strip()

            # Ou usar o campo Marca/Modelo separado se disponível
            if i < len(marca_modelo_matches):
                mm = marca_modelo_matches[i].strip()
                if '/' in mm:
                    parts = mm.split('/')
                    marca = parts[0].strip().upper()
                    modelo = parts[1].strip() if len(parts) > 1 else ""

            # Extrair ano (formato: ANO 2018-2019 ou ANO 2018/2019 ou ANO 2018)
            ano_match = re.search(r'ANO\s+(\d{4})(?:[/-](\d{4}))?', descricao, re.IGNORECASE)
            if ano_match:
                if ano_match.group(2):
                    ano = int(ano_match.group(2))  # Usar o segundo ano
                else:
                    ano = int(ano_match.group(1))

            # Extrair placa
            placa_match = re.search(r'PLACA\s+([A-Z0-9]+)', descricao, re.IGNORECASE)
            if placa_match:
                placa = placa_match.group(1)

            # Verificar se é sucata
            if 'sucata' in desc_lower:
                categoria = "Sucata"
            elif 'recuper' in desc_lower:
                categoria = "Recuperável"
            else:
                categoria = "Conservado"

            # Construir marca_modelo
            marca_modelo = f"{marca} {modelo}".strip()
            if not marca_modelo or marca_modelo == " ":
                # Fallback: extrair do início da descrição
                marca_modelo = descricao[:50] if len(descricao) > 50 else descricao

            # Valor
            valor = 0.0
            if i < len(valor_matches):
                valor_str = valor_matches[i].replace(".", "").replace(",", ".")
                try:
                    valor = float(valor_str)
                except:
                    pass

            # URL da imagem
            url_imagem = img_matches[i] if i < len(img_matches) else None

            # Número do lote
            lote_num = i + 1

            lote = {
                "lote": lote_num,
                "item_id": item_id,
                "marca_modelo": marca_modelo,
                "ano": ano,
                "placa": placa,
                "valor": valor,
                "categoria": categoria,
                "url_lote": url,
                "url_imagem": url_imagem,
                "leilao_id": leilao.id_leilao,
                "leilao_nome": leilao.nome,
                "descricao": descricao[:200] if len(descricao) > 200 else descricao,
            }

            lotes.append(lote)

        return lotes

    def _get_max_page(self, html: str) -> int:
        """Extrai número máximo de páginas"""
        pages = re.findall(r'page=(\d+)', html)
        if pages:
            return max(int(p) for p in pages)
        return 1

    def normalizar_veiculo(self, lote: dict) -> VeiculoLeilao:
        """Normaliza dados para contrato canônico"""
        # Gerar ID único
        id_raw = f"JOAO-EMILIO|{lote.get('leilao_id', '')}|{lote.get('lote', 0)}"
        id_fonte = hashlib.md5(id_raw.encode()).hexdigest()[:16]

        return VeiculoLeilao(
            id_fonte=id_fonte,
            fonte="JOAO-EMILIO",
            edital=lote.get("leilao_nome", ""),
            cidade="",
            data_encerramento=None,
            status_leilao="Disponível",
            lote=lote.get("lote", 0),
            categoria=lote.get("categoria", ""),
            marca_modelo=lote.get("marca_modelo", ""),
            ano=lote.get("ano"),
            valor_inicial=lote.get("valor", 0.0),
            url_lote=lote.get("url_lote", ""),
            url_imagem=lote.get("url_imagem"),
            leilao_nome=lote.get("leilao_nome", ""),
            leilao_id=lote.get("leilao_id", ""),
            coletado_em=datetime.now(timezone.utc).isoformat()
        )

    async def run(self, max_leiloes: int = None) -> List[VeiculoLeilao]:
        """Executa coleta completa"""
        print("=" * 60)
        print("JOÃO EMÍLIO SCRAPER - Iniciando coleta")
        print("=" * 60)

        veiculos = []

        try:
            await self._init_browser()

            # Buscar leilões ativos
            leiloes = await self.get_leiloes_ativos()

            if not leiloes:
                print("[AVISO] Nenhum leilão encontrado")
                return []

            # Limitar se especificado
            if max_leiloes:
                leiloes = leiloes[:max_leiloes]

            # Coletar lotes de cada leilão
            for leilao in leiloes:
                lotes = await self.get_lotes_leilao(leilao)

                for lote in lotes:
                    veiculo = self.normalizar_veiculo(lote)
                    veiculos.append(veiculo)

            self.metrics["veiculos_found"] = len(veiculos)

        finally:
            await self._close_browser()

        self.metrics["finished_at"] = datetime.now(timezone.utc).isoformat()

        # Salvar resultados
        self._save_results(veiculos)

        print("\n" + "=" * 60)
        print(f"RESULTADO: {len(veiculos)} veículos coletados de {len(leiloes)} leilões")
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
    parser = argparse.ArgumentParser(description="João Emílio Scraper")
    parser.add_argument("--max-leiloes", type=int, default=None,
                        help="Limitar número de leilões (para teste)")
    parser.add_argument("--output-dir", type=str, default=None,
                        help="Diretório de saída")
    parser.add_argument("--visible", action="store_true",
                        help="Executar com navegador visível (debug)")
    args = parser.parse_args()

    output_dir = Path(args.output_dir) if args.output_dir else None
    headless = not args.visible

    scraper = JoaoEmilioScraper(output_dir=output_dir, headless=headless)

    # Executar async
    veiculos = asyncio.run(scraper.run(max_leiloes=args.max_leiloes))

    # Resumo
    print(f"\nResumo:")
    print(f"  Requests: {scraper.metrics['requests_made']}")
    print(f"  Leilões: {scraper.metrics['leiloes_found']}")
    print(f"  Veículos: {scraper.metrics['veiculos_found']}")
    print(f"  Erros: {len(scraper.metrics['errors'])}")

    if veiculos:
        print(f"\nExemplos (primeiros 5):")
        for v in veiculos[:5]:
            print(f"  - Lote {v.lote}: {v.marca_modelo} ({v.ano}) - R$ {v.valor_inicial:.2f}")


if __name__ == "__main__":
    main()
