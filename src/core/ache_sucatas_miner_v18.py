"""
Ache Sucatas DaaS - Minerador V18
=================================
NOVA FUNCIONALIDADE: Enriquecimento com IA (OpenAI GPT-4o-mini).

Versao: 18.4
Data: 2026-01-29

Changelog V18.4:
    - FIX: Aumentado dias_retroativos de 1 para 7 dias
    - MOTIVO: Investigacao forense revelou que apenas 21/281 leiloes tinham data futura
    - IMPACTO: Miner agora busca editais publicados nos ultimos 7 dias (antes: 24h)

Changelog V18.3:
    - NOVO: inserir_run_report para gravar execucoes em pipeline_run_reports
    - NOVO: Rastreamento de git_sha para correlacao com deploys
    - NOVO: Metricas de qualidade persistidas em cada execucao

Changelog V18.2:
    - NOVO: TaxonomiaLoader para carregar taxonomia automotiva do Supabase
    - NOVO: Funcao gerar_tags_v18 que usa taxonomia do banco de dados
    - NOVO: Tabela 'taxonomia_automotiva' no Supabase com ~300 termos
    - REMOVIDO: Tags IMOVEL, MOBILIARIO, ELETRONICO (fora do escopo Ache Sucatas)
    - NOTA: Ache Sucatas e focado APENAS em veiculos automotivos

Changelog V18.1:
    - WhitelistLoader para dominios de leiloeiros

Changelog V18.0:
    - NOVO: Classe OpenAIEnricher para analise inteligente de editais
    - NOVO: Extracao de titulo comercial, resumo, lista de veiculos e URL do leiloeiro via IA
    - NOVO: Configuracoes openai_api_key e openai_model no MinerConfig
    - MANTIDO: Todas as funcionalidades do V17 (API detalhes, validacao, quarentena)

Baseado em: V17
Autor: Claude (Implementacao IA)
Contrato: contracts/dataset_contract_v1.md

===============================================================
REGRAS:
1. A IA enriquece os dados extraidos, mas NAO substitui a
   validacao. Se um campo obrigatorio nao existir, o registro
   vai para quarentena.

2. APENAS tags automotivas sao geradas (VEICULO, SUCATA, MOTO,
   CAMINHAO, ONIBUS, CARRETA, MAQUINARIO, DOCUMENTADO, APREENDIDO).
   Tags de IMOVEL, MOBILIARIO, ELETRONICO foram REMOVIDAS.
===============================================================
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

# V18: Import OpenAI
try:
    from openai import OpenAI
    OPENAI_AVAILABLE = True
except ImportError:
    OPENAI_AVAILABLE = False
    OpenAI = None

# Adicionar path do projeto para importar validador
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from src.core.email_notifier import send_alert_email
from src.core.resilience import (
    retry_with_backoff,
    CircuitBreaker,
    CircuitOpenError,
    circuit_registry,
    RETRIABLE_EXCEPTIONS,
)
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
# WHITELIST LOADER - CARREGA DOMINIOS DO SUPABASE
# ============================================================

class WhitelistLoader:
    """
    Carrega whitelist de dominios do Supabase com fallback hardcoded.

    Beneficios:
    - Adicionar/remover dominios sem deploy
    - Fallback seguro se Supabase falhar
    - Performance: carrega 1x no inicio (cache em memoria)
    """

    # Fallback: 167 dominios (atualizado em jan/2026 com lista canonica + portais)
    FALLBACK_WHITELIST = {
        "abataleiloes.com.br", "agilileiloes.com.br", "alanleiloeiro.lel.br", "alexandrecostaleiloes.com.br",
        "alexandroleiloeiro.com.br", "alfaleiloes.com", "alfrancaleiloes.com.br", "alifrancaleiloes.com.br",
        "alinemarquesleiloeira.lel.br", "amaralleiloes.com.br", "analucialeiloeira.com.br", "andersonleiloeiro.lel.br",
        "andrealeiloeira.lel.br", "arremataronline.com.br", "benozzati.com.br", "bfranca.com.br",
        "biasileiloes.com.br", "bidgo.com.br", "bll.org.br", "bnc.org.br",
        "brameleiloes.com.br", "bspleiloes.com.br", "calilleiloes.com.br", "camilaleiloes.com.br",
        "cargneluttileiloes.com.br", "ceciliadelzeirleiloes.com.br", "centraldosleiloes.com.br", "cfrancaleiloes.com.br",
        "clfranca.com.br", "clickleiloes.com.br", "confederacaoleiloes.com.br", "cronos.com.br",
        "danielgarcialeiloes.com.br", "depaulaonline.com.br", "dfranca.com.br", "diegoleiloes.com",
        "diegoleiloes.com.br", "donizetteleiloes.leilao.br", "eckertleiloes.com.br", "edgarcarvalholeiloeiro.com.br",
        "estreladaleiloes.com.br", "fabianoayuppleiloeiro.com.br", "fabioguimaraesleiloes.com.br", "fabioleiloes.com.br",
        "facanhaleiloes.com.br", "fernandoleiloeiro.com.br", "ferronatoleiloes.com.br", "fidalgoleiloes.com.br",
        "fredericoleiloes.com.br", "frfranca.com.br", "gabrielleiloeiro.com.br", "gfrancaleiloes.com.br",
        "giordanoleiloes.com.br", "goldenlance.com.br", "gpleilao.com.br", "gustavoleiloeiro.lel.br",
        "hastasp.com.br", "hastavip.com.br", "hmfrancaleiloes.com.br", "hoppeleiloes.com.br",
        "inovaleilao.com.br", "ipirangaleiloes.com.br", "izabellaferreiraleiloes.com.br", "jfrancaleiloes.com.br",
        "joaoemilio.com.br", "jonasleiloeiro.com.br", "josimarleiloeiro.com.br", "junkesleiloes.com.br",
        "jvleiloes.lel.br", "karlapepe.lel.br", "kcleiloes.com.br", "kfranca.com.br",
        "klfrancaleiloes.com.br", "kronberg.lel.br", "kronleiloes.com.br", "lanceja.co",
        "lanceja.com.br", "lanceleiloes.com.br", "lancenoleilao.com.br", "lancevip.com.br",
        "leilaoseg.com.br", "leiloeiraerikamaciel.com.br", "leiloeirasilvani.com.br", "leiloeiroeduardo.com.br",
        "leiloeirolegentil.com.br", "leiloeironacif.com", "leiloesbrasil.com.br", "leiloesbrasilcassiano.com.br",
        "leiloesceruli.com.br", "leiloesfreire.com.br", "leiloesja.com.br", "leilomaster.com.br",
        "leje.com.br", "lfranca.com.br", "licitardigital.com.br", "liderleiloes.com.br", "lleiloes.com.br",
        "lopesleiloes.com.br", "lopesleiloes.net.br", "lucasleiloeiro.com.br", "lut.com.br",
        "machadoleiloes.com.br", "maiconleiloeiro.com.br", "marcoscostaleiloeiro.com", "marcusviniciusleiloes.com.br",
        "marioricart.lel.br", "mauriciomarizleiloes.com.br", "mauromarcello.lel.br", "megaleiloes.com.br",
        "megaleiloesms.com.br", "mfranca.com.br", "mgl.com.br", "mirandacarvalholeiloes.com.br",
        "mitroleiloes.com.br", "mklance.com.br", "msfranca.com.br", "nortedeminasleiloes.com.br",
        "octaviovianna.lel.br", "ofrancaleiloes.com.br", "onildobastos.com.br", "paulobotelholeiloeiro.com.br",
        "pavanileiloes.com.br", "pedroalmeidaleiloeiro.rio.br", "pedrocastroleiloes.com.br", "petroleiloes.com.br",
        "pfranca.com.br", "portalleiloes.com.br", "portaldecompraspublicas.com.br", "portellaleiloes.com.br",
        "rafaelfrancaleiloes.com.br", "rangelleiloes.com.br", "renovarleiloes.com.br", "rfrancaleiloes.com.br",
        "ricardocorrealeiloes.com.br", "ricardogomesleiloes.com.br",
        "ricoleiloes.com.br", "rioleiloes.com.br", "rodrigocostaleiloeiro.com.br", "rogeriomenezes.com.br",
        "rymerleiloes.com.br", "schulmannleiloes.com.br", "sergiorepresasleiloes.com.br", "serpaleiloes.com.br",
        "sevidanesleiloeira.com.br", "sfranca.com.br", "silasleiloeiro.lel.br", "snleiloes.com.br",
        "sodresantoro.com.br", "sold.com.br", "stfrancaleiloes.com.br", "sumareleiloes.com",
        "sumareleiloes.com.br", "superbid.com.br", "superbid.net", "szortykaleiloes.com.br",
        "tassianamenezes.com.br", "telesleiloes.com.br", "tfleiloes.com.br", "tostesleiloeiro.com.br",
        "viannaleiloes.com.br", "vipleiloes.com", "vipleiloes.com.br", "webleilao.com.br",
        "wfrancaleiloes.com.br", "wmsleiloes.com.br", "wsleiloes.com.br", "zfrancaleiloes.com.br",
        "www25.receita.fazenda.gov.br",  # Regra canonica Receita Federal
    }

    # ================================================================
    # REGRAS CANONICAS: URLs padrao por orgao/tipo
    # ================================================================
    REGRAS_CANONICAS = {
        "receita_federal": {
            "padrao": ["receita federal", "rfb", "secretaria da receita"],
            "url": "http://www25.receita.fazenda.gov.br/sle-sociedade/portal",
            "dominio": "www25.receita.fazenda.gov.br",
        },
    }

    def __init__(self, supabase_url: str, supabase_key: str):
        """
        Inicializa o loader com credenciais do Supabase.

        Args:
            supabase_url: URL do projeto Supabase
            supabase_key: Chave de servico do Supabase
        """
        self.supabase_url = supabase_url
        self.supabase_key = supabase_key
        self.client = None
        self.logger = logging.getLogger("WhitelistLoader")

        if supabase_url and supabase_key:
            try:
                from supabase import create_client
                self.client = create_client(supabase_url, supabase_key)
            except ImportError:
                self.logger.warning("Biblioteca supabase nao instalada")
            except Exception as e:
                self.logger.warning(f"Erro ao conectar Supabase: {e}")

    def carregar(self) -> tuple[set, bool]:
        """
        Carrega whitelist do Supabase.

        Returns:
            tuple: (set_dominios, veio_do_db)
            - set_dominios: Conjunto de dominios validados
            - veio_do_db: True se carregou do Supabase, False se usou fallback
        """
        if not self.client:
            self.logger.warning("Supabase nao conectado - usando whitelist fallback")
            return self.FALLBACK_WHITELIST.copy(), False

        try:
            # Query: SELECT dominio FROM leiloeiros_urls WHERE whitelist_oficial = TRUE
            result = self.client.table("leiloeiros_urls").select("dominio").eq(
                "whitelist_oficial", True
            ).execute()

            if result.data and len(result.data) > 0:
                dominios = {row["dominio"] for row in result.data if row.get("dominio")}
                self.logger.info(f"Whitelist carregada do Supabase: {len(dominios)} dominios")
                return dominios, True
            else:
                self.logger.warning("Nenhum dominio na whitelist do Supabase - usando fallback")
                return self.FALLBACK_WHITELIST.copy(), False

        except Exception as e:
            self.logger.error(f"Erro ao carregar whitelist do Supabase: {e}")
            self.logger.warning("Usando whitelist fallback")
            return self.FALLBACK_WHITELIST.copy(), False

    @staticmethod
    def aplicar_regra_canonica(titulo: str, orgao: str, descricao: str = "") -> Optional[str]:
        """
        Aplica regras canonicas para determinar URL padrao do leiloeiro.

        Args:
            titulo: Titulo do edital
            orgao: Nome do orgao
            descricao: Descricao do edital

        Returns:
            URL canonica se alguma regra bater, None caso contrario
        """
        texto = f"{titulo} {orgao} {descricao}".lower()

        for regra_nome, regra in WhitelistLoader.REGRAS_CANONICAS.items():
            for padrao in regra["padrao"]:
                if padrao in texto:
                    return regra["url"]

        return None


# ============================================================
# EXTRACAO DE TEXTO DO PDF (INALTERADO)
# ============================================================

def extrair_texto_pdf(pdf_bytes: bytes) -> str:
    """
    Extrai texto de um PDF usando pypdfium2 (deterministico, sem IA).
    """
    if not pdf_bytes:
        return ""

    try:
        import pypdfium2 as pdfium
        pdf = pdfium.PdfDocument(pdf_bytes)
        texto_paginas = []

        max_paginas = min(len(pdf), 10)
        for i in range(max_paginas):
            page = pdf[i]
            textpage = page.get_textpage()
            texto_paginas.append(textpage.get_text_range())

        pdf.close()
        return "\n".join(texto_paginas)

    except ImportError:
        logging.getLogger("MinerV18").warning("pypdfium2 nao instalado - extracao de PDF desabilitada")
        return ""
    except Exception as e:
        logging.getLogger("MinerV18").debug(f"Erro ao extrair texto do PDF: {e}")
        return ""


def extrair_descricao_pdf(texto_pdf: str) -> str:
    """Extrai descricao do texto do PDF."""
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

    linhas = [linha.strip() for linha in texto_pdf.split('\n') if len(linha.strip()) > 30]
    if linhas:
        return re.sub(r'\s+', ' ', ' '.join(linhas[:3]))[:500]

    return ""


def extrair_tipo_leilao_pdf(texto_pdf: str) -> str:
    """
    Extrai tipo/modalidade do leilao do texto do PDF.

    FIX 2026-01-29: Corrigido bug onde patterns regex eram tratados como strings literais.
    Agora usa re.search() para patterns com sintaxe regex.
    """
    if not texto_pdf:
        return ""

    texto_lower = texto_pdf.lower()

    # Patterns para leilão eletrônico (alguns são regex, outros são literais)
    ELETRONICO_REGEX = [
        r"leil[aã]o\s*eletr[oô]nico",
        r"eletr[oô]nico",
        r"modo\s+eletr[oô]nico",
        r"forma\s+eletr[oô]nica",
    ]
    ELETRONICO_LITERAL = ["online", "virtual", "pela internet"]

    # Patterns para leilão presencial
    PRESENCIAL_REGEX = [
        r"leil[aã]o\s*presencial",
    ]
    PRESENCIAL_LITERAL = [
        "presencial", "sede da", "local:", "endereco:",
        "comparecimento", "na sede", "no endereco"
    ]

    # Verificar patterns de eletrônico
    tem_eletronico = any(re.search(p, texto_lower) for p in ELETRONICO_REGEX)
    if not tem_eletronico:
        tem_eletronico = any(p in texto_lower for p in ELETRONICO_LITERAL)

    # Verificar patterns de presencial
    tem_presencial = any(re.search(p, texto_lower) for p in PRESENCIAL_REGEX)
    if not tem_presencial:
        tem_presencial = any(p in texto_lower for p in PRESENCIAL_LITERAL)

    if tem_eletronico and tem_presencial:
        return "Hibrido"
    elif tem_eletronico:
        return "Eletronico"
    elif tem_presencial:
        return "Presencial"

    return ""


def extrair_n_edital_pdf(texto_pdf: str) -> Optional[str]:
    """
    V17: Extrai numero do edital do texto do PDF.
    EXCLUSIVAMENTE do PDF - SEM FALLBACK.
    """
    if not texto_pdf:
        return None

    padroes = [
        r"[Ee][Dd][Ii][Tt][Aa][Ll]\s*[NnºÚ°\.]+\s*([0-9]+(?:/[0-9]+)?(?:/[0-9]{4})?)",
        r"[Ee][Dd][Ii][Tt][Aa][Ll]\s+[Dd][Ee]\s+[Ll][Ee][Ii][Ll][ÃãAa][Oo]\s*[NnºÚ°\.]*\s*([0-9]+(?:/[0-9]+)?(?:/[0-9]{4})?)",
        r"[Pp][Rr][Oo][Cc][Ee][Ss][Ss][Oo]\s*[NnºÚ°\.]+\s*([0-9]+(?:/[0-9]+)?(?:/[0-9]{4})?)",
    ]

    for padrao in padroes:
        match = re.search(padrao, texto_pdf)
        if match:
            n_edital = match.group(1).strip()
            n_edital = re.sub(r'\s+', '', n_edital)
            if n_edital:
                return n_edital

    return None


# ============================================================
# V17: NORMALIZACAO DE URL (CORRIGIDA - LIMPA CARACTERES SUJOS)
# ============================================================

def normalizar_url_v17(url: str) -> Optional[str]:
    """
    V17: Normaliza URL conforme regras do contrato.
    CORRIGIDO: Remove caracteres invalidos no final da URL.
    """
    if not url:
        return None

    url = url.strip()

    # V17 FIX: Remover caracteres invalidos no final (parenteses, virgulas, pontos soltos)
    # Isso corrige URLs como: https://www.eckertleiloes.com.br)
    url = re.sub(r'[)\]},;:\s]+$', '', url)
    url = re.sub(r'\.$', '', url)  # Ponto no final (mas manter .br, .com, etc)

    # Remover caracteres invalidos no inicio
    url = re.sub(r'^[<>"\'(\[\s]+', '', url)

    # Se ja tem protocolo, retornar
    if url.lower().startswith(("https://", "http://")):
        return url

    # Se comeca com www., adicionar https://
    if url.lower().startswith("www."):
        return "https://" + url

    # Verificar se tem TLD valido
    tlds_validos = [
        ".com.br", ".net.br", ".org.br", ".gov.br",
        ".com", ".net", ".org"
    ]

    url_lower = url.lower()
    for tld in tlds_validos:
        if tld in url_lower:
            idx = url_lower.find(tld)
            parte_antes = url_lower[:idx]
            if "." in parte_antes or re.match(r'^[a-z0-9-]+$', parte_antes):
                return "https://" + url

    return None


def extrair_leiloeiro_url_pdf(texto_pdf: str) -> Optional[str]:
    """Extrai URL do leiloeiro do texto do PDF."""
    if not texto_pdf:
        return None

    padroes_url = [
        r'https?://[^\s<>"\']+',
        r'www\.[a-zA-Z0-9][a-zA-Z0-9\-]*\.[^\s<>"\']+',
        r'[a-zA-Z0-9][a-zA-Z0-9\-]*\.(?:com|net|org)\.br[^\s<>"\']*',
    ]

    dominios_gov = [
        "pncp.gov.br", "gov.br", "compras.gov.br",
        "comprasnet.gov.br", "licitacoes-e.com.br"
    ]

    for padrao in padroes_url:
        matches = re.findall(padrao, texto_pdf, re.IGNORECASE)
        for url in matches:
            url_lower = url.lower()
            if any(dom in url_lower for dom in dominios_gov):
                continue

            url_normalizada = normalizar_url_v17(url)
            if url_normalizada:
                return url_normalizada

    return None


# ============================================================
# VALIDACAO DE URL V19 (MODIFICADO - USA WHITELIST DINAMICA)
# ============================================================

# NOTA: A whitelist agora e carregada do Supabase via WhitelistLoader.
# O fallback hardcoded esta na classe WhitelistLoader.FALLBACK_WHITELIST.

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


def _esta_na_whitelist_miner(url: str, whitelist: set) -> bool:
    """
    Verifica se o dominio da URL esta na whitelist.

    Args:
        url: URL a verificar
        whitelist: Conjunto de dominios validos

    Returns:
        True se o dominio estiver na whitelist
    """
    dominio = _extrair_dominio_miner(url)
    if not dominio:
        return False
    for dominio_valido in whitelist:
        if dominio == dominio_valido or dominio.endswith("." + dominio_valido):
            return True
    return False


def validar_url_link_leiloeiro_v19(url: str, whitelist: set = None) -> tuple:
    """
    Valida se uma URL pode ser usada como link_leiloeiro.

    Args:
        url: URL a validar
        whitelist: Conjunto de dominios validos (opcional, usa fallback se None)

    Returns:
        tuple: (valido, confianca, motivo)
    """
    if not url:
        return False, 0, "url_vazia"

    # Se nao passou whitelist, usa o fallback da classe WhitelistLoader
    if whitelist is None:
        whitelist = WhitelistLoader.FALLBACK_WHITELIST

    url_limpa = url.strip()
    url_lower = url_limpa.lower()

    if url_lower.startswith(("http://", "https://")):
        return (True, 100, None) if _esta_na_whitelist_miner(url_limpa, whitelist) else (True, 80, None)

    if url_lower.startswith("www."):
        return (True, 100, None) if _esta_na_whitelist_miner(url_limpa, whitelist) else (True, 60, None)

    if _esta_na_whitelist_miner(url_limpa, whitelist):
        return True, 100, None

    if REGEX_TLD_COLADO_MINER.search(url_limpa):
        return False, 0, "tld_colado_em_palavra"

    return False, 0, "sem_prefixo_ou_whitelist"


def processar_link_pncp_v19(
    link_sistema: Optional[str],
    link_edital: Optional[str],
    whitelist: set = None
) -> dict:
    """
    Processa links da API PNCP aplicando validacao V19.

    Args:
        link_sistema: Link do sistema de origem
        link_edital: Link alternativo do edital
        whitelist: Conjunto de dominios validos (opcional)
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

    # V17 FIX: Limpar URL antes de validar
    link_candidato = normalizar_url_v17(link_candidato) or link_candidato

    valido, confianca, motivo = validar_url_link_leiloeiro_v19(link_candidato, whitelist)

    resultado["link_leiloeiro_raw"] = link_candidato
    resultado["link_leiloeiro_valido"] = valido
    resultado["link_leiloeiro_origem_tipo"] = "pncp_api"
    resultado["link_leiloeiro_origem_ref"] = f"pncp_api:{campo_origem}"
    resultado["link_leiloeiro_confianca"] = confianca

    if valido:
        resultado["link_leiloeiro"] = link_candidato

    return resultado


