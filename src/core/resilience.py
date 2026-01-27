#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
=============================================================================
RESILIENCE MODULE - Ache Sucatas DaaS
=============================================================================
Módulo de resiliência para operações externas.

Versão: 1.0.0
Data: 2026-01-26
Autor: Tech Lead (Claude Code)

Componentes:
- retry_with_backoff: Decorator para retry com backoff exponencial
- CircuitBreaker: Classe para circuit breaker pattern
- with_timeout: Decorator para timeout em operações

Uso:
    from src.core.resilience import retry_with_backoff, CircuitBreaker

    @retry_with_backoff(max_retries=3, base_delay=1.0)
    def minha_funcao():
        ...

    circuit = CircuitBreaker(name="openai", failure_threshold=5)
    result = circuit.call(minha_funcao, arg1, arg2)
=============================================================================
"""

import functools
import logging
import random
import threading
import time
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from typing import Any, Callable, Dict, List, Optional, Tuple, Type, Union

logger = logging.getLogger(__name__)


# =============================================================================
# CONFIGURAÇÃO DE ERROS RETRIABLE
# =============================================================================

# Erros que devem causar retry
RETRIABLE_EXCEPTIONS: Tuple[Type[Exception], ...] = (
    TimeoutError,
    ConnectionError,
    ConnectionResetError,
    ConnectionRefusedError,
    OSError,  # Inclui erros de rede
)

# Status HTTP que devem causar retry
RETRIABLE_HTTP_STATUS: Tuple[int, ...] = (
    408,  # Request Timeout
    429,  # Too Many Requests (rate limit)
    500,  # Internal Server Error
    502,  # Bad Gateway
    503,  # Service Unavailable
    504,  # Gateway Timeout
)


# =============================================================================
# RETRY COM BACKOFF EXPONENCIAL
# =============================================================================

def retry_with_backoff(
    max_retries: int = 3,
    base_delay: float = 1.0,
    max_delay: float = 60.0,
    exponential_base: float = 2.0,
    jitter: bool = True,
    retriable_exceptions: Tuple[Type[Exception], ...] = RETRIABLE_EXCEPTIONS,
    on_retry: Optional[Callable[[Exception, int, float], None]] = None,
) -> Callable:
    """
    Decorator para retry com backoff exponencial e jitter.

    Args:
        max_retries: Número máximo de tentativas (default: 3)
        base_delay: Delay base em segundos (default: 1.0)
        max_delay: Delay máximo em segundos (default: 60.0)
        exponential_base: Base do exponencial (default: 2.0)
        jitter: Se True, adiciona variação aleatória (default: True)
        retriable_exceptions: Tupla de exceções que devem causar retry
        on_retry: Callback chamado em cada retry (exception, attempt, delay)

    Returns:
        Decorator function

    Exemplo:
        @retry_with_backoff(max_retries=3, base_delay=2.0)
        def chamar_api():
            response = requests.get(url)
            response.raise_for_status()
            return response.json()
    """
    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        def wrapper(*args, **kwargs) -> Any:
            last_exception = None

            for attempt in range(max_retries + 1):
                try:
                    return func(*args, **kwargs)

                except retriable_exceptions as e:
                    last_exception = e

                    if attempt >= max_retries:
                        logger.error(
                            f"[RETRY] {func.__name__} falhou após {max_retries + 1} tentativas: {e}"
                        )
                        raise

                    # Calcular delay com backoff exponencial
                    delay = min(
                        base_delay * (exponential_base ** attempt),
                        max_delay
                    )

                    # Adicionar jitter (variação aleatória de ±25%)
                    if jitter:
                        delay = delay * (0.75 + random.random() * 0.5)

                    logger.warning(
                        f"[RETRY] {func.__name__} tentativa {attempt + 1}/{max_retries + 1} "
                        f"falhou: {e}. Retry em {delay:.2f}s"
                    )

                    # Callback opcional
                    if on_retry:
                        on_retry(e, attempt + 1, delay)

                    time.sleep(delay)

            # Não deveria chegar aqui, mas por segurança
            if last_exception:
                raise last_exception

        return wrapper
    return decorator


def retry_with_backoff_async(
    max_retries: int = 3,
    base_delay: float = 1.0,
    max_delay: float = 60.0,
    exponential_base: float = 2.0,
    jitter: bool = True,
    retriable_exceptions: Tuple[Type[Exception], ...] = RETRIABLE_EXCEPTIONS,
) -> Callable:
    """
    Versão async do retry_with_backoff.

    Uso:
        @retry_with_backoff_async(max_retries=3)
        async def chamar_api_async():
            ...
    """
    import asyncio

    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        async def wrapper(*args, **kwargs) -> Any:
            last_exception = None

            for attempt in range(max_retries + 1):
                try:
                    return await func(*args, **kwargs)

                except retriable_exceptions as e:
                    last_exception = e

                    if attempt >= max_retries:
                        logger.error(
                            f"[RETRY] {func.__name__} falhou após {max_retries + 1} tentativas: {e}"
                        )
                        raise

                    delay = min(
                        base_delay * (exponential_base ** attempt),
                        max_delay
                    )

                    if jitter:
                        delay = delay * (0.75 + random.random() * 0.5)

                    logger.warning(
                        f"[RETRY] {func.__name__} tentativa {attempt + 1}/{max_retries + 1} "
                        f"falhou: {e}. Retry em {delay:.2f}s"
                    )

                    await asyncio.sleep(delay)

            if last_exception:
                raise last_exception

        return wrapper
    return decorator


# =============================================================================
# CIRCUIT BREAKER
# =============================================================================

class CircuitState(Enum):
    """Estados do Circuit Breaker."""
    CLOSED = "closed"      # Normal - chamadas passam
    OPEN = "open"          # Bloqueado - chamadas falham imediatamente
    HALF_OPEN = "half_open"  # Teste - permite uma chamada para verificar


@dataclass
class CircuitBreakerStats:
    """Estatísticas do Circuit Breaker."""
    total_calls: int = 0
    successful_calls: int = 0
    failed_calls: int = 0
    rejected_calls: int = 0  # Chamadas rejeitadas quando OPEN
    last_failure_time: Optional[datetime] = None
    last_success_time: Optional[datetime] = None
    consecutive_failures: int = 0
    consecutive_successes: int = 0


class CircuitBreaker:
    """
    Implementação do Circuit Breaker Pattern.

    Previne cascata de falhas quando um serviço externo está indisponível.

    Estados:
    - CLOSED: Normal, chamadas passam. Após failure_threshold falhas consecutivas,
              muda para OPEN.
    - OPEN: Bloqueado, chamadas falham imediatamente com CircuitOpenError.
            Após recovery_timeout segundos, muda para HALF_OPEN.
    - HALF_OPEN: Permite uma chamada de teste. Se sucesso, volta para CLOSED.
                 Se falha, volta para OPEN.

    Exemplo:
        circuit = CircuitBreaker(
            name="openai",
            failure_threshold=5,
            recovery_timeout=60.0,
        )

        try:
            result = circuit.call(minha_funcao, arg1, arg2)
        except CircuitOpenError:
            # Serviço indisponível, usar fallback
            result = fallback_value
    """

    def __init__(
        self,
        name: str,
        failure_threshold: int = 5,
        recovery_timeout: float = 60.0,
        success_threshold: int = 2,
        excluded_exceptions: Tuple[Type[Exception], ...] = (),
    ):
        """
        Inicializa o Circuit Breaker.

        Args:
            name: Nome identificador do circuit
            failure_threshold: Número de falhas para abrir o circuit
            recovery_timeout: Tempo em segundos antes de tentar half-open
            success_threshold: Número de sucessos em half-open para fechar
            excluded_exceptions: Exceções que não devem contar como falha
        """
        self.name = name
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout
        self.success_threshold = success_threshold
        self.excluded_exceptions = excluded_exceptions

        self._state = CircuitState.CLOSED
        self._stats = CircuitBreakerStats()
        self._lock = threading.RLock()
        self._opened_at: Optional[datetime] = None

    @property
    def state(self) -> CircuitState:
        """Retorna o estado atual do circuit."""
        with self._lock:
            if self._state == CircuitState.OPEN:
                # Verificar se deve mudar para HALF_OPEN
                if self._should_attempt_reset():
                    self._state = CircuitState.HALF_OPEN
                    logger.info(f"[CIRCUIT] {self.name}: OPEN -> HALF_OPEN (tentando recuperar)")
            return self._state

    @property
    def stats(self) -> CircuitBreakerStats:
        """Retorna estatísticas do circuit."""
        return self._stats

    def _should_attempt_reset(self) -> bool:
        """Verifica se passou tempo suficiente para tentar reset."""
        if self._opened_at is None:
            return False
        elapsed = (datetime.now() - self._opened_at).total_seconds()
        return elapsed >= self.recovery_timeout

    def _record_success(self) -> None:
        """Registra uma chamada bem-sucedida."""
        with self._lock:
            self._stats.total_calls += 1
            self._stats.successful_calls += 1
            self._stats.last_success_time = datetime.now()
            self._stats.consecutive_successes += 1
            self._stats.consecutive_failures = 0

            if self._state == CircuitState.HALF_OPEN:
                if self._stats.consecutive_successes >= self.success_threshold:
                    self._state = CircuitState.CLOSED
                    logger.info(f"[CIRCUIT] {self.name}: HALF_OPEN -> CLOSED (recuperado)")

    def _record_failure(self, exception: Exception) -> None:
        """Registra uma chamada com falha."""
        with self._lock:
            self._stats.total_calls += 1
            self._stats.failed_calls += 1
            self._stats.last_failure_time = datetime.now()
            self._stats.consecutive_failures += 1
            self._stats.consecutive_successes = 0

            if self._state == CircuitState.HALF_OPEN:
                # Falha em half-open volta para open
                self._state = CircuitState.OPEN
                self._opened_at = datetime.now()
                logger.warning(f"[CIRCUIT] {self.name}: HALF_OPEN -> OPEN (falha no teste)")

            elif self._state == CircuitState.CLOSED:
                if self._stats.consecutive_failures >= self.failure_threshold:
                    self._state = CircuitState.OPEN
                    self._opened_at = datetime.now()
                    logger.warning(
                        f"[CIRCUIT] {self.name}: CLOSED -> OPEN "
                        f"({self.failure_threshold} falhas consecutivas)"
                    )

    def call(
        self,
        func: Callable,
        *args,
        fallback: Optional[Callable] = None,
        **kwargs
    ) -> Any:
        """
        Executa uma função através do circuit breaker.

        Args:
            func: Função a ser executada
            *args: Argumentos posicionais
            fallback: Função de fallback se circuit estiver aberto
            **kwargs: Argumentos nomeados

        Returns:
            Resultado da função ou do fallback

        Raises:
            CircuitOpenError: Se circuit estiver aberto e não houver fallback
        """
        current_state = self.state

        if current_state == CircuitState.OPEN:
            self._stats.rejected_calls += 1
            logger.warning(f"[CIRCUIT] {self.name}: Chamada rejeitada (OPEN)")

            if fallback:
                return fallback(*args, **kwargs)
            raise CircuitOpenError(f"Circuit {self.name} está aberto")

        try:
            result = func(*args, **kwargs)
            self._record_success()
            return result

        except self.excluded_exceptions:
            # Exceções excluídas não contam como falha
            raise

        except Exception as e:
            self._record_failure(e)
            raise

    def reset(self) -> None:
        """Reseta o circuit para estado fechado."""
        with self._lock:
            self._state = CircuitState.CLOSED
            self._stats.consecutive_failures = 0
            self._stats.consecutive_successes = 0
            self._opened_at = None
            logger.info(f"[CIRCUIT] {self.name}: Reset manual para CLOSED")


class CircuitOpenError(Exception):
    """Exceção lançada quando o circuit está aberto."""
    pass


# =============================================================================
# CIRCUIT BREAKER REGISTRY
# =============================================================================

class CircuitBreakerRegistry:
    """
    Registry global de circuit breakers.

    Permite gerenciar múltiplos circuits de forma centralizada.

    Uso:
        registry = CircuitBreakerRegistry()
        circuit = registry.get_or_create("openai", failure_threshold=5)
    """

    _instance: Optional['CircuitBreakerRegistry'] = None
    _lock = threading.Lock()

    def __new__(cls) -> 'CircuitBreakerRegistry':
        """Singleton pattern."""
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
                    cls._instance._circuits: Dict[str, CircuitBreaker] = {}
        return cls._instance

    def get_or_create(
        self,
        name: str,
        failure_threshold: int = 5,
        recovery_timeout: float = 60.0,
        **kwargs
    ) -> CircuitBreaker:
        """
        Obtém ou cria um circuit breaker.

        Args:
            name: Nome do circuit
            failure_threshold: Threshold de falhas
            recovery_timeout: Timeout de recuperação
            **kwargs: Outros argumentos para CircuitBreaker

        Returns:
            CircuitBreaker existente ou novo
        """
        if name not in self._circuits:
            self._circuits[name] = CircuitBreaker(
                name=name,
                failure_threshold=failure_threshold,
                recovery_timeout=recovery_timeout,
                **kwargs
            )
        return self._circuits[name]

    def get(self, name: str) -> Optional[CircuitBreaker]:
        """Obtém um circuit pelo nome."""
        return self._circuits.get(name)

    def reset_all(self) -> None:
        """Reseta todos os circuits."""
        for circuit in self._circuits.values():
            circuit.reset()

    def get_all_stats(self) -> Dict[str, dict]:
        """Retorna estatísticas de todos os circuits."""
        return {
            name: {
                "state": circuit.state.value,
                "total_calls": circuit.stats.total_calls,
                "successful_calls": circuit.stats.successful_calls,
                "failed_calls": circuit.stats.failed_calls,
                "rejected_calls": circuit.stats.rejected_calls,
                "consecutive_failures": circuit.stats.consecutive_failures,
            }
            for name, circuit in self._circuits.items()
        }


# Instância global do registry
circuit_registry = CircuitBreakerRegistry()


# =============================================================================
# DECORATOR COMBINADO (RETRY + CIRCUIT BREAKER)
# =============================================================================

def resilient(
    circuit_name: str,
    max_retries: int = 3,
    base_delay: float = 1.0,
    failure_threshold: int = 5,
    recovery_timeout: float = 60.0,
    fallback: Optional[Callable] = None,
) -> Callable:
    """
    Decorator que combina retry com circuit breaker.

    Primeiro tenta retry, depois verifica circuit breaker.

    Args:
        circuit_name: Nome do circuit breaker
        max_retries: Número máximo de retries
        base_delay: Delay base para backoff
        failure_threshold: Threshold do circuit breaker
        recovery_timeout: Timeout de recuperação do circuit
        fallback: Função de fallback

    Exemplo:
        @resilient("openai", max_retries=3, failure_threshold=5)
        def chamar_openai():
            ...
    """
    def decorator(func: Callable) -> Callable:
        circuit = circuit_registry.get_or_create(
            name=circuit_name,
            failure_threshold=failure_threshold,
            recovery_timeout=recovery_timeout,
        )

        @functools.wraps(func)
        def wrapper(*args, **kwargs) -> Any:
            # Verificar estado do circuit
            if circuit.state == CircuitState.OPEN:
                circuit._stats.rejected_calls += 1
                logger.warning(f"[RESILIENT] {func.__name__}: Chamada rejeitada (circuit {circuit_name} OPEN)")
                if fallback:
                    return fallback(*args, **kwargs)
                raise CircuitOpenError(f"Circuit {circuit_name} está aberto")

            last_exception = None

            for attempt in range(max_retries + 1):
                try:
                    result = func(*args, **kwargs)
                    circuit._record_success()
                    return result

                except RETRIABLE_EXCEPTIONS as e:
                    last_exception = e

                    if attempt >= max_retries:
                        circuit._record_failure(e)
                        logger.error(
                            f"[RESILIENT] {func.__name__} falhou após {max_retries + 1} tentativas"
                        )
                        raise

                    delay = min(base_delay * (2 ** attempt), 60.0)
                    delay = delay * (0.75 + random.random() * 0.5)

                    logger.warning(
                        f"[RESILIENT] {func.__name__} tentativa {attempt + 1}/{max_retries + 1} "
                        f"falhou: {e}. Retry em {delay:.2f}s"
                    )
                    time.sleep(delay)

                except Exception as e:
                    # Outras exceções não causam retry, mas contam como falha no circuit
                    circuit._record_failure(e)
                    raise

            if last_exception:
                raise last_exception

        return wrapper
    return decorator


# =============================================================================
# UTILITÁRIOS
# =============================================================================

def is_retriable_http_status(status_code: int) -> bool:
    """Verifica se um status HTTP deve causar retry."""
    return status_code in RETRIABLE_HTTP_STATUS


def get_retry_after(headers: dict) -> Optional[float]:
    """
    Extrai o tempo de retry do header Retry-After.

    Args:
        headers: Dicionário de headers HTTP

    Returns:
        Tempo em segundos ou None
    """
    retry_after = headers.get("Retry-After") or headers.get("retry-after")
    if retry_after:
        try:
            return float(retry_after)
        except ValueError:
            # Pode ser uma data HTTP
            pass
    return None


# =============================================================================
# MÉTRICAS E OBSERVABILIDADE
# =============================================================================

def log_circuit_stats() -> None:
    """Loga estatísticas de todos os circuits."""
    stats = circuit_registry.get_all_stats()
    logger.info("=" * 50)
    logger.info("CIRCUIT BREAKER STATS")
    logger.info("=" * 50)
    for name, data in stats.items():
        logger.info(
            f"  {name}: state={data['state']}, "
            f"calls={data['total_calls']}, "
            f"success={data['successful_calls']}, "
            f"failed={data['failed_calls']}, "
            f"rejected={data['rejected_calls']}"
        )
    logger.info("=" * 50)
