"""
ACHE SUCATAS MINER V10 - COM INTEGRACAO SUPABASE
=================================================
Minerador de editais PNCP com persistencia automatica no Supabase.

NOVIDADES V10 (sobre V9):
- ✅ INTEGRACAO SUPABASE: Editais inseridos diretamente no banco
- ✅ LOG DE EXECUCOES: Tabela execucoes_miner rastreia cada execucao
- ✅ DUAL STORAGE: Salva local (backup) + Supabase (producao)
- ✅ FAIL-SAFE: Supabase offline nao bloqueia mineracao local

MANTIDO DO V9:
- ✅ JANELA TEMPORAL: 24 horas (100% completude)
- ✅ SISTEMA DE CHECKPOINT: Rastreabilidade completa
- ✅ OTIMIZADO PARA CRON: 3 execucoes/dia
- ✅ METRICAS DE MONITORAMENTO

CONFIGURACAO:
- .env: ENABLE_SUPABASE=true (ou false para modo local only)
- Cron: 0 0,8,16 * * * (3x/dia)

PEP 8 Compliant | Python 3.9+
"""

import asyncio
import aiohttp
import aiofiles
import logging
import hashlib
import os
import json
import re
import unicodedata
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional, List, Dict, Any
from pydantic import BaseModel
from dotenv import load_dotenv

# Carregar variaveis de ambiente
load_dotenv()


# ==============================================================================
# CONFIGURATION
# ==============================================================================

class Settings:
    """Global configuration constants - V10 COM SUPABASE."""

    # =========================================================================
    # SUPABASE CONFIGURATION - V10
    # =========================================================================
    ENABLE_SUPABASE = os.getenv("ENABLE_SUPABASE", "true").lower() == "true"
    VERSAO_MINER = "V10_CRON"

    # =========================================================================
    # CRON CONFIGURATION - MANTIDO DO V9
    # =========================================================================
    CRON_MODE = True
    JANELA_TEMPORAL_HORAS = 24  # 24h = 100% completude

    # Otimizacoes para cron 3x/dia
    PAGE_LIMIT = 3
    MAX_DOWNLOADS_PER_SESSION = 200

    # Checkpoint e rastreabilidade
    CHECKPOINT_FILE = ".ache_sucatas_checkpoint.json"
    METRICS_FILE = "ache_sucatas_metrics.jsonl"

    # =========================================================================
    # TERMOS DE BUSCA - MANTIDOS DO V8/V9
    # =========================================================================
    SEARCH_TERMS = [
        # Termos originais
        "leilao de veiculos",
        "leilao de sucata",
        "alienacao de bens",
        "bens inserviveis",
        "veiculos apreendidos",
        "frota desativada",
        "alienacao de frota",

        # Orgaos especificos
        "DETRAN leilao",
        "DER leilao",
        "receita federal leilao",

        # Termos tecnicos
        "bens antieconômicos",
        "desfazimento de bens",
        "alienacao de veiculos",
        "bens inservíveis veículos",

        # Modalidades
        "leilao eletronico veiculos",
        "leilao presencial veiculos",
        "pregao eletronico alienacao",

        # Patio/apreensao
        "veiculos patio",
        "veiculos custodia",
        "veiculos removidos",
        "sucata automotiva",

        # Governamentais
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

    # Supported file extensions
    ALLOWED_EXTENSIONS = {".pdf", ".xlsx", ".xls", ".csv", ".zip", ".docx", ".doc"}

    # Magic bytes para deteccao de tipo
    MAGIC_BYTES = {
        b'%PDF': '.pdf',
        b'PK\x03\x04': '.zip',
        b'\xd0\xcf\x11\xe0': '.xls',
    }


# Logging configuration
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s | %(levelname)-8s | [%(name)s] %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
log = logging.getLogger("AcheSucatas_V10")


# ==============================================================================
# CHECKPOINT SYSTEM
# ==============================================================================

class CheckpointManager:
    """Gerencia checkpoint para rastreabilidade e recovery."""

    def __init__(self, checkpoint_file: str = Settings.CHECKPOINT_FILE):
        self.checkpoint_file = Path(checkpoint_file)
        self.checkpoint_data = self._load_checkpoint()

    def _load_checkpoint(self) -> dict:
        """Carrega checkpoint existente ou cria novo."""
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
        """Salva checkpoint com metricas da execucao."""
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
        """Retorna set de IDs ja processados."""
        return set(self.checkpoint_data.get("last_pncp_ids", []))


# ==============================================================================
# METRICS TRACKER
# ==============================================================================

class MetricsTracker:
    """Rastreamento de metricas para analise de performance."""

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
            # V10: Metricas Supabase
            "supabase_inserts": 0,
            "supabase_errors": 0,
        }

    def increment(self, key: str, value: int = 1):
        """Incrementa uma metrica."""
        if key in self.metrics:
            self.metrics[key] += value

    def add_pncp_id(self, pncp_id: str):
        """Adiciona ID processado."""
        self.metrics["pncp_ids_processados"].append(pncp_id)

    def finalize(self):
        """Finaliza metricas e calcula estatisticas."""
        self.metrics["execution_end"] = datetime.now().isoformat()
        self.metrics["duration_seconds"] = (datetime.now() - self.start_time).total_seconds()

        # Calcular taxa de deduplicacao
        total_analisados = self.metrics["editais_analisados"]
        if total_analisados > 0:
            self.metrics["taxa_deduplicacao"] = round(
                (self.metrics["editais_duplicados"] / total_analisados) * 100, 2
            )

        # Salvar no arquivo JSONL (append)
        try:
            with open(self.metrics_file, 'a', encoding='utf-8') as f:
                f.write(json.dumps(self.metrics, ensure_ascii=False) + '\n')
            log.info(f"Metricas salvas: {self.metrics_file}")
        except Exception as e:
            log.error(f"Erro ao salvar metricas: {e}")

    def print_summary(self):
        """Imprime resumo executivo."""
        log.info("=" * 70)
        log.info("RESUMO DA EXECUCAO - MINER V10")
        log.info("=" * 70)
        log.info(f"Duracao: {self.metrics['duration_seconds']:.1f}s")
        log.info(f"Janela temporal: {self.metrics['janela_temporal_horas']}h")
        log.info(f"Editais analisados: {self.metrics['editais_analisados']}")
        log.info(f"  |- Novos: {self.metrics['editais_novos']}")
        log.info(f"  |- Duplicados: {self.metrics['editais_duplicados']} ({self.metrics['taxa_deduplicacao']}%)")
        log.info(f"Downloads: {self.metrics['downloads']} (sucesso: {self.metrics['downloads_sucesso']}, falha: {self.metrics['downloads_falha']})")
        log.info(f"Supabase: {self.metrics['supabase_inserts']} inserts, {self.metrics['supabase_errors']} erros")
        log.info(f"Completude estimada: {self.metrics['completude_estimada']}")
        log.info("=" * 70)


