"""
ACHE SUCATAS MINER V8 - OTIMIZADO
=================================
Minerador de editais PNCP com melhorias baseadas na análise Comet/Perplexity.

MELHORIAS V8 (sobre V7):
- ✅ FILTRO CRÍTICO: "credenciamento" (elimina 30-40% falsos positivos!)
- ✅ +15 novos termos de busca (DETRAN, DER, antieconômico, etc.)
- ✅ +10 filtros negativos expandidos
- ✅ Keywords de leiloeiros expandidas (joaoemilio, leiloesfreire)
- ✅ Scoring engine otimizado com pesos ajustados

MANTIDO DO V7:
- ✅ Download FIRST → Detect type AFTER
- ✅ Magic bytes + Content-Type detection
- ✅ Suporte a PDF, XLSX, DOCX, ZIP, CSV

PEP 8 Compliant | Python 3.9+
"""

import asyncio
import aiohttp
import aiofiles
import logging
import hashlib
import os
import json
import zipfile
import re
import unicodedata
from datetime import datetime
from pathlib import Path
from typing import Optional, List, Dict, Any, Tuple
from pydantic import BaseModel


# ==============================================================================
# CONFIGURATION
# ==============================================================================

class Settings:
    """Global configuration constants."""

    # =========================================================================
    # TERMOS DE BUSCA - EXPANDIDOS V8 (baseado na análise Comet)
    # =========================================================================
    SEARCH_TERMS = [
        # Termos originais V7
        "leilao de veiculos",
        "leilao de sucata",
        "alienacao de bens",
        "bens inserviveis",
        "veiculos apreendidos",
        "frota desativada",
        "alienacao de frota",
        
        # NOVOS V8 - Órgãos específicos (alta relevância)
        "DETRAN leilao",
        "DER leilao",
        "receita federal leilao",
        
        # NOVOS V8 - Termos técnicos de desfazimento
        "bens antieconômicos",
        "desfazimento de bens",
        "alienacao de veiculos",
        "bens inservíveis veículos",
        
        # NOVOS V8 - Modalidades de leilão
        "leilao eletronico veiculos",
        "leilao presencial veiculos",
        "pregao eletronico alienacao",
        
        # NOVOS V8 - Termos de pátio/apreensão
        "veiculos patio",
        "veiculos custodia",
        "veiculos removidos",
        "sucata automotiva",
        
        # NOVOS V8 - Termos governamentais
        "alienacao patrimonio",
        "desfazimento frota",
    ]

    MODALIDADES = "1|13"
    PAGE_LIMIT = 5
    MAX_DOWNLOADS_PER_SESSION = 500
    MIN_SCORE_TO_DOWNLOAD = 60
    TIMEOUT_SEC = 45
    USER_AGENT = (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/123.0.0.0 Safari/537.36"
    )

    # Supported file extensions
    ALLOWED_EXTENSIONS = {".pdf", ".xlsx", ".xls", ".csv", ".zip", ".docx", ".doc"}

    # Magic bytes para detecção de tipo
    MAGIC_BYTES = {
        b'%PDF': '.pdf',
        b'PK\x03\x04': '.zip',
        b'\xd0\xcf\x11\xe0': '.xls',
    }


