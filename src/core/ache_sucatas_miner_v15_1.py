"""
Ache Sucatas DaaS - Minerador V15.1
===================================
Busca editais no PNCP com enriquecimento via API de Detalhes e fallback PDF.

Versao: 15.1
Data: 2026-01-22
Changelog V15.1:
    - CORRECAO 1: tipo_leilao revertido - sem default "Leilao Eletronico"
                  Fonte: PDF (conforme contrato). Se nao tiver, fica vazio.
    - CORRECAO 2: descricao - mapeamento limpo + fallback PDF
    - CORRECAO 3: objeto_resumido - usa texto REAL do PDF
    - CORRECAO 4: tags - vem do banco (edital_db), nao recalcula no builder
    - Fallback PDF: quando API detalhes falhar, campos PDF sao preenchidos do PDF

Baseado em: V15.0
Autor: Claude Code
Contrato: contracts/dataset_contract_v1.md
"""

import os
import re
import sys
import json
import time
import hashlib
import logging
import argparse
import unicodedata
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional, List, Dict, Any
from dataclasses import dataclass, field

import httpx
from dotenv import load_dotenv

# Adicionar path do projeto para importar validador
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from validators.dataset_validator import (
    validate_record,
    ValidationResult,
    RecordStatus,
    QualityReport,
    new_run_id,
    build_rejection_row,
)

load_dotenv()


# ============================================================
# EXTRACAO DE TEXTO DO PDF (V15.1)
# ============================================================

def extrair_texto_pdf(pdf_bytes: bytes) -> str:
    """
    Extrai texto de um PDF usando pypdfium2 (deterministico, sem IA).

    Args:
        pdf_bytes: Conteudo binario do PDF

    Returns:
        Texto extraido do PDF ou string vazia se falhar
    """
    if not pdf_bytes:
        return ""

    try:
        import pypdfium2 as pdfium
        pdf = pdfium.PdfDocument(pdf_bytes)
        texto_paginas = []

        # Limitar a 10 paginas para performance
        max_paginas = min(len(pdf), 10)
        for i in range(max_paginas):
            page = pdf[i]
            textpage = page.get_textpage()
            texto_paginas.append(textpage.get_text_range())

        pdf.close()
        return "\n".join(texto_paginas)

    except ImportError:
        logging.getLogger("MinerV15.1").warning("pypdfium2 nao instalado - extracao de PDF desabilitada")
        return ""
    except Exception as e:
        logging.getLogger("MinerV15.1").debug(f"Erro ao extrair texto do PDF: {e}")
        return ""


def extrair_descricao_pdf(texto_pdf: str) -> str:
    """
    Extrai descricao do texto do PDF (deterministico).

    Busca secoes como: DESCRICAO, DA LICITACAO, DO EDITAL, etc.

    Args:
        texto_pdf: Texto extraido do PDF

    Returns:
        Descricao extraida ou string vazia
    """
    if not texto_pdf or len(texto_pdf) < 50:
        return ""

    padroes = [
        r"(?:DESCRI[ÇC][ÃA]O|DA\s+LICITA[ÇC][ÃA]O|DO\s+EDITAL)[:\s]*(.{50,500}?)(?:\n\n|\d+\.\s|$)",
        r"(?:torna\s+p[úu]blico|comunica)[:\s]*(.{50,500}?)(?:\n\n|\d+\.\s|$)",
    ]

    for padrao in padroes:
        match = re.search(padrao, texto_pdf, re.IGNORECASE | re.DOTALL)
        if match:
            descricao = match.group(1).strip()
            descricao = re.sub(r'\s+', ' ', descricao)
            return descricao[:500]

    # Fallback: primeiros paragrafos do PDF
    linhas = [l.strip() for l in texto_pdf.split('\n') if len(l.strip()) > 30]
    if linhas:
        return re.sub(r'\s+', ' ', ' '.join(linhas[:3]))[:500]

    return ""


def extrair_tipo_leilao_pdf(texto_pdf: str) -> str:
    """
    Extrai tipo/modalidade do leilao do texto do PDF (deterministico).

    Valores possiveis conforme contrato:
    - Presencial
    - Online / Eletronico
    - Hibrido

    Args:
        texto_pdf: Texto extraido do PDF

    Returns:
        Tipo do leilao ou string vazia
    """
    if not texto_pdf:
        return ""

    texto_lower = texto_pdf.lower()

    # Padroes para detectar tipo
    tem_eletronico = any(p in texto_lower for p in [
        "leil[aã]o eletr[oô]nico", "eletr[oô]nico", "online",
        "modo eletronico", "forma eletronica", "virtual"
    ])
    tem_presencial = any(p in texto_lower for p in [
        "leil[aã]o presencial", "presencial", "sede da",
        "local:", "endereco:", "comparecimento"
    ])

    # Usar regex para match mais preciso
    if re.search(r"leil[aã]o\s+eletr[oô]nico", texto_lower):
        tem_eletronico = True
    if re.search(r"leil[aã]o\s+presencial", texto_lower):
        tem_presencial = True

    if tem_eletronico and tem_presencial:
        return "Hibrido"
    elif tem_eletronico:
        return "Eletronico"
    elif tem_presencial:
        return "Presencial"

    return ""


def extrair_leiloeiro_url_pdf(texto_pdf: str) -> Optional[str]:
    """
    Extrai URL do leiloeiro do texto do PDF (deterministico).

    Args:
        texto_pdf: Texto extraido do PDF

    Returns:
        URL do leiloeiro ou None
    """
    if not texto_pdf:
        return None

    # Padroes de URL
    padroes_url = [
        r'https?://[^\s<>"\']+',
        r'www\.[^\s<>"\']+',
    ]

    # Dominios governamentais para excluir
    dominios_gov = [
        "pncp.gov.br", "gov.br", "compras.gov.br",
        "comprasnet.gov.br", "licitacoes-e.com.br"
    ]

    for padrao in padroes_url:
        matches = re.findall(padrao, texto_pdf, re.IGNORECASE)
        for url in matches:
            url_lower = url.lower()
            # Excluir dominios governamentais
            if not any(dom in url_lower for dom in dominios_gov):
                # Normalizar URL
                if url.lower().startswith("www."):
                    url = "https://" + url
                return url

    return None


# ============================================================
# VALIDACAO DE URL V19 (integrado do patch)
# ============================================================

WHITELIST_DOMINIOS_LEILOEIRO = {
    "lfranca.com.br", "bidgo.com.br", "sodresantoro.com.br", "superbid.net",
    "superbid.com.br", "vipleiloes.com.br", "frfranca.com.br", "lancenoleilao.com.br",
    "leilomaster.com.br", "lut.com.br", "zfrancaleiloes.com.br", "amaralleiloes.com.br",
    "bfranca.com.br", "cronos.com.br", "confederacaoleiloes.com.br", "megaleiloes.com.br",
    "leilaoseg.com.br", "cfrancaleiloes.com.br", "estreladaleiloes.com.br", "sold.com.br",
    "mitroleiloes.com.br", "alifrancaleiloes.com.br", "hastavip.com.br",
    "klfrancaleiloes.com.br", "centraldosleiloes.com.br", "dfranca.com.br",
    "rfrancaleiloes.com.br", "sfranca.com.br", "clickleiloes.com.br", "petroleiloes.com.br",
    "pfranca.com.br", "clfranca.com.br", "tfleiloes.com.br", "kfranca.com.br",
    "lanceja.com.br", "portalleiloes.com.br", "wfrancaleiloes.com.br",
    "rafaelfrancaleiloes.com.br", "alfrancaleiloes.com.br", "jfrancaleiloes.com.br",
    "mfranca.com.br", "msfranca.com.br", "stfrancaleiloes.com.br", "ofrancaleiloes.com.br",
    "hmfrancaleiloes.com.br", "abataleiloes.com.br", "webleilao.com.br",
    "gfrancaleiloes.com.br", "lleiloes.com.br", "lanceleiloes.com.br",
    "lopesleiloes.net.br", "lopesleiloes.com.br",
}

