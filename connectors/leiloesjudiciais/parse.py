"""
Módulo de Parsing - Leilões Judiciais.

Responsável por:
1. Extrair dados do HTML das páginas de lotes
2. Identificar campos relevantes (título, valor, cidade, etc.)
3. Extrair metadados (title, meta tags, JSON-LD)
4. Salvar HTML como evidência (Phase 3 requirement)

NOTA: O site leiloesjudiciais.com.br é uma SPA (Vue.js).
O conteúdo dinâmico é carregado via JavaScript/API.
Este parser extrai o máximo possível do HTML estático.
"""

import hashlib
import os
import re
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
from urllib.parse import urlparse
import json
import logging

try:
    from bs4 import BeautifulSoup
    HAS_BS4 = True
except ImportError:
    HAS_BS4 = False
    BeautifulSoup = None

from .config import Config, config

logger = logging.getLogger(__name__)


@dataclass
class ParsedLot:
    """Dados extraídos de um lote."""
    # Identificação
    url: str
    leilao_id: str
    lote_id: str

    # Dados extraídos do título da página
    titulo_completo: Optional[str] = None
    descricao_veiculo: Optional[str] = None
    cidade: Optional[str] = None
    uf: Optional[str] = None

    # Dados extraídos de meta tags
    og_title: Optional[str] = None
    og_description: Optional[str] = None
    og_image: Optional[str] = None

    # Dados extraídos de JSON-LD
    json_ld_data: Optional[Dict] = None

    # Dados extraídos do HTML
    valor_avaliacao: Optional[float] = None
    valor_lance_minimo: Optional[float] = None
    data_leilao: Optional[str] = None
    status_leilao: Optional[str] = None
    nome_leiloeiro: Optional[str] = None

    # Imagens e documentos
    imagens: List[str] = field(default_factory=list)
    documentos: List[str] = field(default_factory=list)

    # Metadados de extração
    extraction_method: str = "html_static"
    extraction_confidence: float = 0.0
    extraction_timestamp: str = field(
        default_factory=lambda: datetime.utcnow().isoformat()
    )
    warnings: List[str] = field(default_factory=list)


