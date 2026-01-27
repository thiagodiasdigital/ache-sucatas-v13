#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Ache Sucatas DaaS - Auditor V19
===============================
Extrai dados estruturados de editais com foco em links de leiloeiro.
Usa estrategias em cascata para maximizar extracao.

Versao: 19
Data: 2026-01-21
Changelog:
    - V19: Gate de validacao de URLs (rejeita TLD colado em palavras)
    - V19: Proveniencia do link (fonte, arquivo, pagina/posicao)
    - V19: Campos de quarentena (link_leiloeiro_raw, link_leiloeiro_valido)
    - V19: Bloqueio de falsos positivos como "ED.COMEMORA"
    - V19: Validacao estrutural obrigatoria (http/https/www/whitelist)
    - V19.2: Idempotencia - rastreia processamento com auditor_v19_processed_at
    - V19.2: Skip de editais ja processados (exceto com --force)

Baseado em: V18 (CASCATA EXTRACAO)
Autor: Claude Code
"""

from __future__ import annotations

import argparse
import hashlib
import json
import logging
import os
import re
import tempfile
import time
from dataclasses import dataclass, field
from datetime import datetime, date
from io import BytesIO
from pathlib import Path
from typing import Dict, List, Optional, Tuple
from urllib.parse import urlparse

import httpx
import pandas as pd
import pdfplumber
from dotenv import load_dotenv

load_dotenv()

# Import do integrador de lotes (V19.1)
try:
    from src.extractors.lotes_integration import LotesIntegration
    LOTES_INTEGRATION_DISPONIVEL = True
except ImportError:
    LOTES_INTEGRATION_DISPONIVEL = False

# V19.2: Import do módulo de resiliência
try:
    from src.core.resilience import (
        retry_with_backoff,
        CircuitBreaker,
        CircuitOpenError,
        circuit_registry,
    )
    RESILIENCE_DISPONIVEL = True
except ImportError:
    RESILIENCE_DISPONIVEL = False


# ============================================================
# LOGGING
# ============================================================

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-8s | [%(name)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S"
)
logger = logging.getLogger("CloudAuditor_V19")


# ============================================================
# CONFIGURACAO
# ============================================================

@dataclass
class AuditorConfig:
    """Configuracoes do auditor V19."""

    supabase_url: str = ""
    supabase_key: str = ""
    storage_bucket: str = "editais-pdfs"
    timeout_seconds: int = 30
    validar_urls: bool = True
    usar_ocr: bool = False

    request_delay_seconds: float = 0.2

    filtrar_data_passada: bool = False  # V19.3: Desativado por padrão (--excluir-data-passada para ativar)
    excluir_data_passada: bool = False

    batch_size: int = 50

    versao_auditor: str = "V19_URL_GATE_PROVENIENCIA"


# ============================================================
# PLATAFORMAS DE LEILAO CONHECIDAS (WHITELIST)
# ============================================================

PLATAFORMAS_LEILAO = {
    "lanceleiloes.com": "www.lanceleiloes.com.br",
    "lanceleiloes.com.br": "www.lanceleiloes.com.br",
    "www.lanceleiloes.com": "www.lanceleiloes.com.br",
    "superbid.net": "www.superbid.net",

    "dominios_validos": [
        "lfranca.com.br",
        "bidgo.com.br",
        "sodresantoro.com.br",
        "superbid.net",
        "superbid.com.br",
        "vipleiloes.com.br",
        "frfranca.com.br",
        "lancenoleilao.com.br",
        "leilomaster.com.br",
        "lut.com.br",
        "zfrancaleiloes.com.br",
        "amaralleiloes.com.br",
        "bfranca.com.br",
        "cronos.com.br",
        "confederacaoleiloes.com.br",
        "megaleiloes.com.br",
        "leilaoseg.com.br",
        "cfrancaleiloes.com.br",
        "estreladaleiloes.com.br",
        "sold.com.br",
        "mitroleiloes.com.br",
        "alifrancaleiloes.com.br",
        "hastavip.com.br",
        "klfrancaleiloes.com.br",
        "centraldosleiloes.com.br",
        "dfranca.com.br",
        "rfrancaleiloes.com.br",
        "sfranca.com.br",
        "clickleiloes.com.br",
        "petroleiloes.com.br",
        "pfranca.com.br",
        "clfranca.com.br",
        "tfleiloes.com.br",
        "kfranca.com.br",
        "lanceja.com.br",
        "portalleiloes.com.br",
        "wfrancaleiloes.com.br",
        "rafaelfrancaleiloes.com.br",
        "alfrancaleiloes.com.br",
        "jfrancaleiloes.com.br",
        "mfranca.com.br",
        "msfranca.com.br",
        "stfrancaleiloes.com.br",
        "ofrancaleiloes.com.br",
        "hmfrancaleiloes.com.br",
        "abataleiloes.com.br",
        "webleilao.com.br",
        "gfrancaleiloes.com.br",
        "lleiloes.com.br",
        "lanceleiloes.com.br",
        "lopesleiloes.net.br",
        "lopesleiloes.com.br",
    ]
}

DOMINIOS_IGNORAR = [
    "pncp.gov.br",
    "gov.br",
    "comprasnet",
    "google.com",
    "facebook.com",
    "instagram.com",
    "youtube.com",
    "twitter.com",
    "linkedin.com",
    "whatsapp.com",
    ".pdf",
    ".doc",
    ".xls",
    ".jpg",
    ".png",
]

DOMINIOS_EMAIL = [
    "hotmail.com", "hotmail.com.br", "yahoo.com", "yahoo.com.br",
    "gmail.com", "outlook.com", "uol.com.br", "bol.com.br",
    "terra.com.br", "ig.com.br", "globo.com", "msn.com",
    "live.com", "icloud.com"
]

DOMINIOS_CORRECAO = {
    "lanceleiloes.com": "www.lanceleiloes.com.br",
    "www.lanceleiloes.com": "www.lanceleiloes.com.br",
    "lanceleiloes.com.br": "www.lanceleiloes.com.br",
    "superbid.net": "www.superbid.net",
}

# TLDs comuns para validacao
TLDS_VALIDOS = {
    "com", "net", "org", "br", "gov", "edu", "io", "co",
    "com.br", "net.br", "org.br", "gov.br", "edu.br",
}


def corrigir_dominio(url: str) -> str:
    """Corrige dominios conhecidos com problemas."""
    if not url:
        return url

    try:
        parsed = urlparse(url)
        dominio = parsed.netloc.lower()
        dominio_sem_www = dominio.replace("www.", "")

        for errado, correto in DOMINIOS_CORRECAO.items():
            errado_sem_www = errado.replace("www.", "")
            if dominio_sem_www == errado_sem_www:
                return url.replace(parsed.netloc, correto)

    except Exception:
        pass

    return url


# ============================================================
# PROVENIENCIA DO LINK
# ============================================================

@dataclass
class LinkProveniencia:
    """Estrutura de proveniencia do link extraido."""

    candidato_raw: str
    url_validada: Optional[str]
    valido: bool
    origem_tipo: str  # pncp_api | pdf_anexo | pdf_edital | xlsx_anexo | csv_anexo | titulo_descricao | unknown
    origem_ref: str  # ex: "pdf:Relacao_Lotes.pdf:page=143"
    evidencia_trecho: str  # trecho do texto que gerou o match (max 200 chars)
    confianca: int  # 100=whitelist, 80=http(s), 60=www, 0=rejeitado
    motivo_rejeicao: Optional[str] = None

    def to_dict(self) -> dict:
        """Converte para dicionario para persistencia."""
        return {
            "link_leiloeiro_raw": self.candidato_raw,
            "link_leiloeiro": self.url_validada,
            "link_leiloeiro_valido": self.valido,
            "link_leiloeiro_origem_tipo": self.origem_tipo,
            "link_leiloeiro_origem_ref": self.origem_ref,
            "link_leiloeiro_evidencia_trecho": self.evidencia_trecho[:200] if self.evidencia_trecho else None,
            "link_leiloeiro_confianca": self.confianca,
        }


# ============================================================
# VALIDADOR DE URLs V19 (COM GATE)
# ============================================================

class URLValidatorV19:
    """
    Validador de URLs com gate estrutural obrigatorio.

    Gate: Uma URL so e promovida para link_leiloeiro se satisfizer ao menos UM:
    1. Comeca com http:// ou https://
    2. Comeca com www.
    3. Pertence a whitelist de dominios conhecidos

    Bloqueio: Rejeita TLD colado em palavras (ex: ED.COMEMORA)
    """

    # Regex para detectar TLD colado em palavra (falso positivo)
    # Exemplo: "ED.COMEMORA" - TLD .COM colado com "EMORA" sem separador
    REGEX_TLD_COLADO = re.compile(
        r'[A-Za-z0-9]\.(?:com|net|org|br|gov|edu|io|co)[A-Za-z]',
        re.IGNORECASE
    )

    # Regex para URL com prefixo valido
    REGEX_URL_COM_PREFIXO = re.compile(
        r'^https?://[^\s<>"{}|\\^`\[\]]+',
        re.IGNORECASE
    )

    # Regex para URL com www
    REGEX_URL_WWW = re.compile(
        r'^www\.[^\s<>"{}|\\^`\[\]]+',
        re.IGNORECASE
    )

    def __init__(self, timeout: int = 10):
        self.timeout = timeout
        self.logger = logging.getLogger(__name__)
        self.cache: Dict[str, bool] = {}
        self.whitelist = set(PLATAFORMAS_LEILAO["dominios_validos"])

    def _tem_tld_colado(self, texto: str) -> bool:
        """
        Verifica se o texto contem TLD colado em palavra.

        Exemplos de falsos positivos:
        - "ED.COMEMORA" -> True (.COM colado com EMORA)
        - "ABC.NETAMENTE" -> True (.NET colado com AMENTE)

        Exemplos validos:
        - "www.exemplo.com" -> False
        - "https://site.com.br" -> False
        """
        return bool(self.REGEX_TLD_COLADO.search(texto))

    def _extrair_dominio(self, url: str) -> Optional[str]:
        """Extrai dominio de uma URL."""
        try:
            url_normalizada = url
            if not url_normalizada.startswith("http"):
                url_normalizada = "https://" + url_normalizada

            parsed = urlparse(url_normalizada)
            dominio = parsed.netloc.lower()
            return dominio.replace("www.", "")
        except Exception:
            return None

    def _esta_na_whitelist(self, url: str) -> bool:
        """Verifica se o dominio da URL esta na whitelist."""
        dominio = self._extrair_dominio(url)
        if not dominio:
            return False

        for dominio_valido in self.whitelist:
            if dominio == dominio_valido or dominio.endswith("." + dominio_valido):
                return True

        return False

    def validar_estrutural(self, candidato: str) -> Tuple[bool, int, Optional[str]]:
        """
        Aplica gate de validacao estrutural.

        Args:
            candidato: String candidata a URL

        Returns:
            Tupla (valido, confianca, motivo_rejeicao)
            - valido: True se passou no gate
            - confianca: 100=whitelist, 80=http(s), 60=www, 0=rejeitado
            - motivo_rejeicao: Motivo se rejeitado, None caso contrario
        """
        if not candidato:
            return False, 0, "candidato_vazio"

        candidato_limpo = candidato.strip()
        candidato_lower = candidato_limpo.lower()

        # Gate 1: Prefixo http(s) - URLs estruturadas sao validas
        # (nao verificamos TLD colado aqui pois ja tem estrutura de URL)
        if candidato_lower.startswith(("http://", "https://")):
            if self._esta_na_whitelist(candidato_limpo):
                return True, 100, None
            return True, 80, None

        # Gate 2: Prefixo www - URLs estruturadas sao validas
        if candidato_lower.startswith("www."):
            if self._esta_na_whitelist(candidato_limpo):
                return True, 100, None
            return True, 60, None

        # Gate 3: Whitelist de dominios conhecidos (sem prefixo)
        if self._esta_na_whitelist(candidato_limpo):
            return True, 100, None

        # Para candidatos SEM prefixo estruturado e FORA da whitelist:
        # Verificar se e TLD colado em palavra (falso positivo)
        if self._tem_tld_colado(candidato_limpo):
            return False, 0, "tld_colado_em_palavra"

        # Candidato nao passou em nenhum gate
        return False, 0, "sem_prefixo_ou_whitelist"

    def normalizar(self, url: str) -> Optional[str]:
        """
        Normaliza URL para formato padrao.
        So adiciona https:// se a URL passou no gate.
        """
        if not url:
            return None

        url = url.strip()
        url = re.sub(r'\s+', '', url)
        url = url.rstrip(".,;:)>\"'")

        # So adicionar https:// se comeca com www (ja passou no gate)
        if url.startswith("www."):
            url = "https://" + url
        elif not url.startswith("http"):
            # Nao inventar esquema para dominios soltos
            # Se chegou aqui e nao tem http, deve ser whitelist
            url = "https://" + url

        url = corrigir_dominio(url)
        url = url.rstrip("/")

        return url

    def validar_acessibilidade(self, url: str, max_retries: int = 2) -> bool:
        """
        Verifica se URL esta acessivel (opcional).

        V19.2 RESILIENCIA: Inclui retry com backoff para erros de timeout/conexao.

        Args:
            url: URL a validar
            max_retries: Numero maximo de tentativas (default: 2)

        Returns:
            True se URL esta acessivel
        """
        if not url:
            return False

        if url in self.cache:
            return self.cache[url]

        url_check = url
        if not url_check.startswith("http"):
            url_check = "https://" + url_check

        last_error = None
        for attempt in range(max_retries):
            try:
                with httpx.Client(timeout=self.timeout, follow_redirects=True) as client:
                    response = client.head(url_check)
                    valido = response.status_code < 400
                    self.cache[url] = valido
                    return valido

            except (httpx.TimeoutException, httpx.ConnectError, httpx.ConnectTimeout) as e:
                # Erros de rede/timeout devem causar retry
                last_error = e
                if attempt < max_retries - 1:
                    delay = (1.5 ** attempt) * (0.5 + __import__('random').random() * 0.5)
                    self.logger.debug(
                        f"[RETRY] validar_acessibilidade {url} tentativa {attempt + 1}/{max_retries} "
                        f"timeout/conexao. Retry em {delay:.1f}s"
                    )
                    time.sleep(delay)

            except Exception as e:
                # Outros erros nao causam retry
                self.logger.debug(f"URL inacessivel {url}: {e}")
                self.cache[url] = False
                return False

        # Todas as tentativas falharam
        self.logger.debug(f"URL inacessivel {url} apos {max_retries} tentativas: {last_error}")
        self.cache[url] = False
        return False


# ============================================================
# METRICAS
# ============================================================

@dataclass
class AuditorMetrics:
    """Metricas detalhadas do Auditor V19."""

    total_processados: int = 0
    sucessos: int = 0
    falhas: int = 0

    url_extraida_pdf: int = 0
    url_extraida_excel: int = 0
    url_extraida_csv: int = 0
    url_extraida_descricao: int = 0
    url_nao_encontrada: int = 0

    urls_validadas: int = 0
    urls_invalidas: int = 0
    urls_corrigidas: int = 0

    # V19: Metricas de gate
    urls_rejeitadas_tld_colado: int = 0
    urls_rejeitadas_sem_prefixo: int = 0
    urls_aceitas_whitelist: int = 0
    urls_aceitas_http: int = 0
    urls_aceitas_www: int = 0

    data_leilao_encontrada: int = 0
    data_leilao_nao_encontrada: int = 0

    editais_data_passada: int = 0
    editais_excluidos: int = 0

    pdfs_processados: int = 0
    excels_processados: int = 0
    csvs_processados: int = 0

    # V19.1: Metricas de lotes
    lotes_extraidos: int = 0
    lotes_quarentena: int = 0
    pdfs_com_lotes: int = 0

    erros: int = 0
    start_time: datetime = field(default_factory=datetime.now)

    def print_summary(self):
        """Imprime resumo das metricas."""
        duration = (datetime.now() - self.start_time).total_seconds()
        logger.info("=" * 70)
        logger.info("RESUMO - CLOUD AUDITOR V19 (URL GATE + PROVENIENCIA)")
        logger.info("=" * 70)
        logger.info(f"Duracao: {duration:.1f}s")
        logger.info(f"Total processados: {self.total_processados}")
        logger.info(f"  |- Sucesso: {self.sucessos}")
        logger.info(f"  |- Falha: {self.falhas}")
        logger.info("-" * 70)
        logger.info("EXTRACAO DE URLs (por fonte):")
        logger.info(f"  |- PDF: {self.url_extraida_pdf}")
        logger.info(f"  |- Excel: {self.url_extraida_excel}")
        logger.info(f"  |- CSV: {self.url_extraida_csv}")
        logger.info(f"  |- Descricao: {self.url_extraida_descricao}")
        logger.info(f"  |- Nao encontrada: {self.url_nao_encontrada}")
        logger.info("-" * 70)
        logger.info("GATE DE VALIDACAO V19:")
        logger.info(f"  |- Aceitas (whitelist): {self.urls_aceitas_whitelist}")
        logger.info(f"  |- Aceitas (http/https): {self.urls_aceitas_http}")
        logger.info(f"  |- Aceitas (www): {self.urls_aceitas_www}")
        logger.info(f"  |- Rejeitadas (TLD colado): {self.urls_rejeitadas_tld_colado}")
        logger.info(f"  |- Rejeitadas (sem prefixo): {self.urls_rejeitadas_sem_prefixo}")
        logger.info("-" * 70)
        logger.info("VALIDACAO DE URLs:")
        logger.info(f"  |- Validadas: {self.urls_validadas}")
        logger.info(f"  |- Invalidas: {self.urls_invalidas}")
        logger.info(f"  |- Corrigidas: {self.urls_corrigidas}")
        logger.info("-" * 70)
        logger.info("ARQUIVOS PROCESSADOS:")
        logger.info(f"  |- PDFs: {self.pdfs_processados}")
        logger.info(f"  |- Excels: {self.excels_processados}")
        logger.info(f"  |- CSVs: {self.csvs_processados}")
        logger.info("-" * 70)
        logger.info("EXTRACAO DE LOTES (V19.1):")
        logger.info(f"  |- Lotes extraidos: {self.lotes_extraidos}")
        logger.info(f"  |- PDFs com lotes: {self.pdfs_com_lotes}")
        logger.info(f"  |- Quarentena: {self.lotes_quarentena}")
        logger.info("=" * 70)


# ============================================================
# EXTRATOR DE PDF V19
# ============================================================

class PDFExtractorV19:
    """Extrator de dados de PDFs com validacao de URLs V19."""

    def __init__(self, url_validator: URLValidatorV19):
        self.logger = logging.getLogger(__name__)
        self.url_validator = url_validator

        # Regex para URLs genericas (com prefixo http/https)
        self.regex_url_http = re.compile(
            r'https?://[^\s<>"{}|\\^`\[\]]+',
            re.IGNORECASE
        )

        # Regex para URLs com www (sem http)
        self.regex_url_www = re.compile(
            r'(?<![a-zA-Z0-9])www\.[a-zA-Z0-9][^\s<>"{}|\\^`\[\]]*',
            re.IGNORECASE
        )

        # Regex para plataformas conhecidas (whitelist)
        dominios_pattern = "|".join([
            re.escape(d) for d in PLATAFORMAS_LEILAO["dominios_validos"]
        ])
        self.regex_plataformas = re.compile(
            rf'(?:https?://)?(?:www\.)?({dominios_pattern})(?:/[^\s<>"]*)?',
            re.IGNORECASE
        )

        # Regex alternativo para padroes de leilao
        self.regex_padrao_leilao = re.compile(
            r'(?:https?://|www\.)?('
            r'[a-z]+leiloes\.com\.br|'
            r'[a-z]+leil[oõ]es\.com\.br|'
            r'[a-z]franca(?:leiloes)?\.com\.br|'
            r'bidgo\.com\.br|'
            r'superbid\.(?:net|com\.br)|'
            r'sold\.com\.br|'
            r'megaleiloes\.com\.br|'
            r'lanceja\.com\.br|'
            r'hastavip\.com\.br|'
            r'lopesleiloes\.(?:net\.br|com\.br)'
            r')(?:/[^\s<>"]*)?',
            re.IGNORECASE
        )

        self.keywords_contexto = [
            "leilao on-line", "leilão on-line", "leilao online", "leilão online",
            "plataforma eletronica", "plataforma eletrônica",
            "endereco eletronico", "endereço eletrônico",
            "site do leilao", "site do leilão",
            "portal do leilao", "portal do leilão",
            "acesso ao leilao", "acesso ao leilão",
            "local do leilao", "local do leilão",
            "sera realizado", "será realizado",
            "disponivel em", "disponível em",
            "realizado atraves", "realizado através",
            "pelo site", "no site", "acesse", "acessar",
        ]

    def extrair_texto_com_paginas(self, pdf_bytesio: BytesIO) -> List[Tuple[str, int]]:
        """
        Extrai texto do PDF com numero da pagina.

        Returns:
            Lista de tuplas (texto, numero_pagina)
        """
        paginas = []
        try:
            with pdfplumber.open(pdf_bytesio) as pdf:
                for i, page in enumerate(pdf.pages, 1):
                    page_text = page.extract_text()
                    if page_text:
                        paginas.append((page_text, i))
        except Exception as e:
            self.logger.warning(f"Erro ao extrair texto do PDF: {e}")

        return paginas

    def extrair_urls_com_proveniencia(
        self,
        texto: str,
        arquivo_nome: str,
        pagina: Optional[int] = None,
        origem_tipo: str = "pdf_anexo"
    ) -> List[LinkProveniencia]:
        """
        Extrai URLs do texto com informacoes de proveniencia.

        Returns:
            Lista de LinkProveniencia ordenada por confianca
        """
        resultados: List[LinkProveniencia] = []
        urls_vistas = set()

        def criar_origem_ref(pag: Optional[int]) -> str:
            if pag:
                return f"pdf:{arquivo_nome}:page={pag}"
            return f"pdf:{arquivo_nome}"

        def extrair_trecho(texto: str, match_start: int, match_end: int) -> str:
            """Extrai trecho de contexto ao redor do match."""
            inicio = max(0, match_start - 30)
            fim = min(len(texto), match_end + 30)
            trecho = texto[inicio:fim]
            return trecho.replace("\n", " ").strip()[:200]

        # Estrategia 1: Plataformas conhecidas (whitelist) - MAIOR confianca
        for match in self.regex_plataformas.finditer(texto):
            dominio = match.group(1).lower()
            url_candidata = f"https://www.{dominio}"

            if url_candidata in urls_vistas:
                continue
            urls_vistas.add(url_candidata)

            valido, confianca, motivo = self.url_validator.validar_estrutural(url_candidata)
            trecho = extrair_trecho(texto, match.start(), match.end())

            resultados.append(LinkProveniencia(
                candidato_raw=match.group(0),
                url_validada=url_candidata if valido else None,
                valido=valido,
                origem_tipo=origem_tipo,
                origem_ref=criar_origem_ref(pagina),
                evidencia_trecho=trecho,
                confianca=confianca,
                motivo_rejeicao=motivo,
            ))

        # Estrategia 2: Padroes de leilao
        for match in self.regex_padrao_leilao.finditer(texto):
            dominio = match.group(1).lower()
            url_candidata = f"https://www.{dominio}"

            if url_candidata in urls_vistas:
                continue
            urls_vistas.add(url_candidata)

            valido, confianca, motivo = self.url_validator.validar_estrutural(url_candidata)
            trecho = extrair_trecho(texto, match.start(), match.end())

            resultados.append(LinkProveniencia(
                candidato_raw=match.group(0),
                url_validada=url_candidata if valido else None,
                valido=valido,
                origem_tipo=origem_tipo,
                origem_ref=criar_origem_ref(pagina),
                evidencia_trecho=trecho,
                confianca=confianca,
                motivo_rejeicao=motivo,
            ))

        # Estrategia 3: URLs com http/https (ja tem prefixo)
        for match in self.regex_url_http.finditer(texto):
            url_candidata = match.group(0)

            if url_candidata in urls_vistas:
                continue
            urls_vistas.add(url_candidata)

            # Verificar se nao eh dominio ignorado
            if not self._url_relevante(url_candidata):
                continue

            valido, confianca, motivo = self.url_validator.validar_estrutural(url_candidata)
            trecho = extrair_trecho(texto, match.start(), match.end())

            resultados.append(LinkProveniencia(
                candidato_raw=url_candidata,
                url_validada=url_candidata if valido else None,
                valido=valido,
                origem_tipo=origem_tipo,
                origem_ref=criar_origem_ref(pagina),
                evidencia_trecho=trecho,
                confianca=confianca,
                motivo_rejeicao=motivo,
            ))

        # Estrategia 4: URLs com www (sem http)
        for match in self.regex_url_www.finditer(texto):
            url_candidata = match.group(0)

            if url_candidata in urls_vistas:
                continue
            urls_vistas.add(url_candidata)

            if not self._url_relevante(url_candidata):
                continue

            valido, confianca, motivo = self.url_validator.validar_estrutural(url_candidata)
            trecho = extrair_trecho(texto, match.start(), match.end())

            if valido:
                url_normalizada = self.url_validator.normalizar(url_candidata)
            else:
                url_normalizada = None

            resultados.append(LinkProveniencia(
                candidato_raw=url_candidata,
                url_validada=url_normalizada,
                valido=valido,
                origem_tipo=origem_tipo,
                origem_ref=criar_origem_ref(pagina),
                evidencia_trecho=trecho,
                confianca=confianca,
                motivo_rejeicao=motivo,
            ))

        # Ordenar por confianca (maior primeiro)
        resultados.sort(key=lambda x: x.confianca, reverse=True)

        return resultados

    def _url_relevante(self, url: str) -> bool:
        """Verifica se URL e potencialmente de leiloeiro."""
        url_lower = url.lower()

        for dominio in DOMINIOS_IGNORAR:
            if dominio in url_lower:
                return False

        for dominio in DOMINIOS_EMAIL:
            if dominio in url_lower:
                return False

        indicadores_positivos = [
            "leilao", "leilão", "leiloes", "leilões",
            "franca", "bid", "lance", "sold", "hasta",
            "arremate", "arrematacao",
        ]

        for indicador in indicadores_positivos:
            if indicador in url_lower:
                return True

        if ".com.br" in url_lower or ".net.br" in url_lower:
            return True

        return False

    def extrair_link_leiloeiro_com_proveniencia(
        self,
        pdf_bytesio: BytesIO,
        arquivo_nome: str
    ) -> Optional[LinkProveniencia]:
        """
        Extrai o link do leiloeiro mais provavel do PDF com proveniencia.

        Returns:
            LinkProveniencia do melhor link encontrado ou None
        """
        paginas = self.extrair_texto_com_paginas(pdf_bytesio)

        if not paginas:
            self.logger.warning("PDF sem texto extraivel")
            return None

        todos_resultados: List[LinkProveniencia] = []

        for texto, num_pagina in paginas:
            resultados = self.extrair_urls_com_proveniencia(
                texto=texto,
                arquivo_nome=arquivo_nome,
                pagina=num_pagina,
                origem_tipo="pdf_anexo",
            )
            todos_resultados.extend(resultados)

        # Filtrar apenas resultados validos e ordenar por confianca
        validos = [r for r in todos_resultados if r.valido]

        if validos:
            validos.sort(key=lambda x: x.confianca, reverse=True)
            self.logger.debug(f"Encontrados {len(validos)} links validos no PDF")
            return validos[0]

        # Se nao encontrou validos, retornar o primeiro rejeitado para registro
        if todos_resultados:
            self.logger.debug(f"Nenhum link valido; {len(todos_resultados)} rejeitados")
            return todos_resultados[0]

        return None


# ============================================================
# EXTRATOR DE EXCEL/CSV V19
# ============================================================

class ExcelExtractorV19:
    """Extrator de dados de arquivos Excel/CSV com proveniencia."""

    def __init__(self, url_validator: URLValidatorV19):
        self.logger = logging.getLogger(__name__)
        self.url_validator = url_validator
        self.regex_url = re.compile(
            r'https?://[^\s<>"{}|\\^`\[\]]+',
            re.IGNORECASE
        )
        self.regex_www = re.compile(
            r'(?<![a-zA-Z0-9])www\.[a-zA-Z0-9][^\s<>"{}|\\^`\[\]]*',
            re.IGNORECASE
        )

    def extrair_urls_excel_bytesio(
        self,
        excel_bytesio: BytesIO,
        arquivo_nome: str
    ) -> List[LinkProveniencia]:
        """Extrai URLs de arquivo Excel em memoria com proveniencia."""
        resultados = []

        try:
            df = pd.read_excel(excel_bytesio)
            resultados = self._extrair_urls_dataframe(df, arquivo_nome, "xlsx_anexo")
        except Exception as e:
            self.logger.warning(f"Erro lendo Excel: {e}")

        return resultados

    def extrair_urls_csv_bytesio(
        self,
        csv_bytesio: BytesIO,
        arquivo_nome: str
    ) -> List[LinkProveniencia]:
        """Extrai URLs de arquivo CSV em memoria com proveniencia."""
        resultados = []
        encodings = ["utf-8", "latin-1", "cp1252"]

        for encoding in encodings:
            try:
                csv_bytesio.seek(0)
                df = pd.read_csv(csv_bytesio, encoding=encoding, on_bad_lines="skip")
                resultados = self._extrair_urls_dataframe(df, arquivo_nome, "csv_anexo")
                break
            except Exception:
                continue

        return resultados

    def _extrair_urls_dataframe(
        self,
        df: pd.DataFrame,
        arquivo_nome: str,
        origem_tipo: str
    ) -> List[LinkProveniencia]:
        """Extrai URLs de um DataFrame com proveniencia."""
        resultados = []
        urls_vistas = set()

        colunas_interesse = [
            "link", "url", "site", "endereco", "endereço",
            "portal", "plataforma", "leilao", "leilão"
        ]

        for row_idx, row in df.iterrows():
            for col_idx, col in enumerate(df.columns):
                valor = row[col]
                if pd.isna(valor):
                    continue

                valor_str = str(valor)

                # Buscar URLs com http
                for match in self.regex_url.finditer(valor_str):
                    url_candidata = match.group(0)

                    if url_candidata in urls_vistas:
                        continue
                    urls_vistas.add(url_candidata)

                    valido, confianca, motivo = self.url_validator.validar_estrutural(url_candidata)

                    resultados.append(LinkProveniencia(
                        candidato_raw=url_candidata,
                        url_validada=url_candidata if valido else None,
                        valido=valido,
                        origem_tipo=origem_tipo,
                        origem_ref=f"{origem_tipo}:{arquivo_nome}:row={row_idx+1}:col={col}",
                        evidencia_trecho=valor_str[:200],
                        confianca=confianca,
                        motivo_rejeicao=motivo,
                    ))

                # Buscar URLs com www
                for match in self.regex_www.finditer(valor_str):
                    url_candidata = match.group(0)

                    if url_candidata in urls_vistas:
                        continue
                    urls_vistas.add(url_candidata)

                    valido, confianca, motivo = self.url_validator.validar_estrutural(url_candidata)

                    if valido:
                        url_normalizada = self.url_validator.normalizar(url_candidata)
                    else:
                        url_normalizada = None

                    resultados.append(LinkProveniencia(
                        candidato_raw=url_candidata,
                        url_validada=url_normalizada,
                        valido=valido,
                        origem_tipo=origem_tipo,
                        origem_ref=f"{origem_tipo}:{arquivo_nome}:row={row_idx+1}:col={col}",
                        evidencia_trecho=valor_str[:200],
                        confianca=confianca,
                        motivo_rejeicao=motivo,
                    ))

        # Ordenar por confianca
        resultados.sort(key=lambda x: x.confianca, reverse=True)

        return resultados


# ============================================================
# REPOSITORIO SUPABASE V19
# ============================================================

class SupabaseRepositoryV19:
    """Repositorio para persistencia no Supabase com campos V19."""

    def __init__(self, config: AuditorConfig):
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

    def buscar_editais_pendentes(self, limite: int = 100, incluir_ja_processados: bool = False) -> List[dict]:
        """
        Busca editais sem link_leiloeiro ou com link 'N/D'.

        V19.2 IDEMPOTENCIA: Por padrao, exclui editais ja processados pelo V19.
        Use incluir_ja_processados=True para reprocessar (flag --force).

        Args:
            limite: Numero maximo de editais
            incluir_ja_processados: Se True, inclui editais ja processados pelo V19

        Returns:
            Lista de editais pendentes
        """
        if not self.enable_supabase:
            return []

        try:
            query = (
                self.client.table("editais_leilao")
                .select("*")
                .or_("link_leiloeiro.is.null,link_leiloeiro.eq.N/D")
            )

            # V19.2: Filtro de idempotencia - exclui ja processados pelo V19
            if not incluir_ja_processados:
                query = query.is_("auditor_v19_processed_at", "null")
                self.logger.debug("Filtrando editais ja processados pelo V19 (idempotencia ativa)")

            response = (
                query
                .order("created_at", desc=True)
                .limit(limite)
                .execute()
            )
            return response.data

        except Exception as e:
            self.logger.error(f"Erro ao buscar editais pendentes: {e}")
            return []

    def buscar_todos_editais(self, limite: int = None) -> List[dict]:
        """Busca todos os editais."""
        if not self.enable_supabase:
            return []

        try:
            query = (
                self.client.table("editais_leilao")
                .select("*")
                .order("created_at", desc=True)
            )

            if limite:
                query = query.limit(limite)

            response = query.execute()
            return response.data

        except Exception as e:
            self.logger.error(f"Erro ao buscar editais: {e}")
            return []

    def listar_arquivos_storage(self, pncp_id: str, max_retries: int = 3) -> List[dict]:
        """
        Lista arquivos no storage para um edital.

        V19.2: Inclui retry com backoff exponencial.
        V19.3: Normaliza pncp_id substituindo / por - para compatibilidade com storage.
        """
        if not self.enable_supabase:
            return []

        # V19.3: Normalizar pncp_id para nome de pasta (/ -> -)
        folder_name = pncp_id.replace("/", "-")

        last_error = None
        for attempt in range(max_retries):
            try:
                response = self.client.storage.from_(
                    self.config.storage_bucket
                ).list(folder_name)
                return [
                    {"path": f"{folder_name}/{item['name']}", "name": item["name"]}
                    for item in response
                ]
            except Exception as e:
                last_error = e
                if attempt < max_retries - 1:
                    delay = (2 ** attempt) * (0.5 + __import__('random').random() * 0.5)
                    self.logger.warning(
                        f"[RETRY] listar_arquivos_storage tentativa {attempt + 1}/{max_retries} "
                        f"falhou: {e}. Retry em {delay:.1f}s"
                    )
                    time.sleep(delay)

        self.logger.error(f"Erro listando arquivos em {folder_name} apos {max_retries} tentativas: {last_error}")
        return []

    def baixar_arquivo(self, storage_path: str, max_retries: int = 3) -> Optional[bytes]:
        """
        Baixa arquivo do storage.

        V19.2: Inclui retry com backoff exponencial.
        """
        if not self.enable_supabase:
            return None

        last_error = None
        for attempt in range(max_retries):
            try:
                response = self.client.storage.from_(
                    self.config.storage_bucket
                ).download(storage_path)
                return response
            except Exception as e:
                last_error = e
                if attempt < max_retries - 1:
                    delay = (2 ** attempt) * (0.5 + __import__('random').random() * 0.5)
                    self.logger.warning(
                        f"[RETRY] baixar_arquivo tentativa {attempt + 1}/{max_retries} "
                        f"falhou: {e}. Retry em {delay:.1f}s"
                    )
                    time.sleep(delay)

        self.logger.error(f"Erro baixando {storage_path} apos {max_retries} tentativas: {last_error}")
        return None

    def atualizar_link_leiloeiro_v19(
        self,
        pncp_id: str,
        proveniencia: LinkProveniencia,
        run_id: str = None,
        max_retries: int = 3,
    ) -> bool:
        """
        Atualiza link do leiloeiro com campos de proveniencia V19.

        V19.2 IDEMPOTENCIA: Tambem registra timestamp e run_id do processamento.
        V19.2 RESILIENCIA: Inclui retry com backoff exponencial.

        Args:
            pncp_id: pncp_id do edital
            proveniencia: Objeto LinkProveniencia com dados completos
            run_id: ID unico da execucao atual (opcional)
            max_retries: Numero maximo de tentativas

        Returns:
            True se sucesso
        """
        if not self.enable_supabase:
            return False

        dados = {
            "link_leiloeiro": proveniencia.url_validada,
            "link_leiloeiro_raw": proveniencia.candidato_raw,
            "link_leiloeiro_valido": proveniencia.valido,
            "link_leiloeiro_origem_tipo": proveniencia.origem_tipo,
            "link_leiloeiro_origem_ref": proveniencia.origem_ref,
            "link_leiloeiro_evidencia_trecho": proveniencia.evidencia_trecho[:200] if proveniencia.evidencia_trecho else None,
            "link_leiloeiro_confianca": proveniencia.confianca,
            "versao_auditor": self.config.versao_auditor,
            "updated_at": datetime.now().isoformat(),
        }

        # V19.2: Campos de idempotencia
        if run_id:
            dados["auditor_v19_processed_at"] = datetime.now().isoformat()
            dados["auditor_v19_run_id"] = run_id
            dados["auditor_v19_result"] = "found_link" if proveniencia.valido else "no_link"

        last_error = None
        for attempt in range(max_retries):
            try:
                self.client.table("editais_leilao").update(dados).eq(
                    "pncp_id", pncp_id
                ).execute()

                # Registrar domínio do leiloeiro se link válido
                if proveniencia.valido and proveniencia.url_validada:
                    self.registrar_leiloeiro_url(
                        url=proveniencia.url_validada,
                        fonte="auditor"
                    )

                return True

            except Exception as e:
                last_error = e
                if attempt < max_retries - 1:
                    delay = (2 ** attempt) * (0.5 + __import__('random').random() * 0.5)
                    self.logger.warning(
                        f"[RETRY] atualizar_link_leiloeiro_v19 tentativa {attempt + 1}/{max_retries} "
                        f"falhou: {e}. Retry em {delay:.1f}s"
                    )
                    time.sleep(delay)

        self.logger.error(f"Erro atualizando edital {pncp_id} apos {max_retries} tentativas: {last_error}")
        return False

    def marcar_processado_v19(
        self,
        pncp_id: str,
        run_id: str,
        resultado: str = "no_link",
        motivo: str = "sem_link",
        max_retries: int = 3,
    ) -> bool:
        """
        Marca edital como processado pelo V19 mesmo sem encontrar link.

        V19.2 IDEMPOTENCIA: Registra timestamp e run_id para garantir
        que o mesmo edital nao seja reprocessado em execucoes futuras.
        V19.2 RESILIENCIA: Inclui retry com backoff exponencial.
        V19.4 LINEAGE: NAO sobrescreve link_leiloeiro_origem_tipo se ja estiver
              definido (ex: pncp_api do Miner). Apenas atualiza campos de idempotencia.

        Args:
            pncp_id: pncp_id do edital
            run_id: ID unico da execucao atual
            resultado: Resultado do processamento (found_link, no_link, error, skipped)
            motivo: motivo de nao ter link (ex: "sem_link", "pdf_escaneado")
            max_retries: Numero maximo de tentativas

        Returns:
            True se sucesso
        """
        if not self.enable_supabase:
            return False

        # V19.4 LINEAGE FIX: Apenas atualiza campos de idempotencia quando no_link.
        # NAO sobrescreve link_leiloeiro_origem_tipo - pode ter vindo do Miner (pncp_api).
        # Apenas define origem_tipo se o edital realmente nao tinha nenhum link
        # E o resultado e "no_link" (confirma que processamos e nao encontramos).
        dados = {
            "versao_auditor": self.config.versao_auditor,
            "updated_at": datetime.now().isoformat(),
            # V19.2: Campos de idempotencia
            "auditor_v19_processed_at": datetime.now().isoformat(),
            "auditor_v19_run_id": run_id,
            "auditor_v19_result": resultado,
        }

        # V19.4: So define confianca zero se resultado for no_link
        if resultado == "no_link":
            dados["link_leiloeiro_confianca"] = 0

        last_error = None
        for attempt in range(max_retries):
            try:
                self.client.table("editais_leilao").update(dados).eq(
                    "pncp_id", pncp_id
                ).execute()

                self.logger.debug(f"[IDEMPOTENCIA] Edital {pncp_id} marcado como processado (result={resultado})")
                return True

            except Exception as e:
                last_error = e
                if attempt < max_retries - 1:
                    delay = (2 ** attempt) * (0.5 + __import__('random').random() * 0.5)
                    self.logger.warning(
                        f"[RETRY] marcar_processado_v19 tentativa {attempt + 1}/{max_retries} "
                        f"falhou: {e}. Retry em {delay:.1f}s"
                    )
                    time.sleep(delay)

        self.logger.error(f"Erro marcando edital {pncp_id} como processado apos {max_retries} tentativas: {last_error}")
        return False

    def inserir_run_report(
        self,
        run_id: str,
        git_sha: Optional[str],
        job_name: str = "auditor",
    ) -> bool:
        """
        Insere relatorio de execucao na tabela pipeline_run_reports.

        V19.4: Persiste metricas de qualidade para rastreamento historico.

        Args:
            run_id: ID unico da execucao
            git_sha: SHA do commit git (pode ser None)
            job_name: Nome do job (miner ou auditor)

        Returns:
            True se sucesso
        """
        if not self.enable_supabase:
            return False

        try:
            # Buscar metricas atuais do banco
            resp = self.client.rpc('get_pipeline_metrics', {}).execute()
            if resp.data:
                metrics = resp.data
            else:
                # Fallback: calcular via queries
                total_resp = self.client.table("editais_leilao").select("id", count="exact").execute()
                total = total_resp.count or 0

                com_link_resp = self.client.table("editais_leilao").select("id", count="exact").not_.is_("link_leiloeiro", "null").neq("link_leiloeiro", "N/D").execute()
                com_link = com_link_resp.count or 0

                valido_true_resp = self.client.table("editais_leilao").select("id", count="exact").not_.is_("link_leiloeiro", "null").neq("link_leiloeiro", "N/D").eq("link_leiloeiro_valido", True).execute()
                valido_true = valido_true_resp.count or 0

                valido_false_resp = self.client.table("editais_leilao").select("id", count="exact").not_.is_("link_leiloeiro", "null").neq("link_leiloeiro", "N/D").eq("link_leiloeiro_valido", False).execute()
                valido_false = valido_false_resp.count or 0

                origem_pncp_resp = self.client.table("editais_leilao").select("id", count="exact").eq("link_leiloeiro_origem_tipo", "pncp_api").execute()
                origem_pncp = origem_pncp_resp.count or 0

                origem_pdf_resp = self.client.table("editais_leilao").select("id", count="exact").eq("link_leiloeiro_origem_tipo", "pdf_anexo").execute()
                origem_pdf = origem_pdf_resp.count or 0

                metrics = {
                    'total': total,
                    'com_link': com_link,
                    'sem_link': total - com_link,
                    'com_link_valido_true': valido_true,
                    'com_link_valido_false': valido_false,
                    'com_link_valido_null': com_link - valido_true - valido_false,
                    'origem_pncp_api': origem_pncp,
                    'origem_pdf_anexo': origem_pdf,
                }

            # Inserir relatorio
            dados = {
                "run_id": run_id,
                "git_sha": git_sha,
                "job_name": job_name,
                "total": metrics.get('total', 0),
                "com_link": metrics.get('com_link', 0),
                "sem_link": metrics.get('sem_link', 0),
                "com_link_valido_true": metrics.get('com_link_valido_true', 0),
                "com_link_valido_false": metrics.get('com_link_valido_false', 0),
                "com_link_valido_null": metrics.get('com_link_valido_null', 0),
                "origem_pncp_api": metrics.get('origem_pncp_api', 0),
                "origem_pdf_anexo": metrics.get('origem_pdf_anexo', 0),
                "origem_unknown": metrics.get('origem_unknown', 0),
                "origem_null": metrics.get('origem_null', 0),
            }

            self.client.table("pipeline_run_reports").insert(dados).execute()
            self.logger.info(f"[RUN REPORT] Inserido relatorio: run_id={run_id}, total={dados['total']}, valido_null={dados['com_link_valido_null']}")
            return True

        except Exception as e:
            self.logger.warning(f"Erro inserindo run_report: {e}")
            return False

    def _extrair_dominio(self, url: str) -> Optional[str]:
        """
        Extrai o domínio base de uma URL.

        Args:
            url: URL completa (ex: https://www.megaleiloes.com.br/leilao/123)

        Returns:
            Domínio base (ex: megaleiloes.com.br) ou None se inválido
        """
        if not url:
            return None

        try:
            # Normalizar URL
            url_lower = url.lower().strip()

            # Remover protocolo
            url_limpa = re.sub(r'^https?://', '', url_lower)

            # Remover www.
            url_limpa = re.sub(r'^www\.', '', url_limpa)

            # Pegar apenas o domínio (antes da primeira barra)
            dominio = url_limpa.split('/')[0]

            # Validar que parece um domínio válido
            if '.' in dominio and len(dominio) > 3:
                return dominio

            return None

        except Exception:
            return None

    def registrar_leiloeiro_url(
        self,
        url: str,
        fonte: str = "auditor"
    ) -> bool:
        """
        Registra um domínio de leiloeiro na tabela leiloeiros_urls.

        Se o domínio já existe, incrementa a contagem.
        Se não existe, cria novo registro.

        Args:
            url: URL completa do leiloeiro
            fonte: Origem do registro (auditor, miner, manual)

        Returns:
            True se sucesso
        """
        if not self.enable_supabase:
            return False

        dominio = self._extrair_dominio(url)
        if not dominio:
            return False

        try:
            # Tentar inserir ou atualizar usando upsert
            dados = {
                "dominio": dominio,
                "url_exemplo": url,
                "fonte": fonte,
                "qtd_ocorrencias": 1,
                "ultimo_visto": datetime.now().isoformat(),
            }

            # Verificar se já existe
            response = (
                self.client.table("leiloeiros_urls")
                .select("dominio, qtd_ocorrencias")
                .eq("dominio", dominio)
                .execute()
            )

            if response.data:
                # Já existe - incrementar contagem
                nova_qtd = response.data[0]["qtd_ocorrencias"] + 1
                self.client.table("leiloeiros_urls").update({
                    "qtd_ocorrencias": nova_qtd,
                    "ultimo_visto": datetime.now().isoformat(),
                }).eq("dominio", dominio).execute()

                self.logger.debug(f"Leiloeiro atualizado: {dominio} (ocorrências: {nova_qtd})")
            else:
                # Não existe - inserir novo
                dados["primeiro_visto"] = datetime.now().isoformat()
                self.client.table("leiloeiros_urls").insert(dados).execute()

                self.logger.info(f"Novo leiloeiro registrado: {dominio}")

            return True

        except Exception as e:
            # Não falhar o processo principal se der erro aqui
            self.logger.debug(f"Erro registrando leiloeiro {dominio}: {e}")
            return False


# ============================================================
# AUDITOR V19 PRINCIPAL
# ============================================================

class AuditorV19:
    """Auditor de editais - Versao 19 com gate de validacao e proveniencia."""

    def __init__(self, config: AuditorConfig, extrair_lotes: bool = True):
        self.config = config
        self.repo = SupabaseRepositoryV19(config)
        self.url_validator = URLValidatorV19(timeout=config.timeout_seconds)
        self.pdf_extractor = PDFExtractorV19(self.url_validator)
        self.excel_extractor = ExcelExtractorV19(self.url_validator)
        self.logger = logging.getLogger("AuditorV19")
        self.metrics = AuditorMetrics()
        self.temp_dir = tempfile.mkdtemp(prefix="auditor_v19_")

        # Integrador de lotes (V19.1)
        self.extrair_lotes = extrair_lotes and LOTES_INTEGRATION_DISPONIVEL
        self.lotes_integrador = None
        if self.extrair_lotes:
            try:
                self.lotes_integrador = LotesIntegration(
                    supabase_client=self.repo.client if self.repo.enable_supabase else None
                )
                self.logger.info("Integrador de lotes inicializado")
            except Exception as e:
                self.logger.warning(f"Falha ao inicializar integrador de lotes: {e}")
                self.extrair_lotes = False

    def _is_data_passada(self, data_leilao) -> bool:
        """Verifica se a data do leilao ja passou."""
        if not data_leilao:
            return False

        hoje = date.today()

        if isinstance(data_leilao, datetime):
            return data_leilao.date() < hoje
        elif isinstance(data_leilao, date):
            return data_leilao < hoje
        elif isinstance(data_leilao, str):
            try:
                if "T" in data_leilao:
                    dt = datetime.fromisoformat(data_leilao.replace("Z", "+00:00"))
                    return dt.date() < hoje
                if "/" in data_leilao:
                    partes = data_leilao.split("/")
                    if len(partes) == 3:
                        dt = date(int(partes[2]), int(partes[1]), int(partes[0]))
                        return dt < hoje
                if "-" in data_leilao:
                    partes = data_leilao.split("-")
                    if len(partes) == 3:
                        dt = date(int(partes[0]), int(partes[1]), int(partes[2]))
                        return dt < hoje
            except (ValueError, IndexError):
                pass

        return False

    def _atualizar_metricas_gate(self, proveniencia: LinkProveniencia):
        """Atualiza metricas baseado no resultado do gate."""
        if proveniencia.valido:
            if proveniencia.confianca == 100:
                self.metrics.urls_aceitas_whitelist += 1
            elif proveniencia.confianca == 80:
                self.metrics.urls_aceitas_http += 1
            elif proveniencia.confianca == 60:
                self.metrics.urls_aceitas_www += 1
        else:
            if proveniencia.motivo_rejeicao == "tld_colado_em_palavra":
                self.metrics.urls_rejeitadas_tld_colado += 1
            else:
                self.metrics.urls_rejeitadas_sem_prefixo += 1

    def _processar_edital(self, edital: dict) -> Optional[dict]:
        """
        Processa um edital buscando link do leiloeiro com proveniencia.

        Estrategia em cascata:
        1. PDFs (maior probabilidade)
        2. Excel/CSV (dados tabulares)
        3. Descricao (texto do edital)
        """
        pncp_id = edital.get("pncp_id")
        edital_id = edital.get("id")

        if not pncp_id:
            return None

        data_leilao = edital.get("data_leilao")
        if self.config.filtrar_data_passada and data_leilao:
            if self._is_data_passada(data_leilao):
                self.metrics.editais_data_passada += 1
                self.logger.debug(f"Edital {pncp_id} com data passada: {data_leilao}")
                return None

        arquivos = self.repo.listar_arquivos_storage(pncp_id)

        pdfs = [a for a in arquivos if a["name"].lower().endswith(".pdf")]
        excels = [a for a in arquivos if a["name"].lower().endswith((".xlsx", ".xls"))]
        csvs = [a for a in arquivos if a["name"].lower().endswith(".csv")]

        melhor_proveniencia: Optional[LinkProveniencia] = None
        fonte = ""

        # ============================================================
        # CASCATA 1: PDFs
        # ============================================================
        lotes_extraidos_total = 0  # V19.1: contador de lotes

        for pdf_info in pdfs:
            pdf_data = self.repo.baixar_arquivo(pdf_info["path"])
            if not pdf_data:
                continue

            self.metrics.pdfs_processados += 1

            try:
                pdf_bytesio = BytesIO(pdf_data)
                proveniencia = self.pdf_extractor.extrair_link_leiloeiro_com_proveniencia(
                    pdf_bytesio, pdf_info["name"]
                )

                if proveniencia and proveniencia.valido:
                    melhor_proveniencia = proveniencia
                    fonte = "PDF"
                    self.metrics.url_extraida_pdf += 1
                    self._atualizar_metricas_gate(proveniencia)

                    # V19.1: Extrair lotes do PDF
                    if self.extrair_lotes and self.lotes_integrador and edital_id:
                        try:
                            pdf_bytesio.seek(0)  # Reset para reler
                            stats_lotes = self.lotes_integrador.processar_pdf_completo(
                                pdf_bytesio=pdf_bytesio,
                                edital_id=edital_id,
                                arquivo_nome=pdf_info["name"],
                                pncp_id=pncp_id,
                                salvar_banco=True,
                            )
                            lotes_salvos = stats_lotes.get('lotes_salvos', 0)
                            lotes_extraidos_total += lotes_salvos
                            self.metrics.lotes_extraidos += lotes_salvos
                            if lotes_salvos > 0:
                                self.metrics.pdfs_com_lotes += 1
                                self.logger.info(
                                    f"  Lotes extraidos: {lotes_salvos} "
                                    f"({stats_lotes.get('familia_pdf', '?')})"
                                )
                            if not stats_lotes.get('sucesso', True):
                                self.metrics.lotes_quarentena += 1
                        except Exception as e:
                            self.logger.warning(f"Erro extraindo lotes de {pdf_info['name']}: {e}")

                    break
                elif proveniencia:
                    # Guardar rejeitado caso nao encontre nada valido
                    if not melhor_proveniencia:
                        melhor_proveniencia = proveniencia
                    self._atualizar_metricas_gate(proveniencia)

            except Exception as e:
                self.logger.warning(f"Erro processando PDF {pdf_info['path']}: {e}")

        # ============================================================
        # CASCATA 2: Excel
        # ============================================================
        if not melhor_proveniencia or not melhor_proveniencia.valido:
            for excel_info in excels:
                excel_data = self.repo.baixar_arquivo(excel_info["path"])
                if not excel_data:
                    continue

                self.metrics.excels_processados += 1

                try:
                    excel_bytesio = BytesIO(excel_data)
                    resultados = self.excel_extractor.extrair_urls_excel_bytesio(
                        excel_bytesio, excel_info["name"]
                    )

                    for prov in resultados:
                        if prov.valido:
                            melhor_proveniencia = prov
                            fonte = "Excel"
                            self.metrics.url_extraida_excel += 1
                            self._atualizar_metricas_gate(prov)
                            break

                    if melhor_proveniencia and melhor_proveniencia.valido:
                        break

                except Exception as e:
                    self.logger.warning(f"Erro processando Excel {excel_info['path']}: {e}")

        # ============================================================
        # CASCATA 3: CSV
        # ============================================================
        if not melhor_proveniencia or not melhor_proveniencia.valido:
            for csv_info in csvs:
                csv_data = self.repo.baixar_arquivo(csv_info["path"])
                if not csv_data:
                    continue

                self.metrics.csvs_processados += 1

                try:
                    csv_bytesio = BytesIO(csv_data)
                    resultados = self.excel_extractor.extrair_urls_csv_bytesio(
                        csv_bytesio, csv_info["name"]
                    )

                    for prov in resultados:
                        if prov.valido:
                            melhor_proveniencia = prov
                            fonte = "CSV"
                            self.metrics.url_extraida_csv += 1
                            self._atualizar_metricas_gate(prov)
                            break

                    if melhor_proveniencia and melhor_proveniencia.valido:
                        break

                except Exception as e:
                    self.logger.warning(f"Erro processando CSV {csv_info['path']}: {e}")

        # ============================================================
        # CASCATA 4: Descricao
        # ============================================================
        if not melhor_proveniencia or not melhor_proveniencia.valido:
            descricao = edital.get("descricao", "") or ""
            titulo = edital.get("titulo", "") or ""
            texto = f"{titulo} {descricao}"

            if texto.strip():
                resultados = self.pdf_extractor.extrair_urls_com_proveniencia(
                    texto=texto,
                    arquivo_nome="titulo_descricao",
                    pagina=None,
                    origem_tipo="titulo_descricao",
                )

                for prov in resultados:
                    if prov.valido:
                        melhor_proveniencia = prov
                        fonte = "Descricao"
                        self.metrics.url_extraida_descricao += 1
                        self._atualizar_metricas_gate(prov)
                        break

        # ============================================================
        # RESULTADO
        # ============================================================
        if melhor_proveniencia:
            return {
                "pncp_id": pncp_id,
                "edital_id": edital_id,
                "proveniencia": melhor_proveniencia,
                "fonte": fonte if melhor_proveniencia.valido else "Rejeitado",
            }

        self.metrics.url_nao_encontrada += 1
        return None

    def executar(self, limite: int = 100, reprocessar_todos: bool = False, force_reprocess: bool = False, git_sha: Optional[str] = None) -> dict:
        """
        Executa auditoria em editais pendentes.

        V19.2 IDEMPOTENCIA: Gera run_id unico e rastreia processamento.
        V19.4 RUN REPORT: Persiste metricas ao final da execucao.

        Args:
            limite: Numero maximo de editais a processar
            reprocessar_todos: Se True, reprocessa todos os editais (ignora filtro de link)
            force_reprocess: Se True, reprocessa mesmo editais ja processados pelo V19

        Returns:
            Estatisticas da execucao
        """
        # V19.2: Gerar run_id unico para esta execucao
        run_id = f"auditor_v19_{datetime.now().strftime('%Y%m%dT%H%M%S')}_{hashlib.md5(str(time.time()).encode()).hexdigest()[:8]}"
        self.current_run_id = run_id

        self.logger.info("=" * 70)
        self.logger.info("ACHE SUCATAS - CLOUD AUDITOR V19.2 (IDEMPOTENTE)")
        self.logger.info("=" * 70)
        self.logger.info("NOVIDADES V19.2:")
        self.logger.info("  - IDEMPOTENCIA: Rastreia processamento com timestamp e run_id")
        self.logger.info("  - SKIP: Editais ja processados nao sao reprocessados")
        self.logger.info("  - FORCE: Use --force para reprocessar mesmo assim")
        self.logger.info("-" * 70)
        self.logger.info(f"Run ID: {run_id}")
        self.logger.info(f"Supabase: {'ATIVO' if self.repo.enable_supabase else 'DESATIVADO'}")
        self.logger.info(f"Validar URLs: {'SIM' if self.config.validar_urls else 'NAO'}")
        self.logger.info(f"Force Reprocess: {'SIM' if force_reprocess else 'NAO'}")
        self.logger.info("=" * 70)

        if reprocessar_todos:
            self.logger.info("Modo: Reprocessar TODOS os editais (ignora filtro de link)")
            editais = self.repo.buscar_todos_editais(limite)
        else:
            self.logger.info("Modo: Editais pendentes (sem link_leiloeiro)")
            # V19.2: Passa flag de force para incluir ja processados
            editais = self.repo.buscar_editais_pendentes(limite, incluir_ja_processados=force_reprocess)

        if not editais:
            self.logger.info("Nenhum edital para processar")
            return self.metrics.__dict__

        self.logger.info(f"Encontrados {len(editais)} editais para processar")

        for i, edital in enumerate(editais, 1):
            self.metrics.total_processados += 1
            pncp_id = edital.get("pncp_id", "?")

            self.logger.info(f"[{i}/{len(editais)}] Processando {pncp_id}")

            try:
                resultado = self._processar_edital(edital)

                if resultado:
                    proveniencia = resultado["proveniencia"]

                    # V19.2: Passa run_id para rastreamento de idempotencia
                    sucesso = self.repo.atualizar_link_leiloeiro_v19(
                        pncp_id=resultado["pncp_id"],
                        proveniencia=proveniencia,
                        run_id=run_id,
                    )

                    if sucesso:
                        self.metrics.sucessos += 1
                        if proveniencia.valido:
                            self.logger.info(
                                f"  Link VALIDO ({resultado['fonte']}, conf={proveniencia.confianca}): "
                                f"{proveniencia.url_validada}"
                            )
                        else:
                            self.logger.info(
                                f"  Link REJEITADO ({proveniencia.motivo_rejeicao}): "
                                f"{proveniencia.candidato_raw}"
                            )
                    else:
                        self.metrics.falhas += 1
                else:
                    # V19.2: Marcar como processado com run_id para idempotencia
                    self.repo.marcar_processado_v19(
                        pncp_id=pncp_id,
                        run_id=run_id,
                        resultado="no_link",
                        motivo="sem_link"
                    )
                    self.metrics.url_nao_encontrada += 1
                    self.logger.debug(f"  [IDEMPOTENCIA] Marcado como processado (no_link)")

            except Exception as e:
                self.logger.error(f"Erro processando {pncp_id}: {e}")
                # V19.2: Marcar erro para nao reprocessar infinitamente
                self.repo.marcar_processado_v19(
                    pncp_id=pncp_id,
                    run_id=run_id,
                    resultado="error",
                    motivo=str(e)[:100]
                )
                self.metrics.erros += 1
                self.metrics.falhas += 1

            if i % 10 == 0:
                self.logger.info(
                    f"  Progresso: {i}/{len(editais)} | "
                    f"Sucesso: {self.metrics.sucessos} | "
                    f"URLs: PDF={self.metrics.url_extraida_pdf}, "
                    f"Excel={self.metrics.url_extraida_excel}, "
                    f"Descr={self.metrics.url_extraida_descricao}"
                )

        self.metrics.print_summary()

        # V19.4: Inserir run report para rastreamento historico
        self.repo.inserir_run_report(
            run_id=self.current_run_id,
            git_sha=git_sha,
            job_name="auditor"
        )

        return {
            "total_processados": self.metrics.total_processados,
            "links_extraidos": self.metrics.sucessos,
            "links_validados": self.metrics.urls_validadas,
            "links_rejeitados_tld_colado": self.metrics.urls_rejeitadas_tld_colado,
            "erros": self.metrics.erros,
            "run_id": self.current_run_id,
        }


# ============================================================
# ENTRY POINT
# ============================================================

def main():
    """Ponto de entrada do auditor."""
    parser = argparse.ArgumentParser(
        description="Ache Sucatas - Cloud Auditor V19.2 (Idempotente)"
    )
    parser.add_argument(
        "--limite",
        type=int,
        default=100,
        help="Numero maximo de editais a processar (default: 100)"
    )
    parser.add_argument(
        "--reprocessar-todos",
        action="store_true",
        help="Reprocessar TODOS os editais (ignora filtro de link)"
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="V19.2: Reprocessa editais ja processados pelo V19 (ignora idempotencia)"
    )
    parser.add_argument(
        "--sem-validacao",
        action="store_true",
        help="Desabilitar validacao de URLs"
    )
    parser.add_argument(
        "--excluir-data-passada",
        action="store_true",
        help="Excluir editais com data do leilao no passado"
    )
    parser.add_argument(
        "--test-mode",
        action="store_true",
        help="Modo de teste (limite 5)"
    )
    parser.add_argument(
        "--debug",
        action="store_true",
        help="Ativa modo debug com logs detalhados"
    )

    args = parser.parse_args()

    if args.debug:
        logging.getLogger().setLevel(logging.DEBUG)

    # V19.2: Log de aviso quando --force e usado
    if args.force:
        logging.warning("[IDEMPOTENCIA] --force ativo: editais ja processados serao reprocessados")

    config = AuditorConfig(
        supabase_url=os.environ.get("SUPABASE_URL", ""),
        supabase_key=os.environ.get("SUPABASE_SERVICE_KEY", os.environ.get("SUPABASE_KEY", "")),
        validar_urls=not args.sem_validacao,
        excluir_data_passada=args.excluir_data_passada,
    )

    limite = args.limite
    if args.test_mode:
        limite = 5

    # V19.4: Obter git SHA para rastreamento
    git_sha = os.environ.get("GITHUB_SHA")
    if not git_sha:
        try:
            import subprocess
            result = subprocess.run(
                ["git", "rev-parse", "HEAD"],
                capture_output=True,
                text=True,
                timeout=5
            )
            if result.returncode == 0:
                git_sha = result.stdout.strip()
        except Exception:
            git_sha = None

    auditor = AuditorV19(config)
    stats = auditor.executar(
        limite=limite,
        reprocessar_todos=args.reprocessar_todos,
        force_reprocess=args.force,
        git_sha=git_sha,
    )

    logger.info(f"Auditoria finalizada: {stats}")


if __name__ == "__main__":
    main()
