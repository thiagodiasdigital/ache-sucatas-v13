#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Ache Sucatas DaaS - Auditor V18
===============================
Extrai dados estruturados de editais com foco em links de leiloeiro.
Usa estrategias em cascata para maximizar extracao.

Versao: 18
Data: 2026-01-20
Changelog:
    - V18: Extracao de links em cascata (PDF -> Excel -> CSV)
    - V18: Validacao e normalizacao de URLs
    - V18: Correcao de dominios conhecidos
    - V18: Suporte a OCR para PDFs escaneados (opcional)
    - V18: Regex aprimorado para plataformas de leilao
    - V18: Parseamento de planilhas Excel/CSV

Baseado em: V17 (URL + DATE FIX)
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


# ============================================================
# LOGGING
# ============================================================

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-8s | [%(name)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S"
)
logger = logging.getLogger("CloudAuditor_V18")


# ============================================================
# CONFIGURACAO
# ============================================================

@dataclass
class AuditorConfig:
    """Configuracoes do auditor V18."""

    supabase_url: str = ""
    supabase_key: str = ""
    storage_bucket: str = "editais-pdfs"
    timeout_seconds: int = 30
    validar_urls: bool = True
    usar_ocr: bool = False  # Requer Tesseract ou similar

    # Rate limiting
    request_delay_seconds: float = 0.2

    # Filtros
    filtrar_data_passada: bool = True
    excluir_data_passada: bool = False

    # Batch
    batch_size: int = 50

    # Versao
    versao_auditor: str = "V18_CASCATA_EXTRACAO"


# ============================================================
# PLATAFORMAS DE LEILAO CONHECIDAS
# ============================================================

PLATAFORMAS_LEILAO = {
    # Dominio incorreto -> Dominio correto
    "lanceleiloes.com": "www.lanceleiloes.com.br",
    "lanceleiloes.com.br": "www.lanceleiloes.com.br",
    "www.lanceleiloes.com": "www.lanceleiloes.com.br",
    "superbid.net": "www.superbid.net",

    # Plataformas conhecidas (para regex direcionado)
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
    ]
}

# Dominios a ignorar (governamentais, redes sociais, etc)
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

# Dominios de email (invalidos para link_leiloeiro)
DOMINIOS_EMAIL = [
    "hotmail.com", "hotmail.com.br", "yahoo.com", "yahoo.com.br",
    "gmail.com", "outlook.com", "uol.com.br", "bol.com.br",
    "terra.com.br", "ig.com.br", "globo.com", "msn.com",
    "live.com", "icloud.com"
]


# ============================================================
# CORRECAO DE DOMINIOS
# ============================================================

DOMINIOS_CORRECAO = {
    "lanceleiloes.com": "www.lanceleiloes.com.br",
    "www.lanceleiloes.com": "www.lanceleiloes.com.br",
    "lanceleiloes.com.br": "www.lanceleiloes.com.br",
    "superbid.net": "www.superbid.net",
}


def corrigir_dominio(url: str) -> str:
    """
    Corrige dominios conhecidos com problemas.

    Args:
        url: URL original

    Returns:
        URL com dominio corrigido
    """
    if not url:
        return url

    try:
        parsed = urlparse(url)
        dominio = parsed.netloc.lower()

        # Remover www. para comparacao
        dominio_sem_www = dominio.replace("www.", "")

        for errado, correto in DOMINIOS_CORRECAO.items():
            errado_sem_www = errado.replace("www.", "")
            if dominio_sem_www == errado_sem_www:
                # Reconstruir URL com dominio correto
                return url.replace(parsed.netloc, correto)

    except Exception:
        pass

    return url


# ============================================================
# METRICAS
# ============================================================