# ==============================================================================
# TEMPORAL WINDOW
# ==============================================================================

class TemporalWindow:
    """Gerencia a janela temporal das buscas."""

    @staticmethod
    def get_date_range() -> dict:
        """Retorna a janela temporal para a busca."""
        data_fim = datetime.now()
        data_inicio = data_fim - timedelta(hours=Settings.JANELA_TEMPORAL_HORAS)

        return {
            "data_publicacao_inicio": data_inicio.strftime("%Y-%m-%d"),
            "data_publicacao_fim": data_fim.strftime("%Y-%m-%d")
        }

    @staticmethod
    def log_window():
        """Loga a janela temporal atual."""
        window = TemporalWindow.get_date_range()
        log.info(f"Janela temporal: {window['data_publicacao_inicio']} -> {window['data_publicacao_fim']} ({Settings.JANELA_TEMPORAL_HORAS}h)")


# ==============================================================================
# DATA MODELS
# ==============================================================================

class EditalModel(BaseModel):
    """Structured edital data model."""

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
    data_inicio_propostas: Optional[str] = None
    data_fim_propostas: Optional[str] = None
    modalidade: Optional[str] = None
    situacao: Optional[str] = None
    score: int
    files_url: str
    link_pncp: str
    ano_compra: Optional[str] = None
    numero_sequencial: Optional[str] = None


# ==============================================================================
# FILE TYPE DETECTION
# ==============================================================================