REGEX_TLD_COLADO_MINER = re.compile(
    r'[A-Za-z0-9]\.(?:com|net|org)[A-Za-z]',
    re.IGNORECASE
)


def _extrair_dominio_miner(url: str) -> Optional[str]:
    """Extrai dominio de uma URL."""
    try:
        from urllib.parse import urlparse
        url_normalizada = url if url.startswith("http") else "https://" + url
        parsed = urlparse(url_normalizada)
        return parsed.netloc.lower().replace("www.", "")
    except Exception:
        return None


def _esta_na_whitelist_miner(url: str) -> bool:
    """Verifica se o dominio da URL esta na whitelist."""
    dominio = _extrair_dominio_miner(url)
    if not dominio:
        return False
    for dominio_valido in WHITELIST_DOMINIOS_LEILOEIRO:
        if dominio == dominio_valido or dominio.endswith("." + dominio_valido):
            return True
    return False


def validar_url_link_leiloeiro_v19(url: str) -> tuple:
    """
    Valida se uma URL pode ser usada como link_leiloeiro (V19).
    Returns: (valido, confianca, motivo_rejeicao)
    """
    if not url:
        return False, 0, "url_vazia"

    url_limpa = url.strip()
    url_lower = url_limpa.lower()

    if url_lower.startswith(("http://", "https://")):
        return (True, 100, None) if _esta_na_whitelist_miner(url_limpa) else (True, 80, None)

    if url_lower.startswith("www."):
        return (True, 100, None) if _esta_na_whitelist_miner(url_limpa) else (True, 60, None)

    if _esta_na_whitelist_miner(url_limpa):
        return True, 100, None

    if REGEX_TLD_COLADO_MINER.search(url_limpa):
        return False, 0, "tld_colado_em_palavra"

    return False, 0, "sem_prefixo_ou_whitelist"


def processar_link_pncp_v19(link_sistema: Optional[str], link_edital: Optional[str]) -> dict:
    """
    Processa links da API PNCP aplicando validacao V19.
    """
    resultado = {
        "link_leiloeiro": None,
        "link_leiloeiro_raw": None,
        "link_leiloeiro_valido": None,
        "link_leiloeiro_origem_tipo": None,
        "link_leiloeiro_origem_ref": None,
        "link_leiloeiro_confianca": None,
    }

    link_candidato = link_sistema or link_edital
    campo_origem = "linkSistema" if link_sistema else "linkEdital"

    if not link_candidato:
        return resultado

    if "pncp.gov" in link_candidato.lower():
        return resultado

    valido, confianca, motivo = validar_url_link_leiloeiro_v19(link_candidato)

    resultado["link_leiloeiro_raw"] = link_candidato
    resultado["link_leiloeiro_valido"] = valido
    resultado["link_leiloeiro_origem_tipo"] = "pncp_api"
    resultado["link_leiloeiro_origem_ref"] = f"pncp_api:{campo_origem}"
    resultado["link_leiloeiro_confianca"] = confianca

    if valido:
        resultado["link_leiloeiro"] = link_candidato

    return resultado


# ============================================================
# V15: EXTRACAO DE OBJETO_RESUMIDO E GERACAO DE TAGS
# ============================================================

def extrair_objeto_resumido(texto: str, max_chars: int = 500) -> str:
    """
    Extrai objeto_resumido de um texto (titulo, descricao ou PDF).
    Busca secoes como OBJETO, DO OBJETO, OBJETO DA LICITACAO.

    V15.1: Esta funcao deve receber texto REAL do PDF, nao titulo+descricao.

    Args:
        texto: Texto fonte (preferencialmente do PDF)
        max_chars: Tamanho maximo do resumo

    Returns:
        Trecho do objeto ou string vazia
    """
    if not texto or not texto.strip():
        return ""

    texto_limpo = texto.strip()

    # Padroes de secao de objeto (ordem de prioridade)
    padroes_objeto = [
        r"(?:DO\s+)?OBJETO\s*(?:DA\s+LICITA[ÇC][ÃA]O)?[:\s]*(.{10,500}?)(?:\n\n|\d+\.\s|$)",
        r"OBJETO[:\s]+(.{10,500}?)(?:\n\n|\d+\.\s|$)",
    ]

    for padrao in padroes_objeto:
        match = re.search(padrao, texto_limpo, re.IGNORECASE | re.DOTALL)
        if match:
            objeto = match.group(1).strip()
            objeto = re.sub(r'\s+', ' ', objeto)
            return objeto[:max_chars]

    # Fallback: usar o proprio texto truncado se for curto o suficiente
    if len(texto_limpo) <= max_chars:
        return re.sub(r'\s+', ' ', texto_limpo)

    # Fallback: primeira frase ou trecho
    primeira_frase = re.split(r'[.\n]', texto_limpo)[0]
    if len(primeira_frase) >= 20:
        return re.sub(r'\s+', ' ', primeira_frase)[:max_chars]

    return ""


# Dicionario de palavras-chave para tags (V15)
TAGS_KEYWORDS = {
    "VEICULO": ["veiculo", "veiculos", "automovel", "automoveis", "carro", "carros"],
    "SUCATA": ["sucata", "sucatas", "inservivel", "inserviveis", "ferroso", "ferrosos"],
    "MOTO": ["moto", "motos", "motocicleta", "motocicletas", "ciclomotor"],
    "CAMINHAO": ["caminhao", "caminhoes", "caminhonete", "camionete", "truck"],
    "ONIBUS": ["onibus", "microonibus", "micro-onibus"],
    "MAQUINARIO": ["maquina", "maquinas", "equipamento", "equipamentos", "trator", "tratores"],
    "IMOVEL": ["imovel", "imoveis", "terreno", "terrenos", "lote", "lotes", "edificio"],
    "MOBILIARIO": ["moveis", "mobiliario", "cadeira", "mesa", "armario"],
    "ELETRONICO": ["computador", "computadores", "eletronico", "eletronicos", "informatica"],
    "DOCUMENTADO": ["documentado", "documentados", "com documento", "documento ok"],
}


def gerar_tags_v15(titulo: str, descricao: str, objeto: str) -> list:
    """
    Gera tags baseadas em palavras-chave encontradas no conteudo.

    Args:
        titulo: Titulo do edital
        descricao: Descricao do edital
        objeto: Objeto resumido

    Returns:
        Lista de tags encontradas (pode ser vazia)
    """
    # Concatenar todo o texto disponivel
    texto_completo = f"{titulo or ''} {descricao or ''} {objeto or ''}".lower()

    # Normalizar acentos para matching
    texto_normalizado = unicodedata.normalize('NFKD', texto_completo)
    texto_normalizado = texto_normalizado.encode('ASCII', 'ignore').decode('ASCII').lower()

    tags_encontradas = set()

    for tag, keywords in TAGS_KEYWORDS.items():
        for keyword in keywords:
            keyword_norm = unicodedata.normalize('NFKD', keyword)
            keyword_norm = keyword_norm.encode('ASCII', 'ignore').decode('ASCII').lower()

            if keyword_norm in texto_normalizado or keyword in texto_completo:
                tags_encontradas.add(tag)
                break

    return sorted(list(tags_encontradas))


# ============================================================
# CONFIGURACAO
# ============================================================