class LeilaoParser:
    """
    Parser de páginas de lotes.

    Como o site é uma SPA, este parser foca em:
    1. Título da página (contém veículo e localização)
    2. Meta tags (og:*, description)
    3. JSON-LD se disponível
    4. Qualquer dado pré-renderizado no HTML
    5. Salvar HTML como evidência (Phase 3)
    """

    # Padrão do título: "DESCRIÇÃO - CIDADE/UF - Leilões Judiciais"
    TITLE_PATTERN = re.compile(
        r'^(.+?)\s*-\s*([A-Za-zÀ-ÿ\s]+)/([A-Z]{2})\s*-\s*Leilões Judiciais',
        re.IGNORECASE
    )

    # Padrão alternativo: "DESCRIÇÃO - CIDADE/UF"
    TITLE_PATTERN_ALT = re.compile(
        r'^(.+?)\s*-\s*([A-Za-zÀ-ÿ\s]+)/([A-Z]{2})$',
        re.IGNORECASE
    )

    # Padrão para extrair ano de veículo
    YEAR_PATTERN = re.compile(r'(\d{4})/(\d{4})|(\d{4})')

    # Padrão para valores monetários
    MONEY_PATTERN = re.compile(r'R\$\s*([\d.,]+)')

    def __init__(self, cfg: Optional[Config] = None, html_output_dir: Optional[str] = None):
        self.config = cfg or config
        self.html_output_dir = html_output_dir or "out/leiloesjudiciais/html"
        self._saved_htmls: List[Dict[str, str]] = []  # Track saved HTMLs for reporting

    def parse(self, url: str, html: str, save_html: bool = True) -> ParsedLot:
        """
        Faz parsing do HTML de um lote.

        Args:
            url: URL do lote
            html: Conteúdo HTML
            save_html: Se True, salva HTML como evidência

        Returns:
            ParsedLot com dados extraídos
        """
        # Extrai IDs da URL
        leilao_id, lote_id = self._extract_ids_from_url(url)

        result = ParsedLot(
            url=url,
            leilao_id=leilao_id,
            lote_id=lote_id
        )

        # Salva HTML como evidência (Phase 3)
        if save_html and html:
            html_path = self._save_html_evidence(url, html, leilao_id, lote_id)
            if html_path:
                result.warnings.append(f"HTML salvo: {html_path}")

        # Tenta usar BeautifulSoup se disponível
        if HAS_BS4 and html:
            soup = BeautifulSoup(html, 'html.parser')
            self._parse_with_bs4(soup, result)
        else:
            # Fallback para regex
            self._parse_with_regex(html, result)

        # Calcula confiança da extração
        result.extraction_confidence = self._calculate_confidence(result)

        return result

    def _save_html_evidence(
        self,
        url: str,
        html: str,
        leilao_id: str,
        lote_id: str
    ) -> Optional[str]:
        """
        Salva HTML como evidência de extração (Phase 3 requirement).

        Args:
            url: URL do lote
            html: Conteúdo HTML
            leilao_id: ID do leilão
            lote_id: ID do lote

        Returns:
            Caminho do arquivo salvo ou None se erro
        """
        try:
            # Cria diretório se não existir
            Path(self.html_output_dir).mkdir(parents=True, exist_ok=True)

            # Gera hash único para o arquivo
            url_hash = hashlib.md5(url.encode()).hexdigest()[:12]
            filename = f"{leilao_id}_{lote_id}_{url_hash}.html"
            filepath = os.path.join(self.html_output_dir, filename)

            # Salva HTML
            with open(filepath, 'w', encoding='utf-8') as f:
                f.write(f"<!-- URL: {url} -->\n")
                f.write(f"<!-- Timestamp: {datetime.utcnow().isoformat()} -->\n")
                f.write(html)

            # Registra para relatório
            self._saved_htmls.append({
                "url": url,
                "filepath": filepath,
                "leilao_id": leilao_id,
                "lote_id": lote_id,
                "timestamp": datetime.utcnow().isoformat()
            })

            logger.debug(f"HTML salvo: {filepath}")
            return filepath

        except Exception as e:
            logger.warning(f"Erro ao salvar HTML: {e}")
            return None

    def get_saved_htmls(self) -> List[Dict[str, str]]:
        """Retorna lista de HTMLs salvos."""
        return self._saved_htmls.copy()

    def _extract_ids_from_url(self, url: str) -> Tuple[str, str]:
        """Extrai leilao_id e lote_id da URL."""
        pattern = re.compile(self.config.LOT_URL_PATTERN)
        match = pattern.search(url)
        if match:
            return match.groups()
        return "", ""

    def _parse_with_bs4(self, soup: BeautifulSoup, result: ParsedLot):
        """Faz parsing usando BeautifulSoup."""
        # 1. Título da página
        title_tag = soup.find('title')
        if title_tag and title_tag.string:
            result.titulo_completo = title_tag.string.strip()
            self._parse_title(result.titulo_completo, result)

        # 2. Meta tags
        self._parse_meta_tags(soup, result)

        # 3. JSON-LD
        self._parse_json_ld(soup, result)

        # 4. Busca valores no HTML
        self._search_values_in_html(soup, result)

        # 5. Busca imagens
        self._search_images(soup, result)

    def _parse_with_regex(self, html: str, result: ParsedLot):
        """Faz parsing usando apenas regex (fallback)."""
        # Título
        title_match = re.search(r'<title>([^<]+)</title>', html, re.IGNORECASE)
        if title_match:
            result.titulo_completo = title_match.group(1).strip()
            self._parse_title(result.titulo_completo, result)

        # Meta OG
        og_title = re.search(
            r'<meta[^>]+property=["\']og:title["\'][^>]+content=["\']([^"\']+)["\']',
            html, re.IGNORECASE
        )
        if og_title:
            result.og_title = og_title.group(1)

        og_desc = re.search(
            r'<meta[^>]+property=["\']og:description["\'][^>]+content=["\']([^"\']+)["\']',
            html, re.IGNORECASE
        )
        if og_desc:
            result.og_description = og_desc.group(1)

        og_image = re.search(
            r'<meta[^>]+property=["\']og:image["\'][^>]+content=["\']([^"\']+)["\']',
            html, re.IGNORECASE
        )
        if og_image:
            result.og_image = og_image.group(1)

    def _parse_title(self, title: str, result: ParsedLot):
        """
        Extrai informações do título da página.

        Formato esperado: "DESCRIÇÃO - CIDADE/UF - Leilões Judiciais"
        Exemplo: "FIAT/OGGI CS 1983/1983 - CORDEIRO/RJ - Leilões Judiciais"
        """
        # Tenta padrão principal
        match = self.TITLE_PATTERN.match(title)
        if not match:
            # Tenta padrão alternativo
            match = self.TITLE_PATTERN_ALT.match(title)

        if match:
            result.descricao_veiculo = match.group(1).strip()
            result.cidade = match.group(2).strip().title()
            result.uf = match.group(3).upper()
        else:
            result.warnings.append(f"Título não segue padrão esperado: {title}")
            # Tenta extrair pelo menos a descrição
            if " - " in title:
                parts = title.split(" - ")
                result.descricao_veiculo = parts[0].strip()

    def _parse_meta_tags(self, soup: BeautifulSoup, result: ParsedLot):
        """Extrai dados de meta tags."""
        # OG Title
        og_title = soup.find('meta', property='og:title')
        if og_title and og_title.get('content'):
            result.og_title = og_title['content']

        # OG Description
        og_desc = soup.find('meta', property='og:description')
        if og_desc and og_desc.get('content'):
            result.og_description = og_desc['content']

        # OG Image
        og_image = soup.find('meta', property='og:image')
        if og_image and og_image.get('content'):
            result.og_image = og_image['content']
            result.imagens.append(og_image['content'])

        # Description padrão
        meta_desc = soup.find('meta', attrs={'name': 'description'})
        if meta_desc and meta_desc.get('content') and not result.og_description:
            result.og_description = meta_desc['content']

    def _parse_json_ld(self, soup: BeautifulSoup, result: ParsedLot):
        """Extrai dados de JSON-LD (schema.org)."""
        scripts = soup.find_all('script', type='application/ld+json')
        for script in scripts:
            try:
                if script.string:
                    data = json.loads(script.string)
                    result.json_ld_data = data

                    # Tenta extrair informações úteis
                    if isinstance(data, dict):
                        if 'name' in data:
                            result.descricao_veiculo = result.descricao_veiculo or data['name']
                        if 'description' in data:
                            result.og_description = result.og_description or data['description']
                        if 'image' in data:
                            imgs = data['image']
                            if isinstance(imgs, list):
                                result.imagens.extend(imgs)
                            elif isinstance(imgs, str):
                                result.imagens.append(imgs)

            except json.JSONDecodeError:
                result.warnings.append("JSON-LD inválido encontrado")

    def _search_values_in_html(self, soup: BeautifulSoup, result: ParsedLot):
        """Busca valores monetários no HTML."""
        text = soup.get_text()

        # Busca valores de avaliação/lance
        money_matches = self.MONEY_PATTERN.findall(text)
        if money_matches:
            try:
                # Converte primeiro valor encontrado
                value_str = money_matches[0].replace('.', '').replace(',', '.')
                result.valor_avaliacao = float(value_str)
            except ValueError:
                pass

    def _search_images(self, soup: BeautifulSoup, result: ParsedLot):
        """Busca imagens do lote."""
        # Busca imagens com padrões comuns
        for img in soup.find_all('img'):
            src = img.get('src') or img.get('data-src')
            if src and not any(kw in src.lower() for kw in ['logo', 'icon', 'avatar']):
                if src.startswith('http'):
                    result.imagens.append(src)
                elif src.startswith('/'):
                    result.imagens.append(f"{self.config.BASE_URL}{src}")

        # Remove duplicatas mantendo ordem
        seen = set()
        unique_imgs = []
        for img in result.imagens:
            if img not in seen:
                seen.add(img)
                unique_imgs.append(img)
        result.imagens = unique_imgs[:10]  # Limita a 10 imagens

    def _calculate_confidence(self, result: ParsedLot) -> float:
        """
        Calcula score de confiança da extração.

        Pontuação:
        - Título extraído: +30
        - Cidade/UF extraídos: +30
        - Descrição veículo: +20
        - Valor encontrado: +10
        - Imagens: +10
        """
        score = 0.0

        if result.titulo_completo:
            score += 30

        if result.cidade and result.uf:
            score += 30

        if result.descricao_veiculo:
            score += 20

        if result.valor_avaliacao:
            score += 10

        if result.imagens:
            score += 10

        return min(score, 100.0)


def parse_lot(url: str, html: str) -> ParsedLot:
    """Função de conveniência para parsing."""
    parser = LeilaoParser()
    return parser.parse(url, html)