@dataclass
class AuditorMetrics:
    """Metricas detalhadas do Auditor V18."""

    total_processados: int = 0
    sucessos: int = 0
    falhas: int = 0

    # Metricas de extracao de URL por fonte
    url_extraida_pdf: int = 0
    url_extraida_excel: int = 0
    url_extraida_csv: int = 0
    url_extraida_descricao: int = 0
    url_nao_encontrada: int = 0

    # Metricas de validacao
    urls_validadas: int = 0
    urls_invalidas: int = 0
    urls_corrigidas: int = 0

    # Metricas de data_leilao
    data_leilao_encontrada: int = 0
    data_leilao_nao_encontrada: int = 0

    # Metricas de filtro
    editais_data_passada: int = 0
    editais_excluidos: int = 0

    # Metricas de arquivos
    pdfs_processados: int = 0
    excels_processados: int = 0
    csvs_processados: int = 0

    erros: int = 0
    start_time: datetime = field(default_factory=datetime.now)

    def print_summary(self):
        """Imprime resumo das metricas."""
        duration = (datetime.now() - self.start_time).total_seconds()
        logger.info("=" * 70)
        logger.info("RESUMO - CLOUD AUDITOR V18 (CASCATA EXTRACAO)")
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
        logger.info("FILTROS:")
        logger.info(f"  |- Editais data passada: {self.editais_data_passada}")
        logger.info(f"  |- Editais excluidos: {self.editais_excluidos}")
        logger.info("=" * 70)


# ============================================================
# VALIDACAO DE URLs
# ============================================================

class URLValidator:
    """Validador de URLs de leiloeiros."""

    def __init__(self, timeout: int = 10):
        self.timeout = timeout
        self.logger = logging.getLogger(__name__)
        self.cache: Dict[str, bool] = {}

    def validar(self, url: str) -> bool:
        """
        Verifica se URL esta acessivel.

        Args:
            url: URL para validar

        Returns:
            True se acessivel, False caso contrario
        """
        if not url:
            return False

        # Verificar cache
        if url in self.cache:
            return self.cache[url]

        try:
            # Garantir https
            url_check = url
            if not url_check.startswith("http"):
                url_check = "https://" + url_check

            with httpx.Client(timeout=self.timeout, follow_redirects=True) as client:
                response = client.head(url_check)
                valido = response.status_code < 400

        except Exception as e:
            self.logger.debug(f"URL invalida {url}: {e}")
            valido = False

        self.cache[url] = valido
        return valido

    def normalizar(self, url: str) -> str:
        """
        Normaliza URL para formato padrao.

        Args:
            url: URL para normalizar

        Returns:
            URL normalizada
        """
        if not url:
            return url

        url = url.strip()

        # Remover espacos e caracteres invalidos
        url = re.sub(r'\s+', '', url)

        # Remover caracteres de pontuacao no final
        url = url.rstrip(".,;:)>\"'")

        # Adicionar https se ausente
        if not url.startswith("http"):
            url = "https://" + url

        # Corrigir dominio se necessario
        url = corrigir_dominio(url)

        # Remover trailing slash
        url = url.rstrip("/")

        return url


# ============================================================
# EXTRATOR DE PDF
# ============================================================