@dataclass
class MinerConfig:
    """Configuracoes do minerador V15.1."""

    # Supabase
    supabase_url: str = ""
    supabase_key: str = ""

    # PNCP API
    pncp_base_url: str = "https://pncp.gov.br/api"
    pncp_search_url: str = "https://pncp.gov.br/api/search/"
    pncp_consulta_url: str = "https://pncp.gov.br/pncp-api/v1/orgaos"

    # Rate limiting
    rate_limit_seconds: float = 1.0
    search_term_delay_seconds: float = 2.0
    search_page_delay_seconds: float = 0.5

    # Busca
    dias_retroativos: int = 1
    paginas_por_termo: int = 3
    itens_por_pagina: int = 20

    # Timeouts e retries
    timeout_seconds: int = 45
    max_retries: int = 3
    retry_backoff_base: float = 2.0

    # Filtros
    modalidades: str = "1|13"
    min_score: int = 60
    filtrar_data_passada: bool = True

    # Storage
    enable_supabase: bool = True
    enable_storage: bool = True
    storage_bucket: str = "editais-pdfs"
    enable_local_backup: bool = False
    local_backup_dir: str = "ACHE_SUCATAS_DB"

    # Limites
    max_downloads_per_session: int = 200
    run_limit: int = 0

    # User agent
    user_agent: str = (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/123.0.0.0 Safari/537.36"
    )

    # Extensoes permitidas
    allowed_extensions: tuple = (".pdf", ".xlsx", ".xls", ".csv", ".zip", ".docx", ".doc")

    # Termos de busca
    search_terms: List[str] = field(default_factory=lambda: [
        "leilao de veiculos",
        "leilao de sucata",
        "alienacao de bens",
        "bens inserviveis",
        "veiculos apreendidos",
        "frota desativada",
        "alienacao de frota",
        "DETRAN leilao",
        "DER leilao",
        "receita federal leilao",
        "bens antieconômicos",
        "desfazimento de bens",
        "alienacao de veiculos",
        "bens inservíveis veículos",
        "leilao eletronico veiculos",
        "leilao presencial veiculos",
        "pregao eletronico alienacao",
        "veiculos patio",
        "veiculos custodia",
        "veiculos removidos",
        "sucata automotiva",
        "alienacao patrimonio",
        "desfazimento frota",
    ])


# ============================================================
# LOGGING
# ============================================================

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-8s | [%(name)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S"
)
logger = logging.getLogger("MinerV15.1")


# ============================================================
# EXCECOES CUSTOMIZADAS
# ============================================================

class PNCPError(Exception):
    """Erro generico do PNCP."""
    pass


class RateLimitError(PNCPError):
    """Rate limit atingido."""
    pass


class EditalNaoEncontradoError(PNCPError):
    """Edital nao encontrado na API de detalhes."""
    pass


# ============================================================
# UTILS
# ============================================================

def parse_pncp_id(pncp_id: str) -> dict:
    """
    Extrai componentes do pncp_id para montar URLs de detalhe.
    """
    pncp_id_normalizado = pncp_id.replace("/", "-")

    parts = pncp_id_normalizado.split("-")
    if len(parts) >= 4:
        return {
            "cnpj": parts[0],
            "esfera": parts[1],
            "sequencial": parts[2],
            "ano": parts[3]
        }
    return {}


def sanitize_filename(name: str) -> str:
    """Sanitiza string para uso como nome de arquivo."""
    name = unicodedata.normalize('NFKD', name)
    name = name.encode('ascii', 'ignore').decode('ascii')
    name = re.sub(r'[^\w\s-]', '', name)
    name = re.sub(r'[-\s]+', '_', name)
    return name[:100]


def parse_date(date_str: Optional[str]) -> Optional[datetime]:
    """Parse date string to datetime object."""
    if not date_str:
        return None

    date_str = date_str.replace('Z', '+00:00')

    try:
        return datetime.fromisoformat(date_str)
    except ValueError:
        pass

    formats = [
        "%Y-%m-%dT%H:%M:%S",
        "%Y-%m-%d %H:%M:%S",
        "%Y-%m-%d",
        "%d/%m/%Y",
        "%d/%m/%Y %H:%M:%S",
    ]

    for fmt in formats:
        try:
            return datetime.strptime(date_str, fmt)
        except ValueError:
            continue

    return None


# ============================================================
# SCORING ENGINE
# ============================================================

class ScoringEngine:
    """Motor de pontuacao para relevancia de editais."""

    KEYWORDS_POSITIVE = {
        "sucata": 20, "inservível": 18, "inservivel": 18,
        "veículo": 15, "veiculo": 15, "leilão": 15, "leilao": 15,
        "alienação": 12, "alienacao": 12, "bem móvel": 10, "bem movel": 10,
        "apreendido": 10, "pátio": 8, "patio": 8, "removido": 8,
        "detran": 12, "der ": 10, "receita federal": 10,
        "antieconômico": 10, "antieconomico": 10,
        "desfazimento": 10, "custódia": 8, "custodia": 8,
    }

    KEYWORDS_LEILOEIRO = {
        "fernandoleiloeiro": 8, "fernando leiloeiro": 8,
        "lopesleiloes": 8, "lopes leilões": 8,
        "joãoemilio": 8, "joaoemilio": 8,
        "leiloesfreire": 8, "leilões freire": 8,
        "mgrleiloes": 8, "mgr leilões": 8,
        "kcleiloes": 8, "kc leilões": 8,
    }

    KEYWORDS_NEGATIVE = {
        "credenciamento": -50,
        "pregão": -25, "pregao": -25,
        "registro de preço": -20, "registro de preco": -20,
        "ata de registro": -20,
        "habilitação": -15, "habilitacao": -15,
        "qualificação": -15, "qualificacao": -15,
        "chamamento": -12, "manifesta": -12,
        "contratação": -10, "contratacao": -10,
        "fornecimento": -10, "prestação": -10, "prestacao": -10,
    }

    @staticmethod
    def calculate_score(titulo: str, descricao: str, objeto: str = "") -> int:
        """Calcula score de relevancia do edital."""
        texto_completo = f"{titulo} {descricao} {objeto}".lower()
        score = 50

        for kw, points in ScoringEngine.KEYWORDS_POSITIVE.items():
            if kw in texto_completo:
                score += points

        for kw, points in ScoringEngine.KEYWORDS_LEILOEIRO.items():
            if kw in texto_completo:
                score += points

        for kw, points in ScoringEngine.KEYWORDS_NEGATIVE.items():
            if kw in texto_completo:
                score += points

        return min(max(score, 0), 100)


# ============================================================
# FILE TYPE DETECTION
# ============================================================

class FileTypeDetector:
    """Detecta tipo de arquivo por content-type ou magic bytes."""

    CONTENT_TYPE_MAP = {
        "application/pdf": ".pdf",
        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet": ".xlsx",
        "application/vnd.ms-excel": ".xls",
        "text/csv": ".csv",
        "application/zip": ".zip",
        "application/x-zip-compressed": ".zip",
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document": ".docx",
        "application/msword": ".doc",
    }

    MAGIC_BYTES = {
        b'%PDF': '.pdf',
        b'PK\x03\x04': '.zip',
        b'\xd0\xcf\x11\xe0': '.xls',
    }

    @staticmethod
    def detect_by_content_type(content_type: str) -> Optional[str]:
        """Detecta extensao pelo content-type."""
        if not content_type:
            return None
        content_type_lower = content_type.lower().split(';')[0].strip()
        return FileTypeDetector.CONTENT_TYPE_MAP.get(content_type_lower)

    @staticmethod
    def detect_by_magic_bytes(data: bytes) -> Optional[str]:
        """Detecta extensao pelos magic bytes."""
        for magic, ext in FileTypeDetector.MAGIC_BYTES.items():
            if data.startswith(magic):
                if magic == b'PK\x03\x04':
                    if b'xl/' in data[:1000]:
                        return '.xlsx'
                    if b'word/' in data[:1000]:
                        return '.docx'
                return ext
        return None


