"""
Módulo de Descoberta de URLs - Leilões Judiciais.

Responsável por:
1. Fazer parsing do sitemap.xml
2. Extrair URLs de lotes
3. Filtrar por categorias de veículos/sucatas
4. Gerar discovery_report.json (Phase 4)
"""

import json
import os
import re
import xml.etree.ElementTree as ET
from dataclasses import dataclass, field, asdict
from datetime import datetime
from pathlib import Path
from typing import List, Optional, Set
from urllib.parse import urlparse
import logging

import httpx

from .config import Config, config

logger = logging.getLogger(__name__)


@dataclass
class DiscoveredLot:
    """Representa um lote descoberto no sitemap."""
    url: str
    leilao_id: str
    lote_id: str
    lastmod: Optional[str] = None
    priority: Optional[float] = None
    category_hint: Optional[str] = None


@dataclass
class DiscoveryReport:
    """Relatório de descoberta."""
    total_urls_found: int = 0
    lot_urls_found: int = 0
    filtered_vehicle_lots: int = 0
    category_urls: int = 0
    errors: List[str] = field(default_factory=list)
    timestamp: str = field(default_factory=lambda: datetime.utcnow().isoformat())
    # PHASE 4: Additional fields
    sources_used: List[str] = field(default_factory=list)
    top_seeds: List[dict] = field(default_factory=list)

    def to_dict(self) -> dict:
        return asdict(self)

    def save(self, output_dir: str = "out/leiloesjudiciais/reports") -> str:
        """Save discovery report to JSON file."""
        Path(output_dir).mkdir(parents=True, exist_ok=True)
        filepath = os.path.join(output_dir, "discovery_report.json")

        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(self.to_dict(), f, ensure_ascii=False, indent=2)

        logger.info(f"Discovery report saved: {filepath}")
        return filepath