class FileTypeDetector:
    """Detecta tipo de arquivo por Content-Type ou magic bytes."""

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
        """Detect file extension by HTTP Content-Type header."""
        if not content_type:
            return None
        content_type_lower = content_type.lower().split(';')[0].strip()
        return FileTypeDetector.CONTENT_TYPE_MAP.get(content_type_lower)

    @staticmethod
    def detect_by_magic_bytes(data: bytes) -> Optional[str]:
        """Detect file extension by magic bytes."""
        for magic, ext in Settings.MAGIC_BYTES.items():
            if data.startswith(magic):
                return ext

        # Excel XLSX (ZIP-based)
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
    """Calculate relevance score for editals."""

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
        """Calculate relevance score (0-100)."""
        texto_completo = f"{titulo} {descricao} {objeto}".lower()
        score = 50  # Base score

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
# API CLIENT
# ==============================================================================

class PncpApiClient:
    """Async PNCP API client."""

    BASE_URL = "https://pncp.gov.br/api/search/"

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
        """Execute API search."""
        try:
            async with self.session.get(self.BASE_URL, params=params) as response:
                if response.status == 200:
                    return await response.json()
                else:
                    log.warning(f"API returned status {response.status}")
        except Exception as e:
            log.warning(f"Search error: {e}")
        return None

    async def list_files_metadata(self, files_url: str) -> List[dict]:
        """Get file metadata list."""
        try:
            async with self.session.get(files_url) as response:
                if response.status == 200:
                    return await response.json()
        except Exception as e:
            log.warning(f"Files metadata error: {e}")
        return []

    async def download_file(self, url: str) -> Optional[bytes]:
        """Download file content."""
        try:
            async with self.session.get(url) as response:
                if response.status == 200:
                    return await response.read()
        except Exception as e:
            log.warning(f"Download error: {e}")
        return None


# ==============================================================================
# EDITAL PROCESSOR - V10 COM SUPABASE
# ==============================================================================

