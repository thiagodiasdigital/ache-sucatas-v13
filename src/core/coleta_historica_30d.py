"""
COLETA HISTORICA 30 DIAS - SCRIPT UNICO
========================================
Script independente para popular o banco de dados com editais dos ultimos 30 dias.
NAO modifica o minerador principal (ache_sucatas_miner_v11.py).

USO:
    python coleta_historica_30d.py

CONFIGURACAO:
    - Requer .env com SUPABASE_URL e SUPABASE_SERVICE_KEY
    - Busca editais publicados nos ultimos 30 dias
    - Usa os mesmos termos e logica de scoring do minerador principal
"""

import asyncio
import aiohttp
import logging
import hashlib
import os
import re
import unicodedata
from datetime import datetime, timedelta
from typing import Optional, List
from dotenv import load_dotenv

load_dotenv()


# ==============================================================================
# CONFIGURACAO
# ==============================================================================

class Config:
    """Configuracoes para coleta historica de 30 dias."""

    # Janela temporal: 30 dias
    JANELA_DIAS = 30

    # Paginacao - mais paginas para capturar historico
    PAGE_LIMIT = 10  # Mais paginas que o miner diario
    MAX_DOWNLOADS = 500

    # API
    TIMEOUT_SEC = 60
    USER_AGENT = (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/123.0.0.0 Safari/537.36"
    )

    # Modalidades: Leilao (1) e Leilao Eletronico (13)
    MODALIDADES = "1|13"
    MIN_SCORE = 50  # Baixado de 60 para capturar mais editais historicos

    # Debug mode
    DEBUG_SCORES = True  # Mostra scores dos primeiros editais

    # Termos de busca (mesmos do miner principal)
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

    # Storage
    STORAGE_BUCKET = os.getenv("SUPABASE_STORAGE_BUCKET", "editais-pdfs")

    # Extensoes permitidas
    ALLOWED_EXTENSIONS = {".pdf", ".xlsx", ".xls", ".csv", ".zip", ".docx", ".doc"}

    CONTENT_TYPE_MAP = {
        ".pdf": "application/pdf",
        ".xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        ".xls": "application/vnd.ms-excel",
        ".csv": "text/csv",
        ".zip": "application/zip",
        ".docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        ".doc": "application/msword",
    }


# Logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s | %(levelname)-8s | %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
log = logging.getLogger("ColetaHistorica30d")


# ==============================================================================
# SCORING ENGINE (igual ao miner principal)
# ==============================================================================

class ScoringEngine:
    """Calcula score de relevancia para editais."""

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
    def calculate(titulo: str, descricao: str, objeto: str) -> int:
        texto = f"{titulo} {descricao} {objeto}".lower()
        score = 50

        for kw, pts in ScoringEngine.KEYWORDS_POSITIVE.items():
            if kw in texto:
                score += pts

        for kw, pts in ScoringEngine.KEYWORDS_LEILOEIRO.items():
            if kw in texto:
                score += pts

        for kw, pts in ScoringEngine.KEYWORDS_NEGATIVE.items():
            if kw in texto:
                score += pts

        return min(max(score, 0), 100)


# ==============================================================================
# FILE TYPE DETECTION
# ==============================================================================

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
        if not content_type:
            return None
        ct = content_type.lower().split(';')[0].strip()
        return FileTypeDetector.CONTENT_TYPE_MAP.get(ct)

    @staticmethod
    def detect_by_magic_bytes(data: bytes) -> Optional[str]:
        for magic, ext in FileTypeDetector.MAGIC_BYTES.items():
            if data.startswith(magic):
                return ext

        if data.startswith(b'PK\x03\x04'):
            if b'xl/' in data[:1000]:
                return '.xlsx'
            if b'word/' in data[:1000]:
                return '.docx'
            return '.zip'

        return None


# ==============================================================================
# METRICAS SIMPLES
# ==============================================================================

