"""
Configuração do Conector Leilões Judiciais.

Centraliza todas as configurações, constantes e variáveis de ambiente.
"""

import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Optional

# Carrega variáveis do arquivo .env automaticamente
try:
    from dotenv import load_dotenv
    # Procura o .env no diretório deste arquivo
    env_path = Path(__file__).parent / ".env"
    load_dotenv(env_path)
except ImportError:
    pass  # python-dotenv não instalado, usa apenas variáveis de ambiente do sistema


@dataclass
class Config:
    """Configurações do conector."""

    # === IDENTIFICAÇÃO ===
    CONNECTOR_NAME: str = "leiloesjudiciais"
    CONNECTOR_VERSION: str = "1.0.0"
    SOURCE_TYPE: str = "leiloeiro"
    SOURCE_NAME: str = "Leilões Judiciais"

    # === URLs BASE ===
    BASE_URL: str = "https://www.leiloesjudiciais.com.br"
    SITEMAP_URL: str = "https://www.leiloesjudiciais.com.br/sitemap.xml"

    # === CATEGORIAS DE INTERESSE ===
    # URLs de categorias relacionadas a veículos/sucatas
    VEHICLE_CATEGORIES: List[str] = field(default_factory=lambda: [
        "/veiculos/",
        "/veiculos/carros",
        "/veiculos/motos",
        "/veiculos/caminhoes",
        "/veiculos/onibus",
        "/veiculos/tratores",
        "/veiculos/veiculos-agricolas",
        "/veiculos/reboques",
        "/veiculos/semireboques",
        "/diversos/sucatas",
    ])

    # Padrão de URL de lotes: /lote/{leilao_id}/{lote_id}
    LOT_URL_PATTERN: str = r"/lote/(\d+)/(\d+)"

    # === PALAVRAS-CHAVE PARA FILTRO ===
    VEHICLE_KEYWORDS: List[str] = field(default_factory=lambda: [
        "veículo", "veiculo", "carro", "moto", "motocicleta",
        "caminhão", "caminhao", "ônibus", "onibus", "automóvel",
        "automovel", "sucata", "sucatas", "chassi", "placa",
        "renavam", "trator", "reboque", "carreta",
        # Marcas comuns
        "fiat", "volkswagen", "vw", "chevrolet", "gm", "ford",
        "honda", "yamaha", "toyota", "hyundai", "jeep", "nissan",
        "mercedes", "bmw", "audi", "peugeot", "citroen", "renault",
        "scania", "volvo", "iveco", "man", "daf",
    ])

    # === RATE LIMITING ===
    REQUESTS_PER_SECOND: float = 1.0  # 1 requisição por segundo
    REQUEST_TIMEOUT_SECONDS: int = 30
    MAX_RETRIES: int = 3
    RETRY_BACKOFF_FACTOR: float = 2.0  # Exponential backoff

    # === HEADERS HTTP ===
    USER_AGENT: str = (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    )
    ACCEPT_LANGUAGE: str = "pt-BR,pt;q=0.9,en-US;q=0.8,en;q=0.7"

    # === LIMITES ===
    MAX_LOTS_PER_RUN: int = 500  # Limite de lotes por execução
    MAX_CONCURRENT_REQUESTS: int = 1  # Sem concorrência (respeito ao site)

    # === PATHS DE SAÍDA ===
    OUTPUT_DIR: str = "out"
    OUTPUT_FILE: str = "leiloesjudiciais_items.jsonl"
    REPORT_DIR: str = "out/reports"
    QUARANTINE_DIR: str = "out/quarantine"

    # === SUPABASE (via variáveis de ambiente) ===
    @property
    def supabase_url(self) -> Optional[str]:
        return os.getenv("SUPABASE_URL")

    @property
    def supabase_key(self) -> Optional[str]:
        return os.getenv("SUPABASE_SERVICE_KEY")

    @property
    def supabase_enabled(self) -> bool:
        return bool(self.supabase_url and self.supabase_key)

    # === STATUS HTTP ===
    # Códigos que indicam tombstone (não tentar novamente)
    TOMBSTONE_STATUS_CODES: List[int] = field(default_factory=lambda: [404, 410])
    # Códigos que indicam rate limiting
    RATE_LIMIT_STATUS_CODES: List[int] = field(default_factory=lambda: [429, 503])

    def get_headers(self) -> dict:
        """Retorna headers HTTP para requisições."""
        return {
            "User-Agent": self.USER_AGENT,
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": self.ACCEPT_LANGUAGE,
            "Accept-Encoding": "gzip, deflate, br",
            "Connection": "keep-alive",
            "Cache-Control": "no-cache",
        }

    def is_vehicle_url(self, url: str) -> bool:
        """Verifica se URL é de categoria de veículos."""
        url_lower = url.lower()
        return any(cat in url_lower for cat in self.VEHICLE_CATEGORIES)

    def contains_vehicle_keyword(self, text: str) -> bool:
        """Verifica se texto contém palavras-chave de veículos."""
        text_lower = text.lower()
        return any(kw in text_lower for kw in self.VEHICLE_KEYWORDS)


# Instância global de configuração
config = Config()
