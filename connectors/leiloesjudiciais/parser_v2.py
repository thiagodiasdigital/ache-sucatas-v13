"""
Parser V2 - Leilões Judiciais
Extração melhorada com múltiplos fallbacks.

Ordem de extração de título:
1. <h2 class="titulo-lote"> (mais confiável)
2. <title> tag (se não for "undefined")
3. <meta name="description">
4. Título gerado: "Lote {lote_id} - Leilões Judiciais"

Extração de dados adicionais:
- Descrição: <meta name="description">
- Valores: JSON embutido (avaliacao, lance, valorAvaliacao)
- Imagens: <img> dentro de .imagem-wrapper ou .imagens-lote
"""

import hashlib
import json
import os
import re
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
import logging

try:
    from bs4 import BeautifulSoup
    HAS_BS4 = True
except ImportError:
    HAS_BS4 = False

logger = logging.getLogger(__name__)


@dataclass
class ExtractedLot:
    """Dados extraídos do HTML."""
    url: str
    leilao_id: str
    lote_id: str

    # Dados extraídos
    titulo: Optional[str] = None
    descricao: Optional[str] = None
    cidade: Optional[str] = None
    uf: Optional[str] = None

    # Valores
    valor_avaliacao: Optional[float] = None
    valor_lance_minimo: Optional[float] = None
    valor_lance_atual: Optional[float] = None

    # Datas
    data_leilao: Optional[str] = None

    # Imagens
    imagens: List[str] = field(default_factory=list)

    # Qualidade/Metadados
    title_source: str = "none"  # h2, title, meta, generated
    title_quality: str = "missing"  # real, generated, missing
    location_quality: str = "missing"  # real, missing
    extraction_method: str = "html_v2"
    is_valid_page: bool = True  # False se página retornou "undefined"

    extraction_timestamp: str = field(default_factory=lambda: datetime.utcnow().isoformat())
    warnings: List[str] = field(default_factory=list)