class LeilaoDiscovery:
    """
    Descoberta de lotes via sitemap.

    Fluxo:
    1. Busca sitemap.xml
    2. Extrai todas as URLs de lotes (/lote/{id}/{id})
    3. Identifica URLs de categorias de veículos
    4. Retorna lista filtrada
    """

    def __init__(self, cfg: Optional[Config] = None):
        self.config = cfg or config
        self.lot_pattern = re.compile(self.config.LOT_URL_PATTERN)

    def discover_from_sitemap(
        self,
        filter_vehicles_only: bool = True,
        max_lots: Optional[int] = None,
        save_report: bool = True
    ) -> tuple[List[DiscoveredLot], DiscoveryReport]:
        """
        Descobre lotes a partir do sitemap.

        Args:
            filter_vehicles_only: Se True, filtra apenas lotes de veículos
            max_lots: Limite máximo de lotes a retornar
            save_report: Se True, salva discovery_report.json

        Returns:
            Tupla (lista de lotes, relatório)
        """
        report = DiscoveryReport()
        report.sources_used = ["sitemap.xml"]
        lots: List[DiscoveredLot] = []
        category_urls: Set[str] = set()
        leilao_counts: dict = {}  # Track lots per leilao_id

        try:
            # 1. Busca sitemap
            logger.info(f"Fetching sitemap: {self.config.SITEMAP_URL}")
            xml_content = self._fetch_sitemap()
            if not xml_content:
                report.errors.append("Falha ao buscar sitemap")
                return [], report

            # 2. Parse XML
            urls_data = self._parse_sitemap(xml_content)
            report.total_urls_found = len(urls_data)
            logger.info(f"Found {len(urls_data)} URLs in sitemap")

            # 3. Processa cada URL
            for url_data in urls_data:
                url = url_data.get("loc", "")

                # Identifica URLs de categorias
                if self.config.is_vehicle_url(url):
                    category_urls.add(url)
                    continue

                # Verifica se é URL de lote
                match = self.lot_pattern.search(url)
                if not match:
                    continue

                leilao_id, lote_id = match.groups()
                lot = DiscoveredLot(
                    url=url,
                    leilao_id=leilao_id,
                    lote_id=lote_id,
                    lastmod=url_data.get("lastmod"),
                    priority=self._parse_priority(url_data.get("priority")),
                )
                lots.append(lot)

                # Track lots per leilao for top_seeds
                leilao_counts[leilao_id] = leilao_counts.get(leilao_id, 0) + 1

            report.lot_urls_found = len(lots)
            report.category_urls = len(category_urls)

            # PHASE 4: Calculate top seeds (leiloes with most lots)
            sorted_leiloes = sorted(leilao_counts.items(), key=lambda x: -x[1])[:10]
            report.top_seeds = [
                {"leilao_id": lid, "lot_count": count}
                for lid, count in sorted_leiloes
            ]

            # 4. Ordena por data de modificação (mais recentes primeiro)
            lots.sort(key=lambda x: x.lastmod or "", reverse=True)

            # 5. Aplica limite
            if max_lots:
                lots = lots[:max_lots]

            report.filtered_vehicle_lots = len(lots)

            logger.info(f"Discovered {len(lots)} lots ({len(category_urls)} category URLs)")

        except Exception as e:
            logger.error(f"Discovery error: {e}")
            report.errors.append(f"Erro na descoberta: {str(e)}")

        # Save discovery report
        if save_report:
            report.save()

        return lots, report

    def discover_from_category_pages(
        self,
        categories: Optional[List[str]] = None
    ) -> tuple[List[str], DiscoveryReport]:
        """
        Descobre lotes navegando pelas páginas de categoria.

        NOTA: Este método é um fallback para quando o sitemap não é suficiente.
        Como o site é uma SPA, pode não funcionar bem com HTTP puro.

        Args:
            categories: Lista de URLs de categorias (usa config se None)

        Returns:
            Tupla (lista de URLs de lotes, relatório)
        """
        report = DiscoveryReport()
        lot_urls: Set[str] = set()

        categories = categories or self.config.VEHICLE_CATEGORIES

        for cat_path in categories:
            cat_url = f"{self.config.BASE_URL}{cat_path}"
            try:
                html = self._fetch_page(cat_url)
                if html:
                    # Procura links de lotes no HTML
                    urls = self._extract_lot_urls_from_html(html)
                    lot_urls.update(urls)
            except Exception as e:
                report.errors.append(f"Erro em {cat_url}: {str(e)}")

        report.lot_urls_found = len(lot_urls)
        return list(lot_urls), report

    def _fetch_sitemap(self) -> Optional[str]:
        """Busca conteúdo do sitemap."""
        try:
            with httpx.Client(timeout=self.config.REQUEST_TIMEOUT_SECONDS) as client:
                response = client.get(
                    self.config.SITEMAP_URL,
                    headers=self.config.get_headers()
                )
                if response.status_code == 200:
                    return response.text
        except Exception:
            pass
        return None

    def _fetch_page(self, url: str) -> Optional[str]:
        """Busca conteúdo de uma página."""
        try:
            with httpx.Client(timeout=self.config.REQUEST_TIMEOUT_SECONDS) as client:
                response = client.get(url, headers=self.config.get_headers())
                if response.status_code == 200:
                    return response.text
        except Exception:
            pass
        return None

    def _parse_sitemap(self, xml_content: str) -> List[dict]:
        """
        Faz parsing do sitemap XML.

        Returns:
            Lista de dicionários com loc, lastmod, priority
        """
        urls = []
        try:
            # Remove namespace para facilitar parsing
            xml_content = re.sub(r'\sxmlns="[^"]+"', '', xml_content)
            root = ET.fromstring(xml_content)

            for url_elem in root.findall(".//url"):
                url_data = {}

                loc = url_elem.find("loc")
                if loc is not None and loc.text:
                    url_data["loc"] = loc.text.strip()

                lastmod = url_elem.find("lastmod")
                if lastmod is not None and lastmod.text:
                    url_data["lastmod"] = lastmod.text.strip()

                priority = url_elem.find("priority")
                if priority is not None and priority.text:
                    url_data["priority"] = priority.text.strip()

                if "loc" in url_data:
                    urls.append(url_data)

        except ET.ParseError:
            pass

        return urls

    def _parse_priority(self, priority_str: Optional[str]) -> Optional[float]:
        """Converte string de prioridade para float."""
        if not priority_str:
            return None
        try:
            return float(priority_str)
        except ValueError:
            return None

    def _extract_lot_urls_from_html(self, html: str) -> List[str]:
        """
        Extrai URLs de lotes do HTML.

        Args:
            html: Conteúdo HTML da página

        Returns:
            Lista de URLs de lotes encontradas
        """
        urls = []
        # Procura padrões de URL de lotes
        pattern = rf'{re.escape(self.config.BASE_URL)}/lote/\d+/\d+'
        matches = re.findall(pattern, html)
        urls.extend(matches)

        # Também procura caminhos relativos
        rel_pattern = r'href=["\']?(/lote/\d+/\d+)["\']?'
        rel_matches = re.findall(rel_pattern, html)
        for path in rel_matches:
            urls.append(f"{self.config.BASE_URL}{path}")

        return list(set(urls))


# Função de conveniência
def discover_lots(
    filter_vehicles: bool = True,
    max_lots: int = 500
) -> tuple[List[DiscoveredLot], DiscoveryReport]:
    """
    Função de conveniência para descoberta de lotes.

    Args:
        filter_vehicles: Filtrar apenas veículos
        max_lots: Limite máximo

    Returns:
        Tupla (lotes, relatório)
    """
    discovery = LeilaoDiscovery()
    return discovery.discover_from_sitemap(
        filter_vehicles_only=filter_vehicles,
        max_lots=max_lots
    )