class Metrics:
    """Rastreia metricas da coleta."""

    def __init__(self):
        self.start_time = datetime.now()
        self.editais_analisados = 0
        self.editais_novos = 0
        self.editais_duplicados = 0
        self.editais_existentes_db = 0
        self.downloads = 0
        self.downloads_sucesso = 0
        self.downloads_falha = 0
        self.storage_uploads = 0
        self.storage_errors = 0
        self.db_inserts = 0
        self.db_errors = 0

    def print_summary(self):
        duration = (datetime.now() - self.start_time).total_seconds()
        log.info("=" * 70)
        log.info("RESUMO DA COLETA HISTORICA - 30 DIAS")
        log.info("=" * 70)
        log.info(f"Duracao: {duration:.1f}s ({duration/60:.1f} min)")
        log.info(f"Editais analisados: {self.editais_analisados}")
        log.info(f"  |- Novos inseridos: {self.editais_novos}")
        log.info(f"  |- Duplicados (sessao): {self.editais_duplicados}")
        log.info(f"  |- Ja existiam no DB: {self.editais_existentes_db}")
        log.info(f"Downloads: {self.downloads}")
        log.info(f"  |- Sucesso: {self.downloads_sucesso}")
        log.info(f"  |- Falha: {self.downloads_falha}")
        log.info(f"Storage uploads: {self.storage_uploads} (erros: {self.storage_errors})")
        log.info(f"DB inserts: {self.db_inserts} (erros: {self.db_errors})")
        log.info("=" * 70)


# ==============================================================================
# API CLIENT
# ==============================================================================

class PncpApiClient:
    """Cliente para API do PNCP."""

    BASE_URL = "https://pncp.gov.br/api/search/"

    def __init__(self):
        self.session: Optional[aiohttp.ClientSession] = None

    async def __aenter__(self):
        timeout = aiohttp.ClientTimeout(total=Config.TIMEOUT_SEC)
        self.session = aiohttp.ClientSession(
            timeout=timeout,
            headers={"User-Agent": Config.USER_AGENT}
        )
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if self.session:
            await self.session.close()

    async def search(self, params: dict) -> Optional[dict]:
        try:
            async with self.session.get(self.BASE_URL, params=params) as resp:
                if resp.status == 200:
                    return await resp.json()
                log.warning(f"API status {resp.status}")
        except Exception as e:
            log.warning(f"Search error: {e}")
        return None

    async def list_files(self, files_url: str) -> List[dict]:
        try:
            async with self.session.get(files_url) as resp:
                if resp.status == 200:
                    return await resp.json()
        except Exception as e:
            log.warning(f"Files metadata error: {e}")
        return []

    async def download_file(self, url: str) -> Optional[bytes]:
        try:
            async with self.session.get(url) as resp:
                if resp.status == 200:
                    return await resp.read()
        except Exception as e:
            log.warning(f"Download error: {e}")
        return None


# ==============================================================================
# COLETA HISTORICA
# ==============================================================================

