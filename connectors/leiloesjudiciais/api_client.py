"""
Cliente HTTP para API REST do leiloesjudiciais.com.br

Endpoints disponíveis:
- POST /core/api/get-lotes - Lista lotes com filtros e paginação
- GET /core/api/get-tipos - Lista tipos de leilão
- GET /core/api/get-dados-filtros - Dados para filtros (estados, cidades)
- GET /core/api/get-leiloes - Lista leilões ativos

Características:
- Rate limiting configurável (padrão: 1 req/s)
- Retry com backoff exponencial
- Paginação automática com critério de parada seguro
- Hash de conteúdo para idempotência

Uso:
    client = LeiloeiroAPIClient()
    items, stats = client.fetch_all_pages(tipo=1, max_pages=10)
"""

import hashlib
import logging
import time
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Callable, Dict, List, Optional

import httpx

from .config import config

logger = logging.getLogger(__name__)


# ============================================================================
# DATACLASSES
# ============================================================================

@dataclass
class APIResponse:
    """Resposta estruturada da API."""
    success: bool
    data: List[Dict[str, Any]] = field(default_factory=list)
    current_page: int = 1
    total_pages: int = 1
    total_items: int = 0
    error_message: Optional[str] = None
    response_time_ms: float = 0.0
    http_status: int = 0


@dataclass
class FetchStats:
    """Estatísticas agregadas de fetch."""
    total_requests: int = 0
    successful: int = 0
    failed: int = 0
    rate_limited: int = 0
    items_fetched: int = 0
    pages_fetched: int = 0
    total_time_ms: float = 0.0
    started_at: Optional[str] = None
    finished_at: Optional[str] = None

    @property
    def success_rate(self) -> float:
        """Taxa de sucesso em porcentagem."""
        if self.total_requests == 0:
            return 0.0
        return (self.successful / self.total_requests) * 100

    @property
    def avg_response_time_ms(self) -> float:
        """Tempo médio de resposta por request."""
        if self.successful == 0:
            return 0.0
        return self.total_time_ms / self.successful


# ============================================================================
# CLIENTE API
# ============================================================================