# ============================================================
# EXTRACAO DE OBJETO_RESUMIDO E GERACAO DE TAGS
# ============================================================

def extrair_objeto_resumido(texto: str, max_chars: int = 500) -> str:
    """Extrai objeto_resumido de um texto."""
    if not texto or not texto.strip():
        return ""

    texto_limpo = texto.strip()

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

    if len(texto_limpo) <= max_chars:
        return re.sub(r'\s+', ' ', texto_limpo)

    primeira_frase = re.split(r'[.\n]', texto_limpo)[0]
    if len(primeira_frase) >= 20:
        return re.sub(r'\s+', ' ', primeira_frase)[:max_chars]

    return ""


# ============================================================
# TAXONOMIA AUTOMOTIVA LOADER - V18.2
# ============================================================
# NOTA: Carrega taxonomia do Supabase com fallback hardcoded.
# APENAS termos automotivos - SEM imoveis/mobiliario/eletronicos.
# ============================================================

class TaxonomiaLoader:
    """
    Carrega taxonomia automotiva do Supabase para classificacao de editais.

    V18.2: Nova funcionalidade que substitui o dicionario TAGS_KEYWORDS.
    Beneficios:
    - Adicionar/remover termos sem deploy
    - Fallback seguro se Supabase falhar
    - Apenas termos de VEICULOS (sem imoveis, mobiliario, eletronicos)
    """

    # Fallback hardcoded: APENAS termos automotivos
    # REMOVIDO: IMOVEL, MOBILIARIO, ELETRONICO
    FALLBACK_TAXONOMIA = {
        # TIPO - Categorias principais de veiculos
        "VEICULO": ["veiculo", "veiculos", "automovel", "automoveis", "carro", "carros", "automotor", "automotivo"],
        "SUCATA": ["sucata", "sucatas", "inservivel", "inserviveis", "ferroso", "ferrosos", "sucateado"],
        "MOTO": ["moto", "motos", "motocicleta", "motocicletas", "ciclomotor", "ciclomotores", "motociclo"],
        "CAMINHAO": ["caminhao", "caminhoes", "caminhonete", "camionete", "truck", "trucks", "cavalo mecanico"],
        "ONIBUS": ["onibus", "microonibus", "micro-onibus", "micro onibus"],
        "CARRETA": ["carreta", "carretas", "semi-reboque", "semirreboque", "reboque", "reboques", "implemento rodoviario"],
        "MAQUINARIO": [
            "maquina", "maquinas", "trator", "tratores", "retroescavadeira", "escavadeira",
            "pa carregadeira", "carregadeira", "motoniveladora", "patrol"
        ],
        "DOCUMENTADO": ["documentado", "documentados", "com documento", "documento ok"],
        "APREENDIDO": ["apreendido", "apreendidos", "patio", "removido", "removidos", "custodia"],
        # MARCAS - Geram tags de tipo correspondente
        # Leves
        "MARCA_LEVE": [
            "volkswagen", "vw", "volks", "chevrolet", "gm", "fiat", "ford", "toyota", "honda",
            "hyundai", "renault", "peugeot", "citroen", "nissan", "mitsubishi", "jeep", "bmw", "audi"
        ],
        # Pesados
        "MARCA_PESADO": [
            "mercedes-benz", "mercedes", "mb", "scania", "volvo", "iveco", "daf", "man", "agrale"
        ],
        # Motos
        "MARCA_MOTO": ["yamaha", "suzuki", "kawasaki", "triumph", "dafra", "shineray"],
        # Maquinas
        "MARCA_MAQUINA": [
            "caterpillar", "cat", "john deere", "jd", "massey ferguson", "massey", "mf",
            "valtra", "new holland", "nh", "case", "jcb"
        ],
        # Carretas
        "MARCA_CARRETA": ["randon", "facchini", "guerra", "librelato", "noma"],
        # Onibus
        "MARCA_ONIBUS": ["marcopolo", "caio", "busscar", "neobus"],
        # MODELOS POPULARES - Para matching mais preciso
        "MODELO_LEVE": [
            "gol", "polo", "onix", "prisma", "corsa", "celta", "uno", "palio", "strada", "toro",
            "hilux", "corolla", "civic", "fit", "hb20", "creta", "sandero", "logan", "duster",
            "ranger", "ecosport", "ka", "fiesta", "focus", "voyage", "saveiro", "amarok"
        ],
        "MODELO_MOTO": [
            "cg", "titan", "fan", "biz", "bros", "xre", "cb", "twister", "hornet", "pcx",
            "ybr", "factor", "fazer", "lander", "crosser", "nmax", "xtz", "intruder", "yes"
        ],
        "MODELO_PESADO": [
            "atego", "actros", "axor", "accelo", "constellation", "delivery", "worker",
            "r440", "r450", "fh", "fh460", "vm", "daily", "tector", "stralis", "cargo"
        ],
    }

    # Mapeamento de categoria -> tag gerada
    CATEGORIA_TO_TAG = {
        "VEICULO": "VEICULO",
        "SUCATA": "SUCATA",
        "MOTO": "MOTO",
        "CAMINHAO": "CAMINHAO",
        "ONIBUS": "ONIBUS",
        "CARRETA": "CARRETA",
        "MAQUINARIO": "MAQUINARIO",
        "DOCUMENTADO": "DOCUMENTADO",
        "APREENDIDO": "APREENDIDO",
        "MARCA_LEVE": "VEICULO",
        "MARCA_PESADO": "CAMINHAO",
        "MARCA_MOTO": "MOTO",
        "MARCA_MAQUINA": "MAQUINARIO",
        "MARCA_CARRETA": "CARRETA",
        "MARCA_ONIBUS": "ONIBUS",
        "MODELO_LEVE": "VEICULO",
        "MODELO_MOTO": "MOTO",
        "MODELO_PESADO": "CAMINHAO",
    }

    def __init__(self, supabase_url: str, supabase_key: str):
        """
        Inicializa o loader com credenciais do Supabase.
        """
        self.supabase_url = supabase_url
        self.supabase_key = supabase_key
        self.client = None
        self.logger = logging.getLogger("TaxonomiaLoader")

        if supabase_url and supabase_key:
            try:
                from supabase import create_client
                self.client = create_client(supabase_url, supabase_key)
            except ImportError:
                self.logger.warning("Biblioteca supabase nao instalada")
            except Exception as e:
                self.logger.warning(f"Erro ao conectar Supabase: {e}")

    def carregar(self) -> tuple[dict, bool]:
        """
        Carrega taxonomia do Supabase.

        Returns:
            tuple: (dict_taxonomia, veio_do_db)
            - dict_taxonomia: Dicionario {tag: [termos]} para matching
            - veio_do_db: True se carregou do Supabase, False se usou fallback
        """
        if not self.client:
            self.logger.warning("Supabase nao conectado - usando taxonomia fallback")
            return self._converter_fallback_para_dict(), False

        try:
            # Query: SELECT categoria, termo, sinonimos, tag_gerada FROM taxonomia_automotiva WHERE ativo = TRUE
            result = self.client.table("taxonomia_automotiva").select(
                "categoria, termo, sinonimos, tag_gerada"
            ).eq("ativo", True).execute()

            if result.data and len(result.data) > 0:
                taxonomia = self._processar_resultado_db(result.data)
                self.logger.info(f"Taxonomia carregada do Supabase: {len(result.data)} termos")
                return taxonomia, True
            else:
                self.logger.warning("Nenhum termo na taxonomia do Supabase - usando fallback")
                return self._converter_fallback_para_dict(), False

        except Exception as e:
            self.logger.error(f"Erro ao carregar taxonomia do Supabase: {e}")
            self.logger.warning("Usando taxonomia fallback")
            return self._converter_fallback_para_dict(), False

    def _processar_resultado_db(self, rows: list) -> dict:
        """
        Processa resultado do Supabase e converte para formato de matching.

        Formato de saida: {tag_gerada: [lista_de_termos]}
        """
        taxonomia = {}

        for row in rows:
            tag = row.get("tag_gerada")
            termo = row.get("termo", "").lower()
            sinonimos = row.get("sinonimos") or []

            if not tag or not termo:
                continue

            if tag not in taxonomia:
                taxonomia[tag] = []

            # Adiciona termo principal
            if termo not in taxonomia[tag]:
                taxonomia[tag].append(termo)

            # Adiciona sinonimos
            for sinonimo in sinonimos:
                sinonimo_lower = sinonimo.lower().strip()
                if sinonimo_lower and sinonimo_lower not in taxonomia[tag]:
                    taxonomia[tag].append(sinonimo_lower)

        return taxonomia

    def _converter_fallback_para_dict(self) -> dict:
        """
        Converte o fallback hardcoded para formato de matching.
        """
        taxonomia = {}

        for categoria, termos in self.FALLBACK_TAXONOMIA.items():
            tag = self.CATEGORIA_TO_TAG.get(categoria, categoria)

            if tag not in taxonomia:
                taxonomia[tag] = []

            for termo in termos:
                termo_lower = termo.lower()
                if termo_lower not in taxonomia[tag]:
                    taxonomia[tag].append(termo_lower)

        return taxonomia


