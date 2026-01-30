"""
Módulo de Fetch - Leilões Judiciais.

Responsável por:
1. Fazer requisições HTTP com rate limiting
2. Implementar retry com backoff exponencial
3. Tratar erros HTTP (403, 429, 404, 410)
4. Registrar métricas de requisições
"""

import time
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Dict, List, Optional, Tuple
import logging

import httpx

from .config import Config, config

logger = logging.getLogger(__name__)


class FetchStatus(str, Enum):
    """Status do fetch."""
    SUCCESS = "success"
    TOMBSTONE = "tombstone"  # 404, 410 - não tentar novamente
    RATE_LIMITED = "rate_limited"  # 429, 503
    ERROR = "error"
    TIMEOUT = "timeout"


@dataclass
class FetchResult:
    """Resultado de uma requisição."""
    url: str
    status: FetchStatus
    status_code: Optional[int] = None
    content: Optional[str] = None
    error_message: Optional[str] = None
    response_time_ms: float = 0.0
    retries: int = 0
    timestamp: str = field(default_factory=lambda: datetime.utcnow().isoformat())


@dataclass
class FetchStats:
    """Estatísticas de fetch."""
    total_requests: int = 0
    successful: int = 0
    tombstones: int = 0
    rate_limited: int = 0
    errors: int = 0
    timeouts: int = 0
    total_retries: int = 0
    total_time_ms: float = 0.0

    @property
    def success_rate(self) -> float:
        if self.total_requests == 0:
            return 0.0
        return self.successful / self.total_requests * 100

    @property
    def avg_response_time_ms(self) -> float:
        if self.successful == 0:
            return 0.0
        return self.total_time_ms / self.successful