class ParserV2:
    """
    Parser V2 com extração melhorada.
    """

    # Regex patterns
    TITLE_TAG_PATTERN = re.compile(r'<title>([^<]+)</title>', re.IGNORECASE)
    H2_TITULO_PATTERN = re.compile(r'<h2[^>]*class=["\']?titulo-lote["\']?[^>]*>([^<]+)</h2>', re.IGNORECASE)
    META_DESC_PATTERN = re.compile(r'<meta[^>]*name=["\']description["\'][^>]*content=["\']([^"\']+)["\']', re.IGNORECASE)

    # Location patterns in title: "DESCRIÇÃO - CIDADE/UF - Leilões Judiciais"
    LOCATION_PATTERN = re.compile(r'-\s*([A-Za-zÀ-ÿ\s]+)/([A-Z]{2})\s*(?:-\s*Leil|$)', re.IGNORECASE)

    # Value patterns in JSON
    VALUE_PATTERNS = {
        'avaliacao': re.compile(r'["\']?(?:valor_?)?avaliacao["\']?\s*[":]\s*([0-9.,]+)', re.IGNORECASE),
        'lance_minimo': re.compile(r'["\']?lance_?minimo["\']?\s*[":]\s*([0-9.,]+)', re.IGNORECASE),
        'lance_atual': re.compile(r'["\']?lance_?atual["\']?\s*[":]\s*([0-9.,]+)', re.IGNORECASE),
        'valor': re.compile(r'["\']?valor["\']?\s*[":]\s*([0-9.,]+)', re.IGNORECASE),
    }

    # Image patterns
    IMG_PATTERN = re.compile(r'<img[^>]*src=["\']([^"\']+)["\']', re.IGNORECASE)

    def __init__(self, html_output_dir: Optional[str] = None):
        self.html_output_dir = html_output_dir or "out/leiloesjudiciais/html"
        self._stats = {
            'title_from_h2': 0,
            'title_from_title_tag': 0,
            'title_from_meta': 0,
            'title_generated': 0,
            'title_missing': 0,
            'location_found': 0,
            'location_missing': 0,
            'invalid_pages': 0,
        }

    def parse(self, url: str, html: str, save_html: bool = False) -> ExtractedLot:
        """Parse HTML and extract lot data."""
        # Extract IDs from URL
        leilao_id, lote_id = self._extract_ids(url)

        result = ExtractedLot(
            url=url,
            leilao_id=leilao_id,
            lote_id=lote_id
        )

        if not html:
            result.is_valid_page = False
            result.warnings.append("HTML vazio")
            self._stats['invalid_pages'] += 1
            return result

        # Save HTML if requested
        if save_html:
            self._save_html(url, html, leilao_id, lote_id)

        # 1. Extract title (multiple fallbacks)
        self._extract_title(html, result)

        # 2. Check if page is valid (not "undefined")
        if result.titulo and result.titulo.lower().strip() in ['undefined', 'null', '']:
            result.is_valid_page = False
            result.titulo = None
            self._stats['invalid_pages'] += 1

        # 3. Extract description
        self._extract_description(html, result)

        # 4. Extract location from title or description
        self._extract_location(result)

        # 5. Extract values from JSON
        self._extract_values(html, result)

        # 6. Extract images
        self._extract_images(html, result)

        # 7. Generate title if missing (last resort)
        if not result.titulo and result.is_valid_page:
            result.titulo = f"Lote {lote_id} - Leilões Judiciais"
            result.title_source = "generated"
            result.title_quality = "generated"
            self._stats['title_generated'] += 1

        return result

    def _extract_ids(self, url: str) -> Tuple[str, str]:
        """Extract leilao_id and lote_id from URL."""
        match = re.search(r'/lote/(\d+)/(\d+)', url)
        if match:
            return match.groups()
        return "", ""

    def _extract_title(self, html: str, result: ExtractedLot):
        """Extract title from multiple sources."""
        # 1. Try <h2 class="titulo-lote"> (most reliable)
        h2_match = self.H2_TITULO_PATTERN.search(html)
        if h2_match:
            titulo = h2_match.group(1).strip()
            if titulo and titulo.lower() != 'undefined':
                result.titulo = titulo
                result.title_source = "h2"
                result.title_quality = "real"
                self._stats['title_from_h2'] += 1
                return

        # 2. Try <title> tag
        title_match = self.TITLE_TAG_PATTERN.search(html)
        if title_match:
            raw_title = title_match.group(1).strip()
            # Remove " - Leilões Judiciais" suffix
            titulo = re.sub(r'\s*-\s*Leil[õo]es Judiciais\s*$', '', raw_title, flags=re.IGNORECASE)
            if titulo and titulo.lower() != 'undefined':
                result.titulo = titulo
                result.title_source = "title"
                result.title_quality = "real"
                self._stats['title_from_title_tag'] += 1
                return

        # 3. Try <meta name="description">
        meta_match = self.META_DESC_PATTERN.search(html)
        if meta_match:
            desc = meta_match.group(1).strip()
            if desc and desc.lower() != 'undefined' and 'undefined' not in desc.lower()[:20]:
                # Use first sentence as title
                titulo = desc.split(' - ')[0].strip()[:200]
                if titulo:
                    result.titulo = titulo
                    result.title_source = "meta"
                    result.title_quality = "real"
                    self._stats['title_from_meta'] += 1
                    return

        self._stats['title_missing'] += 1

    def _extract_description(self, html: str, result: ExtractedLot):
        """Extract description from meta tag."""
        meta_match = self.META_DESC_PATTERN.search(html)
        if meta_match:
            desc = meta_match.group(1).strip()
            if desc and 'undefined' not in desc.lower()[:20]:
                result.descricao = desc

    def _extract_location(self, result: ExtractedLot):
        """Extract city/state from title or description."""
        text_to_search = result.titulo or result.descricao or ""

        match = self.LOCATION_PATTERN.search(text_to_search)
        if match:
            result.cidade = match.group(1).strip().title()
            result.uf = match.group(2).upper()
            result.location_quality = "real"
            self._stats['location_found'] += 1
        else:
            self._stats['location_missing'] += 1

    def _extract_values(self, html: str, result: ExtractedLot):
        """Extract monetary values from JSON in HTML."""
        for value_type, pattern in self.VALUE_PATTERNS.items():
            match = pattern.search(html)
            if match:
                try:
                    value_str = match.group(1).replace('.', '').replace(',', '.')
                    value = float(value_str)
                    if value > 0:
                        if value_type == 'avaliacao':
                            result.valor_avaliacao = value
                        elif value_type == 'lance_minimo':
                            result.valor_lance_minimo = value
                        elif value_type == 'lance_atual':
                            result.valor_lance_atual = value
                        elif value_type == 'valor' and not result.valor_avaliacao:
                            result.valor_avaliacao = value
                except (ValueError, IndexError):
                    pass

    def _extract_images(self, html: str, result: ExtractedLot):
        """Extract image URLs from HTML."""
        # Look for images in lot image containers
        img_section = re.search(r'class=["\']imagens?-lote["\'][^>]*>(.*?)</div>', html, re.DOTALL | re.IGNORECASE)
        if img_section:
            imgs = self.IMG_PATTERN.findall(img_section.group(1))
        else:
            imgs = self.IMG_PATTERN.findall(html)

        # Filter and clean URLs
        for img in imgs:
            if img and not any(x in img.lower() for x in ['logo', 'icon', 'avatar', 'placeholder']):
                if img.startswith('http'):
                    result.imagens.append(img)
                elif img.startswith('//'):
                    result.imagens.append(f"https:{img}")

        # Limit to 10 images
        result.imagens = result.imagens[:10]

    def _save_html(self, url: str, html: str, leilao_id: str, lote_id: str):
        """Save HTML as evidence."""
        try:
            Path(self.html_output_dir).mkdir(parents=True, exist_ok=True)
            url_hash = hashlib.md5(url.encode()).hexdigest()[:12]
            filename = f"{leilao_id}_{lote_id}_{url_hash}.html"
            filepath = os.path.join(self.html_output_dir, filename)

            with open(filepath, 'w', encoding='utf-8') as f:
                f.write(f"<!-- URL: {url} -->\n")
                f.write(f"<!-- Timestamp: {datetime.utcnow().isoformat()} -->\n")
                f.write(html)
        except Exception as e:
            logger.warning(f"Erro ao salvar HTML: {e}")

    def get_stats(self) -> Dict[str, int]:
        """Return extraction statistics."""
        return self._stats.copy()


def parse_lot(url: str, html: str) -> ExtractedLot:
    """Convenience function."""
    parser = ParserV2()
    return parser.parse(url, html)