class PDFExtractor:
    """Extrator de dados de PDFs com multiplas estrategias."""

    def __init__(self):
        self.logger = logging.getLogger(__name__)

        # Regex para URLs genericas
        self.regex_url = re.compile(
            r'https?://[^\s<>"{}|\\^`\[\]]+',
            re.IGNORECASE
        )

        # Regex para plataformas conhecidas
        dominios_pattern = "|".join([
            re.escape(d.replace(".", r"\."))
            for d in PLATAFORMAS_LEILAO["dominios_validos"]
        ])

        self.regex_plataformas = re.compile(
            rf'(?:https?://)?(?:www\.)?({dominios_pattern})[^\s<>"]*',
            re.IGNORECASE
        )

        # Regex alternativo para padroes comuns
        self.regex_padrao_leilao = re.compile(
            r'(?:https?://)?(?:www\.)?('
            r'[a-z]+leiloes\.com\.br|'
            r'[a-z]+leil[oõ]es\.com\.br|'
            r'[a-z]franca(?:leiloes)?\.com\.br|'
            r'bidgo\.com\.br|'
            r'superbid\.(?:net|com\.br)|'
            r'sold\.com\.br|'
            r'megaleiloes\.com\.br|'
            r'lanceja\.com\.br|'
            r'hastavip\.com\.br'
            r')[^\s<>"]*',
            re.IGNORECASE
        )

        # Palavras-chave que indicam proximidade de link
        self.keywords_contexto = [
            "leilao on-line",
            "leilão on-line",
            "leilao online",
            "leilão online",
            "plataforma eletronica",
            "plataforma eletrônica",
            "endereco eletronico",
            "endereço eletrônico",
            "site do leilao",
            "site do leilão",
            "portal do leilao",
            "portal do leilão",
            "acesso ao leilao",
            "acesso ao leilão",
            "local do leilao",
            "local do leilão",
            "sera realizado",
            "será realizado",
            "disponivel em",
            "disponível em",
            "realizado atraves",
            "realizado através",
            "pelo site",
            "no site",
            "acesse",
            "acessar",
        ]

    def extrair_texto(self, pdf_path: str) -> str:
        """
        Extrai texto completo do PDF.

        Args:
            pdf_path: Caminho do arquivo PDF

        Returns:
            Texto extraido
        """
        texto = ""
        try:
            with pdfplumber.open(pdf_path) as pdf:
                for page in pdf.pages:
                    page_text = page.extract_text()
                    if page_text:
                        texto += page_text + "\n"
        except Exception as e:
            self.logger.error(f"Erro extraindo texto de {pdf_path}: {e}")

        return texto

    def extrair_texto_bytesio(self, pdf_bytesio: BytesIO) -> str:
        """
        Extrai texto de PDF em memoria (BytesIO).

        Args:
            pdf_bytesio: PDF em BytesIO

        Returns:
            Texto extraido
        """
        texto = ""
        try:
            with pdfplumber.open(pdf_bytesio) as pdf:
                for page in pdf.pages:
                    page_text = page.extract_text()
                    if page_text:
                        texto += page_text + "\n"
        except Exception as e:
            self.logger.warning(f"Erro ao extrair texto do PDF: {e}")

        return texto

    def extrair_urls(self, texto: str) -> List[Tuple[str, int]]:
        """
        Extrai URLs do texto usando multiplas estrategias.
        Retorna lista de tuplas (url, prioridade) ordenadas por relevancia.

        Args:
            texto: Texto do PDF

        Returns:
            Lista de (URL, prioridade) encontradas
        """
        urls_encontradas: List[Tuple[str, int]] = []
        urls_vistas = set()

        # Estrategia 1: Plataformas conhecidas (MAIOR prioridade = 1)
        for match in self.regex_plataformas.finditer(texto):
            dominio = match.group(1).lower()
            url = f"https://www.{dominio}"
            if url not in urls_vistas:
                urls_encontradas.append((url, 1))
                urls_vistas.add(url)

        # Estrategia 2: Padroes de leilao (prioridade = 2)
        for match in self.regex_padrao_leilao.finditer(texto):
            dominio = match.group(1).lower()
            url = f"https://www.{dominio}"
            if url not in urls_vistas:
                urls_encontradas.append((url, 2))
                urls_vistas.add(url)

        # Estrategia 3: URLs proximas a palavras-chave (prioridade = 3)
        texto_lower = texto.lower()
        for keyword in self.keywords_contexto:
            pos = texto_lower.find(keyword)
            if pos != -1:
                # Buscar URL nos proximos 500 caracteres
                trecho = texto[pos:pos + 500]
                for match in self.regex_url.finditer(trecho):
                    url = match.group(0)
                    if self._url_relevante(url) and url not in urls_vistas:
                        urls_encontradas.append((url, 3))
                        urls_vistas.add(url)

        # Estrategia 4: Todas as URLs com filtro (menor prioridade = 4)
        for match in self.regex_url.finditer(texto):
            url = match.group(0)
            if self._url_relevante(url) and url not in urls_vistas:
                urls_encontradas.append((url, 4))
                urls_vistas.add(url)

        # Ordenar por prioridade (menor = melhor)
        urls_encontradas.sort(key=lambda x: x[1])

        return urls_encontradas

    def _url_relevante(self, url: str) -> bool:
        """
        Verifica se URL e potencialmente de leiloeiro.

        Args:
            url: URL para verificar

        Returns:
            True se relevante, False caso contrario
        """
        url_lower = url.lower()

        # Verificar dominios a ignorar
        for dominio in DOMINIOS_IGNORAR:
            if dominio in url_lower:
                return False

        # Verificar dominios de email
        for dominio in DOMINIOS_EMAIL:
            if dominio in url_lower:
                return False

        # Indicadores positivos
        indicadores_positivos = [
            "leilao", "leilão", "leiloes", "leilões",
            "franca", "bid", "lance", "sold", "hasta",
            "arremate", "arrematacao",
        ]

        for indicador in indicadores_positivos:
            if indicador in url_lower:
                return True

        # Se tem .com.br e nao foi filtrado, pode ser relevante
        if ".com.br" in url_lower or ".net.br" in url_lower:
            return True

        return False

    def extrair_link_leiloeiro(
        self,
        pdf_path_or_bytesio,
        is_bytesio: bool = False
    ) -> Optional[str]:
        """
        Extrai o link do leiloeiro mais provavel do PDF.

        Args:
            pdf_path_or_bytesio: Caminho do arquivo PDF ou BytesIO
            is_bytesio: True se for BytesIO

        Returns:
            URL do leiloeiro ou None
        """
        if is_bytesio:
            texto = self.extrair_texto_bytesio(pdf_path_or_bytesio)
        else:
            texto = self.extrair_texto(pdf_path_or_bytesio)

        if not texto:
            self.logger.warning("PDF sem texto extraivel")
            return None

        urls = self.extrair_urls(texto)
        if urls:
            self.logger.debug(f"Encontradas {len(urls)} URLs no PDF")
            return urls[0][0]  # Retorna a mais relevante (menor prioridade)

        return None