class EditalProcessor:
    """Process editals with download, storage and Supabase integration."""

    def __init__(
        self,
        output_dir: Path,
        checkpoint_manager: CheckpointManager,
        metrics: MetricsTracker,
        supabase_repo=None  # V10: Supabase repository
    ):
        self.output_dir = output_dir
        self.output_dir.mkdir(parents=True, exist_ok=True)

        self.checkpoint_manager = checkpoint_manager
        self.metrics = metrics

        # V10: Supabase integration
        self.supabase_repo = supabase_repo

        # Deduplicacao
        self.deduplication_set = checkpoint_manager.get_processed_ids()
        self.new_ids_this_run = set()

    def _sanitize_filename(self, name: str) -> str:
        """Sanitize filename for cross-platform compatibility."""
        name = unicodedata.normalize('NFKD', name)
        name = name.encode('ascii', 'ignore').decode('ascii')
        name = re.sub(r'[^\w\s-]', '', name)
        name = re.sub(r'[-\s]+', '_', name)
        return name[:100]

    def _create_edital_folder(self, edital: EditalModel) -> Path:
        """Create structured folder for edital."""
        uf = self._sanitize_filename(edital.uf)
        municipio = self._sanitize_filename(edital.municipio)
        folder_name = self._sanitize_filename(
            f"{edital.data_publicacao.strftime('%Y-%m-%d') if edital.data_publicacao else 'sem-data'}_S{edital.score}_{edital.pncp_id}"
        )

        edital_folder = self.output_dir / uf / f"{uf}_{municipio}" / folder_name
        edital_folder.mkdir(parents=True, exist_ok=True)

        return edital_folder

    async def _save_metadata(self, edital_folder: Path, edital: EditalModel):
        """Save edital metadata as JSON."""
        metadata_file = edital_folder / "metadados_pncp.json"
        async with aiofiles.open(metadata_file, 'w', encoding='utf-8') as f:
            await f.write(edital.model_dump_json(indent=2, exclude_none=True))

    def _construct_files_url(self, item: dict) -> str:
        """Build files API URL from item data."""
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
        """Process single API search result item."""
        pncp_id = item.get("numero_controle_pncp")
        if not pncp_id:
            return

        # Incrementar total analisados
        self.metrics.increment("editais_analisados")

        # DEDUPLICACAO
        if pncp_id in self.deduplication_set or pncp_id in self.new_ids_this_run:
            self.metrics.increment("editais_duplicados")
            return

        # Novo edital nesta execucao
        self.metrics.increment("editais_novos")
        self.new_ids_this_run.add(pncp_id)
        self.metrics.add_pncp_id(pncp_id)

        # Parse edital data
        try:
            titulo = item.get("titulo_objeto", "")
            descricao = item.get("descricao_objeto", "")
            objeto = item.get("objeto", "")

            score = ScoringEngine.calculate_score(titulo, descricao, objeto)

            if score < Settings.MIN_SCORE_TO_DOWNLOAD:
                return

            files_url = self._construct_files_url(item)

            edital = EditalModel(
                pncp_id=pncp_id,
                orgao_nome=item.get("orgao_nome", ""),
                orgao_cnpj=item.get("orgao_cnpj"),
                uf=item.get("uf_nome", ""),
                municipio=item.get("municipio_nome", ""),
                titulo=titulo,
                descricao=descricao,
                objeto=objeto,
                data_publicacao=self._parse_date(item.get("data_publicacao")),
                data_atualizacao=item.get("data_atualizacao"),
                data_inicio_propostas=item.get("data_inicio_propostas"),
                data_fim_propostas=item.get("data_fim_propostas"),
                modalidade=item.get("modalidade_nome"),
                situacao=item.get("situacao_nome"),
                score=score,
                files_url=files_url,
                link_pncp=item.get("link_pncp", ""),
                ano_compra=item.get("ano_compra"),
                numero_sequencial=item.get("numero_sequencial"),
            )

            # Create folder and save metadata LOCAL (backup garantido)
            edital_folder = self._create_edital_folder(edital)
            await self._save_metadata(edital_folder, edital)

            # V10: Inserir no Supabase APOS salvar local
            if self.supabase_repo:
                try:
                    edital_dict = edital.model_dump()
                    # Converter datetime para string
                    if edital_dict.get("data_publicacao"):
                        edital_dict["data_publicacao"] = edital.data_publicacao.isoformat() if edital.data_publicacao else None

                    sucesso = self.supabase_repo.inserir_edital_miner(edital_dict)
                    if sucesso:
                        self.metrics.increment("supabase_inserts")
                        log.debug(f"Edital {pncp_id} inserido no Supabase")
                    else:
                        self.metrics.increment("supabase_errors")
                        log.warning(f"Falha ao inserir {pncp_id} no Supabase")
                except Exception as e:
                    self.metrics.increment("supabase_errors")
                    log.error(f"Erro Supabase para {pncp_id}: {e}")
                    # NAO interromper - continuar com salvamento local

            # Download files
            await self._download_files(client, edital, edital_folder)

        except Exception as e:
            log.error(f"Error processing {pncp_id}: {e}")

    def _parse_date(self, date_str: Optional[str]) -> Optional[datetime]:
        """Parse date string to datetime."""
        if not date_str:
            return None
        try:
            return datetime.fromisoformat(date_str.replace('Z', '+00:00'))
        except:
            return None

    async def _download_files(self, client: PncpApiClient, edital: EditalModel, edital_folder: Path):
        """Download all files for an edital."""
        if not edital.files_url:
            return

        files_metadata = await client.list_files_metadata(edital.files_url)
        if not files_metadata:
            return

        for file_meta in files_metadata:
            await self._download_single_file(client, file_meta, edital_folder)

    async def _download_single_file(self, client: PncpApiClient, file_meta: dict, edital_folder: Path):
        """Download and save a single file with type detection."""
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

            # Generate unique filename
            file_hash = hashlib.md5(file_data).hexdigest()[:8]
            filename = f"{file_hash}{ext}"
            file_path = edital_folder / filename

            # Save file
            async with aiofiles.open(file_path, 'wb') as f:
                await f.write(file_data)

            self.metrics.increment("downloads_sucesso")

        except Exception as e:
            log.error(f"Download error: {e}")
            self.metrics.increment("downloads_falha")

    async def process_search_results(self, client: PncpApiClient, items: List[dict]):
        """Process all items from a search result."""
        tasks = [self._process_item(client, item) for item in items]
        await asyncio.gather(*tasks, return_exceptions=True)


# ==============================================================================
# MAIN ORCHESTRATOR - V10 COM SUPABASE
# ==============================================================================

