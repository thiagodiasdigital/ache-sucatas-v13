"""
Ache Sucatas DaaS - Minerador V14
=================================
Busca editais no PNCP com enriquecimento via API de Detalhes.

Versao: 14.1 (patch V19)
Data: 2026-01-21
Changelog:
    - V14.1: Integração com validação de URL V19 (gate de link_leiloeiro)
    - V14.1: Novos campos: link_leiloeiro_raw, link_leiloeiro_valido, etc.
    - V14.1: Bloqueio de falsos positivos (TLD colado em palavra)
    - V14: Adiciona chamada a API de Detalhes para cada edital
    - V14: Extrai itens e anexos completos via endpoints dedicados
    - V14: Rate limiting configuravel
    - V14: Retry policy com backoff exponencial
    - V14: Download de todos os tipos de anexos (PDF, XLSX, CSV, DOC, etc)

Baseado em: V13 (DATA_QUALITY) + Auditor V19 (URL GATE)
Autor: Claude Code
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

load_dotenv()


# ============================================================
# VALIDAÇÃO DE URL V19 (integrado do patch)
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
    """Extrai domínio de uma URL."""
    try:
        from urllib.parse import urlparse
        url_normalizada = url if url.startswith("http") else "https://" + url
        parsed = urlparse(url_normalizada)
        return parsed.netloc.lower().replace("www.", "")
    except Exception:
        return None


def _esta_na_whitelist_miner(url: str) -> bool:
    """Verifica se o domínio da URL está na whitelist."""
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
    Processa links da API PNCP aplicando validação V19.
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
# CONFIGURACAO
# ============================================================

@dataclass
class MinerConfig:
    """Configuracoes do minerador V14."""

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
    dias_retroativos: int = 1  # 24 horas (compativel com V13)
    paginas_por_termo: int = 3
    itens_por_pagina: int = 20

    # Timeouts e retries
    timeout_seconds: int = 45
    max_retries: int = 3
    retry_backoff_base: float = 2.0

    # Filtros
    modalidades: str = "1|13"  # 1=Leilao, 13=Leilao Eletronico
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
logger = logging.getLogger("MinerV14")


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

    Exemplo: "51174001000193-1-000352-2025" ou "51174001000193-1-000352/2025"
    Retorna: {
        "cnpj": "51174001000193",
        "esfera": "1",
        "sequencial": "000352",
        "ano": "2025"
    }
    """
    # Normalizar: substituir / por - para padronizar formato
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

    # Remove timezone Z se presente
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
                # Verificar se e xlsx/docx (ZIP com estrutura especifica)
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

            # Rate limit (429)
            if response.status_code == 429:
                if retry_count < self.config.max_retries:
                    wait_time = 60  # Espera 60s em caso de rate limit
                    self.logger.warning(f"Rate limit atingido. Aguardando {wait_time}s...")
                    time.sleep(wait_time)
                    return self._retry_request(method, url, params, retry_count + 1)
                raise RateLimitError("Rate limit excedido apos retries")

            # Erro de servidor (5xx)
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
        """
        Busca editais de leilao no periodo.
        Endpoint: /search/
        """
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
        """
        Obtem detalhes completos de um edital.
        Endpoint: /pncp/v1/orgaos/{cnpj}/compras/{ano}/{sequencial}
        """
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
        """
        Obtem itens do edital.
        Endpoint: /pncp/v1/orgaos/{cnpj}/compras/{ano}/{sequencial}/itens
        """
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
            # Pode retornar lista direta ou objeto com campo "itens"
            if isinstance(data, list):
                return data
            return data.get("itens", [])

        return []

    def obter_arquivos(self, pncp_id: str) -> List[dict]:
        """
        Lista arquivos/anexos do edital.
        Endpoint: /pncp/v1/orgaos/{cnpj}/compras/{ano}/{sequencial}/arquivos
        """
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
            # Mapear campos para a tabela editais_leilao
            # Colunas validadas contra o schema do Supabase
            # Nota: Removidos campos inexistentes: objeto, orgao_cnpj, pdf_url, versao_miner
            pncp_id = edital.get("pncp_id")

            # Determinar tags baseado no conteudo
            texto_busca = f"{edital.get('titulo', '')} {edital.get('descricao', '')}".lower()
            if "sucata" in texto_busca:
                tags = ["SUCATA"]
            elif "documentado" in texto_busca or "documento" in texto_busca:
                tags = ["DOCUMENTADO"]
            else:
                tags = ["SEM CLASSIFICACAO"]

            dados = {
                "pncp_id": pncp_id,
                "id_interno": pncp_id,  # Campo obrigatorio - usar pncp_id como identificador
                "n_edital": edital.get("n_edital"),  # Campo obrigatorio
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
                "tags": tags,  # Campo obrigatorio
                "updated_at": datetime.now().isoformat(),
            }

            # Remover campos None
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
                "versao_miner": "V14_ENRIQUECIDO",
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

            # Construir URL publica
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
# MINERADOR PRINCIPAL
# ============================================================