class LeilaoFetcher:
    """
    Fetcher HTTP com rate limiting e retry.

    Características:
    - Rate limit configurável (padrão: 1 req/seg)
    - Retry com backoff exponencial
    - Tratamento de tombstones (404/410)
    - Tratamento de rate limiting (429/503)
    """

    def __init__(self, cfg: Optional[Config] = None):
        self.config = cfg or config
        self.stats = FetchStats()
        self._last_request_time: float = 0
        self._tombstones: set = set()  # URLs que retornaram 404/410

    def fetch(self, url: str) -> FetchResult:
        """
        Faz fetch de uma URL com rate limiting e retry.

        Args:
            url: URL para buscar

        Returns:
            FetchResult com conteúdo ou erro
        """
        # Verifica se é tombstone conhecido
        if url in self._tombstones:
            return FetchResult(
                url=url,
                status=FetchStatus.TOMBSTONE,
                error_message="URL marcada como tombstone (404/410 anterior)"
            )

        # Aplica rate limiting
        self._apply_rate_limit()

        result = self._fetch_with_retry(url)
        self._update_stats(result)

        return result

    def fetch_many(
        self,
        urls: List[str],
        progress_callback: Optional[callable] = None
    ) -> Tuple[List[FetchResult], FetchStats]:
        """
        Faz fetch de múltiplas URLs sequencialmente.

        Args:
            urls: Lista de URLs
            progress_callback: Função chamada após cada URL (url, index, total)

        Returns:
            Tupla (lista de resultados, estatísticas)
        """
        results = []
        total = len(urls)

        for i, url in enumerate(urls):
            result = self.fetch(url)
            results.append(result)

            if progress_callback:
                progress_callback(url, i + 1, total)

        return results, self.stats

    def _apply_rate_limit(self):
        """Aplica rate limiting entre requisições."""
        if self._last_request_time > 0:
            elapsed = time.time() - self._last_request_time
            min_interval = 1.0 / self.config.REQUESTS_PER_SECOND
            if elapsed < min_interval:
                sleep_time = min_interval - elapsed
                time.sleep(sleep_time)

        self._last_request_time = time.time()

    def _fetch_with_retry(self, url: str) -> FetchResult:
        """
        Faz fetch com retry e backoff exponencial.

        Args:
            url: URL para buscar

        Returns:
            FetchResult
        """
        retries = 0
        last_error = None

        while retries <= self.config.MAX_RETRIES:
            try:
                start_time = time.time()

                with httpx.Client(
                    timeout=self.config.REQUEST_TIMEOUT_SECONDS,
                    follow_redirects=True
                ) as client:
                    response = client.get(url, headers=self.config.get_headers())

                elapsed_ms = (time.time() - start_time) * 1000

                # Sucesso
                if response.status_code == 200:
                    return FetchResult(
                        url=url,
                        status=FetchStatus.SUCCESS,
                        status_code=200,
                        content=response.text,
                        response_time_ms=elapsed_ms,
                        retries=retries
                    )

                # Tombstone (404, 410)
                if response.status_code in self.config.TOMBSTONE_STATUS_CODES:
                    self._tombstones.add(url)
                    return FetchResult(
                        url=url,
                        status=FetchStatus.TOMBSTONE,
                        status_code=response.status_code,
                        error_message=f"HTTP {response.status_code}",
                        response_time_ms=elapsed_ms,
                        retries=retries
                    )

                # Rate limiting (429, 503)
                if response.status_code in self.config.RATE_LIMIT_STATUS_CODES:
                    retries += 1
                    if retries <= self.config.MAX_RETRIES:
                        sleep_time = self.config.RETRY_BACKOFF_FACTOR ** retries
                        logger.warning(
                            f"Rate limited ({response.status_code}), "
                            f"aguardando {sleep_time}s antes de retry {retries}"
                        )
                        time.sleep(sleep_time)
                        continue

                    return FetchResult(
                        url=url,
                        status=FetchStatus.RATE_LIMITED,
                        status_code=response.status_code,
                        error_message=f"Rate limited após {retries} tentativas",
                        response_time_ms=elapsed_ms,
                        retries=retries
                    )

                # Outros erros HTTP
                return FetchResult(
                    url=url,
                    status=FetchStatus.ERROR,
                    status_code=response.status_code,
                    error_message=f"HTTP {response.status_code}",
                    response_time_ms=elapsed_ms,
                    retries=retries
                )

            except httpx.TimeoutException as e:
                last_error = str(e)
                retries += 1
                if retries <= self.config.MAX_RETRIES:
                    sleep_time = self.config.RETRY_BACKOFF_FACTOR ** retries
                    logger.warning(f"Timeout, aguardando {sleep_time}s antes de retry {retries}")
                    time.sleep(sleep_time)
                    continue

                return FetchResult(
                    url=url,
                    status=FetchStatus.TIMEOUT,
                    error_message=f"Timeout após {retries} tentativas: {last_error}",
                    retries=retries
                )

            except Exception as e:
                last_error = str(e)
                retries += 1
                if retries <= self.config.MAX_RETRIES:
                    sleep_time = self.config.RETRY_BACKOFF_FACTOR ** retries
                    logger.warning(f"Erro: {e}, aguardando {sleep_time}s antes de retry {retries}")
                    time.sleep(sleep_time)
                    continue

                return FetchResult(
                    url=url,
                    status=FetchStatus.ERROR,
                    error_message=f"Erro após {retries} tentativas: {last_error}",
                    retries=retries
                )

        # Não deveria chegar aqui, mas por segurança
        return FetchResult(
            url=url,
            status=FetchStatus.ERROR,
            error_message=f"Erro desconhecido após {retries} tentativas",
            retries=retries
        )

    def _update_stats(self, result: FetchResult):
        """Atualiza estatísticas."""
        self.stats.total_requests += 1
        self.stats.total_retries += result.retries

        if result.status == FetchStatus.SUCCESS:
            self.stats.successful += 1
            self.stats.total_time_ms += result.response_time_ms
        elif result.status == FetchStatus.TOMBSTONE:
            self.stats.tombstones += 1
        elif result.status == FetchStatus.RATE_LIMITED:
            self.stats.rate_limited += 1
        elif result.status == FetchStatus.TIMEOUT:
            self.stats.timeouts += 1
        else:
            self.stats.errors += 1

    def get_stats_dict(self) -> Dict:
        """Retorna estatísticas como dicionário."""
        return {
            "total_requests": self.stats.total_requests,
            "successful": self.stats.successful,
            "tombstones": self.stats.tombstones,
            "rate_limited": self.stats.rate_limited,
            "errors": self.stats.errors,
            "timeouts": self.stats.timeouts,
            "total_retries": self.stats.total_retries,
            "success_rate_percent": round(self.stats.success_rate, 2),
            "avg_response_time_ms": round(self.stats.avg_response_time_ms, 2),
        }
