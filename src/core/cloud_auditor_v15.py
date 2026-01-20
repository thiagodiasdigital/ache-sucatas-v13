#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
ACHE SUCATAS DaaS - CLOUD AUDITOR V15
=====================================
Extrai dados de editais usando cascata de fontes - 100% CLOUD.
COM FALLBACK PARA API CONSULTA DO PNCP!

V15 (2026-01-19):
- FALLBACK API PNCP: Se PDF não tiver data_leilao, busca na API Consulta!
- CASCATA COMPLETA: PDF → API PNCP → Descrição → Metadados
- MÉTRICAS POR FONTE: Rastreia onde cada dado foi extraído
- COMPATÍVEL: Processa editais de V10, V11, V12
- RATE LIMITING: Delay configurável entre chamadas à API
- BATCH OTIMIZADO: Processamento em lotes com controle de erros

DIFERENÇA CRÍTICA DO V14:
- V14: Só extraía data_leilao do PDF (muitas vezes falhava)
- V15: Se PDF falhar, consulta API PNCP (dataAberturaProposta)

CASCATA DE EXTRAÇÃO para data_leilao:
1. PDF (pdfplumber) → extrair_data_leilao_cascata()
2. API PNCP → dataAberturaProposta (endpoint /consulta/v1/...)
3. Descrição do edital → regex
4. Metadados do Storage → data_inicio_propostas

FLUXO:
1. Query editais no PostgreSQL (pendentes de processamento)
2. Para cada edital:
   a. Download PDF do Storage → extrai texto
   b. Tenta extrair data_leilao do PDF
   c. Se falhar: busca na API Consulta do PNCP
   d. Extrai outros campos (valor, leiloeiro, etc.)
3. UPDATE no PostgreSQL com dados extraídos