def gerar_tags_v18(titulo: str, descricao: str, objeto: str, taxonomia: dict = None) -> list:
    """
    V18.2: Gera tags baseadas na taxonomia automotiva carregada do Supabase.

    IMPORTANTE: Apenas tags de VEICULOS sao geradas.
    Tags de IMOVEL, MOBILIARIO, ELETRONICO foram REMOVIDAS.

    Args:
        titulo: Titulo do edital
        descricao: Descricao do edital
        objeto: Objeto/conteudo do edital
        taxonomia: Dicionario {tag: [termos]} carregado do Supabase

    Returns:
        Lista de tags encontradas (ordenada alfabeticamente)
    """
    # Se nao passou taxonomia, usa fallback
    if taxonomia is None:
        loader = TaxonomiaLoader("", "")
        taxonomia = loader._converter_fallback_para_dict()

    texto_completo = f"{titulo or ''} {descricao or ''} {objeto or ''}".lower()
    texto_normalizado = unicodedata.normalize('NFKD', texto_completo)
    texto_normalizado = texto_normalizado.encode('ASCII', 'ignore').decode('ASCII').lower()

    tags_encontradas = set()

    for tag, keywords in taxonomia.items():
        for keyword in keywords:
            keyword_norm = unicodedata.normalize('NFKD', keyword)
            keyword_norm = keyword_norm.encode('ASCII', 'ignore').decode('ASCII').lower()

            if keyword_norm in texto_normalizado or keyword in texto_completo:
                tags_encontradas.add(tag)
                break

    return sorted(list(tags_encontradas))


# Alias para compatibilidade com codigo existente
def gerar_tags_v17(titulo: str, descricao: str, objeto: str) -> list:
    """
    Wrapper de compatibilidade que usa gerar_tags_v18 com fallback.
    """
    return gerar_tags_v18(titulo, descricao, objeto, taxonomia=None)


def deve_rejeitar_por_categoria(tags: list) -> tuple[bool, str]:
    """
    V19 FIX: Rejeita editais que nao sao de veiculos/sucatas.
    Ache Sucatas e focado APENAS em leiloes de veiculos.

    Retorna: (deve_rejeitar, motivo)
    """
    if not tags:
        return False, ""

    tem_veiculo = any(t in tags for t in ["VEICULO", "SUCATA", "MOTO", "CAMINHAO", "ONIBUS"])
    tem_imovel = "IMOVEL" in tags

    # Rejeitar se tem IMOVEL mas NAO tem nenhum tipo de veiculo
    if tem_imovel and not tem_veiculo:
        return True, "Edital de imovel sem veiculos - fora do escopo do Ache Sucatas"

    return False, ""


# ============================================================
# CONFIGURACAO - V18: ADICIONA OPENAI
# ============================================================

@dataclass
class MinerConfig:
    """Configuracoes do minerador V18."""

    # Supabase
    supabase_url: str = ""
    supabase_key: str = ""

    # PNCP API - V17: RESTAURA API de detalhes
    pncp_base_url: str = "https://pncp.gov.br/api"
    pncp_search_url: str = "https://pncp.gov.br/api/search/"
    # V17 FIX: URL correta da API de detalhes (endpoint atualizado em Jan/2026)
    pncp_consulta_url: str = "https://pncp.gov.br/api/consulta/v1/orgaos"

    # Rate limiting
    rate_limit_seconds: float = 1.0
    search_term_delay_seconds: float = 2.0
    search_page_delay_seconds: float = 0.5

    # Busca
    # V18.4 FIX: Aumentado de 1 para 7 dias para capturar mais leiloes futuros
    dias_retroativos: int = 7
    paginas_por_termo: int = 3
    itens_por_pagina: int = 20

    # Timeouts e retries
    timeout_seconds: int = 45
    max_retries: int = 3
    retry_backoff_base: float = 2.0

    # Filtros
    # 1=Pregao Eletronico, 6=Leilao Eletronico, 7=Leilao Presencial, 13=Concorrencia
    modalidades: str = "1|6|7|13"
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

    # V18: OpenAI Configuration
    openai_api_key: str = field(default_factory=lambda: os.environ.get("OPENAI_API_KEY", ""))
    openai_model: str = "gpt-4o-mini"  # Modelo rapido e barato
    enable_ai_enrichment: bool = True  # Flag para habilitar/desabilitar enriquecimento IA

    # Fase 2: Processamento Incremental
    force_reprocess: bool = False  # Se True, reprocessa mesmo editais que já existem no banco

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
        "bens moveis inserviveis",
        "carros",
        "veiculos",
        "motos",
        "carro",
        "rodantes",
        "sucatas",
        "automoveis",
    ])


# ============================================================
# LOGGING
# ============================================================

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-8s | [%(name)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S"
)
logger = logging.getLogger("MinerV18")


# ============================================================
# EXCECOES CUSTOMIZADAS
# ============================================================

class PNCPError(Exception):
    """Erro generico do PNCP."""
    pass


class RateLimitError(PNCPError):
    """Rate limit atingido."""
    pass


# ============================================================
# UTILS
# ============================================================

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
# V18: COMPONENTE DE INTELIGENCIA ARTIFICIAL (OpenAIEnricher)
# ============================================================