# ============================================================
# CLIENTE PNCP
# ============================================================

class PNCPClient:
    """Cliente para APIs do PNCP."""

    def __init__(self, config: MinerConfig):
        self.config = config
        self.http = httpx.Client(
            timeout=config.timeout_seconds,
            headers={"User-Agent": config.user_agent}
        )
        self.logger = logging.getLogger(__name__)
        self._last_request_time = 0

    def close(self):
        """Fecha o cliente HTTP."""
        self.http.close()

    def _rate_limit(self):
        """Aguarda para respeitar rate limit."""
        elapsed = time.time() - self._last_request_time
        if elapsed < self.config.rate_limit_seconds:
            time.sleep(self.config.rate_limit_seconds - elapsed)
        self._last_request_time = time.time()

    def _retry_request(
        self,
        method: str,
        url: str,
        params: dict = None,
        retry_count: int = 0
    ) -> Optional[httpx.Response]:
        """Executa request com retry e backoff exponencial."""
        try:
            self._rate_limit()

            if method == "GET":
                response = self.http.get(url, params=params)
            else:
                response = self.http.request(method, url, params=params)

            if response.status_code == 429:
                if retry_count < self.config.max_retries:
                    wait_time = 60
                    self.logger.warning(f"Rate limit atingido. Aguardando {wait_time}s...")
                    time.sleep(wait_time)
                    return self._retry_request(method, url, params, retry_count + 1)
                raise RateLimitError("Rate limit excedido apos retries")

            if response.status_code >= 500:
                if retry_count < self.config.max_retries:
                    wait_time = self.config.retry_backoff_base ** retry_count
                    self.logger.warning(
                        f"Erro {response.status_code}. Retry {retry_count + 1}/{self.config.max_retries} "
                        f"em {wait_time:.1f}s"
                    )
                    time.sleep(wait_time)
                    return self._retry_request(method, url, params, retry_count + 1)

            return response

        except httpx.TimeoutException:
            if retry_count < self.config.max_retries:
                wait_time = self.config.retry_backoff_base ** retry_count
                self.logger.warning(f"Timeout. Retry {retry_count + 1}/{self.config.max_retries}")
                time.sleep(wait_time)
                return self._retry_request(method, url, params, retry_count + 1)
            self.logger.error(f"Timeout apos {self.config.max_retries} retries: {url}")
            return None
        except Exception as e:
            self.logger.error(f"Erro na requisicao: {e}")
            return None

    def buscar_editais(
        self,
        termo: str,
        data_inicial: str,
        data_final: str,
        pagina: int = 1
    ) -> Optional[dict]:
        """Busca editais de leilao no periodo."""
        params = {
            "q": termo,
            "tipos_documento": "edital",
            "ordenacao": "-data",
            "pagina": str(pagina),
            "tam_pagina": str(self.config.itens_por_pagina),
            "modalidades": self.config.modalidades,
            "data_publicacao_inicio": data_inicial,
            "data_publicacao_fim": data_final,
        }

        response = self._retry_request("GET", self.config.pncp_search_url, params)

        if response and response.status_code == 200:
            return response.json()

        return None

    def obter_detalhes(self, pncp_id: str) -> Optional[dict]:
        """Obtem detalhes completos de um edital."""
        parsed = parse_pncp_id(pncp_id)
        if not parsed:
            self.logger.warning(f"pncp_id invalido: {pncp_id}")
            return None

        cnpj = re.sub(r'[^0-9]', '', parsed["cnpj"])
        seq = parsed["sequencial"].lstrip('0') or '0'
        ano = parsed["ano"]

        url = f"{self.config.pncp_consulta_url}/{cnpj}/compras/{ano}/{seq}"

        response = self._retry_request("GET", url)

        if response:
            if response.status_code == 200:
                return response.json()
            elif response.status_code == 404:
                self.logger.debug(f"Edital nao encontrado: {pncp_id}")
                return None

        return None

    def obter_itens(self, pncp_id: str) -> List[dict]:
        """Obtem itens do edital."""
        parsed = parse_pncp_id(pncp_id)
        if not parsed:
            return []

        cnpj = re.sub(r'[^0-9]', '', parsed["cnpj"])
        seq = parsed["sequencial"].lstrip('0') or '0'
        ano = parsed["ano"]

        url = f"{self.config.pncp_consulta_url}/{cnpj}/compras/{ano}/{seq}/itens"

        response = self._retry_request("GET", url)

        if response and response.status_code == 200:
            data = response.json()
            if isinstance(data, list):
                return data
            return data.get("itens", [])

        return []

    def obter_arquivos(self, pncp_id: str) -> List[dict]:
        """Lista arquivos/anexos do edital."""
        parsed = parse_pncp_id(pncp_id)
        if not parsed:
            return []

        cnpj = re.sub(r'[^0-9]', '', parsed["cnpj"])
        seq = parsed["sequencial"].lstrip('0') or '0'
        ano = parsed["ano"]

        url = f"{self.config.pncp_consulta_url}/{cnpj}/compras/{ano}/{seq}/arquivos"

        response = self._retry_request("GET", url)

        if response and response.status_code == 200:
            data = response.json()
            if isinstance(data, list):
                return data
            return data.get("arquivos", [])

        return []

    def baixar_arquivo(self, url: str) -> Optional[bytes]:
        """Baixa arquivo da URL especificada."""
        try:
            self._rate_limit()
            response = self.http.get(url, follow_redirects=True)
            if response.status_code == 200:
                return response.content
        except Exception as e:
            self.logger.warning(f"Erro ao baixar arquivo: {e}")
        return None


# ============================================================
# PERSISTENCIA - SUPABASE
# ============================================================

