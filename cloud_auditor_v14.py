#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
ACHE SUCATAS DaaS - CLOUD AUDITOR V14
=====================================
Extrai dados de editais usando cascata de fontes - 100% CLOUD.

V14 (2026-01):
- CLOUD NATIVE: Lê PDFs do Supabase Storage (não mais local)
- BytesIO: pdfplumber.open(BytesIO) para streams
- Query-driven: Lista editais do PostgreSQL, não do filesystem
- Update incremental: Só processa editais sem dados extraídos
- MANTÉM: Todas as funções de extração do V13/V12

FLUXO:
1. Query editais no PostgreSQL (WHERE versao_auditor = 'MINER_V11')
2. Para cada edital: download PDF do Storage → BytesIO
3. pdfplumber.open(BytesIO) → extrai texto
4. Aplica funções de extração V12/V13
5. UPDATE no PostgreSQL com dados extraídos
"""

from __future__ import annotations

import hashlib
import json
import logging
import os
import re
import tempfile
import zipfile
from dataclasses import dataclass
from datetime import datetime
from io import BytesIO
from pathlib import Path
from typing import Dict, List, Optional, Sequence, Tuple

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
log = logging.getLogger("CloudAuditor_V14")

try:
    from docx import Document as DocxDocument
    DOCX_AVAILABLE = True
except ImportError:
    DOCX_AVAILABLE = False
    log.warning("python-docx não instalado. DOCX será ignorado.")


# ==============================================================================
# CONFIGURATION
# ==============================================================================

class Settings:
    """Cloud Auditor V14 configuration."""

    ENABLE_SUPABASE = os.getenv("ENABLE_SUPABASE", "true").lower() == "true"
    ENABLE_SUPABASE_STORAGE = os.getenv("ENABLE_SUPABASE_STORAGE", "true").lower() == "true"

    VERSAO_AUDITOR = "V14_CLOUD"

    # Batch size for processing
    BATCH_SIZE = int(os.getenv("AUDITOR_BATCH_SIZE", "50"))

    # Local backup
    ENABLE_LOCAL_BACKUP = os.getenv("ENABLE_LOCAL_BACKUP", "false").lower() == "true"
    CSV_OUTPUT = Path(os.getenv("CSV_OUTPUT", "analise_editais_v14.csv"))


# ==============================================================================
# CONSTANTS (from V13)
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

TAGS_POR_ORGAO = {
    "prefeitura": "veiculos_municipais",
    "camara": "veiculos_municipais",
    "detran": "veiculos_detran",
    "policia": "veiculos_policiais",
    "tribunal": "veiculos_judiciarios",
    "tj": "veiculos_judiciarios",
    "der": "veiculos_estaduais",
    "receita federal": "bens_apreendidos_federal",
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
REGEX_N_EDITAL = re.compile(
    r"(?i)(?:edital|processo|leilao|pregao).*?(\d{1,5}\s*/\s*20\d{2})",
    re.DOTALL,
)
REGEX_DATA = re.compile(r"\b(\d{1,2}[/\-]\d{1,2}[/\-]20\d{2})\b")
REGEX_DATA_CONTEXTUAL = re.compile(
    r"(?i)(?:data|abertura|sessao|leilao|pregao|realizacao|"
    r"desfazimento|alienacao|hasta|arrematacao).*?"
    r"(\d{1,2}[/\-]\d{1,2}[/\-]20\d{2})",
    re.DOTALL,
)
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
# EXTRACTION FUNCTIONS (from V12/V13)
# ==============================================================================

def corrigir_encoding(texto: str) -> str:
    if not texto or texto == "N/D":
        return texto
    try:
        return texto.encode("latin-1").decode("utf-8")
    except (UnicodeDecodeError, UnicodeEncodeError):
        return texto


def limpar_texto(texto: str, max_length: int = 500) -> str:
    if not texto or texto == "N/D":
        return texto
    texto = re.sub(r"\n{3,}", "\n\n", texto)
    texto = re.sub(r" {2,}", " ", texto)
    if len(texto) > max_length:
        texto = texto[:max_length] + "..."
    return texto.strip()


def converter_data_extenso(match: re.Match) -> str:
    dia = match.group(1).zfill(2)
    mes = MESES_BR.get(match.group(2).lower(), "01")
    ano = match.group(3)
    return f"{dia}/{mes}/{ano}"


def extrair_data_de_texto(texto: str) -> Optional[str]:
    if not texto:
        return None

    matches = REGEX_DATA_CONTEXTUAL.findall(texto)
    if not matches:
        matches = REGEX_DATA.findall(texto)

    for data_str in matches:
        try:
            data_obj = datetime.strptime(data_str.replace("-", "/"), "%d/%m/%Y")
            if data_obj.year >= 2024:
                return data_str
        except ValueError:
            continue

    match_extenso = REGEX_DATA_EXTENSO.search(texto)
    if match_extenso:
        data_convertida = converter_data_extenso(match_extenso)
        try:
            data_obj = datetime.strptime(data_convertida, "%d/%m/%Y")
            if data_obj.year >= 2024:
                return data_convertida
        except ValueError:
            pass

    return None


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
    if not valor_raw:
        return "N/D"
    try:
        valor_float = float(valor_raw)
        return f"R$ {valor_float:,.2f}".replace(',', 'X').replace('.', ',').replace('X', '.')
    except:
        return "N/D"


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


def extrair_titulo_inteligente(pdf_text: str, descricao: str, n_edital: str) -> str:
    if pdf_text:
        linhas = pdf_text.strip().split('\n')
        for linha in linhas[:10]:
            linha_limpa = linha.strip()
            if len(linha_limpa) > 20 and not linha_limpa.replace(' ', '').isdigit():
                ignorar = ['ministério', 'secretaria', 'governo', 'estado', 'página', 'pag.']
                if not any(ig in linha_limpa.lower() for ig in ignorar):
                    return linha_limpa[:100]

    if descricao and len(descricao) > 20:
        return descricao[:100]

    return f"Edital nº {n_edital}" if n_edital else "Edital sem identificação"


def extrair_modalidade(pdf_text: str, descricao: str = "") -> str:
    texto = f"{pdf_text[:2000]} {descricao}".lower()

    tem_online = any(x in texto for x in ['eletrônico', 'eletronico', 'online', 'internet', 'virtual'])
    tem_presencial = any(x in texto for x in ['presencial', 'sede', 'auditório', 'sala', 'comparecimento'])

    if tem_online and tem_presencial:
        return "HÍBRIDO"
    elif tem_online:
        return "ONLINE"
    elif tem_presencial:
        return "PRESENCIAL"
    return "N/D"


def extrair_valor_estimado(pdf_text: str) -> str:
    padrao = r'(?:valor|lance|mínimo|avaliação|avaliacao|estimado)[:\s]*R?\$?\s*([\d.,]+)'
    match = re.search(padrao, pdf_text[:3000], re.IGNORECASE)
    if match:
        valor_str = match.group(1).replace('.', '').replace(',', '.')
        return formatar_valor_br(valor_str)
    return "N/D"


def extrair_quantidade_itens(pdf_text: str) -> str:
    lotes = len(re.findall(r'\bLOTE\s*\d+', pdf_text[:5000], re.IGNORECASE))
    if lotes > 0:
        return str(lotes)

    itens = len(re.findall(r'\bITEM\s*\d+', pdf_text[:5000], re.IGNORECASE))
    if itens > 0:
        return str(itens)

    return "N/D"


def extrair_nome_leiloeiro(pdf_text: str) -> str:
    padrao = r'(?:leiloeiro|leiloeira)[:\s]*(?:oficial|público|a)?\s*[:\s]*([A-ZÀ-Ú][a-zà-ú]+(?:\s+[A-ZÀ-Ú][a-zà-ú]+){1,4})'
    match = re.search(padrao, pdf_text[:3000])
    if match:
        return match.group(1).strip()[:100]
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
                    except:
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


def extrair_texto_pdfs_bytesio(pdf_list: List[BytesIO]) -> str:
    """Extrai texto de múltiplos PDFs em memória."""
    partes = []
    for pdf_bytesio in pdf_list:
        texto = extrair_texto_pdf_bytesio(pdf_bytesio)
        if texto:
            partes.append(texto)
    return " ".join(partes).strip()


# ==============================================================================
# CLOUD AUDITOR CLASS
# ==============================================================================

class CloudAuditor:
    """Auditor que processa editais do Supabase Storage."""

    def __init__(self):
        self.supabase_repo = None
        self.storage_repo = None
        self.resultados = []

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
        """Lista editais que precisam ser processados pelo Auditor."""
        if not self.supabase_repo or not self.supabase_repo.enable_supabase:
            return []

        try:
            # Busca editais inseridos pelo Miner (versao_auditor = 'MINER_V10' ou 'MINER_V11')
            # que ainda não foram processados pelo Auditor V14
            query = (
                self.supabase_repo.client
                .table("editais_leilao")
                .select("*")
                .or_("versao_auditor.eq.MINER_V10,versao_auditor.eq.MINER_V11,versao_auditor.eq.V11_CLOUD")
                .order("created_at", desc=True)
            )

            if limit:
                query = query.limit(limit)

            response = query.execute()

            log.info(f"Encontrados {len(response.data)} editais pendentes de processamento")
            return response.data

        except Exception as e:
            log.error(f"Erro ao listar editais pendentes: {e}")
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
        """Processa um edital: download PDF do Storage, extrai dados, atualiza banco."""
        pncp_id = edital.get("pncp_id")
        storage_path = edital.get("storage_path")

        log.info(f"Processando: {pncp_id}")

        # Download do PDF - priorizar storage_path
        pdf_text = ""
        pdf_path = None

        if self.storage_repo:
            # Tentar pelo storage_path primeiro (formato: CNPJ-1-SEQ/ANO)
            if storage_path:
                arquivos = self.storage_repo.listar_pdfs_por_storage_path(storage_path)
                if arquivos:
                    pdf_path = arquivos[0].get("path")
                    log.debug(f"PDF encontrado via storage_path: {pdf_path}")

            # Fallback: tentar pelo pncp_id
            if not pdf_path and pncp_id:
                arquivos = self.storage_repo.listar_pdfs(pncp_id)
                if arquivos:
                    pdf_path = arquivos[0].get("path")
                    log.debug(f"PDF encontrado via pncp_id: {pdf_path}")

            # Baixar o PDF
            if pdf_path:
                try:
                    pdf_bytesio = self.storage_repo.download_pdf(pdf_path)
                    if pdf_bytesio:
                        pdf_text = extrair_texto_pdf_bytesio(pdf_bytesio)
                        log.debug(f"PDF extraído: {len(pdf_text)} chars")
                except Exception as e:
                    log.warning(f"Erro ao baixar PDF {pdf_path}: {e}")

        # Se não conseguiu do Storage, tentar metadados
        metadados = {}
        if self.storage_repo:
            # Tentar pelo storage_path primeiro, depois pelo pncp_id
            if storage_path:
                metadados = self.storage_repo.download_json(f"{storage_path}/metadados.json") or {}
            if not metadados and pncp_id:
                metadados = self.storage_repo.download_metadados(pncp_id) or {}

        # Extrair dados usando cascata V12/V13
        descricao = edital.get("descricao", "") or metadados.get("descricao", "")
        titulo = edital.get("titulo", "") or metadados.get("titulo", "")

        dados_extraidos = {
            "id_interno": edital.get("id_interno"),
            "pncp_id": pncp_id,
        }

        # Extrair novos dados do PDF
        if pdf_text:
            # Data do leilão (campo crítico)
            data_leilao_atual = edital.get("data_leilao")
            if not data_leilao_atual:
                data_leilao = extrair_data_leilao_cascata(pdf_text, descricao)
                if data_leilao != "N/D":
                    dados_extraidos["data_leilao"] = data_leilao

            # Valor estimado
            valor_atual = edital.get("valor_estimado")
            if not valor_atual:
                valor = extrair_valor_estimado(pdf_text)
                if valor != "N/D":
                    # Converter para decimal
                    try:
                        valor_num = float(valor.replace("R$ ", "").replace(".", "").replace(",", "."))
                        dados_extraidos["valor_estimado"] = valor_num
                    except:
                        pass

            # Quantidade de itens
            qtd_atual = edital.get("quantidade_itens")
            if not qtd_atual:
                qtd = extrair_quantidade_itens(pdf_text)
                if qtd != "N/D":
                    dados_extraidos["quantidade_itens"] = int(qtd)

            # Nome do leiloeiro
            leiloeiro_atual = edital.get("nome_leiloeiro")
            if not leiloeiro_atual:
                nome = extrair_nome_leiloeiro(pdf_text)
                if nome != "N/D":
                    dados_extraidos["nome_leiloeiro"] = nome

            # Link do leiloeiro
            link_atual = edital.get("link_leiloeiro")
            if not link_atual:
                urls = extrair_urls_de_texto(pdf_text)
                link = encontrar_link_leiloeiro(urls, pdf_text)
                if link:
                    dados_extraidos["link_leiloeiro"] = link

            # Modalidade
            modalidade_atual = edital.get("modalidade_leilao")
            if not modalidade_atual or modalidade_atual == "N/D":
                modalidade = extrair_modalidade(pdf_text, descricao)
                if modalidade != "N/D":
                    dados_extraidos["modalidade_leilao"] = modalidade

            # Tags
            tags_atuais = edital.get("tags", [])
            if not tags_atuais or tags_atuais == ["miner_v10"] or tags_atuais == ["miner_v11"]:
                tags = extrair_tags_inteligente(descricao, pdf_text, titulo)
                if tags != "sem_classificacao":
                    dados_extraidos["tags"] = tags.split(",")

            # Título (melhorar se possível)
            titulo_atual = edital.get("titulo", "")
            if not titulo_atual or len(titulo_atual) < 30:
                titulo_melhorado = extrair_titulo_inteligente(pdf_text, descricao, edital.get("n_edital", ""))
                if titulo_melhorado and len(titulo_melhorado) > len(titulo_atual):
                    dados_extraidos["titulo"] = titulo_melhorado

        # Marcar como processado pelo V14
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
            # Remover campos de identificação do update
            update_data = {k: v for k, v in dados_extraidos.items() if k not in ["id_interno", "pncp_id"]}
            # Marcar como processado
            update_data["processado_auditor"] = True

            response = (
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

    def run(self, limit: int = None, reprocess_all: bool = False):
        """Executa o processamento de editais."""
        log.info("=" * 70)
        log.info("ACHE SUCATAS - CLOUD AUDITOR V14")
        log.info("=" * 70)
        log.info(f"Storage: {'ATIVO' if self.storage_repo else 'DESATIVADO'}")
        log.info(f"DB: {'ATIVO' if self.supabase_repo else 'DESATIVADO'}")
        log.info("=" * 70)

        # Listar editais
        if reprocess_all:
            editais = self.listar_todos_editais(limit=limit)
        else:
            editais = self.listar_editais_pendentes(limit=limit)

        if not editais:
            log.info("Nenhum edital para processar")
            return

        log.info(f"Processando {len(editais)} editais...")

        sucessos = 0
        falhas = 0

        for i, edital in enumerate(editais, 1):
            try:
                dados_extraidos = self.processar_edital(edital)
                if dados_extraidos:
                    sucesso = self.atualizar_edital(dados_extraidos)
                    if sucesso:
                        sucessos += 1
                        self.resultados.append(dados_extraidos)
                    else:
                        falhas += 1
                else:
                    falhas += 1

                if i % 10 == 0 or i == len(editais):
                    log.info(f"  [{i}/{len(editais)}] OK: {sucessos}, Falhas: {falhas}")

            except Exception as e:
                log.error(f"Erro ao processar edital: {e}")
                falhas += 1

        # Resumo
        log.info("=" * 70)
        log.info("RESUMO - CLOUD AUDITOR V14")
        log.info("=" * 70)
        log.info(f"Total processados: {len(editais)}")
        log.info(f"Atualizados com sucesso: {sucessos}")
        log.info(f"Falhas: {falhas}")
        log.info("=" * 70)

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

    parser = argparse.ArgumentParser(description="ACHE SUCATAS - Cloud Auditor V14")
    parser.add_argument("--limit", type=int, help="Limitar número de editais")
    parser.add_argument("--reprocess-all", action="store_true", help="Reprocessar todos os editais")
    parser.add_argument("--test-mode", action="store_true", help="Modo de teste (limite 5)")

    args = parser.parse_args()

    limit = args.limit
    if args.test_mode:
        limit = 5

    auditor = CloudAuditor()
    auditor.run(limit=limit, reprocess_all=args.reprocess_all)


if __name__ == "__main__":
    main()