# Logging configuration
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s | %(levelname)-8s | %(message)s',
    datefmt='%H:%M:%S'
)
log = logging.getLogger("AcheSucatas_V8")


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
        'application/pdf': '.pdf',
        'application/x-pdf': '.pdf',
        'application/zip': '.zip',
        'application/x-zip-compressed': '.zip',
        'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet': '.xlsx',
        'application/vnd.ms-excel': '.xls',
        'application/vnd.openxmlformats-officedocument.wordprocessingml.document': '.docx',
        'application/msword': '.doc',
        'text/csv': '.csv',
        'application/csv': '.csv',
        'application/octet-stream': None,
    }

    @classmethod
    def detect_from_content_type(cls, content_type: str) -> Optional[str]:
        """Detecta extensão pelo Content-Type do header HTTP."""
        if not content_type:
            return None

        main_type = content_type.split(';')[0].strip().lower()
        return cls.CONTENT_TYPE_MAP.get(main_type)

    @classmethod
    def detect_from_magic_bytes(cls, content: bytes) -> Optional[str]:
        """Detecta extensão pelos primeiros bytes do arquivo."""
        if not content or len(content) < 4:
            return None

        header = content[:8]

        for magic, ext in Settings.MAGIC_BYTES.items():
            if header.startswith(magic):
                if ext == '.zip' and len(content) > 100:
                    try:
                        if b'word/' in content[:2000]:
                            return '.docx'
                        elif b'xl/' in content[:2000]:
                            return '.xlsx'
                    except:
                        pass
                return ext

        return None

    @classmethod
    def detect_extension(
        cls,
        content: bytes,
        content_type: str = None,
        original_name: str = None
    ) -> str:
        """Detecta extensão usando múltiplas estratégias."""
        # 1. Extensão do nome original
        if original_name:
            ext = Path(original_name).suffix.lower()
            if ext in Settings.ALLOWED_EXTENSIONS:
                return ext

        # 2. Content-Type
        ext = cls.detect_from_content_type(content_type)
        if ext and ext in Settings.ALLOWED_EXTENSIONS:
            return ext

        # 3. Magic bytes
        ext = cls.detect_from_magic_bytes(content)
        if ext and ext in Settings.ALLOWED_EXTENSIONS:
            return ext

        # 4. Fallback
        return '.bin'


# ==============================================================================
# SCORING ENGINE V8 - OTIMIZADO
# ==============================================================================

class ScoringEngine:
    """Content scoring and text normalization utilities - V8 OTIMIZADO."""

    # =========================================================================
    # TERMOS POSITIVOS (expandidos V8)
    # =========================================================================
    TERMOS_OURO = [
        r"\bleilao\b", r"\balienacao\b", r"\bvenda\b", r"\bdesfazimento\b",
        # NOVOS V8
        r"\barrematacao\b", r"\bhasta\s*publica\b",
    ]

    TERMOS_PRATA = [
        r"\bsucata\b", r"\binserviveis\b", r"\bociosos\b",
        r"\bveiculos\b", r"\bpatrimonio\b",
        # NOVOS V8
        r"\bantieconômicos?\b", r"\binservíveis\b", r"\bdesativad[oa]s?\b",
    ]

    CONTEXTO_VEICULAR = [
        "veiculo", "carro", "moto", "caminhao", "onibus", "frota",
        "viatura", "transporte", "fiat", "volks", "ford", "chevrolet",
        "toyota", "honda", "scania", "volvo", "mercedes",
        "sucata automotiva", "semirreboque", "chassi",
        # NOVOS V8
        "automovel", "motocicleta", "utilitario", "pickup",
        "reboque", "carreta", "trator", "kombi", "van",
        "renault", "hyundai", "kia", "nissan", "mitsubishi",
    ]

    # =========================================================================
    # BLACKLIST EXPANDIDA V8 - CRÍTICO!
    # =========================================================================
    BLACKLIST_MORTAL = [
        # Originais V7
        r"\baquisicao\b", r"\bcompra\b", r"\bcontratacao\b",
        r"\bprestacao de servico", r"\blocacao\b", r"\bmanutencao\b",
        r"\breforma\b", r"\bobras\b", r"\bpublicidade\b",
        
        # CRÍTICO V8 - Elimina 30-40% de falsos positivos!
        r"\bcredenciamento\b",
        r"\bcredenciamento de leiloeiros?\b",
        r"\bcadastro de leiloeiros?\b",
        r"\bhabilitacao de leiloeiros?\b",
        
        # NOVOS V8 - Filtros adicionais
        r"\bregistro de precos?\b",
        r"\bata de registro\b",
        r"\bchamamento publico\b",
        r"\binexigibilidade\b",
        r"\bdispensa de licitacao\b",
        r"\bservicos continuados\b",
        r"\bconcurso publico\b",
        r"\bprocesso seletivo\b",
        r"\bconcorrencia publica\b",
        r"\btomada de precos?\b",
    ]

    # =========================================================================
    # ÓRGÃOS DE ALTA RELEVÂNCIA V8
    # =========================================================================
    ORGAOS_PREMIUM = [
        r"\bdetran\b", r"\bder\b", r"\breceita federal\b",
        r"\bpolicia\b", r"\bpm\b", r"\bprf\b",
        r"\btribunal\b", r"\btj[a-z]{2}\b",
        r"\bpatio\b", r"\bcustodia\b",
    ]

    @staticmethod
    def normalize_text(text: str) -> str:
        """Normalize text for scoring."""
        if not text:
            return ""
        text = unicodedata.normalize("NFKD", text)
        text = text.encode("ASCII", "ignore").decode("ASCII")
        return text.lower().strip()

    @classmethod
    def calculate_score(cls, titulo: str, descricao: str) -> int:
        """
        Calcula score de relevância - V8 OTIMIZADO.
        
        Escala: 0-100
        - >= 80: Alta relevância (leilão de veículos confirmado)
        - 60-79: Média relevância (provável leilão)
        - < 60: Baixa relevância (rejeitado)
        """
        combined = cls.normalize_text(f"{titulo} {descricao}")
        score = 0

        # BLACKLIST MORTAL - Rejeição imediata
        for pattern in cls.BLACKLIST_MORTAL:
            if re.search(pattern, combined, re.IGNORECASE):
                return 0

        # Termos OURO (+25 cada, max 50)
        ouro_count = 0
        for pattern in cls.TERMOS_OURO:
            if re.search(pattern, combined, re.IGNORECASE):
                ouro_count += 1
        score += min(ouro_count * 25, 50)

        # Termos PRATA (+15 cada, max 30)
        prata_count = 0
        for pattern in cls.TERMOS_PRATA:
            if re.search(pattern, combined, re.IGNORECASE):
                prata_count += 1
        score += min(prata_count * 15, 30)

        # Contexto VEICULAR (+5 cada, max 20)
        veicular_count = sum(
            1 for term in cls.CONTEXTO_VEICULAR if term in combined
        )
        score += min(veicular_count * 5, 20)

        # BÔNUS V8: Órgãos premium (+15)
        for pattern in cls.ORGAOS_PREMIUM:
            if re.search(pattern, combined, re.IGNORECASE):
                score += 15
                break

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
            async with self.session.get(
                self.BASE_URL, params=params
            ) as response:
                if response.status == 200:
                    return await response.json()
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

    async def download_file(self, url: str) -> Tuple[Optional[bytes], Optional[str]]:
        """
        Download file and return content with Content-Type.
        
        Returns:
            Tuple of (content_bytes, content_type)
        """
        try:
            async with self.session.get(url) as response:
                if response.status == 200:
                    content = await response.read()
                    content_type = response.headers.get('Content-Type', '')
                    return content, content_type
        except Exception as e:
            log.warning(f"Download error: {e}")
        return None, None