class SupabaseRepository:
    """Repositorio para persistencia no Supabase."""

    def __init__(self, config: MinerConfig):
        self.config = config
        self.client = None
        self.logger = logging.getLogger(__name__)
        self.enable_supabase = False

        if not config.supabase_url or not config.supabase_key:
            self.logger.warning("Credenciais Supabase nao configuradas")
            return

        try:
            from supabase import create_client
            self.client = create_client(config.supabase_url, config.supabase_key)
            self.enable_supabase = True
            self.logger.info("Supabase conectado")
        except ImportError:
            self.logger.error("Biblioteca supabase nao instalada")
        except Exception as e:
            self.logger.error(f"Erro ao conectar Supabase: {e}")

    def edital_existe(self, pncp_id: str) -> bool:
        """Verifica se edital ja existe no banco."""
        if not self.enable_supabase:
            return False

        try:
            result = self.client.table("editais_leilao").select("pncp_id").eq(
                "pncp_id", pncp_id
            ).execute()
            return len(result.data) > 0
        except Exception as e:
            self.logger.error(f"Erro ao verificar edital: {e}")
            return False

    def upsert_edital(self, edital: dict) -> bool:
        """Insere ou atualiza edital na tabela editais_leilao."""
        if not self.enable_supabase:
            return False

        try:
            pncp_id = edital.get("pncp_id")

            # V15.1: tags vem do edital (ja calculadas), nao recalcular aqui
            tags = edital.get("tags", [])
            if isinstance(tags, str):
                tags = [t.strip() for t in tags.split(",") if t.strip()]

            dados = {
                "pncp_id": pncp_id,
                "id_interno": pncp_id,
                "n_edital": edital.get("n_edital"),
                "titulo": edital.get("titulo"),
                "descricao": edital.get("descricao"),
                "orgao": edital.get("orgao_nome"),
                "uf": edital.get("uf"),
                "cidade": edital.get("municipio"),
                "data_publicacao": edital.get("data_publicacao"),
                "data_leilao": edital.get("data_leilao"),
                "modalidade_leilao": edital.get("modalidade"),
                "valor_estimado": edital.get("valor_estimado"),
                "link_pncp": edital.get("link_pncp"),
                "link_leiloeiro": edital.get("link_leiloeiro"),
                "score": edital.get("score"),
                "storage_path": edital.get("storage_path"),
                "tags": tags,
                "updated_at": datetime.now().isoformat(),
            }

            dados = {k: v for k, v in dados.items() if v is not None}

            result = self.client.table("editais_leilao").upsert(
                dados,
                on_conflict="pncp_id"
            ).execute()

            return len(result.data) > 0

        except Exception as e:
            self.logger.error(f"Erro ao inserir edital: {e}")
            return False

    def iniciar_execucao(self, config: MinerConfig) -> Optional[int]:
        """Registra inicio de execucao do miner."""
        if not self.enable_supabase:
            return None

        try:
            dados = {
                "versao_miner": "V15.1",
                "janela_temporal_horas": config.dias_retroativos * 24,
                "termos_buscados": len(config.search_terms),
                "paginas_por_termo": config.paginas_por_termo,
                "status": "RUNNING",
                "inicio": datetime.now().isoformat(),
            }

            result = self.client.table("miner_execucoes").insert(dados).execute()

            if result.data:
                return result.data[0].get("id")
        except Exception as e:
            self.logger.error(f"Erro ao iniciar execucao: {e}")

        return None

    def finalizar_execucao(
        self,
        execucao_id: int,
        stats: dict,
        status: str = "SUCCESS"
    ):
        """Finaliza registro de execucao."""
        if not self.enable_supabase or not execucao_id:
            return

        try:
            dados = {
                "status": status,
                "fim": datetime.now().isoformat(),
                "editais_encontrados": stats.get("editais_encontrados", 0),
                "editais_novos": stats.get("editais_novos", 0),
                "editais_enriquecidos": stats.get("editais_enriquecidos", 0),
                "arquivos_baixados": stats.get("arquivos_baixados", 0),
                "erros": stats.get("erros", 0),
            }

            self.client.table("miner_execucoes").update(dados).eq(
                "id", execucao_id
            ).execute()

        except Exception as e:
            self.logger.error(f"Erro ao finalizar execucao: {e}")

    def inserir_quarentena(self, rejection_row: dict) -> bool:
        """Insere registro na tabela de quarentena (dataset_rejections)."""
        if not self.enable_supabase:
            return False

        try:
            dados = {
                "run_id": rejection_row.get("run_id"),
                "id_interno": rejection_row.get("id_interno"),
                "status": rejection_row.get("status"),
                "errors": rejection_row.get("errors", []),
                "raw_record": rejection_row.get("raw_record", {}),
                "normalized_record": rejection_row.get("normalized_record", {}),
            }

            result = self.client.table("dataset_rejections").insert(dados).execute()
            return len(result.data) > 0

        except Exception as e:
            self.logger.error(f"Erro ao inserir na quarentena: {e}")
            return False


# ============================================================
# STORAGE - SUPABASE
# ============================================================

class StorageRepository:
    """Repositorio para upload de arquivos no Supabase Storage."""

    def __init__(self, config: MinerConfig):
        self.config = config
        self.client = None
        self.logger = logging.getLogger(__name__)
        self.enable_storage = False

        if not config.supabase_url or not config.supabase_key:
            return

        try:
            from supabase import create_client
            self.client = create_client(config.supabase_url, config.supabase_key)
            self.enable_storage = True
            self.logger.info(f"Storage conectado: bucket={config.storage_bucket}")
        except Exception as e:
            self.logger.error(f"Erro ao conectar Storage: {e}")

    def upload_file(self, path: str, data: bytes, content_type: str) -> Optional[str]:
        """Upload de arquivo para o Storage."""
        if not self.enable_storage:
            return None

        try:
            result = self.client.storage.from_(self.config.storage_bucket).upload(
                path,
                data,
                {"content-type": content_type, "upsert": "true"}
            )

            public_url = self.client.storage.from_(
                self.config.storage_bucket
            ).get_public_url(path)

            return public_url

        except Exception as e:
            self.logger.error(f"Erro ao fazer upload: {e}")
            return None

    def upload_json(self, pncp_id: str, data: dict) -> Optional[str]:
        """Upload de metadados JSON."""
        path = f"{pncp_id}/metadados.json"
        content = json.dumps(data, ensure_ascii=False, indent=2).encode('utf-8')
        return self.upload_file(path, content, "application/json")


# ============================================================
# MINERADOR PRINCIPAL V15.1
# ============================================================