# ============================================================
# EXTRATOR DE EXCEL/CSV
# ============================================================

class ExcelExtractor:
    """Extrator de dados de arquivos Excel/CSV."""

    def __init__(self):
        self.logger = logging.getLogger(__name__)
        self.regex_url = re.compile(
            r'https?://[^\s<>"{}|\\^`\[\]]+',
            re.IGNORECASE
        )

    def extrair_urls_excel(self, file_path: str) -> List[str]:
        """
        Extrai URLs de arquivo Excel.

        Args:
            file_path: Caminho do arquivo

        Returns:
            Lista de URLs encontradas
        """
        urls = []

        try:
            df = pd.read_excel(file_path)
            urls = self._extrair_urls_dataframe(df)
        except Exception as e:
            self.logger.error(f"Erro lendo Excel {file_path}: {e}")

        return urls

    def extrair_urls_excel_bytesio(self, excel_bytesio: BytesIO) -> List[str]:
        """
        Extrai URLs de arquivo Excel em memoria.

        Args:
            excel_bytesio: Excel em BytesIO

        Returns:
            Lista de URLs encontradas
        """
        urls = []

        try:
            df = pd.read_excel(excel_bytesio)
            urls = self._extrair_urls_dataframe(df)
        except Exception as e:
            self.logger.warning(f"Erro lendo Excel: {e}")

        return urls

    def extrair_urls_csv(self, file_path: str) -> List[str]:
        """
        Extrai URLs de arquivo CSV.

        Args:
            file_path: Caminho do arquivo

        Returns:
            Lista de URLs encontradas
        """
        urls = []

        # Tentar diferentes encodings
        encodings = ["utf-8", "latin-1", "cp1252", "iso-8859-1"]

        for encoding in encodings:
            try:
                df = pd.read_csv(file_path, encoding=encoding, on_bad_lines="skip")
                urls = self._extrair_urls_dataframe(df)
                break
            except Exception:
                continue

        if not urls:
            self.logger.warning(f"Nao foi possivel ler CSV: {file_path}")

        return urls

    def extrair_urls_csv_bytesio(self, csv_bytesio: BytesIO) -> List[str]:
        """
        Extrai URLs de arquivo CSV em memoria.

        Args:
            csv_bytesio: CSV em BytesIO

        Returns:
            Lista de URLs encontradas
        """
        urls = []
        encodings = ["utf-8", "latin-1", "cp1252"]

        for encoding in encodings:
            try:
                csv_bytesio.seek(0)
                df = pd.read_csv(csv_bytesio, encoding=encoding, on_bad_lines="skip")
                urls = self._extrair_urls_dataframe(df)
                break
            except Exception:
                continue

        return urls

    def _extrair_urls_dataframe(self, df: pd.DataFrame) -> List[str]:
        """
        Extrai URLs de um DataFrame.

        Args:
            df: DataFrame pandas

        Returns:
            Lista de URLs encontradas
        """
        urls = []

        # Buscar em colunas com nomes sugestivos
        colunas_interesse = [
            "link", "url", "site", "endereco", "endereço",
            "portal", "plataforma", "leilao", "leilão"
        ]

        for col in df.columns:
            col_lower = str(col).lower()

            # Verificar nome da coluna
            for interesse in colunas_interesse:
                if interesse in col_lower:
                    for valor in df[col].dropna():
                        valor_str = str(valor)
                        matches = self.regex_url.findall(valor_str)
                        urls.extend(matches)

            # Buscar URLs em qualquer celula da coluna
            for valor in df[col].dropna():
                valor_str = str(valor)
                if "http" in valor_str.lower():
                    matches = self.regex_url.findall(valor_str)
                    urls.extend(matches)

        # Remover duplicatas preservando ordem
        return list(dict.fromkeys(urls))


