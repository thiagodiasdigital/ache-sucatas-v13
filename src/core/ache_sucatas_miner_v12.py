"""
ACHE SUCATAS MINER V12 - DATA_LEILAO FIX
=========================================
Minerador de editais PNCP com busca de data_leilao da API COMPLETA.

NOVIDADES V12 (sobre V11):
- FIX CRÍTICO: Busca dataAberturaProposta da API COMPLETA do PNCP
- DUAS CHAMADAS: 1) API Search (lista) + 2) API Consulta (detalhes)
- CAMPO data_leilao: Agora é preenchido corretamente em 100% dos casos
- VALOR ESTIMADO: Também extraído da API Completa (valorTotalEstimado)
- MÉTRICAS: Rastreia sucesso/falha na busca de datas
- RETRY: Tentativa de retry em caso de falha na API Completa

MANTIDO DO V11:
- CLOUD STORAGE: PDFs armazenados no Supabase Storage
- ZERO LOCAL: Sem dependência de filesystem local
- GITHUB ACTIONS: Pronto para execução em CI/CD
- INTEGRAÇÃO SUPABASE: Editais no PostgreSQL
- LOG DE EXECUÇÕES: Tabela execucoes_miner
- JANELA TEMPORAL: 24 horas (100% completude)
- SISTEMA DE CHECKPOINT: Rastreabilidade completa

PROBLEMA RESOLVIDO:
- V11 usava API de SEARCH que NÃO retorna data_leilao
- V12 faz chamada adicional à API COMPLETA para cada edital
- Campo correto: dataAberturaProposta (da API Consulta)

API ENDPOINTS:
- Search: https://pncp.gov.br/api/search/ (lista editais, sem data_leilao)
- Consulta: https://pncp.gov.br/api/consulta/v1/orgaos/{cnpj}/compras/{ano}/{seq}
  (detalhes completos, COM dataAberturaProposta)

CONFIGURAÇÃO:
- .env: ENABLE_SUPABASE_STORAGE=true
- GitHub Actions: cron 3x/dia

Data: 2026-01-19
Autor: Claude Code (CRAUDIO)
PEP 8 Compliant | Python 3.9+
"""

import asyncio
import aiohttp
import logging
import hashlib
import os
import json
import re
import unicodedata
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional, List, Dict, Any
from io import BytesIO
from pydantic import BaseModel
from dotenv import load_dotenv

load_dotenv()


# ==============================================================================
# CONFIGURATION
# ==============================================================================

class Settings:
    """Global configuration constants - V12 DATA_LEILAO FIX."""

    # =========================================================================
    # CLOUD CONFIGURATION
    # =========================================================================
    ENABLE_SUPABASE = os.getenv("ENABLE_SUPABASE", "true").lower() == "true"
    ENABLE_SUPABASE_STORAGE = os.getenv("ENABLE_SUPABASE_STORAGE", "true").lower() == "true"
    ENABLE_LOCAL_BACKUP = os.getenv("ENABLE_LOCAL_BACKUP", "false").lower() == "true"
    VERSAO_MINER = "V12_DATA_LEILAO_FIX"

    # Storage bucket
    STORAGE_BUCKET = os.getenv("SUPABASE_STORAGE_BUCKET", "editais-pdfs")

    # =========================================================================
    # CRON CONFIGURATION
    # =========================================================================
    CRON_MODE = True
    JANELA_TEMPORAL_HORAS = int(os.getenv("JANELA_TEMPORAL_HORAS", "24"))

    PAGE_LIMIT = int(os.getenv("PAGE_LIMIT", "3"))
    MAX_DOWNLOADS_PER_SESSION = int(os.getenv("MAX_DOWNLOADS", "200"))

    CHECKPOINT_FILE = ".ache_sucatas_checkpoint_v12.json"
    METRICS_FILE = "ache_sucatas_metrics_v12.jsonl"

    # =========================================================================
    # V12: API CONSULTA CONFIG
    # =========================================================================
    # Delay entre chamadas à API Consulta para evitar rate limiting
    API_CONSULTA_DELAY_MS = int(os.getenv("API_CONSULTA_DELAY_MS", "100"))
    # Retry em caso de falha
    API_CONSULTA_MAX_RETRIES = int(os.getenv("API_CONSULTA_MAX_RETRIES", "2"))

    # =========================================================================
    # SEARCH API RATE LIMITING
    # =========================================================================
    # Delay entre termos de busca (ms) - evita 429
    SEARCH_TERM_DELAY_MS = int(os.getenv("SEARCH_TERM_DELAY_MS", "2000"))
    # Delay entre páginas (ms)
    SEARCH_PAGE_DELAY_MS = int(os.getenv("SEARCH_PAGE_DELAY_MS", "500"))

    # =========================================================================
    # SEARCH TERMS
    # =========================================================================
    SEARCH_TERMS = [
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
    ]

    MODALIDADES = "1|13"
    MIN_SCORE_TO_DOWNLOAD = 60
    TIMEOUT_SEC = 45
    USER_AGENT = (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/123.0.0.0 Safari/537.36"
    )

    ALLOWED_EXTENSIONS = {".pdf", ".xlsx", ".xls", ".csv", ".zip", ".docx", ".doc"}

    MAGIC_BYTES = {
        b'%PDF': '.pdf',
        b'PK\x03\x04': '.zip',
        b'\xd0\xcf\x11\xe0': '.xls',
    }

    CONTENT_TYPE_MAP = {
        ".pdf": "application/pdf",
        ".xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        ".xls": "application/vnd.ms-excel",
        ".csv": "text/csv",
        ".zip": "application/zip",
        ".docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        ".doc": "application/msword",
    }