class MinerV15_1:
    """Minerador de editais do PNCP - Versao 15.1 com fallback PDF."""

    def __init__(self, config: MinerConfig):
        self.config = config
        self.pncp = PNCPClient(config)
        self.repo = SupabaseRepository(config) if config.enable_supabase else None
        self.storage = StorageRepository(config) if config.enable_storage else None
        self.logger = logging.getLogger("MinerV15.1")

        self.processed_ids = set()

        self.run_id = new_run_id()
        self.quality_report = QualityReport(run_id=self.run_id)

        self.stats = {
            "inicio": None,
            "fim": None,
            "editais_encontrados": 0,
            "editais_novos": 0,
            "editais_duplicados": 0,
            "editais_enriquecidos": 0,
            "editais_filtrados_data_passada": 0,
            "arquivos_baixados": 0,
            "arquivos_falha": 0,
            "storage_uploads": 0,
            "supabase_inserts": 0,
            "quarentena_inserts": 0,
            "pdf_fallbacks": 0,  # V15.1: contador de fallbacks PDF
            "erros": 0,
        }

    def _get_value(self, item: dict, keys: List[str]) -> Any:
        """Helper para obter valor de multiplas chaves possiveis."""
        for k in keys:
            val = item.get(k)
            if val is not None:
                return val
        return None

    def _enriquecer_edital(self, item: dict) -> dict:
        """
        Enriquece dados do edital com API de Detalhes e fallback PDF.

        V15.1: Se API de detalhes falhar, campos PDF sao preenchidos do PDF.
        """
        pncp_id = self._get_value(item, ["numeroControlePNCP", "numero_controle_pncp", "pncp_id"])

        if not pncp_id:
            return {}

        # Dados basicos da busca
        # V15: Corrigido mapeamento - API PNCP retorna 'title' e 'description'
        edital = {
            "pncp_id": pncp_id,
            "titulo": self._get_value(item, ["title", "titulo", "tituloObjeto", "titulo_objeto"]) or "",
            "descricao": self._get_value(item, ["description", "descricao", "descricaoObjeto", "descricao_objeto"]) or "",
            "objeto": self._get_value(item, ["objeto", "objeto_resumido"]) or "",
            "orgao_nome": self._get_value(item, ["orgaoNome", "orgao_nome"]) or "Orgao Desconhecido",
            "orgao_cnpj": self._get_value(item, ["orgaoCnpj", "orgao_cnpj", "cnpj"]),
            "uf": self._get_value(item, ["unidadeFederativaNome", "uf_nome", "uf"]) or "BR",
            "municipio": self._get_value(item, ["municipioNome", "municipio_nome", "cidade"]) or "Diversos",
            "modalidade": self._get_value(item, ["modalidadeNome", "modalidade_nome"]),
            "situacao": self._get_value(item, ["situacaoNome", "situacao_nome"]),
            "data_publicacao": None,
            "data_leilao": None,
            "valor_estimado": None,
            "link_leiloeiro": None,
            "link_pncp": f"https://pncp.gov.br/app/editais/{pncp_id}",
            "itens": [],
            "arquivos": [],
            # V15.1: campos para controle de fonte
            "texto_pdf": "",
            "api_detalhes_ok": False,
        }

        data_pub_str = self._get_value(item, [
            "dataPublicacaoPncp", "data_publicacao_pncp",
            "data_publicacao", "createdAt"
        ])
        if data_pub_str:
            edital["data_publicacao"] = parse_date(data_pub_str)

        # Obter detalhes completos via API
        self.logger.debug(f"Enriquecendo: {pncp_id}")
        detalhes = self.pncp.obter_detalhes(pncp_id)

        if detalhes:
            self.stats["editais_enriquecidos"] += 1
            edital["api_detalhes_ok"] = True

            # V15: Principio "nao sobrescrever com vazio"
            titulo_detalhes = detalhes.get("objetoCompra") or ""
            if titulo_detalhes and (not edital.get("titulo") or len(titulo_detalhes) > len(edital.get("titulo", ""))):
                edital["titulo"] = titulo_detalhes

            descricao_detalhes = detalhes.get("descricao") or ""
            if descricao_detalhes and (not edital.get("descricao") or len(descricao_detalhes) > len(edital.get("descricao", ""))):
                edital["descricao"] = descricao_detalhes

            objeto_api = detalhes.get("objeto") or detalhes.get("objetoCompra") or ""
            if objeto_api and not edital.get("objeto"):
                edital["objeto"] = objeto_api[:500]

            if detalhes.get("modalidadeNome"):
                edital["modalidade"] = detalhes["modalidadeNome"]

            valor = detalhes.get("valorTotalEstimado") or detalhes.get("valorGlobal")
            if valor:
                try:
                    edital["valor_estimado"] = float(valor)
                except (ValueError, TypeError):
                    pass

            data_leilao_str = detalhes.get("dataAberturaProposta") or detalhes.get("dataInicioVigencia")
            if data_leilao_str:
                edital["data_leilao"] = parse_date(data_leilao_str)

            if detalhes.get("orgaoEntidade", {}).get("razaoSocial"):
                edital["orgao_nome"] = detalhes["orgaoEntidade"]["razaoSocial"]

            unidade = detalhes.get("unidadeOrgao", {})
            if unidade.get("municipio"):
                edital["municipio"] = unidade["municipio"]
            if unidade.get("uf"):
                edital["uf"] = unidade["uf"]

            resultado_link = processar_link_pncp_v19(
                link_sistema=detalhes.get("linkSistema"),
                link_edital=detalhes.get("linkEdital"),
            )
            edital["link_leiloeiro"] = resultado_link["link_leiloeiro"]
            edital["link_leiloeiro_raw"] = resultado_link["link_leiloeiro_raw"]
            edital["link_leiloeiro_valido"] = resultado_link["link_leiloeiro_valido"]
            edital["link_leiloeiro_origem_tipo"] = resultado_link["link_leiloeiro_origem_tipo"]
            edital["link_leiloeiro_origem_ref"] = resultado_link["link_leiloeiro_origem_ref"]
            edital["link_leiloeiro_confianca"] = resultado_link["link_leiloeiro_confianca"]

            numero_compra = detalhes.get("numeroCompra", "")
            ano_compra = detalhes.get("anoCompra", "")
            if numero_compra and ano_compra:
                edital["n_edital"] = f"{numero_compra}/{ano_compra}"
            elif numero_compra:
                edital["n_edital"] = numero_compra
            else:
                parsed = parse_pncp_id(pncp_id)
                if parsed:
                    edital["n_edital"] = f"{parsed.get('sequencial', '0')}/{parsed.get('ano', '0')}"

            if not edital.get("data_publicacao"):
                data_pub_detalhe = detalhes.get("dataPublicacaoPncp") or detalhes.get("dataInclusao")
                if data_pub_detalhe:
                    edital["data_publicacao"] = parse_date(data_pub_detalhe)

        # Obter itens do edital
        itens = self.pncp.obter_itens(pncp_id)
        if itens:
            edital["itens"] = itens
            self.logger.debug(f"  {len(itens)} itens encontrados")

        # Obter lista de arquivos
        arquivos = self.pncp.obter_arquivos(pncp_id)
        if arquivos:
            edital["arquivos"] = arquivos
            self.logger.debug(f"  {len(arquivos)} arquivos encontrados")

        return edital

    def _calcular_score(self, edital: dict) -> int:
        """Calcula score de relevancia do edital."""
        return ScoringEngine.calculate_score(
            edital.get("titulo", ""),
            edital.get("descricao", ""),
            edital.get("objeto", "")
        )

    def _baixar_arquivos(self, edital: dict) -> dict:
        """
        Baixa todos os arquivos do edital e faz upload para Storage.
        V15.1: Extrai texto do PDF para fallback.
        """
        arquivos = edital.get("arquivos", [])
        if not arquivos:
            return edital

        pdf_url = None
        storage_path = None
        texto_pdf = ""

        for arquivo in arquivos:
            url = arquivo.get("url")
            if not url:
                continue

            self.logger.debug(f"Baixando: {arquivo.get('titulo', 'arquivo')}")

            data = self.pncp.baixar_arquivo(url)
            if not data:
                self.stats["arquivos_falha"] += 1
                continue

            content_type = arquivo.get("tipo")
            ext = FileTypeDetector.detect_by_content_type(content_type)
            if not ext:
                ext = FileTypeDetector.detect_by_magic_bytes(data)

            if not ext or ext not in self.config.allowed_extensions:
                self.stats["arquivos_falha"] += 1
                continue

            self.stats["arquivos_baixados"] += 1

            # V15.1: Extrair texto do primeiro PDF encontrado
            if ext == ".pdf" and not texto_pdf:
                texto_pdf = extrair_texto_pdf(data)
                if texto_pdf:
                    self.logger.debug(f"  Texto PDF extraido: {len(texto_pdf)} chars")

            # Upload para Storage
            if self.storage and self.storage.enable_storage:
                file_hash = hashlib.md5(data).hexdigest()[:8]
                filename = f"{file_hash}{ext}"
                path = f"{edital['pncp_id']}/{filename}"

                mime_map = {
                    ".pdf": "application/pdf",
                    ".xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                    ".xls": "application/vnd.ms-excel",
                    ".csv": "text/csv",
                    ".zip": "application/zip",
                    ".docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                    ".doc": "application/msword",
                }

                storage_url = self.storage.upload_file(
                    path,
                    data,
                    mime_map.get(ext, "application/octet-stream")
                )

                if storage_url:
                    self.stats["storage_uploads"] += 1

                    if ext == ".pdf" and not pdf_url:
                        pdf_url = storage_url
                        storage_path = path

            # Backup local (opcional)
            if self.config.enable_local_backup:
                self._salvar_local(edital, data, ext)

        edital["pdf_storage_url"] = pdf_url
        edital["storage_path"] = storage_path
        edital["texto_pdf"] = texto_pdf

        return edital

    def _salvar_local(self, edital: dict, data: bytes, ext: str):
        """Salva arquivo localmente (backup)."""
        try:
            base_dir = Path(self.config.local_backup_dir)
            uf = sanitize_filename(edital.get("uf", "BR"))
            municipio = sanitize_filename(edital.get("municipio", "Diversos"))
            pncp_id = sanitize_filename(edital.get("pncp_id", "unknown"))

            folder = base_dir / uf / f"{uf}_{municipio}" / pncp_id
            folder.mkdir(parents=True, exist_ok=True)

            file_hash = hashlib.md5(data).hexdigest()[:8]
            filepath = folder / f"{file_hash}{ext}"

            with open(filepath, 'wb') as f:
                f.write(data)

        except Exception as e:
            self.logger.warning(f"Erro ao salvar local: {e}")

    def _processar_edital(self, item: dict) -> bool:
        """Processa um edital completo com fallback PDF."""
        pncp_id = self._get_value(item, ["numeroControlePNCP", "numero_controle_pncp", "pncp_id"])

        if not pncp_id:
            return False

        self.stats["editais_encontrados"] += 1

        if pncp_id in self.processed_ids:
            self.stats["editais_duplicados"] += 1
            return False

        self.processed_ids.add(pncp_id)
        self.stats["editais_novos"] += 1

        try:
            # 1. Enriquecer com API de Detalhes
            edital = self._enriquecer_edital(item)

            if not edital:
                return False

            # 2. Calcular score
            score = self._calcular_score(edital)
            edital["score"] = score

            if score < self.config.min_score:
                self.logger.debug(f"Score baixo ({score}): {pncp_id}")
                return False

            # 3. Filtrar data passada
            if self.config.filtrar_data_passada and edital.get("data_leilao"):
                hoje = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
                if edital["data_leilao"] < hoje:
                    self.stats["editais_filtrados_data_passada"] += 1
                    self.logger.debug(f"Data passada: {pncp_id} ({edital['data_leilao'].date()})")
                    return False

            # 4. Baixar arquivos e extrair texto PDF
            edital = self._baixar_arquivos(edital)

            # 5. Upload metadados
            if self.storage and self.storage.enable_storage:
                metadados = edital.copy()
                for key in ["data_publicacao", "data_leilao"]:
                    if metadados.get(key) and isinstance(metadados[key], datetime):
                        metadados[key] = metadados[key].isoformat()
                # Nao enviar texto_pdf nos metadados (muito grande)
                metadados.pop("texto_pdf", None)
                self.storage.upload_json(pncp_id, metadados)

            # 6. VALIDACAO: Preparar registro no formato do contrato
            edital_db = edital.copy()
            for key in ["data_publicacao", "data_leilao"]:
                if edital_db.get(key) and isinstance(edital_db[key], datetime):
                    edital_db[key] = edital_db[key].strftime("%d-%m-%Y")

            # V15.1: Obter texto do PDF para campos que vem do PDF
            texto_pdf = edital_db.get("texto_pdf", "")

            # V15.1 CORRECAO 3: objeto_resumido DEVE usar texto REAL do PDF
            if texto_pdf:
                objeto_v15 = extrair_objeto_resumido(texto_pdf)
            else:
                # Fallback: usar titulo+descricao se nao tiver PDF
                titulo_v15 = edital_db.get("titulo", "")
                descricao_v15 = edital_db.get("descricao", "")
                texto_fonte = f"{titulo_v15} {descricao_v15}"
                objeto_v15 = extrair_objeto_resumido(texto_fonte)

            # V15.1 CORRECAO 2: descricao - preferir PDF conforme contrato
            descricao_final = edital_db.get("descricao", "")
            if texto_pdf and not descricao_final:
                descricao_pdf = extrair_descricao_pdf(texto_pdf)
                if descricao_pdf:
                    descricao_final = descricao_pdf
                    self.stats["pdf_fallbacks"] += 1

            # V15.1 CORRECAO 1: tipo_leilao - vem do PDF, sem default
            tipo_leilao = ""
            if texto_pdf:
                tipo_leilao = extrair_tipo_leilao_pdf(texto_pdf)
            # Se nao conseguiu extrair do PDF e tem modalidade da API, usar ela
            if not tipo_leilao and edital_db.get("modalidade"):
                tipo_leilao = edital_db.get("modalidade", "")

            # V15.1: leiloeiro_url - fallback para PDF
            leiloeiro_url = edital_db.get("link_leiloeiro")
            if not leiloeiro_url and texto_pdf:
                leiloeiro_url = extrair_leiloeiro_url_pdf(texto_pdf)
                if leiloeiro_url:
                    self.stats["pdf_fallbacks"] += 1

            # V15.1 CORRECAO 4: tags - gerar baseado no conteudo
            # Usar texto do PDF se disponivel, senao usar titulo/descricao
            if texto_pdf:
                tags_v15 = gerar_tags_v15("", "", texto_pdf[:2000])
            else:
                titulo_v15 = edital_db.get("titulo", "")
                descricao_v15 = edital_db.get("descricao", "")
                tags_v15 = gerar_tags_v15(titulo_v15, descricao_v15, objeto_v15)

            # Persistir tags no edital_db para uso no builder final
            edital_db["tags"] = tags_v15

            # Montar registro no formato esperado pelo validador
            registro_validacao = {
                "id_interno": edital_db.get("pncp_id"),
                "municipio": edital_db.get("municipio"),
                "uf": edital_db.get("uf"),
                "data_leilao": edital_db.get("data_leilao"),
                "pncp_url": edital_db.get("link_pncp"),
                "data_atualizacao": datetime.now().strftime("%d-%m-%Y"),
                "titulo": edital_db.get("titulo", ""),
                "descricao": descricao_final,
                "orgao": edital_db.get("orgao_nome"),
                "n_edital": edital_db.get("n_edital"),
                "objeto_resumido": objeto_v15,
                # V15.1 CORRECAO 4: tags vem do edital_db, nao recalcula
                "tags": ", ".join(edital_db.get("tags", [])) if isinstance(edital_db.get("tags"), list) else edital_db.get("tags", ""),
                "valor_estimado": edital_db.get("valor_estimado"),
                # V15.1 CORRECAO 1: tipo_leilao sem default "Leilao Eletronico"
                "tipo_leilao": tipo_leilao,
                "leiloeiro_url": leiloeiro_url,
                "data_publicacao": edital_db.get("data_publicacao"),
            }

            # 7. VALIDAR REGISTRO
            validation_result = validate_record(registro_validacao)
            self.quality_report.register(validation_result)

            # 8. ROTEAMENTO
            if self.repo and self.repo.enable_supabase:
                if validation_result.status == RecordStatus.VALID:
                    edital_normalizado = edital_db.copy()
                    edital_normalizado.update({
                        "tags": validation_result.normalized_record.get("tags", edital_db.get("tags")),
                        "link_pncp": validation_result.normalized_record.get("pncp_url", edital_db.get("link_pncp")),
                        "link_leiloeiro": validation_result.normalized_record.get("leiloeiro_url", edital_db.get("link_leiloeiro")),
                    })

                    if self.repo.upsert_edital(edital_normalizado):
                        self.stats["supabase_inserts"] += 1
                        self.logger.info(f"[VALID] Edital {pncp_id} salvo na tabela principal")
                    else:
                        self.stats["erros"] += 1
                else:
                    rejection_row = build_rejection_row(
                        run_id=self.run_id,
                        raw_record=registro_validacao,
                        result=validation_result,
                    )

                    if self.repo.inserir_quarentena(rejection_row):
                        self.stats["quarentena_inserts"] += 1
                        self.logger.info(
                            f"[{validation_result.status.value.upper()}] Edital {pncp_id} "
                            f"enviado para quarentena ({len(validation_result.errors)} erros)"
                        )
                    else:
                        self.stats["erros"] += 1

            return True

        except Exception as e:
            self.logger.error(f"Erro ao processar {pncp_id}: {e}")
            self.stats["erros"] += 1
            return False

    def executar(self) -> dict:
        """Executa o ciclo completo de mineracao."""
        self.stats["inicio"] = datetime.now().isoformat()

        data_final = datetime.now()
        data_inicial = data_final - timedelta(days=self.config.dias_retroativos)

        data_inicial_str = data_inicial.strftime("%Y-%m-%d")
        data_final_str = data_final.strftime("%Y-%m-%d")

        self.logger.info("=" * 70)
        self.logger.info("ACHE SUCATAS MINER V15.1 - CONTRATO OU NADA")
        self.logger.info("=" * 70)
        self.logger.info(f"Periodo: {data_inicial_str} a {data_final_str}")
        self.logger.info(f"Termos de busca: {len(self.config.search_terms)}")
        self.logger.info(f"Paginas por termo: {self.config.paginas_por_termo}")
        self.logger.info(f"Score minimo: {self.config.min_score}")
        self.logger.info(f"Supabase: {'ATIVO' if self.repo and self.repo.enable_supabase else 'DESATIVADO'}")
        self.logger.info(f"Storage: {'ATIVO' if self.storage and self.storage.enable_storage else 'DESATIVADO'}")
        self.logger.info("=" * 70)

        execucao_id = None
        if self.repo:
            execucao_id = self.repo.iniciar_execucao(self.config)
            if execucao_id:
                self.logger.info(f"Execucao #{execucao_id} iniciada")

        try:
            for i, termo in enumerate(self.config.search_terms, 1):
                if self.config.run_limit > 0 and self.stats["editais_encontrados"] >= self.config.run_limit:
                    self.logger.warning(
                        f"RUN_LIMIT atingido ({self.config.run_limit} editais). Encerrando busca."
                    )
                    break

                if self.stats["arquivos_baixados"] >= self.config.max_downloads_per_session:
                    self.logger.warning(
                        f"Limite de downloads atingido ({self.config.max_downloads_per_session})"
                    )
                    break

                self.logger.info(f"[{i}/{len(self.config.search_terms)}] Buscando: '{termo}'")

                for pagina in range(1, self.config.paginas_por_termo + 1):
                    resultado = self.pncp.buscar_editais(
                        termo,
                        data_inicial_str,
                        data_final_str,
                        pagina
                    )

                    if not resultado or not resultado.get("items"):
                        break

                    items = resultado["items"]
                    self.logger.info(f"  Pagina {pagina}: {len(items)} editais")

                    for item in items:
                        if self.config.run_limit > 0 and self.stats["editais_encontrados"] >= self.config.run_limit:
                            self.logger.warning(
                                f"RUN_LIMIT atingido ({self.config.run_limit} editais). Parando processamento."
                            )
                            break
                        self._processar_edital(item)

                    if self.config.run_limit > 0 and self.stats["editais_encontrados"] >= self.config.run_limit:
                        break

                    time.sleep(self.config.search_page_delay_seconds)

                time.sleep(self.config.search_term_delay_seconds)

            self.stats["fim"] = datetime.now().isoformat()

            if self.repo and execucao_id:
                self.repo.finalizar_execucao(execucao_id, self.stats, "SUCCESS")

        except Exception as e:
            self.logger.error(f"Erro na mineracao: {e}")
            self.stats["erros"] += 1
            self.stats["fim"] = datetime.now().isoformat()

            if self.repo and execucao_id:
                self.repo.finalizar_execucao(execucao_id, self.stats, "FAILED")

            raise

        finally:
            self.pncp.close()

        self._imprimir_resumo()
        self._imprimir_relatorio_qualidade()
        self._salvar_relatorio_json()

        return self.stats

    def _imprimir_relatorio_qualidade(self):
        """Imprime resumo do relatorio de qualidade."""
        self.logger.info("=" * 70)
        self.logger.info("RELATORIO DE QUALIDADE - VALIDACAO")
        self.logger.info("=" * 70)
        self.quality_report.print_summary()
        self.logger.info("=" * 70)

    def _salvar_relatorio_json(self):
        """Salva relatorio de qualidade em JSON."""
        try:
            reports_dir = Path(__file__).parent.parent.parent / "reports" / "quality"
            reports_dir.mkdir(parents=True, exist_ok=True)

            filepath = reports_dir / f"{self.run_id}.json"
            with open(filepath, "w", encoding="utf-8") as f:
                f.write(self.quality_report.to_json())

            self.logger.info(f"Relatorio salvo: {filepath}")

        except Exception as e:
            self.logger.error(f"Erro ao salvar relatorio JSON: {e}")

    def _imprimir_resumo(self):
        """Imprime resumo da execucao."""
        self.logger.info("=" * 70)
        self.logger.info("RESUMO DA EXECUCAO - MINER V15.1")
        self.logger.info("=" * 70)
        self.logger.info(f"Run ID: {self.run_id}")
        self.logger.info(f"Editais encontrados: {self.stats['editais_encontrados']}")
        self.logger.info(f"  |- Novos: {self.stats['editais_novos']}")
        self.logger.info(f"  |- Duplicados: {self.stats['editais_duplicados']}")
        self.logger.info(f"  |- Filtrados (data passada): {self.stats['editais_filtrados_data_passada']}")
        self.logger.info(f"Editais enriquecidos: {self.stats['editais_enriquecidos']}")
        self.logger.info(f"Arquivos baixados: {self.stats['arquivos_baixados']}")
        self.logger.info(f"Storage uploads: {self.stats['storage_uploads']}")
        self.logger.info(f"PDF fallbacks: {self.stats['pdf_fallbacks']}")
        self.logger.info("-" * 70)
        self.logger.info("ROTEAMENTO (validacao):")
        self.logger.info(f"  |- Tabela principal (validos): {self.stats['supabase_inserts']}")
        self.logger.info(f"  |- Quarentena (draft/not_sellable/rejected): {self.stats['quarentena_inserts']}")
        self.logger.info(f"Erros: {self.stats['erros']}")
        self.logger.info("=" * 70)