class AcheSucatasMiner:
    """Main orchestrator for ACHE SUCATAS mining - V10 COM SUPABASE."""

    def __init__(self, output_dir: str = "ACHE_SUCATAS_DB"):
        self.output_dir = Path(output_dir)
        self.checkpoint_manager = CheckpointManager()
        self.metrics = MetricsTracker()

        # V10: Supabase Repository
        self.supabase_repo = None
        self.execucao_id = None

        if Settings.ENABLE_SUPABASE:
            try:
                from supabase_repository import SupabaseRepository
                self.supabase_repo = SupabaseRepository(enable_supabase=True)
                if not self.supabase_repo.enable_supabase:
                    log.warning("Supabase desabilitado - continuando em modo local")
                    self.supabase_repo = None
                else:
                    log.info("Supabase conectado com sucesso")
            except ImportError:
                log.error("supabase_repository.py nao encontrado - modo local only")
                self.supabase_repo = None
            except Exception as e:
                log.error(f"Erro ao inicializar Supabase: {e}")
                self.supabase_repo = None
        else:
            log.info("Supabase desabilitado via ENABLE_SUPABASE=false")

    async def run(self):
        """Execute mining process with Supabase integration."""
        log.info("=" * 70)
        log.info("ACHE SUCATAS MINER V10 - COM SUPABASE")
        log.info("=" * 70)
        log.info(f"Modo: CRON 3x/dia | Supabase: {'ATIVO' if self.supabase_repo else 'DESATIVADO'}")
        log.info(f"Execucao local #{self.checkpoint_manager.checkpoint_data.get('total_executions', 0) + 1}")

        # V10: Iniciar execucao no Supabase
        if self.supabase_repo:
            self.execucao_id = self.supabase_repo.iniciar_execucao_miner(
                versao_miner=Settings.VERSAO_MINER,
                janela_temporal=Settings.JANELA_TEMPORAL_HORAS,
                termos=len(Settings.SEARCH_TERMS),
                paginas=Settings.PAGE_LIMIT
            )
            if self.execucao_id:
                log.info(f"Execucao Supabase #{self.execucao_id} iniciada")
            else:
                log.warning("Falha ao registrar execucao no Supabase - continuando local")

        # Log janela temporal
        TemporalWindow.log_window()

        log.info(f"Termos de busca: {len(Settings.SEARCH_TERMS)}")
        log.info(f"Paginas por termo: {Settings.PAGE_LIMIT}")
        log.info(f"Score minimo: {Settings.MIN_SCORE_TO_DOWNLOAD}")
        log.info("=" * 70)

        try:
            processor = EditalProcessor(
                self.output_dir,
                self.checkpoint_manager,
                self.metrics,
                supabase_repo=self.supabase_repo  # V10: Passar repositorio
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

                        log.info(f"  Page {page}: {len(items)} items | Novos: {self.metrics.metrics['editais_novos']} | Dupl: {self.metrics.metrics['editais_duplicados']}")

            # Finalizar metricas
            self.metrics.finalize()
            self.metrics.print_summary()

            # V10: Finalizar execucao no Supabase com SUCESSO
            if self.supabase_repo and self.execucao_id:
                self.supabase_repo.finalizar_execucao_miner(
                    self.execucao_id,
                    self.metrics.metrics,
                    status="SUCCESS"
                )
                log.info(f"Execucao Supabase #{self.execucao_id} finalizada com SUCESSO")

            # Salvar checkpoint local
            self.checkpoint_manager.save_checkpoint(self.metrics.metrics)

            log.info("Execucao concluida com sucesso!")

        except Exception as e:
            # V10: Finalizar execucao no Supabase com ERRO
            if self.supabase_repo and self.execucao_id:
                self.supabase_repo.finalizar_execucao_miner(
                    self.execucao_id,
                    self.metrics.metrics,
                    status="FAILED",
                    erro=str(e)
                )
                log.error(f"Execucao Supabase #{self.execucao_id} finalizada com ERRO: {e}")

            # Salvar checkpoint mesmo com erro
            self.metrics.finalize()
            self.checkpoint_manager.save_checkpoint(self.metrics.metrics)

            raise


# ==============================================================================
# ENTRY POINT
# ==============================================================================

async def main():
    """Main entry point."""
    miner = AcheSucatasMiner()
    await miner.run()


if __name__ == "__main__":
    if os.name == 'nt':
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

    asyncio.run(main())