class OpenAIEnricher:
    """
    Componente de Inteligencia Artificial (V18).
    Transforma texto bruto e metadados em inteligencia de mercado.

    Brief 3.6: Inclui tracking de tokens para FinOps.
    V18.3: Inclui retry com backoff e circuit breaker para resiliencia.
    """

    # Precos OpenAI GPT-4o-mini (USD por 1M tokens) - Jan 2026
    PRICE_INPUT_PER_1M = 0.15
    PRICE_OUTPUT_PER_1M = 0.60

    # V18.3: Configuracao de resiliencia
    MAX_RETRIES = 3
    RETRY_BASE_DELAY = 2.0  # segundos
    CIRCUIT_FAILURE_THRESHOLD = 5
    CIRCUIT_RECOVERY_TIMEOUT = 120.0  # segundos

    def __init__(self, api_key: str, model: str):
        """
        Inicializa o enriquecedor com a API OpenAI.

        Args:
            api_key: Chave da API OpenAI
            model: Modelo a ser usado (ex: gpt-4o-mini)
        """
        self.client = None
        self.model = model
        self.logger = logging.getLogger("AI_Enricher")

        # Brief 3.6: Contadores de tokens para FinOps
        self.total_input_tokens = 0
        self.total_output_tokens = 0
        self.total_requests = 0

        # V18.3: Contadores de resiliencia
        self.retry_count = 0
        self.circuit_rejections = 0

        # V18.3: Circuit breaker para OpenAI
        self.circuit = circuit_registry.get_or_create(
            name="openai",
            failure_threshold=self.CIRCUIT_FAILURE_THRESHOLD,
            recovery_timeout=self.CIRCUIT_RECOVERY_TIMEOUT,
        )

        if not OPENAI_AVAILABLE:
            self.logger.warning("Biblioteca openai nao instalada - enriquecimento IA desabilitado")
            return

        if api_key:
            try:
                self.client = OpenAI(api_key=api_key)
                self.logger.info(f"OpenAI Enricher inicializado com modelo: {model}")
            except Exception as e:
                self.logger.error(f"Erro ao inicializar OpenAI: {e}")
                self.client = None
        else:
            self.logger.warning("OPENAI_API_KEY nao configurada - enriquecimento IA desabilitado")

    def get_estimated_cost(self) -> float:
        """Brief 3.6: Retorna custo estimado total em USD."""
        input_cost = (self.total_input_tokens / 1_000_000) * self.PRICE_INPUT_PER_1M
        output_cost = (self.total_output_tokens / 1_000_000) * self.PRICE_OUTPUT_PER_1M
        return round(input_cost + output_cost, 6)

    def get_token_stats(self) -> dict:
        """Brief 3.6: Retorna estatisticas de uso de tokens."""
        return {
            "total_requests": self.total_requests,
            "total_input_tokens": self.total_input_tokens,
            "total_output_tokens": self.total_output_tokens,
            "total_tokens": self.total_input_tokens + self.total_output_tokens,
            "estimated_cost_usd": self.get_estimated_cost(),
            # V18.3: Metricas de resiliencia
            "retry_count": self.retry_count,
            "circuit_rejections": self.circuit_rejections,
            "circuit_state": self.circuit.state.value if self.circuit else "unknown",
        }

    def _call_openai_api_with_retry(self, messages: list, max_tokens: int = 500) -> dict:
        """
        V18.3: Chama a API OpenAI com retry e backoff exponencial.

        Args:
            messages: Lista de mensagens para a API
            max_tokens: Maximo de tokens na resposta

        Returns:
            Dicionario com dados parseados ou {} em caso de falha

        Raises:
            Exception: Se todas as tentativas falharem
        """
        last_exception = None

        for attempt in range(self.MAX_RETRIES + 1):
            try:
                response = self.client.chat.completions.create(
                    model=self.model,
                    messages=messages,
                    response_format={"type": "json_object"},
                    temperature=0.1,
                    max_tokens=max_tokens,
                    timeout=30.0,  # V18.3: Timeout explicito
                )

                content = response.choices[0].message.content
                dados = json.loads(content)

                # Registrar uso de tokens para FinOps
                if hasattr(response, 'usage') and response.usage:
                    self.total_input_tokens += response.usage.prompt_tokens
                    self.total_output_tokens += response.usage.completion_tokens
                    self.total_requests += 1

                return dados

            except json.JSONDecodeError as e:
                # Erro de parsing nao deve causar retry
                self.logger.error(f"Erro ao parsear resposta JSON da IA: {e}")
                return {}

            except Exception as e:
                last_exception = e
                error_type = type(e).__name__

                # Verificar se e erro retriable
                is_retriable = (
                    "timeout" in str(e).lower() or
                    "rate" in str(e).lower() or
                    "limit" in str(e).lower() or
                    "connection" in str(e).lower() or
                    "503" in str(e) or
                    "502" in str(e) or
                    "500" in str(e) or
                    "429" in str(e)
                )

                if not is_retriable or attempt >= self.MAX_RETRIES:
                    self.logger.error(
                        f"[OPENAI] Falha definitiva apos {attempt + 1} tentativas: {error_type}: {e}"
                    )
                    raise

                # Calcular delay com backoff
                delay = min(
                    self.RETRY_BASE_DELAY * (2 ** attempt),
                    60.0
                ) * (0.75 + __import__('random').random() * 0.5)

                self.retry_count += 1
                self.logger.warning(
                    f"[OPENAI] Tentativa {attempt + 1}/{self.MAX_RETRIES + 1} falhou: {error_type}. "
                    f"Retry em {delay:.1f}s"
                )

                time.sleep(delay)

        # Nao deveria chegar aqui
        if last_exception:
            raise last_exception
        return {}

    def enriquecer_edital(self, texto_pdf: str, metadados_pncp: dict) -> dict:
        """
        Analisa o edital e retorna dados estruturados.

        Args:
            texto_pdf: Texto extraido do PDF do edital
            metadados_pncp: Dicionario com metadados do PNCP (titulo, orgao_nome, municipio)

        Returns:
            Dicionario com dados enriquecidos:
            - titulo_comercial: Titulo vendedor para o edital
            - resumo_oportunidade: Resumo comercial (max 280 chars)
            - lista_veiculos: Lista dos principais veiculos/bens
            - url_leilao_oficial: URL do leiloeiro corrigida
        """
        # Verificacoes de seguranca
        if not self.client:
            return {}

        if not texto_pdf or len(texto_pdf) < 100:
            self.logger.debug("Texto PDF muito curto para enriquecimento")
            return {}

        # OTIMIZACAO DE CUSTO:
        # Envia apenas o inicio (definicao) e o fim (links/anexos) do edital.
        # Editais grandes queimam tokens desnecessarios.
        texto_input = (
            f"--- INICIO DO EDITAL ---\n{texto_pdf[:4000]}\n"
            f"\n--- ... CORTE DE CONTEUDO ... ---\n"
            f"\n--- FINAL DO EDITAL ---\n{texto_pdf[-3000:]}"
        )

        system_prompt = """
        Voce e o motor de inteligencia do 'Ache Sucatas', um DaaS para compradores de leiloes.
        Sua missao e ler editais publicos (muitas vezes mal formatados) e extrair dados comerciais precisos.

        REGRAS DE EXTRACAO:
        1. TITULO_COMERCIAL: Ignore o juridiques. Crie um titulo vendedor: [Tipo Ativo] + [Cidade/Orgao] + [Tipo Venda]. Ex: "Leilao de Frota (Carros e Motos) - Prefeitura de Salto/SP".
        2. RESUMO: Max 280 chars. Resuma a oportunidade. Diga se tem documento ou sucata. Diga se e Online ou Presencial.
        3. LISTA_VEICULOS: Liste apenas os modelos principais (Ex: "Gol, Uno, Caminhao MB 1113"). Agrupe por categorias (Leves, Pesados, Motos). Ignore moveis/eletronicos.
        4. URL_LEILOEIRO: CRITICO. Encontre o site do leiloeiro ou portal de compras.
           - O texto pode ter erros de OCR (ex: "www. leiloes .com" ou "portal\ndecompras").
           - VOCE DEVE CORRIGIR E RECONSTRUIR A URL para um formato valido de navegador (https://...).
           - Se houver multiplas URLs, priorize a plataforma de lances.

        Retorne APENAS um JSON estrito com estas chaves:
        {
            "titulo_comercial": "string",
            "resumo_oportunidade": "string",
            "lista_veiculos": "string",
            "url_leilao_oficial": "string ou null"
        }
        """

        user_prompt = f"""
        CONTEXTO (PNCP):
        Titulo Original: {metadados_pncp.get('titulo', '')}
        Orgao: {metadados_pncp.get('orgao_nome', '')}
        Cidade: {metadados_pncp.get('municipio', '')}

        TEXTO DO EDITAL (PDF):
        {texto_input}
        """

        # V18.3: Verificar circuit breaker antes de chamar API
        if self.circuit.state.value == "open":
            self.circuit_rejections += 1
            self.logger.warning(
                f"[CIRCUIT] OpenAI circuit OPEN - chamada rejeitada "
                f"(rejections={self.circuit_rejections})"
            )
            return {}

        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt}
        ]

        try:
            self.logger.debug("Enviando edital para analise IA (com resiliencia)...")

            # V18.3: Usar circuit breaker + retry
            dados = self.circuit.call(
                self._call_openai_api_with_retry,
                messages=messages,
                max_tokens=500,
                fallback=lambda **kw: {},  # Fallback retorna dict vazio
            )

            if dados:
                self.logger.debug(f"IA retornou: {list(dados.keys())}")
            return dados

        except CircuitOpenError:
            self.circuit_rejections += 1
            self.logger.warning("[CIRCUIT] OpenAI circuit aberto - usando fallback")
            return {}

        except Exception as e:
            self.logger.error(f"[OPENAI] Falha na IA apos retry e circuit breaker: {e}")
            return {}


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
        # V19 FIX: Penalizar imoveis - Ache Sucatas e apenas para veiculos
        "imóvel": -40, "imovel": -40, "imóveis": -40, "imoveis": -40,
        "terreno": -35, "terrenos": -35,
        "edificio": -35, "edifício": -35,
        "lote urbano": -30, "lote rural": -30,
        "área urbana": -25, "area urbana": -25,
        "área rural": -25, "area rural": -25,
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
# CLIENTE PNCP - V17: COM API DE DETALHES (RESTAURADA)
# ============================================================

class PNCPClient:
    """
    Cliente para APIs do PNCP.
    V17: RESTAURA API de detalhes para obter campos obrigatorios.
    """

    def __init__(self, config: MinerConfig):
        self.config = config
        self.http = httpx.Client(
            timeout=config.timeout_seconds,
            headers={"User-Agent": config.user_agent},
            follow_redirects=True  # V17 FIX: Seguir redirects automaticamente
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
            "data_inicial": data_inicial,
            "data_final": data_final,
        }

        if self.config.modalidades:
            params["modalidades"] = self.config.modalidades

        try:
            response = self._retry_request("GET", self.config.pncp_search_url, params)

            if response and response.status_code == 200:
                return response.json()
            return None

        except Exception as e:
            self.logger.error(f"Erro na busca: {e}")
            return None

    def obter_detalhes(self, pncp_id: str) -> Optional[dict]:
        """
        V17: RESTAURADO - Obtem detalhes do edital via API de consulta.

        Essa API retorna campos criticos:
        - dataAberturaProposta -> data_leilao
        - valorTotalEstimado -> valor_estimado
        - dataPublicacaoPncp -> data_publicacao

        URL: https://pncp.gov.br/pncp-api/v1/orgaos/{cnpj}/compras/{ano}/{seq}
        """
        # Parsear pncp_id: formato "CNPJ-ESFERA-SEQ/ANO" ou "CNPJ-ESFERA-SEQ-ANO"
        pncp_id_normalizado = pncp_id.replace("/", "-")
        parts = pncp_id_normalizado.split("-")

        if len(parts) < 4:
            self.logger.debug(f"pncp_id invalido para detalhes: {pncp_id}")
            return None

        cnpj = parts[0]
        # esfera = parts[1]  # nao usado na URL
        seq = parts[2]
        ano = parts[3]

        url = f"{self.config.pncp_consulta_url}/{cnpj}/compras/{ano}/{seq}"

        try:
            response = self._retry_request("GET", url)

            if response and response.status_code == 200:
                return response.json()
            return None

        except Exception as e:
            self.logger.debug(f"Erro ao obter detalhes: {e}")
            return None

    def obter_arquivos(self, pncp_id: str) -> List[dict]:
        """Obtem lista de arquivos do edital."""
        pncp_id_normalizado = pncp_id.replace("/", "-")

        parts = pncp_id_normalizado.split("-")
        if len(parts) < 4:
            return []

        cnpj = parts[0]
        esfera = parts[1]
        sequencial = parts[2]
        ano = parts[3]

        url = f"{self.config.pncp_base_url}/pncp/v1/orgaos/{cnpj}/compras/{ano}/{sequencial}/arquivos"

        try:
            response = self._retry_request("GET", url)

            if response and response.status_code == 200:
                return response.json() if isinstance(response.json(), list) else []
            return []

        except Exception as e:
            self.logger.debug(f"Erro ao obter arquivos: {e}")
            return []

    def baixar_arquivo(self, url: str) -> Optional[bytes]:
        """Baixa um arquivo do PNCP."""
        try:
            response = self._retry_request("GET", url)

            if response and response.status_code == 200:
                return response.content
            return None

        except Exception as e:
            self.logger.debug(f"Erro ao baixar arquivo: {e}")
            return None