class LeiloeiroAPIClient:
    """
    Cliente para API REST do leiloesjudiciais.com.br.

    Características:
    - Rate limiting configurável
    - Retry com backoff exponencial
    - Paginação automática com critério de parada seguro
    - Hash de conteúdo para idempotência

    Exemplo:
        client = LeiloeiroAPIClient()

        # Buscar uma página
        response = client.get_lotes(page=1, tipo=1)

        # Buscar todas as páginas
        items, stats = client.fetch_all_pages(tipo=1)
    """

    BASE_URL = "https://api.leiloesjudiciais.com.br/core/api"

    def __init__(
        self,
        requests_per_second: float = 1.0,
        timeout: int = 30,
        max_retries: int = 3,
        backoff_factor: float = 2.0
    ):
        """
        Inicializa o cliente.

        Args:
            requests_per_second: Rate limit (padrão: 1 req/s)
            timeout: Timeout em segundos (padrão: 30)
            max_retries: Máximo de retries por request (padrão: 3)
            backoff_factor: Fator de backoff exponencial (padrão: 2.0)
        """
        self.rate_limit = requests_per_second
        self.timeout = timeout
        self.max_retries = max_retries
        self.backoff_factor = backoff_factor
        self.stats = FetchStats()
        self._last_request_time = 0.0

    def get_lotes(
        self,
        page: int = 1,
        per_page: int = 50,
        estado: Optional[str] = None,
        cidade: Optional[str] = None,
        valor_min: Optional[float] = None,
        valor_max: Optional[float] = None,
        palavra_chave: Optional[str] = None,
        leilao_id: Optional[int] = None,
    ) -> APIResponse:
        """
        Busca lotes da API com filtros.

        NOTA: A API leiloesjudiciais não suporta filtro por tipo/categoria.
        O filtro deve ser feito no código após receber os dados.

        Categorias retornadas (id_categoria):
        - 1: Veículos (escopo do projeto)
        - 2: Bens Diversos
        - 3: Imóveis (excluir)

        Args:
            page: Número da página (1-indexed)
            per_page: Itens por página (max 100)
            estado: UF
            cidade: Nome da cidade
            valor_min/max: Faixa de valor
            palavra_chave: Busca textual
            leilao_id: ID específico de leilão

        Returns:
            APIResponse com dados e metadata
        """
        self._apply_rate_limit()

        # Monta payload
        payload: Dict[str, Any] = {
            "pg": page,
            "qtd_por_pagina": min(per_page, 100),
        }

        # Adiciona filtros opcionais (apenas os que funcionam)
        if estado:
            payload["estado"] = estado
        if cidade:
            payload["cidade"] = cidade
        if valor_min is not None:
            payload["valor_min"] = valor_min
        if valor_max is not None:
            payload["valor_max"] = valor_max
        if palavra_chave:
            payload["palavra_chave"] = palavra_chave
        if leilao_id is not None:
            payload["leilao_id"] = leilao_id

        return self._post_with_retry("get-lotes", payload)

    def fetch_all_pages(
        self,
        max_pages: Optional[int] = None,
        per_page: int = 50,
        progress_callback: Optional[Callable[[int, int, int], None]] = None,
        **filters
    ) -> tuple[List[Dict], FetchStats]:
        """
        Busca todas as páginas de lotes.

        IMPORTANTE: Critério de parada seguro - para quando currentPage >= totalPages.
        A API pode retornar a última página repetida se pg > totalPages.

        NOTA: A API não suporta filtro por tipo/categoria server-side.
        O filtro por id_categoria deve ser feito após receber os dados.

        Args:
            max_pages: Limite de páginas (None = sem limite)
            per_page: Itens por página
            progress_callback: Callback(page, total_pages, items_so_far)
            **filters: Filtros adicionais (estado, cidade, etc)

        Returns:
            Tupla (lista de lotes, estatísticas)
        """
        # Reset stats
        self.stats = FetchStats(started_at=datetime.utcnow().isoformat())

        all_items: List[Dict] = []
        current_page = 1
        total_pages = 1
        seen_hashes: set = set()  # Para detectar páginas repetidas

        logger.info(f"Iniciando fetch de todas as páginas (max_pages={max_pages})")

        while current_page <= total_pages:
            # Verifica limite de páginas
            if max_pages and current_page > max_pages:
                logger.info(f"Atingido limite de {max_pages} páginas")
                break

            # Faz request
            response = self.get_lotes(
                page=current_page,
                per_page=per_page,
                **filters
            )

            if not response.success:
                logger.error(f"Erro na página {current_page}: {response.error_message}")
                self.stats.failed += 1
                # Não quebra - tenta próxima página
                current_page += 1
                continue

            # Atualiza total_pages com valor real da API
            total_pages = response.total_pages

            # Verifica se estamos recebendo páginas repetidas (bug da API)
            if response.data:
                first_item_hash = self.generate_content_hash(response.data[0])
                if first_item_hash in seen_hashes:
                    logger.warning(f"Detectada página repetida em pg={current_page}, parando")
                    break
                seen_hashes.add(first_item_hash)

            # Adiciona items
            all_items.extend(response.data)
            self.stats.pages_fetched += 1
            self.stats.items_fetched += len(response.data)
            self.stats.total_time_ms += response.response_time_ms

            # Progress callback
            if progress_callback:
                progress_callback(current_page, total_pages, len(all_items))

            logger.info(
                f"Página {current_page}/{total_pages}: "
                f"{len(response.data)} lotes (total: {len(all_items)})"
            )

            # Próxima página
            current_page += 1

            # Critério de parada: chegou na última página
            if current_page > total_pages:
                logger.info(f"Todas as {total_pages} páginas processadas")
                break

        self.stats.finished_at = datetime.utcnow().isoformat()

        logger.info(
            f"Fetch concluído: {len(all_items)} lotes em "
            f"{self.stats.pages_fetched} páginas "
            f"({self.stats.success_rate:.1f}% sucesso)"
        )

        return all_items, self.stats

    def _post_with_retry(self, endpoint: str, payload: Dict) -> APIResponse:
        """
        Faz POST com retry e backoff exponencial.
        """
        url = f"{self.BASE_URL}/{endpoint}"
        last_error: Optional[str] = None

        for attempt in range(self.max_retries + 1):
            start_time = time.time()

            try:
                with httpx.Client(timeout=self.timeout) as client:
                    response = client.post(
                        url,
                        json=payload,
                        headers={
                            "Content-Type": "application/json",
                            "Accept": "application/json",
                            "User-Agent": config.USER_AGENT,
                        }
                    )

                elapsed_ms = (time.time() - start_time) * 1000
                self.stats.total_requests += 1

                # Sucesso
                if response.status_code == 200:
                    self.stats.successful += 1
                    return self._parse_response(response.json(), elapsed_ms, response.status_code)

                # Rate limited - retry com backoff
                if response.status_code in config.RATE_LIMIT_STATUS_CODES:
                    self.stats.rate_limited += 1
                    wait_time = self.backoff_factor ** attempt
                    logger.warning(f"Rate limited (HTTP {response.status_code}), aguardando {wait_time}s")
                    time.sleep(wait_time)
                    continue

                # Erro do servidor - retry
                if response.status_code >= 500:
                    wait_time = self.backoff_factor ** attempt
                    logger.warning(f"Server error (HTTP {response.status_code}), retry em {wait_time}s")
                    time.sleep(wait_time)
                    continue

                # Erro do cliente - não retry
                self.stats.failed += 1
                return APIResponse(
                    success=False,
                    error_message=f"HTTP {response.status_code}",
                    http_status=response.status_code,
                    response_time_ms=elapsed_ms
                )

            except httpx.TimeoutException as e:
                last_error = f"Timeout: {e}"
                wait_time = self.backoff_factor ** attempt
                logger.warning(f"{last_error}, retry em {wait_time}s")
                time.sleep(wait_time)

            except httpx.RequestError as e:
                last_error = f"Request error: {e}"
                wait_time = self.backoff_factor ** attempt
                logger.warning(f"{last_error}, retry em {wait_time}s")
                time.sleep(wait_time)

            except Exception as e:
                last_error = f"Unexpected error: {e}"
                logger.error(last_error)
                break

        # Esgotou retries
        self.stats.failed += 1
        return APIResponse(
            success=False,
            error_message=last_error or "Max retries exceeded"
        )

    def _parse_response(self, data: Dict, elapsed_ms: float, status_code: int) -> APIResponse:
        """
        Parseia resposta da API para estrutura padronizada.

        Formato da API leiloesjudiciais:
        {
            "items": [...],
            "totalItems": 123,
            "currentPage": 1,
            "totalPages": 5,
            "itemsPerPage": 50
        }
        """
        # Extrai lotes - a API usa "items"
        lotes = data.get("items", data.get("lotes", data.get("data", [])))

        # Extrai metadata de paginação
        current_page = data.get("currentPage", data.get("pagina_atual", 1))
        total_pages = data.get("totalPages", data.get("total_paginas", 1))
        total_items = data.get("totalItems", data.get("total", len(lotes)))

        return APIResponse(
            success=True,
            data=lotes if isinstance(lotes, list) else [],
            current_page=current_page,
            total_pages=total_pages,
            total_items=total_items,
            response_time_ms=elapsed_ms,
            http_status=status_code
        )

    def _apply_rate_limit(self):
        """Aplica rate limiting entre requests."""
        if self._last_request_time > 0:
            elapsed = time.time() - self._last_request_time
            min_interval = 1.0 / self.rate_limit
            if elapsed < min_interval:
                sleep_time = min_interval - elapsed
                time.sleep(sleep_time)
        self._last_request_time = time.time()

    @staticmethod
    def generate_content_hash(item: Dict) -> str:
        """
        Gera hash único para item da API.

        Usado para:
        - Detectar duplicatas
        - Idempotência em reruns
        - Detectar páginas repetidas
        """
        # Campos que definem unicidade
        key_fields = [
            str(item.get("id", "")),
            str(item.get("leilao_id", "")),
            item.get("titulo", ""),
        ]
        content = "|".join(key_fields)
        return hashlib.sha256(content.encode()).hexdigest()


# ============================================================================
# FUNÇÕES AUXILIARES
# ============================================================================

def fetch_tipos_leilao() -> List[Dict]:
    """Busca tipos de leilão disponíveis."""
    client = LeiloeiroAPIClient()
    try:
        with httpx.Client(timeout=30) as http:
            response = http.get(f"{client.BASE_URL}/get-tipos")
            if response.status_code == 200:
                return response.json()
    except Exception as e:
        logger.error(f"Erro ao buscar tipos: {e}")
    return []


def fetch_dados_filtros() -> Dict:
    """Busca dados para filtros (estados, cidades, categorias)."""
    client = LeiloeiroAPIClient()
    try:
        with httpx.Client(timeout=30) as http:
            response = http.get(f"{client.BASE_URL}/get-dados-filtros")
            if response.status_code == 200:
                return response.json()
    except Exception as e:
        logger.error(f"Erro ao buscar dados de filtros: {e}")
    return {}