# ==============================================================================
# UTILITY FUNCTIONS
# ==============================================================================

async def save_metadata_json(
    target_path: Path,
    edital: EditalModel,
    files_meta: List[dict]
):
    """Save edital metadata to JSON file."""
    metadata = {
        "pncp_id": edital.pncp_id,
        "titulo": edital.titulo,
        "descricao": edital.descricao,
        "objeto": edital.objeto,
        "orgao_nome": edital.orgao_nome,
        "orgao_cnpj": edital.orgao_cnpj,
        "uf": edital.uf,
        "municipio": edital.municipio,
        "data_publicacao": edital.data_publicacao.isoformat() if edital.data_publicacao else None,
        "data_atualizacao": edital.data_atualizacao,
        "data_inicio_propostas": edital.data_inicio_propostas,
        "data_fim_propostas": edital.data_fim_propostas,
        "modalidade": edital.modalidade,
        "situacao": edital.situacao,
        "score": edital.score,
        "link_pncp": edital.link_pncp,
        "files_meta": files_meta,
        "miner_version": "V8",
        "extracted_at": datetime.now().isoformat()
    }

    json_path = target_path / "metadados_pncp.json"
    async with aiofiles.open(json_path, "w", encoding="utf-8") as f:
        await f.write(json.dumps(metadata, ensure_ascii=False, indent=2))