# ============================================================
# ENTRY POINT
# ============================================================

def main():
    """Ponto de entrada do minerador V15.1."""
    parser = argparse.ArgumentParser(
        description="Ache Sucatas Miner V15.1 - Minerador de editais PNCP com fallback PDF"
    )
    parser.add_argument(
        "--dias",
        type=int,
        default=1,
        help="Numero de dias retroativos para busca (default: 1 = 24h)"
    )
    parser.add_argument(
        "--paginas",
        type=int,
        default=3,
        help="Numero de paginas por termo de busca (default: 3)"
    )
    parser.add_argument(
        "--score-minimo",
        type=int,
        default=60,
        help="Score minimo para processar edital (default: 60)"
    )
    parser.add_argument(
        "--sem-filtro-data",
        action="store_true",
        help="Desabilita filtro de data passada"
    )
    parser.add_argument(
        "--local-backup",
        action="store_true",
        help="Habilita backup local dos arquivos"
    )
    parser.add_argument(
        "--debug",
        action="store_true",
        help="Ativa modo debug com logs detalhados"
    )

    args = parser.parse_args()

    if args.debug:
        logging.getLogger().setLevel(logging.DEBUG)

    run_limit = int(os.environ.get("RUN_LIMIT", "0"))
    if run_limit > 0:
        logger.info(f"MODO TESTE: RUN_LIMIT={run_limit} (maximo de editais a processar)")

    config = MinerConfig(
        supabase_url=os.environ.get("SUPABASE_URL", ""),
        supabase_key=os.environ.get("SUPABASE_SERVICE_KEY", os.environ.get("SUPABASE_KEY", "")),
        dias_retroativos=args.dias,
        paginas_por_termo=args.paginas,
        min_score=args.score_minimo,
        filtrar_data_passada=not args.sem_filtro_data,
        enable_local_backup=args.local_backup,
        run_limit=run_limit,
    )

    miner = MinerV15_1(config)
    stats = miner.executar()

    logger.info(f"Mineracao finalizada: {stats['editais_novos']} novos, {stats['erros']} erros")


if __name__ == "__main__":
    main()