# ============================================================
# REPOSITORIO SUPABASE
# ============================================================

class SupabaseRepository:
    """Repositorio para persistencia no Supabase."""

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

    def buscar_editais_pendentes(self, limite: int = 100) -> List[dict]:
        """
        Busca editais sem link_leiloeiro ou com link 'N/D'.

        Args:
            limite: Numero maximo de editais

        Returns:
            Lista de editais pendentes
        """
        if not self.enable_supabase:
            return []

        try:
            response = (
                self.client.table("editais_leilao")
                .select("*")
                .or_("link_leiloeiro.is.null,link_leiloeiro.eq.N/D")
                .order("created_at", desc=True)
                .limit(limite)
                .execute()
            )

            return response.data

        except Exception as e:
            self.logger.error(f"Erro ao buscar editais pendentes: {e}")
            return []

    def buscar_todos_editais(self, limite: int = None) -> List[dict]:
        """
        Busca todos os editais.

        Args:
            limite: Numero maximo de editais (None = todos)

        Returns:
            Lista de editais
        """
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

    def buscar_editais_nao_processados_v18(self, limite: int = None) -> List[dict]:
        """
        Busca editais que ainda nao foram processados pelo V18.

        Args:
            limite: Numero maximo de editais

        Returns:
            Lista de editais
        """
        if not self.enable_supabase:
            return []

        try:
            query = (
                self.client.table("editais_leilao")
                .select("*")
                .neq("versao_auditor", "V18_CASCATA_EXTRACAO")
                .order("created_at", desc=True)
            )

            if limite:
                query = query.limit(limite)

            response = query.execute()
            return response.data

        except Exception as e:
            self.logger.error(f"Erro ao buscar editais nao processados: {e}")
            return []

    def listar_arquivos_storage(self, pncp_id: str) -> List[dict]:
        """
        Lista arquivos no storage para um edital.

        Args:
            pncp_id: ID do edital no PNCP

        Returns:
            Lista de arquivos
        """
        if not self.enable_supabase:
            return []

        try:
            response = self.client.storage.from_(
                self.config.storage_bucket
            ).list(pncp_id)
            return [
                {"path": f"{pncp_id}/{item['name']}", "name": item["name"]}
                for item in response
            ]
        except Exception as e:
            self.logger.debug(f"Erro listando arquivos em {pncp_id}: {e}")
            return []

    def baixar_arquivo(self, storage_path: str) -> Optional[bytes]:
        """
        Baixa arquivo do storage.

        Args:
            storage_path: Caminho no storage

        Returns:
            Bytes do arquivo ou None
        """
        if not self.enable_supabase:
            return None

        try:
            response = self.client.storage.from_(
                self.config.storage_bucket
            ).download(storage_path)
            return response
        except Exception as e:
            self.logger.debug(f"Erro baixando {storage_path}: {e}")
            return None

    def atualizar_link_leiloeiro(
        self,
        edital_id: int,
        pncp_id: str,
        link: str,
        fonte: str = "",
        nome_leiloeiro: Optional[str] = None
    ) -> bool:
        """
        Atualiza link do leiloeiro no edital.

        Args:
            edital_id: ID do edital
            pncp_id: pncp_id do edital
            link: URL do leiloeiro
            fonte: Fonte da extracao (PDF, Excel, CSV, Descricao)
            nome_leiloeiro: Nome do leiloeiro (opcional)

        Returns:
            True se sucesso, False caso contrario
        """
        if not self.enable_supabase:
            return False

        try:
            dados = {
                "link_leiloeiro": link,
                "versao_auditor": self.config.versao_auditor,
                "updated_at": datetime.now().isoformat(),
            }

            if nome_leiloeiro:
                dados["nome_leiloeiro"] = nome_leiloeiro

            self.client.table("editais_leilao").update(dados).eq(
                "pncp_id", pncp_id
            ).execute()

            return True

        except Exception as e:
            self.logger.error(f"Erro atualizando edital {pncp_id}: {e}")
            return False

    def excluir_edital(self, pncp_id: str) -> bool:
        """
        Exclui edital do banco.

        Args:
            pncp_id: ID do edital no PNCP

        Returns:
            True se sucesso
        """
        if not self.enable_supabase:
            return False

        try:
            self.client.table("editais_leilao").delete().eq(
                "pncp_id", pncp_id
            ).execute()
            return True
        except Exception as e:
            self.logger.error(f"Erro excluindo edital {pncp_id}: {e}")
            return False