class MinerV14:
    """Minerador de editais do PNCP - Versao 14 com Enriquecimento."""

    def __init__(self, config: MinerConfig):
        self.config = config
        self.pncp = PNCPClient(config)
        self.repo = SupabaseRepository(config) if config.enable_supabase else None
        self.storage = StorageRepository(config) if config.enable_storage else None
        self.logger = logging.getLogger("MinerV14")

        # Deduplicacao em memoria
        self.processed_ids = set()

        # Estatisticas
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
        Enriquece dados do edital com API de Detalhes.

        Args:
            item: Dados basicos da busca

        Returns:
            Edital enriquecido com todos os campos
        """
        pncp_id = self._get_value(item, ["numeroControlePNCP", "numero_controle_pncp", "pncp_id"])

        if not pncp_id:
            return {}

        # Dados basicos da busca
        edital = {
            "pncp_id": pncp_id,
            "titulo": self._get_value(item, ["titulo", "tituloObjeto", "titulo_objeto"]) or "",
            "descricao": self._get_value(item, ["descricao", "descricaoObjeto", "descricao_objeto"]) or "",
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
        }

        # Parse data publicacao (varios nomes possiveis entre APIs)
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

            # Titulo completo
            if detalhes.get("objetoCompra"):
                edital["titulo"] = detalhes["objetoCompra"]

            # Descricao detalhada
            if detalhes.get("descricao"):
                edital["descricao"] = detalhes["descricao"]

            # Modalidade
            if detalhes.get("modalidadeNome"):
                edital["modalidade"] = detalhes["modalidadeNome"]

            # Valor estimado
            valor = detalhes.get("valorTotalEstimado") or detalhes.get("valorGlobal")
            if valor:
                try:
                    edital["valor_estimado"] = float(valor)
                except (ValueError, TypeError):
                    pass

            # Data do leilao (dataAberturaProposta ou dataInicioVigencia)
            data_leilao_str = detalhes.get("dataAberturaProposta") or detalhes.get("dataInicioVigencia")
            if data_leilao_str:
                edital["data_leilao"] = parse_date(data_leilao_str)

            # Orgao completo
            if detalhes.get("orgaoEntidade", {}).get("razaoSocial"):
                edital["orgao_nome"] = detalhes["orgaoEntidade"]["razaoSocial"]

            # Municipio e UF da unidade
            unidade = detalhes.get("unidadeOrgao", {})
            if unidade.get("municipio"):
                edital["municipio"] = unidade["municipio"]
            if unidade.get("uf"):
                edital["uf"] = unidade["uf"]

            # Link do leiloeiro COM VALIDAÇÃO V19
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

            # Numero do edital (obrigatorio na tabela)
            numero_compra = detalhes.get("numeroCompra", "")
            ano_compra = detalhes.get("anoCompra", "")
            if numero_compra and ano_compra:
                edital["n_edital"] = f"{numero_compra}/{ano_compra}"
            elif numero_compra:
                edital["n_edital"] = numero_compra
            else:
                # Fallback: extrair do pncp_id (sequencial/ano)
                parsed = parse_pncp_id(pncp_id)
                if parsed:
                    edital["n_edital"] = f"{parsed.get('sequencial', '0')}/{parsed.get('ano', '0')}"

            # Data publicacao (pegar da API de detalhes se nao veio da busca)
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

        Returns:
            Edital atualizado com URLs do storage
        """
        arquivos = edital.get("arquivos", [])
        if not arquivos:
            return edital

        pdf_url = None
        storage_path = None

        for arquivo in arquivos:
            url = arquivo.get("url")
            if not url:
                continue

            self.logger.debug(f"Baixando: {arquivo.get('titulo', 'arquivo')}")

            data = self.pncp.baixar_arquivo(url)
            if not data:
                self.stats["arquivos_falha"] += 1
                continue

            # Detectar tipo de arquivo
            content_type = arquivo.get("tipo")
            ext = FileTypeDetector.detect_by_content_type(content_type)
            if not ext:
                ext = FileTypeDetector.detect_by_magic_bytes(data)

            if not ext or ext not in self.config.allowed_extensions:
                self.stats["arquivos_falha"] += 1
                continue

            self.stats["arquivos_baixados"] += 1

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

                    # Guardar URL do primeiro PDF
                    if ext == ".pdf" and not pdf_url:
                        pdf_url = storage_url
                        storage_path = path

            # Backup local (opcional)
            if self.config.enable_local_backup:
                self._salvar_local(edital, data, ext)

        edital["pdf_storage_url"] = pdf_url
        edital["storage_path"] = storage_path

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
        """
        Processa um edital completo.

        Returns:
            True se processado com sucesso, False caso contrario
        """
        pncp_id = self._get_value(item, ["numeroControlePNCP", "numero_controle_pncp", "pncp_id"])

        if not pncp_id:
            return False

        self.stats["editais_encontrados"] += 1

        # Deduplicacao
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

            # 4. Baixar arquivos
            edital = self._baixar_arquivos(edital)

            # 5. Upload metadados
            if self.storage and self.storage.enable_storage:
                # Preparar dados para JSON (converter datetime)
                metadados = edital.copy()
                for key in ["data_publicacao", "data_leilao"]:
                    if metadados.get(key) and isinstance(metadados[key], datetime):
                        metadados[key] = metadados[key].isoformat()

                self.storage.upload_json(pncp_id, metadados)

            # 6. Persistir no Supabase
            if self.repo and self.repo.enable_supabase:
                # Converter datetime para string ISO
                edital_db = edital.copy()
                for key in ["data_publicacao", "data_leilao"]:
                    if edital_db.get(key) and isinstance(edital_db[key], datetime):
                        edital_db[key] = edital_db[key].isoformat()

                if self.repo.upsert_edital(edital_db):
                    self.stats["supabase_inserts"] += 1
                    self.logger.info(f"Edital {pncp_id} salvo com sucesso")
                else:
                    self.stats["erros"] += 1

            return True

        except Exception as e:
            self.logger.error(f"Erro ao processar {pncp_id}: {e}")
            self.stats["erros"] += 1
            return False

    def executar(self) -> dict:
        """
        Executa o ciclo completo de mineracao.

        Returns:
            Estatisticas da execucao
        """
        self.stats["inicio"] = datetime.now().isoformat()

        # Definir periodo de busca
        data_final = datetime.now()
        data_inicial = data_final - timedelta(days=self.config.dias_retroativos)

        data_inicial_str = data_inicial.strftime("%Y-%m-%d")
        data_final_str = data_final.strftime("%Y-%m-%d")

        self.logger.info("=" * 70)
        self.logger.info("ACHE SUCATAS MINER V14 - ENRIQUECIMENTO")
        self.logger.info("=" * 70)
        self.logger.info(f"Periodo: {data_inicial_str} a {data_final_str}")
        self.logger.info(f"Termos de busca: {len(self.config.search_terms)}")
        self.logger.info(f"Paginas por termo: {self.config.paginas_por_termo}")
        self.logger.info(f"Score minimo: {self.config.min_score}")
        self.logger.info(f"Supabase: {'ATIVO' if self.repo and self.repo.enable_supabase else 'DESATIVADO'}")
        self.logger.info(f"Storage: {'ATIVO' if self.storage and self.storage.enable_storage else 'DESATIVADO'}")
        self.logger.info("=" * 70)

        # Registrar inicio da execucao
        execucao_id = None
        if self.repo:
            execucao_id = self.repo.iniciar_execucao(self.config)
            if execucao_id:
                self.logger.info(f"Execucao #{execucao_id} iniciada")

        try:
            # Loop por termos de busca
            for i, termo in enumerate(self.config.search_terms, 1):
                if self.stats["arquivos_baixados"] >= self.config.max_downloads_per_session:
                    self.logger.warning(
                        f"Limite de downloads atingido ({self.config.max_downloads_per_session})"
                    )
                    break

                self.logger.info(f"[{i}/{len(self.config.search_terms)}] Buscando: '{termo}'")

                # Loop por paginas
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

                    # Processar cada edital
                    for item in items:
                        self._processar_edital(item)

                    # Delay entre paginas
                    time.sleep(self.config.search_page_delay_seconds)

                # Delay entre termos
                time.sleep(self.config.search_term_delay_seconds)

            # Finalizar
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

        # Imprimir resumo
        self._imprimir_resumo()

        return self.stats

    def _imprimir_resumo(self):
        """Imprime resumo da execucao."""
        self.logger.info("=" * 70)
        self.logger.info("RESUMO DA EXECUCAO - MINER V14")
        self.logger.info("=" * 70)
        self.logger.info(f"Editais encontrados: {self.stats['editais_encontrados']}")
        self.logger.info(f"  |- Novos: {self.stats['editais_novos']}")
        self.logger.info(f"  |- Duplicados: {self.stats['editais_duplicados']}")
        self.logger.info(f"  |- Filtrados (data passada): {self.stats['editais_filtrados_data_passada']}")
        self.logger.info(f"Editais enriquecidos: {self.stats['editais_enriquecidos']}")
        self.logger.info(f"Arquivos baixados: {self.stats['arquivos_baixados']}")
        self.logger.info(f"Storage uploads: {self.stats['storage_uploads']}")
        self.logger.info(f"Supabase inserts: {self.stats['supabase_inserts']}")
        self.logger.info(f"Erros: {self.stats['erros']}")
        self.logger.info("=" * 70)


# ============================================================
# ENTRY POINT
# ============================================================

def main():
    """Ponto de entrada do minerador."""
    parser = argparse.ArgumentParser(
        description="Ache Sucatas Miner V14 - Minerador de editais PNCP com enriquecimento"
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

    # Configurar nivel de log
    if args.debug:
        logging.getLogger().setLevel(logging.DEBUG)

    # Carregar configuracao
    config = MinerConfig(
        supabase_url=os.environ.get("SUPABASE_URL", ""),
        supabase_key=os.environ.get("SUPABASE_SERVICE_KEY", os.environ.get("SUPABASE_KEY", "")),
        dias_retroativos=args.dias,
        paginas_por_termo=args.paginas,
        min_score=args.score_minimo,
        filtrar_data_passada=not args.sem_filtro_data,
        enable_local_backup=args.local_backup,
    )

    # Executar minerador
    miner = MinerV14(config)
    stats = miner.executar()

    logger.info(f"Mineracao finalizada: {stats['editais_novos']} novos, {stats['erros']} erros")


if __name__ == "__main__":
    main()