# ============================================================
# REPOSITORIO SUPABASE
# ============================================================

class SupabaseRepository:
    """Repositorio para persistencia no Supabase."""

    def __init__(self, config: MinerConfig):
        self.config = config
        self.client = None
        self.logger = logging.getLogger(__name__)
        self.enable_supabase = False

        if not config.supabase_url or not config.supabase_key:
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

            tags = edital.get("tags", [])
            if isinstance(tags, str):
                tags = [t.strip() for t in tags.split(",") if t.strip()]

            def convert_date_to_iso(date_str):
                if not date_str:
                    return None
                if isinstance(date_str, str) and "-" in date_str:
                    parts = date_str.split("-")
                    if len(parts) == 3 and len(parts[0]) == 2:
                        return f"{parts[2]}-{parts[1]}-{parts[0]}"
                return date_str

            dados = {
                "pncp_id": pncp_id,
                "id_interno": pncp_id,
                "n_edital": edital.get("n_edital"),
                "titulo": edital.get("titulo"),
                "descricao": edital.get("descricao"),
                "orgao": edital.get("orgao_nome"),
                "uf": edital.get("uf"),
                "cidade": edital.get("municipio"),
                "data_publicacao": convert_date_to_iso(edital.get("data_publicacao")),
                "data_leilao": convert_date_to_iso(edital.get("data_leilao")),
                "modalidade_leilao": edital.get("modalidade"),
                "valor_estimado": edital.get("valor_estimado"),
                "link_pncp": edital.get("link_pncp"),
                "link_leiloeiro": edital.get("link_leiloeiro"),
                "score": edital.get("score"),
                "storage_path": edital.get("storage_path"),
                "tags": tags,
                "produtos_destaque": edital.get("produtos_destaque"),  # V18: Campo novo
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

    def iniciar_execucao(self, config: MinerConfig, run_id: str = None) -> Optional[int]:
        """
        Registra inicio de execucao do miner.

        Brief 2.2: Inclui run_id para correlacao com QualityReport.
        """
        if not self.enable_supabase:
            return None

        try:
            dados = {
                "versao_miner": "V18",
                "janela_temporal_horas": config.dias_retroativos * 24,
                "termos_buscados": len(config.search_terms),
                "paginas_por_termo": config.paginas_por_termo,
                "status": "RUNNING",
                "inicio": datetime.now().isoformat(),
                "run_id": run_id,  # Brief 2.2: Correlacao com QualityReport
                "modo_processamento": "FULL" if config.force_reprocess else "INCREMENTAL",
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
        status: str = "SUCCESS",
        quality_report: QualityReport = None,
        finops: dict = None
    ):
        """
        Finaliza registro de execucao.

        Brief 2.2: Inclui metricas do QualityReport para analise historica.
        Brief 3.6: Inclui metricas de FinOps (custos).
        """
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
                # Brief 2.1: Processamento incremental
                "editais_skip_existe": stats.get("editais_skip_existe", 0),
            }

            # Brief 2.2: Metricas do QualityReport
            if quality_report:
                dados["total_processados"] = quality_report.executed_total
                dados["total_validos"] = quality_report.valid_count
                dados["total_quarentena"] = quality_report.total_quarentena
                dados["taxa_validos_percent"] = quality_report.taxa_validos_percent
                dados["taxa_quarentena_percent"] = quality_report.taxa_quarentena_percent
                dados["duracao_segundos"] = quality_report.duration_seconds

            # Brief 3.6: Metricas de FinOps
            if finops:
                dados["cost_estimated_total"] = finops.get("cost_total", 0)
                dados["cost_openai_estimated"] = finops.get("cost_openai", 0)
                dados["num_pdfs"] = finops.get("num_pdfs", 0)
                dados["custo_por_mil_registros"] = finops.get("custo_por_mil", 0)

            self.client.table("miner_execucoes").update(dados).eq(
                "id", execucao_id
            ).execute()

        except Exception as e:
            self.logger.error(f"Erro ao finalizar execucao: {e}")

    def salvar_quality_report(
        self,
        quality_report: QualityReport,
        execucao_id: int = None
    ) -> bool:
        """
        Brief 3.2: Persiste QualityReport detalhado na tabela quality_reports.

        Guarda métricas completas incluindo breakdown por status e top_errors.
        """
        if not self.enable_supabase or not quality_report:
            return False

        try:
            # Calcular top errors a partir do QualityReport
            top_errors = []
            if hasattr(quality_report, 'error_counts') and quality_report.error_counts:
                total = sum(quality_report.error_counts.values())
                for code, count in sorted(
                    quality_report.error_counts.items(),
                    key=lambda x: x[1],
                    reverse=True
                )[:10]:
                    top_errors.append({
                        "reason_code": code,
                        "count": count,
                        "percent": round(100.0 * count / total, 2) if total > 0 else 0
                    })

            dados = {
                "run_id": quality_report.run_id,
                "execucao_id": execucao_id,
                "total_processados": quality_report.executed_total,
                "total_validos": quality_report.valid_count,
                "total_draft": getattr(quality_report, 'draft_count', 0),
                "total_not_sellable": getattr(quality_report, 'not_sellable_count', 0),
                "total_rejected": getattr(quality_report, 'rejected_count', 0),
                "taxa_validos_percent": quality_report.taxa_validos_percent,
                "taxa_quarentena_percent": quality_report.taxa_quarentena_percent,
                "duracao_segundos": quality_report.duration_seconds,
                "top_errors": top_errors,
                "storage_path": f"quality_reports/{quality_report.run_id}.json",
            }

            # UPSERT: se já existe com mesmo run_id, atualiza
            self.client.table("quality_reports").upsert(
                dados,
                on_conflict="run_id"
            ).execute()

            self.logger.info(f"QualityReport salvo na tabela: run_id={quality_report.run_id}")
            return True

        except Exception as e:
            self.logger.error(f"Erro ao salvar QualityReport: {e}")
            return False

    def registrar_evento(
        self,
        run_id: str,
        etapa: str,
        evento: str,
        nivel: str = "info",
        mensagem: str = None,
        dados: dict = None,
        duracao_ms: int = None,
        items_processados: int = 0,
        items_sucesso: int = 0,
        items_erro: int = 0
    ) -> bool:
        """
        Brief 3.4: Registra evento do pipeline para observabilidade.

        Etapas válidas: inicio, busca, coleta, pdf_download, pdf_parse,
                        extract, enrich, validate, upsert, quarantine, fim
        """
        if not self.enable_supabase:
            return False

        try:
            registro = {
                "run_id": run_id,
                "etapa": etapa,
                "evento": evento,
                "nivel": nivel,
                "mensagem": mensagem,
                "dados": dados or {},
                "duracao_ms": duracao_ms,
                "items_processados": items_processados,
                "items_sucesso": items_sucesso,
                "items_erro": items_erro,
            }

            self.client.table("pipeline_events").insert(registro).execute()
            return True

        except Exception as e:
            # Não logar erro para evitar loop infinito
            return False

    def criar_alerta(
        self,
        run_id: str,
        execucao_id: int,
        tipo: str,
        severidade: str,
        titulo: str,
        mensagem: str,
        dados: dict = None
    ) -> bool:
        """
        Cria um alerta no sistema de observabilidade.

        Tipos válidos:
            - high_quarantine_rate: Taxa de quarentena acima do limite
            - execution_failed: Execução falhou
            - long_duration: Duração anormalmente longa
            - no_valid_records: Nenhum registro válido
            - api_error: Erro de API externa
            - storage_error: Erro de storage
            - openai_error: Erro de OpenAI

        Severidades: info, warning, critical
        """
        if not self.enable_supabase:
            return False

        try:
            registro = {
                "run_id": run_id,
                "execucao_id": execucao_id,
                "tipo": tipo,
                "severidade": severidade,
                "titulo": titulo,
                "mensagem": mensagem,
                "dados": dados or {},
            }

            self.client.table("pipeline_alerts").insert(registro).execute()
            self.logger.warning(f"[ALERTA:{severidade.upper()}] {titulo}")

            # Enviar email para alertas críticos e warnings
            if severidade in ["critical", "warning"]:
                email_enviado = send_alert_email(
                    severidade=severidade,
                    titulo=titulo,
                    mensagem=mensagem,
                    dados=dados,
                    run_id=run_id
                )
                if email_enviado:
                    self.logger.info(f"[EMAIL] Alerta enviado por email")
                    # Atualizar registro no banco
                    try:
                        self.client.table("pipeline_alerts").update({
                            "email_enviado": True,
                            "email_enviado_at": datetime.utcnow().isoformat()
                        }).eq("run_id", run_id).eq("tipo", tipo).execute()
                    except Exception:
                        pass  # Não falhar se não conseguir atualizar

            return True

        except Exception as e:
            self.logger.error(f"Erro ao criar alerta: {e}")
            return False

    def verificar_e_criar_alertas(
        self,
        run_id: str,
        execucao_id: int,
        quality_report,
        duracao_segundos: float,
        status: str
    ) -> int:
        """
        Verifica métricas e cria alertas automaticamente.

        Regras:
            - Taxa quarentena > 30%: critical
            - Taxa quarentena > 15%: warning
            - Execução falhou: critical
            - Duração > 30 min: warning
            - Nenhum válido (com processados > 0): warning

        Retorna: número de alertas criados
        """
        alertas_criados = 0

        # 1. Verificar se execução falhou
        if status == "FAILED":
            self.criar_alerta(
                run_id=run_id,
                execucao_id=execucao_id,
                tipo="execution_failed",
                severidade="critical",
                titulo="Execucao do pipeline falhou",
                mensagem=f"A execucao {run_id} terminou com status FAILED.",
                dados={"status": status}
            )
            alertas_criados += 1

        # 2. Verificar taxa de quarentena
        if quality_report and quality_report.executed_total > 0:
            taxa_quarentena = quality_report.taxa_quarentena_percent

            if taxa_quarentena > 30:
                self.criar_alerta(
                    run_id=run_id,
                    execucao_id=execucao_id,
                    tipo="high_quarantine_rate",
                    severidade="critical",
                    titulo=f"Taxa de quarentena critica: {taxa_quarentena:.1f}%",
                    mensagem=f"A taxa de quarentena esta em {taxa_quarentena:.1f}%, muito acima do limite de 30%.",
                    dados={
                        "taxa_quarentena": taxa_quarentena,
                        "total_processados": quality_report.executed_total,
                        "total_quarentena": quality_report.total_quarentena,
                        "limite": 30
                    }
                )
                alertas_criados += 1
            elif taxa_quarentena > 15:
                self.criar_alerta(
                    run_id=run_id,
                    execucao_id=execucao_id,
                    tipo="high_quarantine_rate",
                    severidade="warning",
                    titulo=f"Taxa de quarentena elevada: {taxa_quarentena:.1f}%",
                    mensagem=f"A taxa de quarentena esta em {taxa_quarentena:.1f}%, acima do limite de 15%.",
                    dados={
                        "taxa_quarentena": taxa_quarentena,
                        "total_processados": quality_report.executed_total,
                        "total_quarentena": quality_report.total_quarentena,
                        "limite": 15
                    }
                )
                alertas_criados += 1

        # 3. Verificar se nenhum registro válido
        if quality_report and quality_report.executed_total > 0 and quality_report.valid_count == 0:
            self.criar_alerta(
                run_id=run_id,
                execucao_id=execucao_id,
                tipo="no_valid_records",
                severidade="warning",
                titulo="Nenhum registro valido na execucao",
                mensagem=f"Foram processados {quality_report.executed_total} registros, mas nenhum foi considerado valido.",
                dados={
                    "total_processados": quality_report.executed_total,
                    "total_quarentena": quality_report.total_quarentena
                }
            )
            alertas_criados += 1

        # 4. Verificar duração anormal (> 30 minutos)
        if duracao_segundos > 1800:  # 30 minutos
            self.criar_alerta(
                run_id=run_id,
                execucao_id=execucao_id,
                tipo="long_duration",
                severidade="warning",
                titulo=f"Execucao muito longa: {duracao_segundos/60:.1f} minutos",
                mensagem=f"A execucao levou {duracao_segundos/60:.1f} minutos, acima do esperado.",
                dados={
                    "duracao_segundos": duracao_segundos,
                    "duracao_minutos": duracao_segundos / 60
                }
            )
            alertas_criados += 1

        return alertas_criados

    def inserir_quarentena(self, rejection_row: dict) -> bool:
        """
        Insere registro na tabela de quarentena.

        IDEMPOTÊNCIA: Usa upsert com on_conflict(run_id, id_interno).
        Se o mesmo registro do mesmo run já existe, atualiza em vez de duplicar.

        BRIEF 1.2: Inclui reason_code e reason_detail para queries diretas.
        """
        if not self.enable_supabase:
            return False

        try:
            errors = rejection_row.get("errors", [])
            status = rejection_row.get("status", "unknown")

            # Extrair reason_code e reason_detail do primeiro erro
            if errors and len(errors) > 0:
                first_error = errors[0]
                reason_code = first_error.get("code", status)
                reason_detail = first_error.get("message", f"Status: {status}")[:500]
            else:
                reason_code = status
                reason_detail = f"Status: {status}"

            dados = {
                "run_id": rejection_row.get("run_id"),
                "id_interno": rejection_row.get("id_interno"),
                "status": status,
                "reason_code": reason_code,
                "reason_detail": reason_detail,
                "errors": errors,
                "raw_record": rejection_row.get("raw_record", {}),
                "normalized_record": rejection_row.get("normalized_record", {}),
            }

            # UPSERT: idempotência garantida via UNIQUE(run_id, id_interno)
            result = self.client.table("dataset_rejections").upsert(
                dados,
                on_conflict="run_id,id_interno"
            ).execute()
            return len(result.data) > 0

        except Exception as e:
            self.logger.error(f"Erro ao inserir na quarentena: {e}")
            return False

    def inserir_run_report(
        self,
        run_id: str,
        git_sha: str = None,
        job_name: str = "miner",
    ) -> bool:
        """
        Insere relatorio de execucao na tabela pipeline_run_reports.

        V18.3: Adiciona rastreamento de execucoes do Miner para auditoria.

        Args:
            run_id: ID unico da execucao
            git_sha: SHA do commit git (pode ser None)
            job_name: Nome do job (miner ou auditor)

        Returns:
            True se sucesso
        """
        if not self.enable_supabase:
            self.logger.warning("[RUN REPORT] Supabase desativado, ignorando run_report")
            return False

        metrics = None

        # Tentar RPC primeiro, fallback para queries se RPC falhar
        try:
            resp = self.client.rpc('get_pipeline_metrics', {}).execute()
            if resp.data:
                metrics = resp.data
                self.logger.debug("[RUN REPORT] Metricas obtidas via RPC")
        except Exception as rpc_err:
            self.logger.debug(f"[RUN REPORT] RPC get_pipeline_metrics indisponivel: {rpc_err}")

        # Fallback: calcular via queries diretas se RPC falhou ou retornou vazio
        if not metrics:
            self.logger.debug("[RUN REPORT] Usando fallback de queries para metricas")
            try:
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
            except Exception as query_err:
                self.logger.warning(f"[RUN REPORT] Erro obtendo metricas via queries: {query_err}")
                # Usar metricas zeradas como fallback final
                metrics = {
                    'total': 0, 'com_link': 0, 'sem_link': 0,
                    'com_link_valido_true': 0, 'com_link_valido_false': 0,
                    'com_link_valido_null': 0, 'origem_pncp_api': 0, 'origem_pdf_anexo': 0,
                }

        # Inserir relatorio
        try:
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
            self.logger.info(f"[RUN REPORT] Inserido relatorio: run_id={run_id}, job_name={job_name}, total={dados['total']}")
            return True

        except Exception as insert_err:
            self.logger.error(f"[RUN REPORT] Erro ao inserir na tabela pipeline_run_reports: {insert_err}")
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
# MINERADOR PRINCIPAL V18
# ============================================================