async def extract_zip_file(zip_path: Path, target_dir: Path):
    """Extract ZIP file contents."""
    try:
        with zipfile.ZipFile(zip_path, 'r') as zf:
            for member in zf.namelist():
                ext = Path(member).suffix.lower()
                if ext in Settings.ALLOWED_EXTENSIONS:
                    zf.extract(member, target_dir)
                    log.info(f"   📦 Extracted from ZIP: {member}")
    except Exception as e:
        log.warning(f"   ZIP extraction error: {e}")


# ==============================================================================
# MAIN MINER
# ==============================================================================

class EditalMiner:
    """Main edital mining orchestrator - V8."""

    def __init__(self, output_dir: str = "ACHE_SUCATAS_DB"):
        self.root_dir = Path(output_dir)
        self.root_dir.mkdir(exist_ok=True)
        self.deduplication_set: set = set()
        self.stats = {
            "processed": 0,
            "accepted": 0,
            "rejected": 0,
            "rejected_blacklist": 0,
            "downloads": 0,
            "downloads_by_type": {},
            "skipped_types": {}
        }

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
        if not pncp_id or pncp_id in self.deduplication_set:
            return

        self.deduplication_set.add(pncp_id)
        self.stats["processed"] += 1

        titulo = item.get("title", "")
        descricao = item.get("description", "")
        score = ScoringEngine.calculate_score(titulo, descricao)

        # V8: Rastrear rejeições por blacklist
        if score == 0:
            self.stats["rejected_blacklist"] += 1
            self.stats["rejected"] += 1
            return

        if score < Settings.MIN_SCORE_TO_DOWNLOAD:
            self.stats["rejected"] += 1
            return

        self.stats["accepted"] += 1

        # Parse publication date
        data_str = item.get("data_publicacao_pncp", "")
        dt_pub = None
        if data_str:
            try:
                dt_pub = datetime.fromisoformat(data_str[:19])
            except:
                pass

        # Build edital model
        edital = EditalModel(
            pncp_id=pncp_id,
            orgao_nome=item.get("orgao_nome", "ND"),
            orgao_cnpj=item.get("orgao_cnpj"),
            uf=item.get("uf", "BR"),
            municipio=item.get("municipio_nome", "ND"),
            titulo=titulo,
            descricao=descricao,
            objeto=item.get("objeto"),
            data_publicacao=dt_pub,
            data_atualizacao=item.get("data_atualizacao"),
            data_inicio_propostas=item.get("data_inicio_propostas"),
            data_fim_propostas=item.get("data_fim_propostas"),
            modalidade=item.get("modalidade"),
            situacao=item.get("situacao"),
            score=score,
            files_url=self._construct_files_url(item),
            link_pncp=f"https://pncp.gov.br/app/editais/{pncp_id}",
            ano_compra=item.get("ano_compra") or item.get("ano"),
            numero_sequencial=item.get("numero_sequencial")
        )

        log.info(
            f"[Score {score}] {edital.municipio}/{edital.uf}: "
            f"{edital.titulo[:60]}..."
        )

        await self._download_attachments(client, edital)

    async def _download_attachments(
        self,
        client: PncpApiClient,
        edital: EditalModel
    ):
        """Download all attachments for an edital."""
        if not edital.files_url:
            return

        if self.stats["downloads"] >= Settings.MAX_DOWNLOADS_PER_SESSION:
            return

        files_meta = await client.list_files_metadata(edital.files_url)

        # Build target directory path
        safe_mun = ScoringEngine.normalize_text(edital.municipio)
        safe_mun = safe_mun.replace(" ", "_").upper()

        date_str = "SEM_DATA"
        if edital.data_publicacao:
            date_str = edital.data_publicacao.strftime("%Y-%m-%d")

        pncp_safe = edital.pncp_id.replace('/', '-')
        target_path = (
            self.root_dir / f"{edital.uf}_{safe_mun}" /
            f"{date_str}_S{edital.score}_{pncp_safe}"
        )

        # Save metadata first
        if not target_path.exists():
            target_path.mkdir(parents=True, exist_ok=True)

        await save_metadata_json(target_path, edital, files_meta)

        # Download files
        for f_meta in files_meta:
            original_name = f_meta.get("titulo", "documento")
            url = f_meta.get("url")

            if not url:
                continue

            # Download FIRST
            content, content_type = await client.download_file(url)

            if not content:
                log.warning(f"   Falha ao baixar: {original_name}")
                continue

            # Detect type AFTER
            ext = FileTypeDetector.detect_extension(
                content=content,
                content_type=content_type,
                original_name=original_name
            )

            # Filter unsupported types
            if ext == '.bin' or ext not in Settings.ALLOWED_EXTENSIONS:
                self.stats["skipped_types"][ext] = (
                    self.stats["skipped_types"].get(ext, 0) + 1
                )
                log.warning(f"   Tipo não suportado ({ext}): {original_name}")
                continue

            # Generate safe filename - V8 FIX: Remove caracteres inválidos!
            file_hash = hashlib.md5(content).hexdigest()[:6]
            safe_name = ScoringEngine.normalize_text(original_name)
            # Remover caracteres inválidos para Windows/Linux
            safe_name = re.sub(r'[<>:"/\\|?*]', '_', safe_name)
            safe_name = safe_name.replace(" ", "_")[:50]
            final_name = f"{safe_name}_{file_hash}{ext}"

            output_path = target_path / final_name

            # Save file
            if not output_path.exists():
                async with aiofiles.open(output_path, "wb") as f:
                    await f.write(content)

                self.stats["downloads"] += 1
                self.stats["downloads_by_type"][ext] = (
                    self.stats["downloads_by_type"].get(ext, 0) + 1
                )
                log.info(f"   ✅ Downloaded: {final_name} ({ext})")

                # Extract ZIP if applicable
                if ext == ".zip":
                    await extract_zip_file(output_path, target_path)

    async def run(self):
        """Execute main mining workflow."""
        log.info("=" * 60)
        log.info("ACHE SUCATAS MINER v8.0 (OTIMIZADO) - STARTED")
        log.info("=" * 60)
        log.info("MELHORIAS V8:")
        log.info("  - Filtro 'credenciamento' (elimina falsos positivos)")
        log.info("  - +15 novos termos de busca")
        log.info("  - +10 filtros negativos")
        log.info("  - Órgãos premium (DETRAN, DER, Receita Federal)")
        log.info("=" * 60)

        async with PncpApiClient() as client:
            for term in Settings.SEARCH_TERMS:
                if self.stats["downloads"] >= Settings.MAX_DOWNLOADS_PER_SESSION:
                    break

                log.info(f"Searching: '{term}'")

                for page in range(1, Settings.PAGE_LIMIT + 1):
                    params = {
                        "q": term,
                        "tipos_documento": "edital",
                        "ordenacao": "-data",
                        "pagina": str(page),
                        "tam_pagina": "20",
                        "modalidades": Settings.MODALIDADES
                    }

                    data = await client.search(params)
                    if not data or not data.get("items"):
                        break

                    tasks = [
                        self._process_item(client, item)
                        for item in data["items"]
                    ]
                    await asyncio.gather(*tasks)

                    await asyncio.sleep(1)

        # Final report
        print("\n" + "=" * 60)
        print("MINERAÇÃO CONCLUÍDA - V8")
        print("=" * 60)
        print(f"  Processados: {self.stats['processed']}")
        print(f"  Aceitos (score >= {Settings.MIN_SCORE_TO_DOWNLOAD}): {self.stats['accepted']}")
        print(f"  Rejeitados total: {self.stats['rejected']}")
        print(f"  Rejeitados por BLACKLIST: {self.stats['rejected_blacklist']}")
        print(f"  Downloads: {self.stats['downloads']}")

        if self.stats['downloads_by_type']:
            print(f"\n  Downloads por tipo:")
            for ext, count in sorted(self.stats['downloads_by_type'].items()):
                print(f"    {ext}: {count} arquivos")

        if self.stats['skipped_types']:
            print(f"\n  Tipos ignorados:")
            for ext, count in sorted(self.stats['skipped_types'].items()):
                print(f"    {ext}: {count} arquivos")

        print("=" * 60)


# ==============================================================================
# ENTRY POINT
# ==============================================================================

if __name__ == "__main__":
    if os.name == 'nt':
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

    asyncio.run(EditalMiner().run())