class ColetaHistorica:
    """Executa coleta historica de 30 dias."""

    def __init__(self):
        self.metrics = Metrics()
        self.processed_ids = set()  # Deduplicacao na sessao

        # Supabase Repository (PostgreSQL)
        self.supabase_repo = None
        try:
            from supabase_repository import SupabaseRepository
            self.supabase_repo = SupabaseRepository(enable_supabase=True)
            if not self.supabase_repo.enable_supabase:
                log.error("Supabase nao configurado - verifique .env")
                self.supabase_repo = None
            else:
                log.info("Supabase PostgreSQL conectado")
        except Exception as e:
            log.error(f"Erro ao conectar Supabase: {e}")
            self.supabase_repo = None

        # Supabase Storage
        self.storage_repo = None
        try:
            from supabase_storage import SupabaseStorageRepository
            self.storage_repo = SupabaseStorageRepository(bucket_name=Config.STORAGE_BUCKET)
            if not self.storage_repo.enable_storage:
                log.warning("Supabase Storage nao configurado")
                self.storage_repo = None
            else:
                log.info(f"Supabase Storage conectado: bucket={Config.STORAGE_BUCKET}")
        except Exception as e:
            log.error(f"Erro ao conectar Storage: {e}")
            self.storage_repo = None

        # Carregar IDs existentes do banco (usa paginação para pegar todos)
        self.existing_ids = set()
        if self.supabase_repo:
            try:
                self.existing_ids = self.supabase_repo.listar_todos_pncp_ids()
                log.info(f"Carregados {len(self.existing_ids)} IDs existentes do banco")
            except Exception as e:
                log.warning(f"Nao foi possivel carregar IDs existentes: {e}")

    def _get_date_range(self) -> dict:
        """Retorna janela de 30 dias."""
        data_fim = datetime.now()
        data_inicio = data_fim - timedelta(days=Config.JANELA_DIAS)
        return {
            "data_publicacao_inicio": data_inicio.strftime("%Y-%m-%d"),
            "data_publicacao_fim": data_fim.strftime("%Y-%m-%d")
        }

    def _construct_files_url(self, item: dict) -> str:
        """Constroi URL para lista de arquivos do edital."""
        cnpj = item.get("orgao_cnpj")
        ano = item.get("ano_compra") or item.get("ano")
        seq = item.get("numero_sequencial")

        if cnpj and ano and seq:
            return (
                f"https://pncp.gov.br/api/pncp/v1/orgaos/{cnpj}/"
                f"compras/{ano}/{seq}/arquivos"
            )
        return ""

    def _parse_date(self, date_str: Optional[str]) -> Optional[datetime]:
        if not date_str:
            return None
        try:
            return datetime.fromisoformat(date_str.replace('Z', '+00:00'))
        except:
            return None

    def _normalize_pncp_id(self, pncp_id: str) -> str:
        """Normaliza pncp_id para formato padrao com hifen (-)."""
        if not pncp_id:
            return ""
        # API retorna com "/" antes do ano, banco usa "-"
        return pncp_id.replace("/", "-")

    async def _process_item(self, client: PncpApiClient, item: dict):
        """Processa um item da busca."""
        pncp_id_raw = item.get("numero_controle_pncp")
        if not pncp_id_raw:
            return

        # Normalizar formato do pncp_id (API usa "/" , banco usa "-")
        pncp_id = self._normalize_pncp_id(pncp_id_raw)

        self.metrics.editais_analisados += 1

        # Deduplicacao: ja processado nesta sessao?
        if pncp_id in self.processed_ids:
            self.metrics.editais_duplicados += 1
            return

        # Ja existe no banco?
        if pncp_id in self.existing_ids:
            self.metrics.editais_existentes_db += 1
            return

        self.processed_ids.add(pncp_id)

        try:
            titulo = item.get("titulo_objeto", "")
            descricao = item.get("descricao_objeto", "")
            objeto = item.get("objeto", "")

            score = ScoringEngine.calculate(titulo, descricao, objeto)

            # Debug: mostrar primeiros editais com seus scores
            if Config.DEBUG_SCORES and self.metrics.editais_analisados <= 10:
                log.info(f"  [DEBUG] Score={score} | {titulo[:60]}...")

            if score < Config.MIN_SCORE:
                return

            files_url = self._construct_files_url(item)

            # Construir link PNCP
            cnpj = item.get("orgao_cnpj", "")
            ano = item.get("ano_compra", "")
            seq = item.get("numero_sequencial", "")
            link_pncp = f"https://pncp.gov.br/app/editais/{cnpj}/{ano}/{seq}" if cnpj and ano and seq else ""

            # Campo correto é "uf" (sigla), não "uf_nome" (vem None)
            edital_data = {
                "pncp_id": pncp_id,
                "orgao_nome": item.get("orgao_nome", ""),
                "orgao_cnpj": cnpj,
                "uf": item.get("uf", ""),
                "municipio": item.get("municipio_nome", ""),
                "titulo": titulo,
                "descricao": descricao,
                "objeto": objeto,
                "data_publicacao": self._parse_date(item.get("data_publicacao")),
                "modalidade": item.get("modalidade_nome"),
                "situacao": item.get("situacao_nome"),
                "score": score,
                "files_url": files_url,
                "link_pncp": link_pncp,
                "ano_compra": ano,
                "numero_sequencial": seq,
                "storage_path": None,
                "pdf_storage_url": None,
            }

            # Download e upload de arquivos
            if files_url:
                pdf_url = await self._download_and_upload_files(client, files_url, pncp_id)
                if pdf_url:
                    edital_data["pdf_storage_url"] = pdf_url
                    edital_data["storage_path"] = f"{pncp_id}/"

            # Inserir no banco
            await self._insert_to_db(edital_data)

        except Exception as e:
            log.error(f"Erro processando {pncp_id}: {e}")

    async def _download_and_upload_files(
        self, client: PncpApiClient, files_url: str, pncp_id: str
    ) -> Optional[str]:
        """Download arquivos e upload para Storage. Retorna URL do primeiro PDF."""
        files_metadata = await client.list_files(files_url)
        if not files_metadata:
            return None

        pdf_storage_url = None

        for file_meta in files_metadata:
            url = file_meta.get("url")
            if not url:
                continue

            self.metrics.downloads += 1

            try:
                file_data = await client.download_file(url)
                if not file_data:
                    self.metrics.downloads_falha += 1
                    continue

                # Detectar tipo
                content_type = file_meta.get("tipo")
                ext = FileTypeDetector.detect_by_content_type(content_type)
                if not ext:
                    ext = FileTypeDetector.detect_by_magic_bytes(file_data)

                if not ext or ext not in Config.ALLOWED_EXTENSIONS:
                    self.metrics.downloads_falha += 1
                    continue

                self.metrics.downloads_sucesso += 1

                # Upload para Storage
                if self.storage_repo and self.storage_repo.enable_storage:
                    file_hash = hashlib.md5(file_data).hexdigest()[:8]
                    filename = f"{file_hash}{ext}"
                    mime_type = Config.CONTENT_TYPE_MAP.get(ext, "application/octet-stream")

                    storage_url = self.storage_repo.upload_file(
                        f"{pncp_id}/{filename}",
                        file_data,
                        mime_type
                    )

                    if storage_url:
                        self.metrics.storage_uploads += 1
                        # Guardar URL do primeiro PDF
                        if ext == ".pdf" and not pdf_storage_url:
                            pdf_storage_url = storage_url
                    else:
                        self.metrics.storage_errors += 1

            except Exception as e:
                log.warning(f"Erro download/upload: {e}")
                self.metrics.downloads_falha += 1

        return pdf_storage_url

    async def _insert_to_db(self, edital_data: dict):
        """Insere edital no Supabase."""
        if not self.supabase_repo:
            return

        try:
            # Converter datetime para string
            if edital_data.get("data_publicacao"):
                edital_data["data_publicacao"] = edital_data["data_publicacao"].isoformat()

            sucesso = self.supabase_repo.inserir_edital_miner(edital_data)
            if sucesso:
                self.metrics.db_inserts += 1
                self.metrics.editais_novos += 1
                log.info(f"  + Inserido: {edital_data['pncp_id']} | Score: {edital_data['score']} | {edital_data['uf']}")
            else:
                self.metrics.db_errors += 1
        except Exception as e:
            self.metrics.db_errors += 1
            log.error(f"Erro DB para {edital_data['pncp_id']}: {e}")

    async def run(self):
        """Executa a coleta historica."""
        log.info("=" * 70)
        log.info("COLETA HISTORICA - ULTIMOS 30 DIAS")
        log.info("=" * 70)

        if not self.supabase_repo:
            log.error("Supabase nao configurado. Abortando.")
            return

        date_range = self._get_date_range()
        log.info(f"Janela: {date_range['data_publicacao_inicio']} -> {date_range['data_publicacao_fim']}")
        log.info(f"Termos de busca: {len(Config.SEARCH_TERMS)}")
        log.info(f"Paginas por termo: {Config.PAGE_LIMIT}")
        log.info(f"Score minimo: {Config.MIN_SCORE}")
        log.info(f"Editais existentes no banco: {len(self.existing_ids)}")
        log.info("=" * 70)

        async with PncpApiClient() as client:
            for i, term in enumerate(Config.SEARCH_TERMS, 1):
                if self.metrics.downloads >= Config.MAX_DOWNLOADS:
                    log.warning(f"Limite de downloads atingido ({Config.MAX_DOWNLOADS})")
                    break

                log.info(f"[{i}/{len(Config.SEARCH_TERMS)}] Buscando: '{term}'")

                for page in range(1, Config.PAGE_LIMIT + 1):
                    params = {
                        "q": term,
                        "tipos_documento": "edital",
                        "ordenacao": "-data",
                        "pagina": str(page),
                        "tam_pagina": "20",
                        "modalidades": Config.MODALIDADES,
                        **date_range
                    }

                    data = await client.search(params)
                    if not data or not data.get("items"):
                        break

                    items = data["items"]

                    # Processar items sequencialmente para evitar rate limit
                    for item in items:
                        await self._process_item(client, item)
                        await asyncio.sleep(0.1)  # Pequeno delay

                    log.info(f"  Pagina {page}: {len(items)} items")

                    # Se menos de 20 items, nao tem mais paginas
                    if len(items) < 20:
                        break

        self.metrics.print_summary()
        log.info("Coleta historica concluida!")


# ==============================================================================
# ENTRY POINT
# ==============================================================================

async def main():
    coleta = ColetaHistorica()
    await coleta.run()


if __name__ == "__main__":
    if os.name == 'nt':
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

    asyncio.run(main())