Data: 2026-01-19
Autor: Claude Code (CRAUDIO)
"""

from __future__ import annotations

import hashlib
import json
import logging
import os
import re
import time
from dataclasses import dataclass, field
from datetime import datetime
from io import BytesIO
from pathlib import Path
from typing import Dict, List, Optional, Sequence, Tuple
import requests

import pandas as pd
import pdfplumber
from dotenv import load_dotenv

load_dotenv()

# Logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s | %(levelname)-8s | [%(name)s] %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
log = logging.getLogger("CloudAuditor_V15")


# ==============================================================================
# CONFIGURATION
# ==============================================================================

class Settings:
    """Cloud Auditor V15 configuration."""

    ENABLE_SUPABASE = os.getenv("ENABLE_SUPABASE", "true").lower() == "true"
    ENABLE_SUPABASE_STORAGE = os.getenv("ENABLE_SUPABASE_STORAGE", "true").lower() == "true"

    VERSAO_AUDITOR = "V15_API_FALLBACK"

    # Batch size for processing
    BATCH_SIZE = int(os.getenv("AUDITOR_BATCH_SIZE", "50"))

    # V15: API PNCP Fallback Configuration
    ENABLE_API_FALLBACK = os.getenv("ENABLE_API_FALLBACK", "true").lower() == "true"
    API_CONSULTA_DELAY_MS = int(os.getenv("API_CONSULTA_DELAY_MS", "200"))
    API_CONSULTA_TIMEOUT = int(os.getenv("API_CONSULTA_TIMEOUT", "10"))
    API_CONSULTA_MAX_RETRIES = int(os.getenv("API_CONSULTA_MAX_RETRIES", "2"))

    # User-Agent para API
    USER_AGENT = (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/123.0.0.0 Safari/537.36"
    )

    # Local backup
    ENABLE_LOCAL_BACKUP = os.getenv("ENABLE_LOCAL_BACKUP", "false").lower() == "true"
    CSV_OUTPUT = Path(os.getenv("CSV_OUTPUT", "analise_editais_v15.csv"))


# ==============================================================================
# METRICS TRACKER - V15 ENHANCED
# ==============================================================================

@dataclass
class AuditorMetrics:
    """Métricas detalhadas do Auditor V15."""
    total_processados: int = 0
    sucessos: int = 0
    falhas: int = 0

    # Métricas de data_leilao por fonte
    data_leilao_pdf: int = 0
    data_leilao_api: int = 0
    data_leilao_descricao: int = 0
    data_leilao_nenhuma: int = 0

    # Métricas de API
    api_chamadas: int = 0
    api_sucesso: int = 0
    api_falha: int = 0

    # Métricas de extração
    valor_extraido: int = 0
    quantidade_extraida: int = 0
    leiloeiro_extraido: int = 0
    link_extraido: int = 0
    modalidade_extraida: int = 0

    start_time: datetime = field(default_factory=datetime.now)

    def print_summary(self):
        duration = (datetime.now() - self.start_time).total_seconds()
        log.info("=" * 70)
        log.info("RESUMO - CLOUD AUDITOR V15 (API FALLBACK)")
        log.info("=" * 70)
        log.info(f"Duração: {duration:.1f}s")
        log.info(f"Total processados: {self.total_processados}")
        log.info(f"  |- Sucesso: {self.sucessos}")
        log.info(f"  |- Falha: {self.falhas}")
        log.info("-" * 70)
        log.info("EXTRAÇÃO DE data_leilao (por fonte):")
        log.info(f"  |- PDF: {self.data_leilao_pdf}")
        log.info(f"  |- API PNCP: {self.data_leilao_api}")
        log.info(f"  |- Descrição: {self.data_leilao_descricao}")
        log.info(f"  |- Não encontrada: {self.data_leilao_nenhuma}")
        if self.total_processados > 0:
            taxa = ((self.data_leilao_pdf + self.data_leilao_api + self.data_leilao_descricao) / self.total_processados) * 100
            log.info(f"  |- TAXA SUCESSO: {taxa:.1f}%")
        log.info("-" * 70)
        log.info(f"API PNCP (fallback):")
        log.info(f"  |- Chamadas: {self.api_chamadas}")
        log.info(f"  |- Sucesso: {self.api_sucesso}")
        log.info(f"  |- Falha: {self.api_falha}")
        log.info("-" * 70)
        log.info(f"Outros campos extraídos:")
        log.info(f"  |- valor_estimado: {self.valor_extraido}")
        log.info(f"  |- quantidade_itens: {self.quantidade_extraida}")
        log.info(f"  |- nome_leiloeiro: {self.leiloeiro_extraido}")
        log.info(f"  |- link_leiloeiro: {self.link_extraido}")
        log.info(f"  |- modalidade: {self.modalidade_extraida}")
        log.info("=" * 70)


# ==============================================================================
# CONSTANTS (from V14)
# ==============================================================================

DOMINIOS_INVALIDOS = {
    'hotmail.com', 'hotmail.com.br', 'yahoo.com', 'yahoo.com.br',
    'gmail.com', 'outlook.com', 'uol.com.br', 'bol.com.br',
    'terra.com.br', 'ig.com.br', 'globo.com', 'msn.com',
    'live.com', 'icloud.com'
}

MAPA_TAGS = {
    'sucata': ['sucata', 'sucateamento'],
    'documentado': ['documentado', 'com documento'],
    'sem_documento': ['sem documento', 'indocumentado'],
    'sinistrado': ['sinistrado', 'acidentado'],
    'automovel': ['automóvel', 'automovel', 'carro'],
    'motocicleta': ['motocicleta', 'moto'],
    'caminhao': ['caminhão', 'caminhao'],
    'onibus': ['ônibus', 'onibus'],
    'utilitario': ['utilitário', 'pick-up', 'van'],
    'apreendido': ['apreendido', 'apreensão']
}

KEYWORDS_LEILOEIRO = [
    "leiloeiro", "leilao", "lance", "arrematacao", "superbid",
    "sodresantoro", "zukerman", "joaoemilio", "leiloesfreire",
    "megaleiloes", "sold", "leilomaster", "vipleiloes",
]

MESES_BR = {
    "janeiro": "01", "fevereiro": "02", "março": "03", "marco": "03",
    "abril": "04", "maio": "05", "junho": "06", "julho": "07",
    "agosto": "08", "setembro": "09", "outubro": "10",
    "novembro": "11", "dezembro": "12"
}

# Regex patterns
REGEX_DATA_CONTEXTUAL = re.compile(
    r"(?i)(?:data|abertura|sessao|leilao|pregao|realizacao|"
    r"desfazimento|alienacao|hasta|arrematacao).*?"
    r"(\d{1,2}[/\-]\d{1,2}[/\-]20\d{2})",
    re.DOTALL,
)
REGEX_DATA = re.compile(r"\b(\d{1,2}[/\-]\d{1,2}[/\-]20\d{2})\b")
REGEX_DATA_EXTENSO = re.compile(
    r"(\d{1,2})\s*de\s*(janeiro|fevereiro|março|marco|abril|maio|junho|"
    r"julho|agosto|setembro|outubro|novembro|dezembro)\s*de\s*(20\d{2})",
    re.IGNORECASE
)

SUPPORTED_TLDS = r"(?:\.leilao\.br|\.com\.br|\.com|\.org\.br|\.gov\.br|\.net\.br|\.net)"
REGEX_URL = re.compile(
    rf"(?:https?://)?(?:www\.)?[\w\-\.]+{SUPPORTED_TLDS}"
    r"(?:/[\w\-\./?%&=~#]*)?",
    re.IGNORECASE,
)


# ==============================================================================
# API PNCP CLIENT - V15 NEW
# ==============================================================================

class PncpApiClient:
    """
    Cliente para API Consulta do PNCP - V15.

    Usado como FALLBACK quando a extração do PDF falhar.
    Endpoint: https://pncp.gov.br/api/consulta/v1/orgaos/{cnpj}/compras/{ano}/{seq}
    """

    BASE_URL = "https://pncp.gov.br/api/consulta/v1/orgaos"

    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": Settings.USER_AGENT,
            "Accept": "application/json",
        })

    def extrair_componentes_pncp_id(self, pncp_id: str) -> Optional[Dict[str, str]]:
        """
        Extrai CNPJ, ANO, SEQUENCIAL do pncp_id.

        Formatos aceitos:
        - "12345678901234-1-000123/2025"
        - "12345678901234-1-000123-2025"
        - "12.345.678/0001-34-1-000123/2025"
        """
        if not pncp_id:
            return None

        # Limpar formatação do CNPJ
        pncp_limpo = re.sub(r'[.\-/]', '', pncp_id.replace('/', '-'))

        # Padrão: CNPJ(14)-CODIGO(1)-SEQUENCIAL(6)-ANO(4)
        match = re.search(r'(\d{14})-?(\d+)-?(\d+)-?(\d{4})$', pncp_limpo)
        if match:
            return {
                'cnpj': match.group(1),
                'codigo': match.group(2),
                'sequencial': match.group(3).lstrip('0') or '0',
                'ano': match.group(4),
            }

        # Tentar formato alternativo
        match = re.search(r'(\d{14})\D+(\d+)\D+(\d+)\D+(\d{4})', pncp_id)
        if match:
            return {
                'cnpj': match.group(1),
                'codigo': match.group(2),
                'sequencial': match.group(3).lstrip('0') or '0',
                'ano': match.group(4),
            }

        log.debug(f"Não foi possível extrair componentes de: {pncp_id}")
        return None

    def buscar_detalhes(self, cnpj: str, ano: str, sequencial: str) -> Optional[Dict]:
        """
        Busca detalhes completos do edital na API Consulta.

        Retorna dict com:
        - dataAberturaProposta (data do leilão!)
        - valorTotalEstimado
        - modalidadeNome
        - situacaoNome
        - etc.
        """
        url = f"{self.BASE_URL}/{cnpj}/compras/{ano}/{sequencial}"

        for tentativa in range(Settings.API_CONSULTA_MAX_RETRIES + 1):
            try:
                # Rate limiting
                if Settings.API_CONSULTA_DELAY_MS > 0:
                    time.sleep(Settings.API_CONSULTA_DELAY_MS / 1000)

                response = self.session.get(
                    url,
                    timeout=Settings.API_CONSULTA_TIMEOUT
                )

                if response.status_code == 200:
                    return response.json()
                elif response.status_code == 404:
                    log.debug(f"API 404: {cnpj}/{ano}/{sequencial}")
                    return None
                else:
                    log.warning(f"API status {response.status_code}: {url}")

            except requests.Timeout:
                log.warning(f"Timeout API (tentativa {tentativa + 1}): {url}")
            except requests.RequestException as e:
                log.warning(f"Erro API (tentativa {tentativa + 1}): {e}")

            if tentativa < Settings.API_CONSULTA_MAX_RETRIES:
                time.sleep(1)  # Espera antes de retry

        return None

    def buscar_data_leilao(self, pncp_id: str) -> Optional[datetime]:
        """
        Busca data do leilão (dataAberturaProposta) a partir do pncp_id.

        Returns:
            datetime se encontrado, None caso contrário
        """
        componentes = self.extrair_componentes_pncp_id(pncp_id)
        if not componentes:
            return None

        detalhes = self.buscar_detalhes(
            componentes['cnpj'],
            componentes['ano'],
            componentes['sequencial']
        )

        if not detalhes:
            return None

        data_str = detalhes.get('dataAberturaProposta')
        if not data_str:
            return None

        return self._parse_datetime(data_str)

    def buscar_valor_estimado(self, pncp_id: str) -> Optional[float]:
        """Busca valor estimado a partir do pncp_id."""
        componentes = self.extrair_componentes_pncp_id(pncp_id)
        if not componentes:
            return None

        detalhes = self.buscar_detalhes(
            componentes['cnpj'],
            componentes['ano'],
            componentes['sequencial']
        )

        if not detalhes:
            return None

        valor = detalhes.get('valorTotalEstimado')
        if valor is not None:
            try:
                return float(valor)
            except (ValueError, TypeError):
                pass

        return None

    def _parse_datetime(self, date_str: str) -> Optional[datetime]:
        """Parse datetime string from API."""
        if not date_str:
            return None

        try:
            # Formato ISO 8601: 2026-01-20T10:00:00
            return datetime.fromisoformat(date_str.replace('Z', '+00:00'))
        except ValueError:
            pass

        # Tentar outros formatos
        formats = [
            "%Y-%m-%dT%H:%M:%S",
            "%Y-%m-%d %H:%M:%S",
            "%Y-%m-%d",
        ]
        for fmt in formats:
            try:
                return datetime.strptime(date_str, fmt)
            except ValueError:
                continue

        return None


# ==============================================================================
# EXTRACTION FUNCTIONS (from V14)
# ==============================================================================

def corrigir_encoding(texto: str) -> str:
    if not texto or texto == "N/D":
        return texto
    try:
        return texto.encode("latin-1").decode("utf-8")
    except (UnicodeDecodeError, UnicodeEncodeError):
        return texto


def formatar_data_br(data_raw) -> str:
    if not data_raw or data_raw == "N/D":
        return "N/D"

    data_str = str(data_raw).strip()

    if re.match(r'^\d{2}/\d{2}/\d{4}$', data_str):
        return data_str

    match = re.match(r'^(\d{4})-(\d{2})-(\d{2})', data_str)
    if match:
        ano, mes, dia = match.groups()
        return f"{dia}/{mes}/{ano}"

    match = re.match(r'^(\d{2})[-.](\d{2})[-.](\d{4})$', data_str)
    if match:
        dia, mes, ano = match.groups()
        return f"{dia}/{mes}/{ano}"

    return "N/D"


def formatar_valor_br(valor_raw) -> str:
    """Formata valor para moeda brasileira. Nunca retorna 'nan'."""
    import math

    if not valor_raw:
        return "N/D"

    if isinstance(valor_raw, float) and (math.isnan(valor_raw) or math.isinf(valor_raw)):
        return "N/D"

    try:
        valor_float = float(valor_raw)
        if math.isnan(valor_float) or math.isinf(valor_float):
            return "N/D"
        return f"R$ {valor_float:,.2f}".replace(',', 'X').replace('.', ',').replace('X', '.')
    except (ValueError, TypeError):
        return "N/D"


def normalizar_url(url: str) -> str:
    url = url.strip()
    url = re.sub(r"\s+", "", url)
    url = url.rstrip(".,;:)>")
    url = url.rstrip("\"'")
    if not url:
        return ""
    if not url.lower().startswith(("http://", "https://")):
        url = "https://" + url
    return url


def extrair_urls_de_texto(texto: str) -> List[str]:
    if not texto:
        return []
    urls = REGEX_URL.findall(texto)
    urls_limpas = []
    for raw in urls:
        url = normalizar_url(raw)
        if url and len(url) > 10:
            urls_limpas.append(url)
    return list(dict.fromkeys(urls_limpas))


def encontrar_link_leiloeiro(urls: Sequence[str], texto_completo: str = "") -> Optional[str]:
    urls_unicas = list(dict.fromkeys([u for u in urls if u]))

    for url in urls_unicas:
        url_lower = url.lower()
        if any(keyword in url_lower for keyword in KEYWORDS_LEILOEIRO):
            return url

    for url in urls_unicas:
        url_lower = url.lower()
        if "gov" in url_lower or "pncp" in url_lower:
            continue
        if any(tld in url_lower for tld in [".com.br", ".com", ".net.br", ".net"]):
            return url

    return None


def extrair_tags_inteligente(descricao: str, pdf_text: str, titulo: str) -> str:
    texto_completo = f"{titulo} {descricao} {pdf_text[:3000]}".lower()
    tags_encontradas = set()

    for tag, palavras_chave in MAPA_TAGS.items():
        for palavra in palavras_chave:
            if palavra.lower() in texto_completo:
                tags_encontradas.add(tag)
                break

    if not tags_encontradas:
        if 'veículo' in texto_completo or 'veiculo' in texto_completo:
            tags_encontradas.add('veiculo')
        if 'leilão' in texto_completo or 'leilao' in texto_completo:
            tags_encontradas.add('leilao')

    if not tags_encontradas:
        return "sem_classificacao"

    return ','.join(sorted(tags_encontradas))


def extrair_modalidade(pdf_text: str, descricao: str = "") -> str:
    texto = f"{pdf_text[:2000]} {descricao}".lower()

    keywords_eletronico = [
        'eletrônico', 'eletronico', 'online', 'internet', 'virtual',
        'plataforma digital', 'meio eletrônico', 'forma eletrônica',
        'site', 'portal', 'sistema eletrônico'
    ]

    keywords_presencial = [
        'presencial', 'sede', 'auditório', 'auditorio', 'sala',
        'comparecimento', 'in loco', 'endereço', 'endereco',
        'local do leilão', 'local do leilao'
    ]

    tem_eletronico = any(kw in texto for kw in keywords_eletronico)
    tem_presencial = any(kw in texto for kw in keywords_presencial)

    if tem_eletronico and tem_presencial:
        return "Híbrido"
    elif tem_eletronico:
        return "Eletrônico"
    elif tem_presencial:
        return "Presencial"
    return "N/D"


def extrair_valor_estimado(pdf_text: str) -> str:
    padrao = r'(?:valor|lance|mínimo|avaliação|avaliacao|estimado)[:\s]*R?\$?\s*([\d.,]+)'
    match = re.search(padrao, pdf_text[:3000], re.IGNORECASE)
    if match:
        valor_str = match.group(1).replace('.', '').replace(',', '.')
        return formatar_valor_br(valor_str)
    return "N/D"


def extrair_quantidade_itens(pdf_text: str) -> str:
    if not pdf_text:
        return "N/D"

    texto_busca = pdf_text[:8000]

    padroes_explicitos = [
        r'[Tt]otal\s+de\s+(\d+)\s+(?:lotes?|itens?|veículos?|bens?)',
        r'(\d+)\s*\([a-záéíóúâêîôû\s]+\)\s+(?:lotes?|itens?|veículos?)',
        r'[Cc]omposto\s+por\s+(\d+)\s+(?:lotes?|itens?|veículos?)',
        r'[Cc]ontendo\s+(\d+)\s+(?:lotes?|itens?|veículos?)',
        r'(\d+)\s+(?:lotes?|itens?)\s+disponíveis',
        r'[Dd]ividido\s+em\s+(\d+)\s+(?:lotes?|itens?)',
        r'[Ll]ote\s+\d+\s+(?:ao?|até)\s+(?:[Ll]ote\s+)?(\d+)',
        r'[Ll]otes?\s+\d+\s+a\s+(\d+)',
        r'[Ss]ão\s+(\d+)\s+(?:lotes?|itens?|veículos?)',
        r'[Qq]uantidade[:\s]+(\d+)\s*(?:lotes?|itens?|veículos?)?',
    ]

    for padrao in padroes_explicitos:
        match = re.search(padrao, texto_busca, re.IGNORECASE)
        if match:
            qtd = int(match.group(1))
            if 1 <= qtd <= 9999:
                return str(qtd)

    lotes_pattern = r'\b[Ll][Oo][Tt][Ee]\s*(?:N[ºo°]?\s*)?(\d+)'
    lotes_matches = re.findall(lotes_pattern, texto_busca)
    if lotes_matches:
        max_lote = max(int(n) for n in lotes_matches)
        if max_lote >= 1:
            return str(max_lote)

    itens_pattern = r'\b[Ii][Tt][Ee][Mm]\s*(?:N[ºo°]?\s*)?(\d+)'
    itens_matches = re.findall(itens_pattern, texto_busca)
    if itens_matches:
        max_item = max(int(n) for n in itens_matches)
        if max_item >= 1:
            return str(max_item)

    lotes_count = len(re.findall(r'\b[Ll]ote\b', texto_busca))
    if lotes_count >= 2:
        return str(lotes_count)

    return "N/D"


def extrair_nome_leiloeiro(pdf_text: str) -> str:
    if not pdf_text:
        return "N/D"

    texto_busca = pdf_text[:5000]

    padroes = [
        r'[Ll]eiloeiro(?:a)?(?:\s+[Oo]ficial|\s+[Pp]úblico)?[:\s]+([A-ZÀ-Ú][a-zà-ú]+(?:\s+[A-ZÀ-Ú][a-zà-ú]+){1,5})\s*[-–]\s*[Mm]atrícula',
        r'[Ll]eiloeiro(?:a)?(?:\s+[Oo]ficial|\s+[Pp]úblico)?[:\s]+([A-ZÀ-Ú][a-zà-ú]+(?:\s+[A-ZÀ-Ú][a-zà-ú]+){1,5})\s*,?\s*(?:inscrit[oa]|CPF|matrícula)',
        r'(?:conduzido|realizado|presidido)\s+(?:pelo|pela)\s+(?:leiloeiro|leiloeira)(?:\s+oficial)?\s+([A-ZÀ-Ú][a-zà-ú]+(?:\s+[A-ZÀ-Ú][a-zà-ú]+){1,5})',
        r'[Ll]eiloeiro(?:a)?\s+designad[oa][:\s]+([A-ZÀ-Ú][a-zà-ú]+(?:\s+[A-ZÀ-Ú][a-zà-ú]+){1,5})',
        r'[Ll]eiloeiro(?:a)?(?:\s+[Oo]ficial|\s+[Pp]úblico)?[:\s]+([A-ZÀ-Ú][a-zà-ú]+(?:\s+(?:de\s+|da\s+|do\s+|dos\s+|das\s+)?[A-ZÀ-Ú][a-zà-ú]+){1,5})',
        r'[Ll]eiloeiro(?:a)?[:\s]*([A-ZÀ-Ú][a-zà-ú]+(?:\s+[A-ZÀ-Ú][a-zà-ú]+){1,4})',
    ]

    for padrao in padroes:
        match = re.search(padrao, texto_busca)
        if match:
            nome = match.group(1).strip()
            if len(nome.split()) >= 2 and len(nome) < 80:
                nome = re.sub(r'\s*[-–,].*$', '', nome).strip()
                if len(nome) >= 5:
                    return nome[:100]

    return "N/D"


def extrair_data_leilao_cascata(pdf_text: str, descricao: str = "") -> str:
    """Cascata de extração para data_leilao do PDF."""

    # FONTE 1: DESCRIÇÃO
    if descricao:
        padroes_desc = [
            r'(?:leil[ãa]o.*?dia|dia.*?leil[ãa]o).*?(\d{1,2}[/.-]\d{1,2}[/.-]20\d{2})',
            r'(?:realizar[aá]|ocorrer[aá]).*?(\d{1,2}[/.-]\d{1,2}[/.-]20\d{2})',
            r'(\d{1,2}[/.-]\d{1,2}[/.-]20\d{2}).*?(?:às|as|hora|h)\s*\d{1,2}',
        ]

        for padrao in padroes_desc:
            match = re.search(padrao, descricao[:2000], re.IGNORECASE | re.DOTALL)
            if match:
                data_formatada = formatar_data_br(match.group(1))
                if data_formatada != "N/D":
                    return data_formatada

    # FONTE 2: PDF
    if pdf_text:
        padroes_pdf = [
            r'(?:data\s*(?:do|de)\s*leil[ãa]o)[:\s]*(\d{1,2}[/.-]\d{1,2}[/.-]20\d{2})',
            r'(?:leil[ãa]o|hasta|pregão).*?(?:dia|data)[:\s]*(\d{1,2}[/.-]\d{1,2}[/.-]20\d{2})',
            r'(?:será|ser[aá])\s*realizado.*?(\d{1,2}[/.-]\d{1,2}[/.-]20\d{2})',
            r'(\d{1,2}[/.-]\d{1,2}[/.-]20\d{2})[,\s]*(?:às|as|[àa]s|hora)[:\s]*\d{1,2}',
            r'dia\s*(\d{1,2}[/.-]\d{1,2}[/.-]20\d{2})\s*[àa]s?\s*\d{1,2}',
        ]

        texto_busca = pdf_text[:5000]

        for padrao in padroes_pdf:
            matches = re.finditer(padrao, texto_busca, re.IGNORECASE | re.DOTALL)
            for match in matches:
                data_str = match.group(1)
                data_formatada = formatar_data_br(data_str)
                if data_formatada != "N/D":
                    try:
                        partes = data_formatada.split('/')
                        data_obj = datetime(int(partes[2]), int(partes[1]), int(partes[0]))
                        if data_obj.year >= 2020:
                            return data_formatada
                    except (ValueError, IndexError):
                        return data_formatada

    return "N/D"


# ==============================================================================
# CLOUD PDF EXTRACTION
# ==============================================================================

def extrair_texto_pdf_bytesio(pdf_bytesio: BytesIO) -> str:
    """Extrai texto de PDF em memória (BytesIO)."""
    partes = []
    try:
        with pdfplumber.open(pdf_bytesio) as pdf:
            for page in pdf.pages:
                text = page.extract_text()
                if text:
                    partes.append(text)
    except Exception as e:
        log.warning(f"Erro ao extrair texto do PDF: {e}")
    return " ".join(partes).strip()


# ==============================================================================
# CLOUD AUDITOR V15 CLASS
# ==============================================================================

class CloudAuditor:
    """
    Auditor V15 que processa editais do Supabase Storage.

    NOVIDADE: Fallback para API PNCP quando extração do PDF falhar!
    """

    def __init__(self):
        self.supabase_repo = None
        self.storage_repo = None
        self.api_client = PncpApiClient() if Settings.ENABLE_API_FALLBACK else None
        self.resultados = []
        self.metrics = AuditorMetrics()

        # Initialize Supabase PostgreSQL
        if Settings.ENABLE_SUPABASE:
            try:
                from supabase_repository import SupabaseRepository
                self.supabase_repo = SupabaseRepository(enable_supabase=True)
                if not self.supabase_repo.enable_supabase:
                    log.warning("Supabase DB desabilitado")
                    self.supabase_repo = None
                else:
                    log.info("Supabase PostgreSQL conectado")
            except Exception as e:
                log.error(f"Erro ao inicializar Supabase DB: {e}")

        # Initialize Supabase Storage
        if Settings.ENABLE_SUPABASE_STORAGE:
            try:
                from supabase_storage import SupabaseStorageRepository
                self.storage_repo = SupabaseStorageRepository()
                if not self.storage_repo.enable_storage:
                    log.warning("Supabase Storage desabilitado")
                    self.storage_repo = None
                else:
                    log.info("Supabase Storage conectado")
            except Exception as e:
                log.error(f"Erro ao inicializar Supabase Storage: {e}")

    def listar_editais_pendentes(self, limit: int = None) -> List[dict]:
        """Lista editais que precisam ser processados pelo Auditor V15."""
        if not self.supabase_repo or not self.supabase_repo.enable_supabase:
            return []

        try:
            # V15: Processa editais de V10, V11, V12 e também V14 que não conseguiram data_leilao
            query = (
                self.supabase_repo.client
                .table("editais_leilao")
                .select("*")
                .or_(
                    "versao_auditor.eq.MINER_V10,"
                    "versao_auditor.eq.MINER_V11,"
                    "versao_auditor.eq.V11_CLOUD,"
                    "versao_auditor.eq.V12_DATA_LEILAO_FIX,"
                    "versao_auditor.eq.V14_CLOUD"
                )
                .order("created_at", desc=True)
            )

            if limit:
                query = query.limit(limit)

            response = query.execute()

            log.info(f"Encontrados {len(response.data)} editais para processar")
            return response.data

        except Exception as e:
            log.error(f"Erro ao listar editais pendentes: {e}")
            return []

    def listar_editais_sem_data_leilao(self, limit: int = None) -> List[dict]:
        """Lista editais que NÃO têm data_leilao preenchida (prioridade)."""
        if not self.supabase_repo or not self.supabase_repo.enable_supabase:
            return []

        try:
            query = (
                self.supabase_repo.client
                .table("editais_leilao")
                .select("*")
                .is_("data_leilao", "null")
                .order("created_at", desc=True)
            )

            if limit:
                query = query.limit(limit)

            response = query.execute()

            log.info(f"Encontrados {len(response.data)} editais SEM data_leilao")
            return response.data

        except Exception as e:
            log.error(f"Erro ao listar editais sem data_leilao: {e}")
            return []

    def listar_todos_editais(self, limit: int = None) -> List[dict]:
        """Lista todos os editais no banco."""
        if not self.supabase_repo or not self.supabase_repo.enable_supabase:
            return []

        try:
            query = (
                self.supabase_repo.client
                .table("editais_leilao")
                .select("*")
                .order("created_at", desc=True)
            )

            if limit:
                query = query.limit(limit)

            response = query.execute()
            log.info(f"Encontrados {len(response.data)} editais no banco")
            return response.data

        except Exception as e:
            log.error(f"Erro ao listar editais: {e}")
            return []

    def processar_edital(self, edital: dict) -> Optional[dict]:
        """
        Processa um edital com CASCATA COMPLETA de fontes.

        Cascata para data_leilao:
        1. PDF (pdfplumber)
        2. API PNCP (dataAberturaProposta) - V15 NEW!
        3. Descrição/metadados
        """
        pncp_id = edital.get("pncp_id")
        storage_path = edital.get("storage_path")

        log.info(f"Processando: {pncp_id}")

        # Download do PDF
        pdf_text = ""
        pdf_path = None

        if self.storage_repo:
            if storage_path:
                arquivos = self.storage_repo.listar_pdfs_por_storage_path(storage_path)
                if arquivos:
                    pdf_path = arquivos[0].get("path")

            if not pdf_path and pncp_id:
                arquivos = self.storage_repo.listar_pdfs(pncp_id)
                if arquivos:
                    pdf_path = arquivos[0].get("path")

            if pdf_path:
                try:
                    pdf_bytesio = self.storage_repo.download_pdf(pdf_path)
                    if pdf_bytesio:
                        pdf_text = extrair_texto_pdf_bytesio(pdf_bytesio)
                        log.debug(f"PDF extraído: {len(pdf_text)} chars")
                except Exception as e:
                    log.warning(f"Erro ao baixar PDF {pdf_path}: {e}")

        # Metadados
        metadados = {}
        if self.storage_repo:
            if storage_path:
                metadados = self.storage_repo.download_json(f"{storage_path}/metadados.json") or {}
            if not metadados and pncp_id:
                metadados = self.storage_repo.download_metadados(pncp_id) or {}

        descricao = edital.get("descricao", "") or metadados.get("descricao", "")
        titulo = edital.get("titulo", "") or metadados.get("titulo", "")

        dados_extraidos = {
            "id_interno": edital.get("id_interno"),
            "pncp_id": pncp_id,
        }

        # ====================================================================
        # CASCATA DE EXTRAÇÃO PARA data_leilao - V15 ENHANCED
        # ====================================================================
        data_leilao_atual = edital.get("data_leilao")
        data_leilao_fonte = None

        if not data_leilao_atual:
            # FONTE 1: PDF
            if pdf_text:
                data_leilao_str = extrair_data_leilao_cascata(pdf_text, descricao)
                if data_leilao_str != "N/D":
                    dados_extraidos["data_leilao"] = data_leilao_str
                    data_leilao_fonte = "PDF"
                    self.metrics.data_leilao_pdf += 1
                    log.debug(f"  data_leilao (PDF): {data_leilao_str}")

            # FONTE 2: API PNCP (FALLBACK) - V15 NEW!
            if not data_leilao_fonte and self.api_client and Settings.ENABLE_API_FALLBACK:
                self.metrics.api_chamadas += 1
                try:
                    data_leilao_dt = self.api_client.buscar_data_leilao(pncp_id)
                    if data_leilao_dt:
                        # Converter para string ISO
                        dados_extraidos["data_leilao"] = data_leilao_dt.isoformat()
                        data_leilao_fonte = "API"
                        self.metrics.data_leilao_api += 1
                        self.metrics.api_sucesso += 1
                        log.debug(f"  data_leilao (API): {data_leilao_dt}")
                    else:
                        self.metrics.api_falha += 1
                except Exception as e:
                    log.warning(f"  Erro API PNCP: {e}")
                    self.metrics.api_falha += 1

            # FONTE 3: Descrição (última tentativa)
            if not data_leilao_fonte and descricao:
                data_leilao_str = extrair_data_leilao_cascata("", descricao)
                if data_leilao_str != "N/D":
                    dados_extraidos["data_leilao"] = data_leilao_str
                    data_leilao_fonte = "DESCRICAO"
                    self.metrics.data_leilao_descricao += 1

            if not data_leilao_fonte:
                self.metrics.data_leilao_nenhuma += 1

        # ====================================================================
        # EXTRAIR OUTROS CAMPOS DO PDF
        # ====================================================================
        if pdf_text:
            # Valor estimado
            valor_atual = edital.get("valor_estimado")
            if not valor_atual:
                valor = extrair_valor_estimado(pdf_text)
                if valor != "N/D":
                    try:
                        valor_num = float(valor.replace("R$ ", "").replace(".", "").replace(",", "."))
                        dados_extraidos["valor_estimado"] = valor_num
                        self.metrics.valor_extraido += 1
                    except ValueError:
                        pass

            # Quantidade de itens
            qtd_atual = edital.get("quantidade_itens")
            if not qtd_atual:
                qtd = extrair_quantidade_itens(pdf_text)
                if qtd != "N/D":
                    dados_extraidos["quantidade_itens"] = int(qtd)
                    self.metrics.quantidade_extraida += 1

            # Nome do leiloeiro
            leiloeiro_atual = edital.get("nome_leiloeiro")
            if not leiloeiro_atual:
                nome = extrair_nome_leiloeiro(pdf_text)
                if nome != "N/D":
                    dados_extraidos["nome_leiloeiro"] = nome
                    self.metrics.leiloeiro_extraido += 1

            # Link do leiloeiro
            link_atual = edital.get("link_leiloeiro")
            if not link_atual:
                urls = extrair_urls_de_texto(pdf_text)
                link = encontrar_link_leiloeiro(urls, pdf_text)
                if link:
                    dados_extraidos["link_leiloeiro"] = link
                    self.metrics.link_extraido += 1

            # Modalidade
            modalidade_atual = edital.get("modalidade_leilao")
            if not modalidade_atual or modalidade_atual == "N/D":
                modalidade = extrair_modalidade(pdf_text, descricao)
                if modalidade != "N/D":
                    dados_extraidos["modalidade_leilao"] = modalidade
                    self.metrics.modalidade_extraida += 1

            # Tags
            tags_atuais = edital.get("tags", [])
            if not tags_atuais or tags_atuais in [["miner_v10"], ["miner_v11"], ["miner_v12"]]:
                tags = extrair_tags_inteligente(descricao, pdf_text, titulo)
                if tags != "sem_classificacao":
                    dados_extraidos["tags"] = tags.split(",")

        # Marcar como processado pelo V15
        dados_extraidos["versao_auditor"] = Settings.VERSAO_AUDITOR
        dados_extraidos["updated_at"] = datetime.now().isoformat()

        return dados_extraidos

    def atualizar_edital(self, dados_extraidos: dict) -> bool:
        """Atualiza edital no Supabase com dados extraídos."""
        if not self.supabase_repo or not self.supabase_repo.enable_supabase:
            return False

        pncp_id = dados_extraidos.get("pncp_id")
        if not pncp_id:
            return False

        try:
            update_data = {k: v for k, v in dados_extraidos.items() if k not in ["id_interno", "pncp_id"]}
            update_data["processado_auditor"] = True

            (
                self.supabase_repo.client
                .table("editais_leilao")
                .update(update_data)
                .eq("pncp_id", pncp_id)
                .execute()
            )

            log.info(f"Edital {pncp_id} atualizado com sucesso")
            return True

        except Exception as e:
            log.error(f"Erro ao atualizar edital {pncp_id}: {e}")
            return False

    def run(
        self,
        limit: int = None,
        reprocess_all: bool = False,
        only_missing_data: bool = False
    ):
        """
        Executa o processamento de editais.

        Args:
            limit: Limitar número de editais
            reprocess_all: Reprocessar todos os editais
            only_missing_data: Processar apenas editais sem data_leilao
        """
        log.info("=" * 70)
        log.info("ACHE SUCATAS - CLOUD AUDITOR V15 (API FALLBACK)")
        log.info("=" * 70)
        log.info(f"Storage: {'ATIVO' if self.storage_repo else 'DESATIVADO'}")
        log.info(f"DB: {'ATIVO' if self.supabase_repo else 'DESATIVADO'}")
        log.info(f"API Fallback: {'ATIVO' if self.api_client else 'DESATIVADO'}")
        log.info("=" * 70)

        # Listar editais conforme modo
        if only_missing_data:
            log.info("Modo: Apenas editais SEM data_leilao")
            editais = self.listar_editais_sem_data_leilao(limit=limit)
        elif reprocess_all:
            log.info("Modo: Reprocessar TODOS")
            editais = self.listar_todos_editais(limit=limit)
        else:
            log.info("Modo: Editais pendentes")
            editais = self.listar_editais_pendentes(limit=limit)

        if not editais:
            log.info("Nenhum edital para processar")
            return

        log.info(f"Processando {len(editais)} editais...")

        for i, edital in enumerate(editais, 1):
            self.metrics.total_processados += 1

            try:
                dados_extraidos = self.processar_edital(edital)
                if dados_extraidos:
                    sucesso = self.atualizar_edital(dados_extraidos)
                    if sucesso:
                        self.metrics.sucessos += 1
                        self.resultados.append(dados_extraidos)
                    else:
                        self.metrics.falhas += 1
                else:
                    self.metrics.falhas += 1

                if i % 10 == 0 or i == len(editais):
                    log.info(
                        f"  [{i}/{len(editais)}] OK: {self.metrics.sucessos} | "
                        f"data_leilao: PDF={self.metrics.data_leilao_pdf}, "
                        f"API={self.metrics.data_leilao_api}"
                    )

            except Exception as e:
                log.error(f"Erro ao processar edital: {e}")
                self.metrics.falhas += 1

        # Resumo
        self.metrics.print_summary()

        # Salvar backup CSV se habilitado
        if Settings.ENABLE_LOCAL_BACKUP and self.resultados:
            self._salvar_backup_csv()

    def _salvar_backup_csv(self):
        """Salva backup CSV dos resultados."""
        try:
            df = pd.DataFrame(self.resultados)
            df.to_csv(Settings.CSV_OUTPUT, index=False, encoding="utf-8-sig")
            log.info(f"Backup CSV salvo: {Settings.CSV_OUTPUT}")
        except Exception as e:
            log.error(f"Erro ao salvar CSV: {e}")


# ==============================================================================
# ENTRY POINT
# ==============================================================================

def main():
    import argparse

    parser = argparse.ArgumentParser(description="ACHE SUCATAS - Cloud Auditor V15 (API Fallback)")
    parser.add_argument("--limit", type=int, help="Limitar número de editais")
    parser.add_argument("--reprocess-all", action="store_true", help="Reprocessar todos os editais")
    parser.add_argument("--only-missing-data", action="store_true", help="Processar apenas editais sem data_leilao")
    parser.add_argument("--test-mode", action="store_true", help="Modo de teste (limite 5)")

    args = parser.parse_args()

    limit = args.limit
    if args.test_mode:
        limit = 5

    auditor = CloudAuditor()
    auditor.run(
        limit=limit,
        reprocess_all=args.reprocess_all,
        only_missing_data=args.only_missing_data
    )


if __name__ == "__main__":
    main()