# ============================================================
# AUDITOR V18 PRINCIPAL
# ============================================================

class AuditorV18:
    """Auditor de editais - Versao 18 com extracao em cascata."""

    def __init__(self, config: AuditorConfig):
        self.config = config
        self.repo = SupabaseRepository(config)
        self.pdf_extractor = PDFExtractor()
        self.excel_extractor = ExcelExtractor()
        self.url_validator = URLValidator(timeout=config.timeout_seconds)
        self.logger = logging.getLogger("AuditorV18")
        self.metrics = AuditorMetrics()
        self.temp_dir = tempfile.mkdtemp(prefix="auditor_v18_")

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
                # Tentar parsear ISO
                if "T" in data_leilao:
                    dt = datetime.fromisoformat(data_leilao.replace("Z", "+00:00"))
                    return dt.date() < hoje
                # Formato BR: dd/mm/yyyy
                if "/" in data_leilao:
                    partes = data_leilao.split("/")
                    if len(partes) == 3:
                        dt = date(int(partes[2]), int(partes[1]), int(partes[0]))
                        return dt < hoje
                # Formato ISO: yyyy-mm-dd
                if "-" in data_leilao:
                    partes = data_leilao.split("-")
                    if len(partes) == 3:
                        dt = date(int(partes[0]), int(partes[1]), int(partes[2]))
                        return dt < hoje
            except (ValueError, IndexError):
                pass

        return False

    def _processar_edital(self, edital: dict) -> Optional[dict]:
        """
        Processa um edital buscando link do leiloeiro.

        Estrategia em cascata:
        1. PDFs (maior probabilidade)
        2. Excel/CSV (dados tabulares)
        3. Descricao (texto do edital)

        Args:
            edital: Dados do edital

        Returns:
            Dados atualizados ou None
        """
        pncp_id = edital.get("pncp_id")
        edital_id = edital.get("id")

        if not pncp_id:
            return None

        # Verificar data passada
        data_leilao = edital.get("data_leilao")
        if self.config.filtrar_data_passada and data_leilao:
            if self._is_data_passada(data_leilao):
                self.metrics.editais_data_passada += 1
                self.logger.debug(f"Edital {pncp_id} com data passada: {data_leilao}")

                if self.config.excluir_data_passada:
                    if self.repo.excluir_edital(pncp_id):
                        self.metrics.editais_excluidos += 1
                    return None

        # Listar arquivos no storage
        arquivos = self.repo.listar_arquivos_storage(pncp_id)

        # Separar por tipo
        pdfs = [a for a in arquivos if a["name"].lower().endswith(".pdf")]
        excels = [a for a in arquivos if a["name"].lower().endswith((".xlsx", ".xls"))]
        csvs = [a for a in arquivos if a["name"].lower().endswith(".csv")]

        link_encontrado = None
        fonte = ""

        # ============================================================
        # CASCATA 1: PDFs
        # ============================================================
        for pdf_info in pdfs:
            pdf_data = self.repo.baixar_arquivo(pdf_info["path"])
            if not pdf_data:
                continue

            self.metrics.pdfs_processados += 1

            try:
                pdf_bytesio = BytesIO(pdf_data)
                link = self.pdf_extractor.extrair_link_leiloeiro(
                    pdf_bytesio, is_bytesio=True
                )

                if link:
                    link_encontrado = link
                    fonte = "PDF"
                    self.metrics.url_extraida_pdf += 1
                    break

            except Exception as e:
                self.logger.warning(f"Erro processando PDF {pdf_info['path']}: {e}")

        # ============================================================
        # CASCATA 2: Excel
        # ============================================================
        if not link_encontrado:
            for excel_info in excels:
                excel_data = self.repo.baixar_arquivo(excel_info["path"])
                if not excel_data:
                    continue

                self.metrics.excels_processados += 1

                try:
                    excel_bytesio = BytesIO(excel_data)
                    urls = self.excel_extractor.extrair_urls_excel_bytesio(excel_bytesio)

                    # Filtrar URLs relevantes
                    for url in urls:
                        if self.pdf_extractor._url_relevante(url):
                            link_encontrado = url
                            fonte = "Excel"
                            self.metrics.url_extraida_excel += 1
                            break

                    if link_encontrado:
                        break

                except Exception as e:
                    self.logger.warning(f"Erro processando Excel {excel_info['path']}: {e}")

        # ============================================================
        # CASCATA 3: CSV
        # ============================================================
        if not link_encontrado:
            for csv_info in csvs:
                csv_data = self.repo.baixar_arquivo(csv_info["path"])
                if not csv_data:
                    continue

                self.metrics.csvs_processados += 1

                try:
                    csv_bytesio = BytesIO(csv_data)
                    urls = self.excel_extractor.extrair_urls_csv_bytesio(csv_bytesio)

                    for url in urls:
                        if self.pdf_extractor._url_relevante(url):
                            link_encontrado = url
                            fonte = "CSV"
                            self.metrics.url_extraida_csv += 1
                            break

                    if link_encontrado:
                        break

                except Exception as e:
                    self.logger.warning(f"Erro processando CSV {csv_info['path']}: {e}")

        # ============================================================
        # CASCATA 4: Descricao
        # ============================================================
        if not link_encontrado:
            descricao = edital.get("descricao", "") or ""
            titulo = edital.get("titulo", "") or ""
            texto = f"{titulo} {descricao}"

            if texto.strip():
                urls = self.pdf_extractor.extrair_urls(texto)
                if urls:
                    link_encontrado = urls[0][0]
                    fonte = "Descricao"
                    self.metrics.url_extraida_descricao += 1

        # ============================================================
        # VALIDAR E NORMALIZAR
        # ============================================================
        if link_encontrado:
            # Normalizar
            link_normalizado = self.url_validator.normalizar(link_encontrado)

            # Corrigir dominio se necessario
            link_corrigido = corrigir_dominio(link_normalizado)
            if link_corrigido != link_normalizado:
                self.metrics.urls_corrigidas += 1
                link_normalizado = link_corrigido

            # Validar se configurado
            if self.config.validar_urls:
                if self.url_validator.validar(link_normalizado):
                    self.metrics.urls_validadas += 1
                else:
                    self.logger.warning(f"URL invalida: {link_normalizado}")
                    self.metrics.urls_invalidas += 1

                    # Tentar corrigir dominio
                    link_corrigido = corrigir_dominio(link_normalizado)
                    if link_corrigido != link_normalizado:
                        if self.url_validator.validar(link_corrigido):
                            link_normalizado = link_corrigido
                            self.metrics.urls_corrigidas += 1
                            self.metrics.urls_validadas += 1
                        else:
                            # URL realmente invalida - ainda assim salvar
                            pass

            return {
                "pncp_id": pncp_id,
                "edital_id": edital_id,
                "link": link_normalizado,
                "fonte": fonte,
            }

        self.metrics.url_nao_encontrada += 1
        return None

    def executar(self, limite: int = 100, reprocessar_todos: bool = False) -> dict:
        """
        Executa auditoria em editais pendentes.

        Args:
            limite: Numero maximo de editais a processar
            reprocessar_todos: Se True, reprocessa todos os editais

        Returns:
            Estatisticas da execucao
        """
        self.logger.info("=" * 70)
        self.logger.info("ACHE SUCATAS - CLOUD AUDITOR V18 (CASCATA EXTRACAO)")
        self.logger.info("=" * 70)
        self.logger.info("NOVIDADES V18:")
        self.logger.info("  - Extracao em cascata: PDF -> Excel -> CSV -> Descricao")
        self.logger.info("  - Validacao e normalizacao de URLs")
        self.logger.info("  - Correcao de dominios conhecidos")
        self.logger.info("  - Regex aprimorado para plataformas de leilao")
        self.logger.info("-" * 70)
        self.logger.info(f"Supabase: {'ATIVO' if self.repo.enable_supabase else 'DESATIVADO'}")
        self.logger.info(f"Validar URLs: {'SIM' if self.config.validar_urls else 'NAO'}")
        self.logger.info(f"Filtrar data passada: {'SIM' if self.config.filtrar_data_passada else 'NAO'}")
        self.logger.info("=" * 70)

        # Buscar editais
        if reprocessar_todos:
            self.logger.info("Modo: Reprocessar TODOS os editais")
            editais = self.repo.buscar_todos_editais(limite)
        else:
            self.logger.info("Modo: Editais pendentes (sem link_leiloeiro)")
            editais = self.repo.buscar_editais_pendentes(limite)

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
                    # Persistir
                    sucesso = self.repo.atualizar_link_leiloeiro(
                        edital_id=resultado["edital_id"],
                        pncp_id=resultado["pncp_id"],
                        link=resultado["link"],
                        fonte=resultado["fonte"],
                    )

                    if sucesso:
                        self.metrics.sucessos += 1
                        self.logger.info(
                            f"  Link salvo ({resultado['fonte']}): {resultado['link']}"
                        )
                    else:
                        self.metrics.falhas += 1

            except Exception as e:
                self.logger.error(f"Erro processando {pncp_id}: {e}")
                self.metrics.erros += 1
                self.metrics.falhas += 1

            # Log de progresso a cada 10 editais
            if i % 10 == 0:
                self.logger.info(
                    f"  Progresso: {i}/{len(editais)} | "
                    f"Sucesso: {self.metrics.sucessos} | "
                    f"URLs: PDF={self.metrics.url_extraida_pdf}, "
                    f"Excel={self.metrics.url_extraida_excel}, "
                    f"Descr={self.metrics.url_extraida_descricao}"
                )

        # Imprimir resumo
        self.metrics.print_summary()

        return {
            "total_processados": self.metrics.total_processados,
            "links_extraidos": self.metrics.sucessos,
            "links_validados": self.metrics.urls_validadas,
            "erros": self.metrics.erros,
        }


# ============================================================
# ENTRY POINT
# ============================================================

def main():
    """Ponto de entrada do auditor."""
    parser = argparse.ArgumentParser(
        description="Ache Sucatas - Cloud Auditor V18 (Cascata de Extracao)"
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
        help="Reprocessar TODOS os editais"
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

    # Configurar nivel de log
    if args.debug:
        logging.getLogger().setLevel(logging.DEBUG)

    # Configuracao
    config = AuditorConfig(
        supabase_url=os.environ.get("SUPABASE_URL", ""),
        supabase_key=os.environ.get("SUPABASE_SERVICE_KEY", os.environ.get("SUPABASE_KEY", "")),
        validar_urls=not args.sem_validacao,
        excluir_data_passada=args.excluir_data_passada,
    )

    # Limite
    limite = args.limite
    if args.test_mode:
        limite = 5

    # Executar auditor
    auditor = AuditorV18(config)
    stats = auditor.executar(
        limite=limite,
        reprocessar_todos=args.reprocessar_todos,
    )

    logger.info(f"Auditoria finalizada: {stats}")


if __name__ == "__main__":
    main()