class MinerV18:
    """
    Minerador de editais do PNCP - Versao 18.

    NOVIDADE V18:
    - Enriquecimento com IA (OpenAI GPT-4o-mini)
    - Extracao de titulo comercial, resumo e lista de veiculos
    - Correcao automatica de URLs pelo modelo de IA

    MANTIDO DO V17:
    - API de detalhes para obter campos obrigatorios
    - Mapeamento EXCLUSIVO (Prompt Garantidor)
    - Limpeza de URLs
    - Validacao e roteamento para quarentena
    """

    def __init__(self, config: MinerConfig):
        self.config = config
        self.pncp = PNCPClient(config)
        self.repo = SupabaseRepository(config) if config.enable_supabase else None
        self.storage = StorageRepository(config) if config.enable_storage else None

        # V18: Inicializa o AI Enricher
        self.ai_enricher = OpenAIEnricher(config.openai_api_key, config.openai_model)

        # V18.1: Carregar whitelist do Supabase (com fallback hardcoded)
        loader = WhitelistLoader(config.supabase_url, config.supabase_key)
        self.whitelist_dominios, from_db = loader.carregar()
        self.whitelist_from_db = from_db  # Para logging/debug

        # V18.2: Carregar taxonomia automotiva do Supabase (com fallback hardcoded)
        taxonomia_loader = TaxonomiaLoader(config.supabase_url, config.supabase_key)
        self.taxonomia_automotiva, taxonomia_from_db = taxonomia_loader.carregar()
        self.taxonomia_from_db = taxonomia_from_db  # Para logging/debug

        self.logger = logging.getLogger("MinerV18")

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
            "pdf_extractions": 0,
            "api_detalhes_ok": 0,
            "api_detalhes_falha": 0,
            "ai_enrichments": 0,  # V18: Contador de enriquecimentos IA
            "ai_enrichments_failed": 0,  # V18: Contador de falhas IA
            "erros": 0,
        }

    def _extrair_dados_busca_e_detalhes(self, item: dict) -> dict:
        """
        V17: Extrai dados da busca + API de detalhes.

        MAPEAMENTO EXCLUSIVO (Prompt Garantidor):
        - data_leilao      <- EXCLUSIVAMENTE dataAberturaProposta (API detalhes)
        - valor_estimado   <- EXCLUSIVAMENTE valorTotalEstimado (API detalhes)
        - data_publicacao  <- EXCLUSIVAMENTE dataPublicacaoPncp (API detalhes)
        - n_edital         <- EXCLUSIVAMENTE do PDF (sem fallback)
        """
        pncp_id = item.get("numeroControlePNCP") or item.get("numero_controle_pncp") or item.get("pncp_id")

        if not pncp_id:
            return {}

        # Dados basicos da busca
        edital = {
            "pncp_id": pncp_id,
            "titulo": item.get("title") or item.get("titulo") or item.get("tituloObjeto") or "",
            "descricao": item.get("description") or item.get("descricao") or "",
            "objeto": item.get("objeto") or "",
            "orgao_nome": item.get("orgaoNome") or item.get("orgao_nome") or "Orgao Desconhecido",
            "orgao_cnpj": item.get("orgaoCnpj") or item.get("orgao_cnpj"),
            "uf": item.get("unidadeFederativaNome") or item.get("uf") or item.get("siglaUf") or "BR",
            "municipio": item.get("municipioNome") or item.get("municipio_nome") or item.get("cidade") or "Diversos",
            "modalidade": item.get("modalidadeNome") or item.get("modalidade_nome"),
            "situacao": item.get("situacaoNome") or item.get("situacao_nome"),

            # Campos que virao da API de detalhes
            "data_publicacao": None,
            "data_leilao": None,
            "valor_estimado": None,

            # n_edital vem do PDF
            "n_edital": None,

            "link_leiloeiro": None,
            "link_pncp": f"https://pncp.gov.br/app/editais/{pncp_id}",
            "arquivos": [],
            "texto_pdf": "",
            "produtos_destaque": None,  # V18: Campo para lista de veiculos da IA
        }

        # V17: CHAMAR API DE DETALHES para obter campos obrigatorios
        detalhes = self.pncp.obter_detalhes(pncp_id)

        if detalhes:
            self.stats["api_detalhes_ok"] += 1

            # data_publicacao <- EXCLUSIVAMENTE dataPublicacaoPncp
            data_pub_str = detalhes.get("dataPublicacaoPncp")
            if data_pub_str:
                edital["data_publicacao"] = parse_date(data_pub_str)

            # data_leilao <- EXCLUSIVAMENTE dataAberturaProposta
            data_leilao_str = detalhes.get("dataAberturaProposta")
            if data_leilao_str:
                edital["data_leilao"] = parse_date(data_leilao_str)

            # valor_estimado <- EXCLUSIVAMENTE valorTotalEstimado
            valor = detalhes.get("valorTotalEstimado")
            if valor:
                try:
                    edital["valor_estimado"] = float(valor)
                except (ValueError, TypeError):
                    pass

            # Link leiloeiro dos detalhes
            link_sistema = detalhes.get("linkSistemaOrigem")
            link_edital = detalhes.get("linkEdital")

            if link_sistema or link_edital:
                resultado_link = processar_link_pncp_v19(
                    link_sistema, link_edital, self.whitelist_dominios
                )
                if resultado_link["link_leiloeiro"]:
                    edital["link_leiloeiro"] = resultado_link["link_leiloeiro"]
        else:
            self.stats["api_detalhes_falha"] += 1
            self.logger.debug(f"API detalhes falhou para {pncp_id}")

        self.stats["editais_enriquecidos"] += 1
        return edital

    def _calcular_score(self, edital: dict) -> int:
        """Calcula score de relevancia do edital."""
        return ScoringEngine.calculate_score(
            edital.get("titulo", ""),
            edital.get("descricao", ""),
            edital.get("objeto", "")
        )

    def _baixar_arquivos(self, edital: dict) -> dict:
        """Baixa todos os arquivos do edital e faz upload para Storage."""
        pncp_id = edital.get("pncp_id")
        if not pncp_id:
            return edital

        arquivos = self.pncp.obter_arquivos(pncp_id)
        if not arquivos:
            return edital

        edital["arquivos"] = arquivos
        self.logger.debug(f"  {len(arquivos)} arquivos encontrados")

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

            if ext == ".pdf" and not texto_pdf:
                texto_pdf = extrair_texto_pdf(data)
                if texto_pdf:
                    self.logger.debug(f"  Texto PDF extraido: {len(texto_pdf)} chars")
                    self.stats["pdf_extractions"] += 1
                    pdf_url = url

            if self.storage and self.storage.enable_storage:
                filename = f"{arquivo.get('titulo', 'arquivo')}{ext}"
                filename = sanitize_filename(filename)
                path = f"{pncp_id}/{filename}"

                public_url = self.storage.upload_file(path, data, content_type or "application/octet-stream")
                if public_url:
                    self.stats["storage_uploads"] += 1
                    if not storage_path:
                        storage_path = path

            if self.config.enable_local_backup:
                self._salvar_local(pncp_id, arquivo.get("titulo", "arquivo"), ext, data)

        edital["texto_pdf"] = texto_pdf
        edital["pdf_url"] = pdf_url
        edital["storage_path"] = storage_path

        return edital

    def _salvar_local(self, pncp_id: str, titulo: str, ext: str, data: bytes):
        """Salva arquivo localmente para backup."""
        try:
            base_dir = Path(self.config.local_backup_dir)
            edital_dir = base_dir / sanitize_filename(pncp_id)
            edital_dir.mkdir(parents=True, exist_ok=True)

            filename = f"{sanitize_filename(titulo)}{ext}"
            filepath = edital_dir / filename

            with open(filepath, 'wb') as f:
                f.write(data)

        except Exception as e:
            self.logger.warning(f"Erro ao salvar local: {e}")

    def _processar_edital(self, item: dict) -> bool:
        """
        Processa um edital completo.
        V18: Usa busca + API detalhes + PDF + IA.
        """
        pncp_id = item.get("numeroControlePNCP") or item.get("numero_controle_pncp") or item.get("pncp_id")

        if not pncp_id:
            return False

        self.stats["editais_encontrados"] += 1

        if pncp_id in self.processed_ids:
            self.stats["editais_duplicados"] += 1
            return False

        self.processed_ids.add(pncp_id)

        # Fase 2: Processamento Incremental
        # Verifica se edital já existe no banco (skip se não for force_reprocess)
        if self.repo and self.repo.enable_supabase and not self.config.force_reprocess:
            if self.repo.edital_existe(pncp_id):
                self.stats["editais_skip_existe"] = self.stats.get("editais_skip_existe", 0) + 1
                self.logger.debug(f"[SKIP] Edital {pncp_id} ja existe no banco (use --force para reprocessar)")
                return False

        self.stats["editais_novos"] += 1

        try:
            # 1. V17: Extrair dados da busca + API detalhes
            edital = self._extrair_dados_busca_e_detalhes(item)

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

            # ============================================================
            # V18: ENRIQUECIMENTO COM IA (NOVO BLOCO)
            # ============================================================
            texto_pdf = edital.get("texto_pdf", "")

            # So chama a IA se tivermos texto do PDF extraido e IA habilitada
            if self.config.enable_ai_enrichment and texto_pdf and len(texto_pdf) > 100:
                self.logger.info(f"Enriquecendo edital {pncp_id} com IA...")

                dados_ai = self.ai_enricher.enriquecer_edital(
                    texto_pdf,
                    {
                        "titulo": edital["titulo"],
                        "orgao_nome": edital["orgao_nome"],
                        "municipio": edital["municipio"]
                    }
                )

                # Se a IA retornou dados, atualizamos o edital (Prioridade para IA)
                if dados_ai:
                    self.stats["ai_enrichments"] += 1

                    if dados_ai.get("titulo_comercial"):
                        # Substitui titulo chato do PNCP pelo titulo comercial da IA
                        edital["titulo"] = dados_ai["titulo_comercial"]
                        self.logger.debug(f"  Titulo IA: {dados_ai['titulo_comercial'][:50]}...")

                    if dados_ai.get("resumo_oportunidade"):
                        # Substitui descricao juridica pelo resumo comercial
                        edital["descricao"] = dados_ai["resumo_oportunidade"]
                        self.logger.debug(f"  Resumo IA: {dados_ai['resumo_oportunidade'][:50]}...")

                    if dados_ai.get("url_leilao_oficial"):
                        # A IA achou e corrigiu o link.
                        # Validamos com funcao existente para garantir que nao e link malicioso
                        url_ia = dados_ai["url_leilao_oficial"]
                        if "http" in url_ia:
                            # Valida a URL da IA usando whitelist carregada do Supabase
                            valido, confianca, motivo = validar_url_link_leiloeiro_v19(
                                url_ia, self.whitelist_dominios
                            )
                            if valido:
                                edital["link_leiloeiro"] = url_ia
                                self.logger.debug(f"  URL IA: {url_ia}")
                            else:
                                self.logger.debug(f"  URL IA rejeitada ({motivo}): {url_ia}")

                    # Adiciona a lista de produtos como campo novo
                    if dados_ai.get("lista_veiculos"):
                        edital["produtos_destaque"] = dados_ai["lista_veiculos"]
                        self.logger.debug(f"  Veiculos IA: {dados_ai['lista_veiculos'][:50]}...")
                else:
                    self.stats["ai_enrichments_failed"] += 1
            # ============================================================
            # FIM DO BLOCO IA
            # ============================================================

            # 4.5 REGRAS CANONICAS: Se nao tem link, verificar regras por orgao
            if not edital.get("link_leiloeiro"):
                url_canonica = WhitelistLoader.aplicar_regra_canonica(
                    edital.get("titulo", ""),
                    edital.get("orgao", ""),
                    edital.get("descricao", "")
                )
                if url_canonica:
                    edital["link_leiloeiro"] = url_canonica
                    edital["link_leiloeiro_origem_ref"] = "regra_canonica"
                    edital["link_leiloeiro_confianca"] = 100
                    self.logger.debug(f"  URL canonica aplicada: {url_canonica}")

            # 5. Upload metadados
            if self.storage and self.storage.enable_storage:
                metadados = edital.copy()
                for key in ["data_publicacao", "data_leilao"]:
                    if metadados.get(key) and isinstance(metadados[key], datetime):
                        metadados[key] = metadados[key].isoformat()
                metadados.pop("texto_pdf", None)
                self.storage.upload_json(pncp_id, metadados)

            # 6. VALIDACAO: Preparar registro no formato do contrato
            edital_db = edital.copy()

            for key in ["data_publicacao", "data_leilao"]:
                if edital_db.get(key) and isinstance(edital_db[key], datetime):
                    edital_db[key] = edital_db[key].strftime("%d-%m-%Y")

            texto_pdf = edital_db.get("texto_pdf", "")

            # n_edital EXCLUSIVAMENTE do PDF
            n_edital = None
            if texto_pdf:
                n_edital = extrair_n_edital_pdf(texto_pdf)

            valor_estimado = edital_db.get("valor_estimado")

            # objeto_resumido
            if texto_pdf:
                objeto_v17 = extrair_objeto_resumido(texto_pdf)
            else:
                titulo_v17 = edital_db.get("titulo", "")
                descricao_v17 = edital_db.get("descricao", "")
                texto_fonte = f"{titulo_v17} {descricao_v17}"
                objeto_v17 = extrair_objeto_resumido(texto_fonte)

            # descricao
            descricao_final = edital_db.get("descricao", "")
            if texto_pdf and not descricao_final:
                descricao_pdf = extrair_descricao_pdf(texto_pdf)
                if descricao_pdf:
                    descricao_final = descricao_pdf

            # tipo_leilao
            # FIX 2026-01-29: Adiciona mapeamento de modalidade PNCP para tipo esperado
            MODALIDADE_PARA_TIPO = {
                "6": "Eletronico",      # PNCP: Leilão Eletrônico
                "7": "Presencial",       # PNCP: Leilão Presencial
                "Leilão": "Eletronico",
                "Leilão Eletrônico": "Eletronico",
                "Leilao Eletronico": "Eletronico",
                "Leilão Presencial": "Presencial",
                "Leilao Presencial": "Presencial",
            }

            tipo_leilao = ""
            if texto_pdf:
                tipo_leilao = extrair_tipo_leilao_pdf(texto_pdf)

            # Fallback para modalidade da API PNCP
            if not tipo_leilao:
                modalidade_raw = edital_db.get("modalidade", "")
                if modalidade_raw:
                    tipo_leilao = MODALIDADE_PARA_TIPO.get(str(modalidade_raw), modalidade_raw)

            # leiloeiro_url - fallback para PDF
            leiloeiro_url = edital_db.get("link_leiloeiro")
            if not leiloeiro_url and texto_pdf:
                leiloeiro_url = extrair_leiloeiro_url_pdf(texto_pdf)

            # tags - V18.2: Usa taxonomia automotiva carregada do Supabase
            # NOTA: Apenas tags de VEICULOS sao geradas (sem imoveis/mobiliario/eletronicos)
            if texto_pdf:
                tags_v18 = gerar_tags_v18("", "", texto_pdf[:2000], self.taxonomia_automotiva)
            else:
                titulo_v18 = edital_db.get("titulo", "")
                descricao_v18 = edital_db.get("descricao", "")
                tags_v18 = gerar_tags_v18(titulo_v18, descricao_v18, objeto_v17, self.taxonomia_automotiva)

            edital_db["tags"] = tags_v18

            # V19 FIX: Rejeitar editais fora do escopo (imoveis sem veiculos)
            deve_rejeitar, motivo_rejeicao = deve_rejeitar_por_categoria(tags_v18)
            if deve_rejeitar:
                self.logger.warning(f"[REJEITADO] {pncp_id}: {motivo_rejeicao}")
                self.stats["editais_rejeitados_categoria"] = self.stats.get("editais_rejeitados_categoria", 0) + 1
                return False  # V18.1 FIX: Era 'continue' mas esta fora de loop

            # Registro para validacao
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
                "n_edital": n_edital,
                "objeto_resumido": objeto_v17,
                "tags": ", ".join(edital_db.get("tags", [])) if isinstance(edital_db.get("tags"), list) else edital_db.get("tags", ""),
                "valor_estimado": valor_estimado,
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
                        "n_edital": n_edital,
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
        self.logger.info("ACHE SUCATAS MINER V18 - COM ENRIQUECIMENTO IA")
        self.logger.info("=" * 70)
        self.logger.info(f"Periodo: {data_inicial_str} a {data_final_str}")
        self.logger.info(f"Termos de busca: {len(self.config.search_terms)}")
        self.logger.info(f"Paginas por termo: {self.config.paginas_por_termo}")
        self.logger.info(f"Score minimo: {self.config.min_score}")
        self.logger.info(f"Supabase: {'ATIVO' if self.repo and self.repo.enable_supabase else 'DESATIVADO'}")
        self.logger.info(f"Storage: {'ATIVO' if self.storage and self.storage.enable_storage else 'DESATIVADO'}")
        self.logger.info(f"OpenAI: {'ATIVO' if self.ai_enricher.client else 'DESATIVADO'}")
        self.logger.info(f"Modelo IA: {self.config.openai_model}")
        self.logger.info("-" * 70)
        self.logger.info("V18 NOVIDADES:")
        self.logger.info("  - Enriquecimento com IA (OpenAI GPT-4o-mini)")
        self.logger.info("  - Titulo comercial gerado pela IA")
        self.logger.info("  - Resumo da oportunidade (280 chars)")
        self.logger.info("  - Lista de veiculos/bens principais")
        self.logger.info("  - Correcao automatica de URLs pelo modelo")
        self.logger.info("-" * 70)
        self.logger.info("MANTIDO DO V17:")
        self.logger.info("  - API detalhes para campos obrigatorios")
        self.logger.info("  - data_leilao <- dataAberturaProposta")
        self.logger.info("  - valor_estimado <- valorTotalEstimado")
        self.logger.info("  - n_edital <- EXCLUSIVAMENTE do PDF")
        self.logger.info("-" * 70)
        self.logger.info("WHITELIST V18.1:")
        whitelist_fonte = "Supabase" if self.whitelist_from_db else "Fallback hardcoded"
        self.logger.info(f"  - Fonte: {whitelist_fonte}")
        self.logger.info(f"  - Dominios carregados: {len(self.whitelist_dominios)}")
        self.logger.info("-" * 70)
        self.logger.info("TAXONOMIA AUTOMOTIVA V18.2:")
        taxonomia_fonte = "Supabase" if self.taxonomia_from_db else "Fallback hardcoded"
        self.logger.info(f"  - Fonte: {taxonomia_fonte}")
        total_termos = sum(len(termos) for termos in self.taxonomia_automotiva.values())
        self.logger.info(f"  - Tags disponiveis: {len(self.taxonomia_automotiva)}")
        self.logger.info(f"  - Total de termos: {total_termos}")
        self.logger.info("  - NOTA: IMOVEL, MOBILIARIO, ELETRONICO foram REMOVIDOS")
        self.logger.info("-" * 70)
        self.logger.info("MODO DE PROCESSAMENTO (Fase 2):")
        if self.config.force_reprocess:
            self.logger.info("  - Modo: FULL (--force)")
            self.logger.info("  - Todos os editais serao processados, mesmo existentes")
        else:
            self.logger.info("  - Modo: INCREMENTAL")
            self.logger.info("  - Editais existentes no banco serao ignorados")
            self.logger.info("  - Use --force para reprocessar todos")
        self.logger.info("=" * 70)

        execucao_id = None
        if self.repo:
            # Brief 2.2: Passar run_id para correlacao com QualityReport
            execucao_id = self.repo.iniciar_execucao(self.config, run_id=self.run_id)
            if execucao_id:
                self.logger.info(f"Execucao #{execucao_id} iniciada (run_id: {self.run_id})")

            # Brief 3.4: Registrar evento de início
            self.repo.registrar_evento(
                run_id=self.run_id,
                etapa="inicio",
                evento="start",
                nivel="info",
                mensagem=f"Pipeline iniciado - Modo: {'FULL' if self.config.force_reprocess else 'INCREMENTAL'}",
                dados={
                    "versao": "V18",
                    "modo": "FULL" if self.config.force_reprocess else "INCREMENTAL",
                    "dias_retroativos": self.config.dias_retroativos,
                    "termos": len(self.config.search_terms),
                    "paginas_por_termo": self.config.paginas_por_termo,
                }
            )

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
                # Brief 3.6: Calcular metricas de FinOps
                finops = self._calcular_finops()

                # Brief 2.2: Incluir QualityReport na finalizacao
                self.repo.finalizar_execucao(
                    execucao_id,
                    self.stats,
                    "SUCCESS",
                    quality_report=self.quality_report,
                    finops=finops
                )

        except Exception as e:
            self.logger.error(f"Erro na mineracao: {e}")
            self.stats["erros"] += 1
            self.stats["fim"] = datetime.now().isoformat()

            if self.repo and execucao_id:
                # Brief 3.6: Calcular metricas de FinOps mesmo em falha
                finops = self._calcular_finops()

                # Brief 2.2: Incluir QualityReport mesmo em falha
                self.repo.finalizar_execucao(
                    execucao_id,
                    self.stats,
                    "FAILED",
                    quality_report=self.quality_report,
                    finops=finops
                )

                # Brief 3.4.1: Criar alerta de falha
                self.repo.verificar_e_criar_alertas(
                    run_id=self.run_id,
                    execucao_id=execucao_id,
                    quality_report=self.quality_report,
                    duracao_segundos=self.quality_report.duration_seconds if self.quality_report else 0,
                    status="FAILED"
                )

            raise

        finally:
            self.pncp.close()

        # Brief 1.3: Finalizar relatório com timestamp e duração
        self.quality_report.finalize()

        # Brief 3.2: Persistir QualityReport na tabela
        if self.repo:
            self.repo.salvar_quality_report(self.quality_report, execucao_id)

        # Brief 3.4: Registrar evento de fim
        if self.repo:
            self.repo.registrar_evento(
                run_id=self.run_id,
                etapa="fim",
                evento="success",
                nivel="info",
                mensagem=f"Pipeline finalizado com sucesso",
                dados={
                    "total_processados": self.quality_report.executed_total,
                    "total_validos": self.quality_report.valid_count,
                    "taxa_validos": self.quality_report.taxa_validos_percent,
                },
                duracao_ms=int(self.quality_report.duration_seconds * 1000),
                items_processados=self.quality_report.executed_total,
                items_sucesso=self.quality_report.valid_count,
                items_erro=self.stats.get("erros", 0)
            )

        # Brief 3.4.1: Verificar e criar alertas automáticos
        if self.repo:
            alertas = self.repo.verificar_e_criar_alertas(
                run_id=self.run_id,
                execucao_id=execucao_id,
                quality_report=self.quality_report,
                duracao_segundos=self.quality_report.duration_seconds,
                status="SUCCESS"
            )
            if alertas > 0:
                self.logger.warning(f"[ALERTAS] {alertas} alerta(s) criado(s) nesta execucao")

        self._imprimir_resumo()
        self._imprimir_relatorio_qualidade()
        self._salvar_relatorio_json()
        self._upload_relatorio_storage()

        # V18.3: Inserir run report para rastreamento historico
        if self.repo:
            git_sha = self._get_git_sha()
            self.logger.info(f"[RUN REPORT] Gravando relatorio para run_id={self.run_id}")
            run_report_ok = self.repo.inserir_run_report(
                run_id=self.run_id,
                git_sha=git_sha,
                job_name="miner"
            )
            if not run_report_ok:
                self.logger.error(
                    f"[RUN REPORT] FALHA ao gravar relatorio! "
                    f"run_id={self.run_id}, git_sha={git_sha}, job_name=miner"
                )
            else:
                self.logger.info(f"[RUN REPORT] Relatorio gravado com sucesso")

        return self.stats

    def _imprimir_relatorio_qualidade(self):
        """
        Brief 1.3: Imprime relatório de qualidade com métricas completas.

        Inclui: totais, taxas percentuais, duração e top motivos.
        """
        report = self.quality_report
        self.logger.info("")
        self.logger.info("=" * 70)
        self.logger.info("RELATORIO DE QUALIDADE - BRIEF 1.3")
        self.logger.info("=" * 70)
        self.logger.info(f"Run ID:       {report.run_id}")
        self.logger.info(f"Inicio:       {report.started_at}")
        self.logger.info(f"Fim:          {report.finished_at}")
        self.logger.info(f"Duracao:      {report.duration_seconds:.2f}s")
        self.logger.info("-" * 70)
        self.logger.info(f"Processados:  {report.executed_total}")
        self.logger.info(f"Validos:      {report.valid_count} ({report.taxa_validos_percent}%)")
        self.logger.info(f"Quarentena:   {report.total_quarentena} ({report.taxa_quarentena_percent}%)")
        self.logger.info(f"  |- Draft:        {report.draft_count}")
        self.logger.info(f"  |- Not sellable: {report.not_sellable_count}")
        self.logger.info(f"  |- Rejected:     {report.rejected_count}")
        self.logger.info("-" * 70)

        if report.top_reason_codes:
            self.logger.info("Top motivos de quarentena:")
            for item in report.top_reason_codes[:5]:
                self.logger.info(f"  - {item['code']}: {item['count']}")

        # Alerta se taxa de quarentena > 20%
        if report.taxa_quarentena_percent > 20:
            self.logger.warning(
                f"[ALERTA] Taxa de quarentena acima de 20%! "
                f"({report.taxa_quarentena_percent}%)"
            )

        self.logger.info("=" * 70)

    def _salvar_relatorio_json(self):
        """Salva relatorio de qualidade em JSON local."""
        try:
            reports_dir = Path(__file__).parent.parent.parent / "reports" / "quality"
            reports_dir.mkdir(parents=True, exist_ok=True)

            filepath = reports_dir / f"{self.run_id}.json"
            with open(filepath, "w", encoding="utf-8") as f:
                f.write(self.quality_report.to_json())

            self.logger.info(f"Relatorio local salvo: {filepath}")

        except Exception as e:
            self.logger.error(f"Erro ao salvar relatorio JSON local: {e}")

    def _get_git_sha(self) -> str:
        """
        V18.3: Obtém o SHA do commit git atual para rastreamento.

        Returns:
            SHA do commit ou None se não disponível
        """
        try:
            import subprocess
            result = subprocess.run(
                ["git", "rev-parse", "HEAD"],
                capture_output=True,
                text=True,
                timeout=5
            )
            if result.returncode == 0:
                return result.stdout.strip()
        except Exception:
            pass
        return None

    def _upload_relatorio_storage(self):
        """
        Brief 1.3: Upload do relatório de qualidade para Supabase Storage.

        Bucket: reports
        Path: quality_reports/{run_id}.json
        """
        if not self.storage or not self.storage.enable_storage:
            self.logger.debug("Storage desativado, skip upload do relatorio")
            return

        try:
            report_json = self.quality_report.to_json()
            filename = f"quality_reports/{self.run_id}.json"

            # Upload para o bucket de reports
            url = self.storage.client.storage.from_("reports").upload(
                filename,
                report_json.encode("utf-8"),
                {"content-type": "application/json", "upsert": "true"}
            )

            # Gerar URL pública (se bucket for público) ou URL assinada
            public_url = self.storage.client.storage.from_("reports").get_public_url(filename)

            self.logger.info(f"Relatorio enviado para Storage: {filename}")
            self.logger.info(f"URL: {public_url}")

        except Exception as e:
            # Não é crítico se falhar - relatório local já foi salvo
            self.logger.warning(f"Erro ao fazer upload do relatorio para Storage: {e}")

    def _calcular_finops(self) -> dict:
        """
        Brief 3.6: Calcula metricas de FinOps para a execucao.

        Retorna:
            dict com cost_total, cost_openai, num_pdfs, custo_por_mil
        """
        # Custo OpenAI (se disponivel)
        cost_openai = 0.0
        if self.ai_enricher and hasattr(self.ai_enricher, 'get_estimated_cost'):
            cost_openai = self.ai_enricher.get_estimated_cost()

        # Custo estimado de infraestrutura (Supabase, storage, etc)
        # Estimativa: $0.001 por PDF + $0.0005 por edital processado
        num_pdfs = self.stats.get("pdf_extractions", 0)
        num_editais = self.stats.get("editais_novos", 0)

        cost_infra = (num_pdfs * 0.001) + (num_editais * 0.0005)
        cost_total = cost_openai + cost_infra

        # Custo por 1000 registros
        custo_por_mil = 0.0
        if num_editais > 0:
            custo_por_mil = (cost_total / num_editais) * 1000

        finops = {
            "cost_total": round(cost_total, 6),
            "cost_openai": round(cost_openai, 6),
            "num_pdfs": num_pdfs,
            "custo_por_mil": round(custo_por_mil, 4),
        }

        self.logger.info(f"FinOps: custo_total=${finops['cost_total']:.4f}, openai=${finops['cost_openai']:.4f}")

        return finops

    def _imprimir_resumo(self):
        """Imprime resumo da execucao."""
        self.logger.info("=" * 70)
        self.logger.info("RESUMO DA EXECUCAO - MINER V18")
        self.logger.info("=" * 70)
        self.logger.info(f"Run ID: {self.run_id}")
        self.logger.info(f"Editais encontrados: {self.stats['editais_encontrados']}")
        self.logger.info(f"  |- Novos processados: {self.stats['editais_novos']}")
        self.logger.info(f"  |- Duplicados (mesmo run): {self.stats['editais_duplicados']}")
        self.logger.info(f"  |- Skip (ja existe no banco): {self.stats.get('editais_skip_existe', 0)}")
        self.logger.info(f"  |- Filtrados (data passada): {self.stats['editais_filtrados_data_passada']}")
        self.logger.info(f"  |- Rejeitados (imoveis): {self.stats.get('editais_rejeitados_categoria', 0)}")
        self.logger.info(f"Editais enriquecidos: {self.stats['editais_enriquecidos']}")
        self.logger.info(f"API detalhes: OK={self.stats['api_detalhes_ok']} / Falha={self.stats['api_detalhes_falha']}")
        self.logger.info(f"Arquivos baixados: {self.stats['arquivos_baixados']}")
        self.logger.info(f"Storage uploads: {self.stats['storage_uploads']}")
        self.logger.info(f"PDF extractions: {self.stats['pdf_extractions']}")
        self.logger.info("-" * 70)
        self.logger.info("ENRIQUECIMENTO IA (V18):")
        self.logger.info(f"  |- Editais enriquecidos com IA: {self.stats['ai_enrichments']}")
        self.logger.info(f"  |- Falhas de enriquecimento IA: {self.stats['ai_enrichments_failed']}")
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
    """Ponto de entrada do minerador V18."""
    parser = argparse.ArgumentParser(
        description="Ache Sucatas Miner V18 - Minerador de editais PNCP com Enriquecimento IA"
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
        "--sem-ia",
        action="store_true",
        help="Desabilita enriquecimento com IA (OpenAI)"
    )
    parser.add_argument(
        "--modelo-ia",
        type=str,
        default="gpt-4o-mini",
        help="Modelo OpenAI para enriquecimento (default: gpt-4o-mini)"
    )
    parser.add_argument(
        "--debug",
        action="store_true",
        help="Ativa modo debug com logs detalhados"
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Forca reprocessamento de editais que ja existem no banco (modo full)"
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
        enable_ai_enrichment=not args.sem_ia,
        openai_model=args.modelo_ia,
        force_reprocess=args.force,  # Fase 2: Processamento Incremental
    )

    miner = MinerV18(config)
    stats = miner.executar()

    logger.info(f"Mineracao finalizada: {stats['editais_novos']} novos, {stats['ai_enrichments']} enriquecidos com IA, {stats['erros']} erros")


if __name__ == "__main__":
    main()