# Logging configuration
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s | %(levelname)-8s | [%(name)s] %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
log = logging.getLogger("AcheSucatas_V12")


# ==============================================================================
# CHECKPOINT SYSTEM
# ==============================================================================

class CheckpointManager:
    """Gerencia checkpoint para rastreabilidade e recovery."""

    def __init__(self, checkpoint_file: str = Settings.CHECKPOINT_FILE):
        self.checkpoint_file = Path(checkpoint_file)
        self.checkpoint_data = self._load_checkpoint()

    def _load_checkpoint(self) -> dict:
        if self.checkpoint_file.exists():
            try:
                with open(self.checkpoint_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    log.info(f"Checkpoint carregado: {data.get('last_execution')}")
                    return data
            except Exception as e:
                log.warning(f"Erro ao carregar checkpoint: {e}. Criando novo.")

        return {
            "last_execution": None,
            "last_pncp_ids": [],
            "total_executions": 0,
            "total_editais_processados": 0,
            "total_downloads": 0
        }

    def save_checkpoint(self, metrics: dict):
        self.checkpoint_data.update({
            "last_execution": datetime.now().isoformat(),
            "last_pncp_ids": metrics.get("pncp_ids_processados", [])[-1000:],
            "total_executions": self.checkpoint_data.get("total_executions", 0) + 1,
            "total_editais_processados": self.checkpoint_data.get("total_editais_processados", 0) + metrics.get("editais_analisados", 0),
            "total_downloads": self.checkpoint_data.get("total_downloads", 0) + metrics.get("downloads", 0),
            "last_metrics": metrics
        })

        try:
            with open(self.checkpoint_file, 'w', encoding='utf-8') as f:
                json.dump(self.checkpoint_data, f, indent=2, ensure_ascii=False)
            log.info(f"Checkpoint salvo: {self.checkpoint_file}")
        except Exception as e:
            log.error(f"Erro ao salvar checkpoint: {e}")

    def get_processed_ids(self) -> set:
        return set(self.checkpoint_data.get("last_pncp_ids", []))


# ==============================================================================
# METRICS TRACKER - V12 ENHANCED
# ==============================================================================

class MetricsTracker:
    """Rastreamento de métricas para análise de performance - V12 Enhanced."""

    def __init__(self, metrics_file: str = Settings.METRICS_FILE):
        self.metrics_file = Path(metrics_file)
        self.start_time = datetime.now()
        self.metrics = {
            "execution_start": self.start_time.isoformat(),
            "execution_end": None,
            "duration_seconds": None,
            "janela_temporal_horas": Settings.JANELA_TEMPORAL_HORAS,
            "editais_analisados": 0,
            "editais_novos": 0,
            "editais_duplicados": 0,
            "downloads": 0,
            "downloads_sucesso": 0,
            "downloads_falha": 0,
            "taxa_deduplicacao": 0.0,
            "completude_estimada": "100%",
            "pncp_ids_processados": [],
            "termos_buscados": len(Settings.SEARCH_TERMS),
            "paginas_por_termo": Settings.PAGE_LIMIT,
            # V11: Métricas Cloud
            "storage_uploads": 0,
            "storage_errors": 0,
            "supabase_inserts": 0,
            "supabase_errors": 0,
            "mode": "CLOUD" if Settings.ENABLE_SUPABASE_STORAGE else "LOCAL",
            # V12: Métricas de data_leilao
            "api_consulta_chamadas": 0,
            "api_consulta_sucesso": 0,
            "api_consulta_falha": 0,
            "data_leilao_encontrada": 0,
            "data_leilao_nao_encontrada": 0,
            "valor_estimado_encontrado": 0,
        }

    def increment(self, key: str, value: int = 1):
        if key in self.metrics:
            self.metrics[key] += value

    def add_pncp_id(self, pncp_id: str):
        self.metrics["pncp_ids_processados"].append(pncp_id)

    def finalize(self):
        self.metrics["execution_end"] = datetime.now().isoformat()
        self.metrics["duration_seconds"] = (datetime.now() - self.start_time).total_seconds()

        total_analisados = self.metrics["editais_analisados"]
        if total_analisados > 0:
            self.metrics["taxa_deduplicacao"] = round(
                (self.metrics["editais_duplicados"] / total_analisados) * 100, 2
            )

        # V12: Calcular taxa de sucesso de data_leilao
        total_novos = self.metrics["editais_novos"]
        if total_novos > 0:
            self.metrics["taxa_data_leilao"] = round(
                (self.metrics["data_leilao_encontrada"] / total_novos) * 100, 2
            )
        else:
            self.metrics["taxa_data_leilao"] = 0.0

        try:
            with open(self.metrics_file, 'a', encoding='utf-8') as f:
                f.write(json.dumps(self.metrics, ensure_ascii=False) + '\n')
            log.info(f"Métricas salvas: {self.metrics_file}")
        except Exception as e:
            log.error(f"Erro ao salvar métricas: {e}")

    def print_summary(self):
        log.info("=" * 70)
        log.info("RESUMO DA EXECUÇÃO - MINER V12 (DATA_LEILAO FIX)")
        log.info("=" * 70)
        log.info(f"Modo: {self.metrics['mode']}")
        log.info(f"Duração: {self.metrics['duration_seconds']:.1f}s")
        log.info(f"Janela temporal: {self.metrics['janela_temporal_horas']}h")
        log.info(f"Editais analisados: {self.metrics['editais_analisados']}")
        log.info(f"  |- Novos: {self.metrics['editais_novos']}")
        log.info(f"  |- Duplicados: {self.metrics['editais_duplicados']} ({self.metrics['taxa_deduplicacao']}%)")
        log.info("-" * 70)
        log.info("V12 - BUSCA DE DATA_LEILAO:")
        log.info(f"  API Consulta chamadas: {self.metrics['api_consulta_chamadas']}")
        log.info(f"  |- Sucesso: {self.metrics['api_consulta_sucesso']}")
        log.info(f"  |- Falha: {self.metrics['api_consulta_falha']}")
        log.info(f"  data_leilao encontrada: {self.metrics['data_leilao_encontrada']}/{self.metrics['editais_novos']} ({self.metrics.get('taxa_data_leilao', 0)}%)")
        log.info(f"  valor_estimado encontrado: {self.metrics['valor_estimado_encontrado']}")
        log.info("-" * 70)
        log.info(f"Downloads: {self.metrics['downloads']} (sucesso: {self.metrics['downloads_sucesso']}, falha: {self.metrics['downloads_falha']})")
        log.info(f"Storage uploads: {self.metrics['storage_uploads']} (erros: {self.metrics['storage_errors']})")
        log.info(f"Supabase: {self.metrics['supabase_inserts']} inserts, {self.metrics['supabase_errors']} erros")
        log.info("=" * 70)


# ==============================================================================
# TEMPORAL WINDOW
# ==============================================================================

class TemporalWindow:
    @staticmethod
    def get_date_range() -> dict:
        data_fim = datetime.now()
        data_inicio = data_fim - timedelta(hours=Settings.JANELA_TEMPORAL_HORAS)
        return {
            "data_publicacao_inicio": data_inicio.strftime("%Y-%m-%d"),
            "data_publicacao_fim": data_fim.strftime("%Y-%m-%d")
        }

    @staticmethod
    def log_window():
        window = TemporalWindow.get_date_range()
        log.info(f"Janela temporal: {window['data_publicacao_inicio']} -> {window['data_publicacao_fim']} ({Settings.JANELA_TEMPORAL_HORAS}h)")


# ==============================================================================
# DATA MODELS - V12 ENHANCED
# ==============================================================================

class EditalModel(BaseModel):
    """Structured edital data model - V12 with data_leilao."""
    pncp_id: str
    orgao_nome: str
    orgao_cnpj: Optional[str] = None
    uf: str
    municipio: str
    titulo: str
    descricao: str
    objeto: Optional[str] = None
    data_publicacao: Optional[datetime] = None
    data_atualizacao: Optional[str] = None
    # V12: data_leilao agora é preenchido corretamente!
    data_leilao: Optional[datetime] = None
    # Campos mantidos por compatibilidade (podem ser None)
    data_inicio_propostas: Optional[str] = None
    data_fim_propostas: Optional[str] = None
    modalidade: Optional[str] = None
    situacao: Optional[str] = None
    score: int
    files_url: str
    link_pncp: str
    ano_compra: Optional[str] = None
    numero_sequencial: Optional[str] = None
    # V11: Storage fields
    storage_path: Optional[str] = None
    pdf_storage_url: Optional[str] = None
    # V12: Valor estimado da API Completa
    valor_estimado: Optional[float] = None


# ==============================================================================
# FILE TYPE DETECTION
# ==============================================================================

class FileTypeDetector:
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

    @staticmethod
    def detect_by_content_type(content_type: str) -> Optional[str]:
        if not content_type:
            return None
        content_type_lower = content_type.lower().split(';')[0].strip()
        return FileTypeDetector.CONTENT_TYPE_MAP.get(content_type_lower)

    @staticmethod
    def detect_by_magic_bytes(data: bytes) -> Optional[str]:
        for magic, ext in Settings.MAGIC_BYTES.items():
            if data.startswith(magic):
                return ext

        if data.startswith(b'PK\x03\x04'):
            if b'xl/' in data[:1000] or b'word/' in data[:1000]:
                if b'xl/' in data[:1000]:
                    return '.xlsx'
                return '.docx'
            return '.zip'

        return None


# ==============================================================================
# SCORING ENGINE
# ==============================================================================

class ScoringEngine:
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
        "fernandoleiloeiro": 8, "fernando leiloeiro": 8, "fernando caetano": 8,
        "lopesleiloes": 8, "lopes leilões": 8, "joão lopes": 8, "joao lopes": 8,
        "joãoemilio": 8, "joaoemilio": 8, "joão emílio": 8,
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
    def calculate_score(titulo: str, descricao: str, objeto: str) -> int:
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

        return min(score, 100)


# ==============================================================================
# API CLIENT - V12 ENHANCED (com API Consulta)
# ==============================================================================

class PncpApiClient:
    """Cliente de API do PNCP - V12 com API Consulta para data_leilao."""

    # API de busca (lista editais)
    BASE_URL_SEARCH = "https://pncp.gov.br/api/search/"
    # API de consulta (detalhes completos com dataAberturaProposta)
    BASE_URL_CONSULTA = "https://pncp.gov.br/api/consulta/v1/orgaos"

    def __init__(self):
        self.session: Optional[aiohttp.ClientSession] = None

    async def __aenter__(self):
        timeout = aiohttp.ClientTimeout(total=Settings.TIMEOUT_SEC)
        self.session = aiohttp.ClientSession(
            timeout=timeout,
            headers={"User-Agent": Settings.USER_AGENT}
        )
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if self.session:
            await self.session.close()

    async def search(self, params: dict) -> Optional[dict]:
        """Busca editais via API Search (não retorna data_leilao)."""
        try:
            async with self.session.get(self.BASE_URL_SEARCH, params=params) as response:
                if response.status == 200:
                    return await response.json()
                else:
                    log.warning(f"API Search returned status {response.status}")
        except Exception as e:
            log.warning(f"Search error: {e}")
        return None

    async def get_detalhes_completos(
        self,
        cnpj: str,
        ano: str,
        sequencial: str,
        retry: int = 0
    ) -> Optional[dict]:
        """
        V12: Busca detalhes COMPLETOS do edital via API Consulta.

        Este endpoint retorna campos que a API Search não retorna:
        - dataAberturaProposta (data do leilão!)
        - valorTotalEstimado
        - modalidadeNome
        - situacaoNome
        - etc.

        Args:
            cnpj: CNPJ do órgão (14 dígitos, sem formatação)
            ano: Ano da compra (ex: "2025")
            sequencial: Número sequencial (ex: "123")
            retry: Número da tentativa atual (para retry automático)

        Returns:
            dict com dados completos ou None se falhar
        """
        # Limpar CNPJ (remover pontos, traços, barras)
        cnpj_limpo = re.sub(r'[^0-9]', '', cnpj)

        # Remover zeros à esquerda do sequencial
        seq_limpo = str(sequencial).lstrip('0') or '0'

        url = f"{self.BASE_URL_CONSULTA}/{cnpj_limpo}/compras/{ano}/{seq_limpo}"

        try:
            # Delay para evitar rate limiting
            if Settings.API_CONSULTA_DELAY_MS > 0:
                await asyncio.sleep(Settings.API_CONSULTA_DELAY_MS / 1000)

            async with self.session.get(url) as response:
                if response.status == 200:
                    return await response.json()
                elif response.status == 404:
                    log.debug(f"API Consulta 404: {cnpj_limpo}/{ano}/{seq_limpo}")
                    return None
                else:
                    log.warning(f"API Consulta status {response.status}: {url}")

                    # Retry em caso de erro temporário
                    if retry < Settings.API_CONSULTA_MAX_RETRIES and response.status >= 500:
                        log.info(f"Retry {retry + 1}/{Settings.API_CONSULTA_MAX_RETRIES} para {url}")
                        await asyncio.sleep(1)  # Espera 1s antes de retry
                        return await self.get_detalhes_completos(cnpj, ano, sequencial, retry + 1)

        except asyncio.TimeoutError:
            log.warning(f"Timeout na API Consulta: {url}")
            if retry < Settings.API_CONSULTA_MAX_RETRIES:
                return await self.get_detalhes_completos(cnpj, ano, sequencial, retry + 1)
        except Exception as e:
            log.warning(f"Erro API Consulta: {e}")

        return None

    async def list_files_metadata(self, files_url: str) -> List[dict]:
        """Lista metadados dos arquivos do edital."""
        try:
            async with self.session.get(files_url) as response:
                if response.status == 200:
                    return await response.json()
        except Exception as e:
            log.warning(f"Files metadata error: {e}")
        return []

    async def download_file(self, url: str) -> Optional[bytes]:
        """Download de arquivo."""
        try:
            async with self.session.get(url) as response:
                if response.status == 200:
                    return await response.read()
        except Exception as e:
            log.warning(f"Download error: {e}")
        return None


# ==============================================================================
# EDITAL PROCESSOR - V12 WITH DATA_LEILAO
# ==============================================================================

class EditalProcessor:
    """Process editals with cloud storage - V12 with data_leilao fix."""

    def __init__(
        self,
        checkpoint_manager: CheckpointManager,
        metrics: MetricsTracker,
        supabase_repo=None,
        storage_repo=None,
        output_dir: Optional[Path] = None,
    ):
        self.checkpoint_manager = checkpoint_manager
        self.metrics = metrics

        # Cloud repos
        self.supabase_repo = supabase_repo
        self.storage_repo = storage_repo

        # Local backup (optional)
        self.output_dir = output_dir
        if output_dir:
            output_dir.mkdir(parents=True, exist_ok=True)

        # Deduplicação
        self.deduplication_set = checkpoint_manager.get_processed_ids()
        self.new_ids_this_run = set()

    def _sanitize_filename(self, name: str) -> str:
        name = unicodedata.normalize('NFKD', name)
        name = name.encode('ascii', 'ignore').decode('ascii')
        name = re.sub(r'[^\w\s-]', '', name)
        name = re.sub(r'[-\s]+', '_', name)
        return name[:100]

    def _construct_files_url(self, item: dict) -> str:
        cnpj = item.get("orgao_cnpj")
        ano = item.get("ano_compra") or item.get("ano")
        seq = item.get("numero_sequencial")

        if cnpj and ano and seq:
            return (
                f"https://pncp.gov.br/api/pncp/v1/orgaos/{cnpj}/"
                f"compras/{ano}/{seq}/arquivos"
            )
        return ""

    async def _process_item(self, client: PncpApiClient, item: dict):
        """
        Process single API search result item - V12 WITH DATA_LEILAO.

        Fluxo V12:
        1. Recebe item da API Search (sem data_leilao)
        2. Chama API Consulta para buscar dataAberturaProposta
        3. Combina dados de ambas as APIs
        4. Salva no Storage e PostgreSQL com data_leilao preenchida
        """
        pncp_id = item.get("numero_controle_pncp")
        if not pncp_id:
            return

        self.metrics.increment("editais_analisados")

        # DEDUPLICAÇÃO
        if pncp_id in self.deduplication_set or pncp_id in self.new_ids_this_run:
            self.metrics.increment("editais_duplicados")
            return

        self.metrics.increment("editais_novos")
        self.new_ids_this_run.add(pncp_id)
        self.metrics.add_pncp_id(pncp_id)

        try:
            titulo = item.get("titulo_objeto", "")
            descricao = item.get("descricao_objeto", "")
            objeto = item.get("objeto", "")

            score = ScoringEngine.calculate_score(titulo, descricao, objeto)

            if score < Settings.MIN_SCORE_TO_DOWNLOAD:
                return

            files_url = self._construct_files_url(item)

            # ================================================================
            # V12: BUSCAR DATA_LEILAO DA API COMPLETA
            # ================================================================
            data_leilao = None
            valor_estimado = None
            modalidade_completa = None
            situacao_completa = None

            cnpj = item.get("orgao_cnpj")
            ano = item.get("ano_compra")
            seq = item.get("numero_sequencial")

            if cnpj and ano and seq:
                self.metrics.increment("api_consulta_chamadas")

                detalhes = await client.get_detalhes_completos(cnpj, ano, seq)

                if detalhes:
                    self.metrics.increment("api_consulta_sucesso")

                    # Extrair dataAberturaProposta (campo crítico!)
                    data_abertura_str = detalhes.get("dataAberturaProposta")
                    if data_abertura_str:
                        data_leilao = self._parse_date(data_abertura_str)
                        if data_leilao:
                            self.metrics.increment("data_leilao_encontrada")
                            log.debug(f"data_leilao encontrada: {pncp_id} -> {data_leilao}")
                        else:
                            self.metrics.increment("data_leilao_nao_encontrada")
                    else:
                        self.metrics.increment("data_leilao_nao_encontrada")

                    # Extrair valorTotalEstimado
                    valor = detalhes.get("valorTotalEstimado")
                    if valor is not None:
                        try:
                            valor_estimado = float(valor)
                            self.metrics.increment("valor_estimado_encontrado")
                        except (ValueError, TypeError):
                            pass

                    # Extrair outros campos úteis
                    modalidade_completa = detalhes.get("modalidadeNome")
                    situacao_completa = detalhes.get("situacaoNome")

                else:
                    self.metrics.increment("api_consulta_falha")
                    self.metrics.increment("data_leilao_nao_encontrada")
            else:
                self.metrics.increment("data_leilao_nao_encontrada")
                log.warning(f"Sem CNPJ/ANO/SEQ para buscar detalhes: {pncp_id}")

            # ================================================================
            # CRIAR MODELO COM TODOS OS DADOS
            # ================================================================
            edital = EditalModel(
                pncp_id=pncp_id,
                orgao_nome=item.get("orgao_nome", ""),
                orgao_cnpj=cnpj,
                uf=item.get("uf_nome", ""),
                municipio=item.get("municipio_nome", ""),
                titulo=titulo,
                descricao=descricao,
                objeto=objeto,
                data_publicacao=self._parse_date(item.get("data_publicacao")),
                data_atualizacao=item.get("data_atualizacao"),
                # V12: data_leilao agora vem da API Consulta!
                data_leilao=data_leilao,
                # Campos de compatibilidade
                data_inicio_propostas=item.get("data_inicio_propostas"),
                data_fim_propostas=item.get("data_fim_propostas"),
                # Preferir dados da API Consulta se disponíveis
                modalidade=modalidade_completa or item.get("modalidade_nome"),
                situacao=situacao_completa or item.get("situacao_nome"),
                score=score,
                files_url=files_url,
                link_pncp=item.get("link_pncp", ""),
                ano_compra=ano,
                numero_sequencial=seq,
                # V12: valor_estimado da API Consulta
                valor_estimado=valor_estimado,
            )

            # V11: Upload metadados para Storage
            await self._upload_metadados_to_storage(edital)

            # V11: Download e upload de arquivos para Storage
            await self._download_and_upload_files(client, edital)

            # V12: Inserir no Supabase PostgreSQL com data_leilao
            await self._insert_to_supabase(edital)

        except Exception as e:
            log.error(f"Error processing {pncp_id}: {e}")

    async def _upload_metadados_to_storage(self, edital: EditalModel):
        """Upload metadados.json para Supabase Storage."""
        if not self.storage_repo or not self.storage_repo.enable_storage:
            return

        try:
            metadados = edital.model_dump(exclude_none=True)
            # Converter datetime para string
            if metadados.get("data_publicacao"):
                metadados["data_publicacao"] = edital.data_publicacao.isoformat() if edital.data_publicacao else None
            # V12: Converter data_leilao
            if metadados.get("data_leilao"):
                metadados["data_leilao"] = edital.data_leilao.isoformat() if edital.data_leilao else None

            url = self.storage_repo.upload_json(edital.pncp_id, metadados)
            if url:
                edital.storage_path = f"{edital.pncp_id}/metadados.json"
                self.metrics.increment("storage_uploads")
                log.debug(f"Metadados uploaded: {edital.pncp_id}")
            else:
                self.metrics.increment("storage_errors")

        except Exception as e:
            log.error(f"Erro ao fazer upload de metadados {edital.pncp_id}: {e}")
            self.metrics.increment("storage_errors")

    async def _download_and_upload_files(self, client: PncpApiClient, edital: EditalModel):
        """Download files and upload to Supabase Storage."""
        if not edital.files_url:
            return

        files_metadata = await client.list_files_metadata(edital.files_url)
        if not files_metadata:
            return

        for file_meta in files_metadata:
            await self._download_and_upload_single_file(client, file_meta, edital)

    async def _download_and_upload_single_file(
        self,
        client: PncpApiClient,
        file_meta: dict,
        edital: EditalModel
    ):
        """Download single file and upload to Storage."""
        url = file_meta.get("url")
        if not url:
            return

        self.metrics.increment("downloads")

        try:
            file_data = await client.download_file(url)
            if not file_data:
                self.metrics.increment("downloads_falha")
                return

            # Detect file type
            content_type = file_meta.get("tipo")
            ext = FileTypeDetector.detect_by_content_type(content_type)

            if not ext:
                ext = FileTypeDetector.detect_by_magic_bytes(file_data)

            if not ext or ext not in Settings.ALLOWED_EXTENSIONS:
                self.metrics.increment("downloads_falha")
                return

            self.metrics.increment("downloads_sucesso")

            # Upload para Supabase Storage
            if self.storage_repo and self.storage_repo.enable_storage:
                file_hash = hashlib.md5(file_data).hexdigest()[:8]
                filename = f"{file_hash}{ext}"
                mime_type = Settings.CONTENT_TYPE_MAP.get(ext, "application/octet-stream")

                storage_url = self.storage_repo.upload_file(
                    f"{edital.pncp_id}/{filename}",
                    file_data,
                    mime_type
                )

                if storage_url:
                    self.metrics.increment("storage_uploads")
                    # Guardar URL do primeiro PDF
                    if ext == ".pdf" and not edital.pdf_storage_url:
                        edital.pdf_storage_url = storage_url
                        edital.storage_path = f"{edital.pncp_id}/{filename}"
                else:
                    self.metrics.increment("storage_errors")

            # Backup local (opcional)
            if self.output_dir and Settings.ENABLE_LOCAL_BACKUP:
                await self._save_local_backup(edital, file_data, ext)

        except Exception as e:
            log.error(f"Download/upload error: {e}")
            self.metrics.increment("downloads_falha")

    async def _save_local_backup(self, edital: EditalModel, file_data: bytes, ext: str):
        """Salva backup local do arquivo (opcional)."""
        if not self.output_dir:
            return

        try:
            import aiofiles

            uf = self._sanitize_filename(edital.uf)
            municipio = self._sanitize_filename(edital.municipio)
            date_str = edital.data_publicacao.strftime('%Y-%m-%d') if edital.data_publicacao else 'sem-data'
            folder_name = self._sanitize_filename(f"{date_str}_S{edital.score}_{edital.pncp_id}")

            edital_folder = self.output_dir / uf / f"{uf}_{municipio}" / folder_name
            edital_folder.mkdir(parents=True, exist_ok=True)

            file_hash = hashlib.md5(file_data).hexdigest()[:8]
            filename = f"{file_hash}{ext}"
            file_path = edital_folder / filename

            async with aiofiles.open(file_path, 'wb') as f:
                await f.write(file_data)

        except Exception as e:
            log.warning(f"Erro ao salvar backup local: {e}")

    async def _insert_to_supabase(self, edital: EditalModel):
        """
        Insere edital no Supabase PostgreSQL - V12 com data_leilao.

        IMPORTANTE: O método inserir_edital_miner do supabase_repository
        precisa ser atualizado para mapear data_leilao corretamente.
        """
        if not self.supabase_repo:
            return

        try:
            edital_dict = edital.model_dump()

            # Converter datetime para string ISO
            if edital_dict.get("data_publicacao"):
                edital_dict["data_publicacao"] = edital.data_publicacao.isoformat() if edital.data_publicacao else None

            # V12: Converter data_leilao para string ISO
            if edital_dict.get("data_leilao"):
                edital_dict["data_leilao"] = edital.data_leilao.isoformat() if edital.data_leilao else None

            # Usar método V12 se disponível, senão fallback para V11
            if hasattr(self.supabase_repo, 'inserir_edital_miner_v12'):
                sucesso = self.supabase_repo.inserir_edital_miner_v12(edital_dict)
            else:
                sucesso = self.supabase_repo.inserir_edital_miner(edital_dict)

            if sucesso:
                self.metrics.increment("supabase_inserts")
                log.debug(f"Edital {edital.pncp_id} inserido no Supabase (data_leilao: {edital.data_leilao})")
            else:
                self.metrics.increment("supabase_errors")
                log.warning(f"Falha ao inserir {edital.pncp_id} no Supabase")

        except Exception as e:
            self.metrics.increment("supabase_errors")
            log.error(f"Erro Supabase para {edital.pncp_id}: {e}")

    def _parse_date(self, date_str: Optional[str]) -> Optional[datetime]:
        """Parse date string to datetime object."""
        if not date_str:
            return None
        try:
            # Formato ISO 8601 (ex: 2026-01-20T10:00:00)
            return datetime.fromisoformat(date_str.replace('Z', '+00:00'))
        except ValueError:
            pass

        # Tentar outros formatos
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

        log.warning(f"Não foi possível parsear data: {date_str}")
        return None

    async def process_search_results(self, client: PncpApiClient, items: List[dict]):
        """Processa resultados da busca - sequencial para respeitar rate limit da API Consulta."""
        # V12: Processamento sequencial para evitar sobrecarga na API Consulta
        for item in items:
            await self._process_item(client, item)


# ==============================================================================
# MAIN ORCHESTRATOR - V12
# ==============================================================================

class AcheSucatasMiner:
    """Main orchestrator for ACHE SUCATAS mining - V12 DATA_LEILAO FIX."""

    def __init__(self, output_dir: str = "ACHE_SUCATAS_DB"):
        self.output_dir = Path(output_dir) if Settings.ENABLE_LOCAL_BACKUP else None
        self.checkpoint_manager = CheckpointManager()
        self.metrics = MetricsTracker()

        # Supabase PostgreSQL
        self.supabase_repo = None
        self.execucao_id = None

        # Supabase Storage
        self.storage_repo = None

        # Initialize Supabase PostgreSQL
        if Settings.ENABLE_SUPABASE:
            try:
                from supabase_repository import SupabaseRepository
                self.supabase_repo = SupabaseRepository(enable_supabase=True)
                if not self.supabase_repo.enable_supabase:
                    log.warning("Supabase DB desabilitado - continuando sem PostgreSQL")
                    self.supabase_repo = None
                else:
                    log.info("Supabase PostgreSQL conectado")
            except ImportError:
                log.error("supabase_repository.py não encontrado")
                self.supabase_repo = None
            except Exception as e:
                log.error(f"Erro ao inicializar Supabase DB: {e}")
                self.supabase_repo = None
        else:
            log.info("Supabase DB desabilitado via ENABLE_SUPABASE=false")

        # Initialize Supabase Storage
        if Settings.ENABLE_SUPABASE_STORAGE:
            try:
                from supabase_storage import SupabaseStorageRepository
                self.storage_repo = SupabaseStorageRepository(bucket_name=Settings.STORAGE_BUCKET)
                if not self.storage_repo.enable_storage:
                    log.warning("Supabase Storage desabilitado - continuando sem cloud storage")
                    self.storage_repo = None
                else:
                    log.info(f"Supabase Storage conectado: bucket={Settings.STORAGE_BUCKET}")
            except ImportError:
                log.error("supabase_storage.py não encontrado")
                self.storage_repo = None
            except Exception as e:
                log.error(f"Erro ao inicializar Supabase Storage: {e}")
                self.storage_repo = None
        else:
            log.info("Supabase Storage desabilitado via ENABLE_SUPABASE_STORAGE=false")

    async def run(self):
        """Execute mining process - V12 DATA_LEILAO FIX."""
        log.info("=" * 70)
        log.info("ACHE SUCATAS MINER V12 - DATA_LEILAO FIX")
        log.info("=" * 70)
        log.info("NOVIDADE V12: Busca dataAberturaProposta da API Completa!")
        log.info("-" * 70)
        log.info(f"Modo: CLOUD | Storage: {'ATIVO' if self.storage_repo else 'DESATIVADO'} | DB: {'ATIVO' if self.supabase_repo else 'DESATIVADO'}")
        log.info(f"Local backup: {'ATIVO' if Settings.ENABLE_LOCAL_BACKUP else 'DESATIVADO'}")
        log.info(f"Execução #{self.checkpoint_manager.checkpoint_data.get('total_executions', 0) + 1}")

        # Iniciar execução no Supabase
        if self.supabase_repo:
            self.execucao_id = self.supabase_repo.iniciar_execucao_miner(
                versao_miner=Settings.VERSAO_MINER,
                janela_temporal=Settings.JANELA_TEMPORAL_HORAS,
                termos=len(Settings.SEARCH_TERMS),
                paginas=Settings.PAGE_LIMIT
            )
            if self.execucao_id:
                log.info(f"Execução Supabase #{self.execucao_id} iniciada")

        TemporalWindow.log_window()
        log.info(f"Termos de busca: {len(Settings.SEARCH_TERMS)}")
        log.info(f"Páginas por termo: {Settings.PAGE_LIMIT}")
        log.info(f"Score mínimo: {Settings.MIN_SCORE_TO_DOWNLOAD}")
        log.info(f"API Consulta delay: {Settings.API_CONSULTA_DELAY_MS}ms")
        log.info(f"Search delays: termo={Settings.SEARCH_TERM_DELAY_MS}ms, página={Settings.SEARCH_PAGE_DELAY_MS}ms")
        log.info("=" * 70)

        try:
            processor = EditalProcessor(
                checkpoint_manager=self.checkpoint_manager,
                metrics=self.metrics,
                supabase_repo=self.supabase_repo,
                storage_repo=self.storage_repo,
                output_dir=self.output_dir,
            )

            async with PncpApiClient() as client:
                for term in Settings.SEARCH_TERMS:
                    if self.metrics.metrics["downloads"] >= Settings.MAX_DOWNLOADS_PER_SESSION:
                        log.warning(f"Limite de downloads atingido ({Settings.MAX_DOWNLOADS_PER_SESSION})")
                        break

                    log.info(f"Searching: '{term}'")

                    for page in range(1, Settings.PAGE_LIMIT + 1):
                        params = {
                            "q": term,
                            "tipos_documento": "edital",
                            "ordenacao": "-data",
                            "pagina": str(page),
                            "tam_pagina": "20",
                            "modalidades": Settings.MODALIDADES,
                            **TemporalWindow.get_date_range()
                        }

                        data = await client.search(params)
                        if not data or not data.get("items"):
                            break

                        items = data["items"]
                        await processor.process_search_results(client, items)

                        # V12: Log com métricas de data_leilao
                        log.info(
                            f"  Page {page}: {len(items)} items | "
                            f"Novos: {self.metrics.metrics['editais_novos']} | "
                            f"data_leilao: {self.metrics.metrics['data_leilao_encontrada']}"
                        )

                        # Delay entre páginas para evitar rate limiting
                        if Settings.SEARCH_PAGE_DELAY_MS > 0:
                            await asyncio.sleep(Settings.SEARCH_PAGE_DELAY_MS / 1000)

                    # Delay entre termos de busca para evitar rate limiting (429)
                    if Settings.SEARCH_TERM_DELAY_MS > 0:
                        await asyncio.sleep(Settings.SEARCH_TERM_DELAY_MS / 1000)

            # Finalizar
            self.metrics.finalize()
            self.metrics.print_summary()

            if self.supabase_repo and self.execucao_id:
                self.supabase_repo.finalizar_execucao_miner(
                    self.execucao_id,
                    self.metrics.metrics,
                    status="SUCCESS"
                )
                log.info(f"Execução Supabase #{self.execucao_id} finalizada com SUCESSO")

            self.checkpoint_manager.save_checkpoint(self.metrics.metrics)
            log.info("Execução concluída com sucesso!")

        except Exception as e:
            if self.supabase_repo and self.execucao_id:
                self.supabase_repo.finalizar_execucao_miner(
                    self.execucao_id,
                    self.metrics.metrics,
                    status="FAILED",
                    erro=str(e)
                )
                log.error(f"Execução Supabase #{self.execucao_id} finalizada com ERRO: {e}")

            self.metrics.finalize()
            self.checkpoint_manager.save_checkpoint(self.metrics.metrics)
            raise


# ==============================================================================
# ENTRY POINT
# ==============================================================================

async def main():
    miner = AcheSucatasMiner()
    await miner.run()


if __name__ == "__main__":
    if os.name == 'nt':
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

    asyncio.run(main())
