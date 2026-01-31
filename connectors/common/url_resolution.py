"""
Utilitário Centralizado de Resolução de URLs.

Este módulo é o ÚNICO ponto de resolução de URLs de lotes para todos os
conectores. NUNCA construa URLs por concatenação hardcoded em outros módulos.

Estratégia de resolução (em ordem de preferência):
1. URL canônica da API (campo url, link, nm_url_lote, etc.)
2. href real extraído do HTML (resolvido com urljoin)
3. HEAD request para obter URL final após redirects
4. Fallback construído (marcado com url_constructed=True)

Uso:
    from connectors.common.url_resolution import resolve_lote_url, head_resolve_final_url

    result = resolve_lote_url(
        candidate_urls=["https://...", "https://..."],
        fallback_constructed="https://site.com/lote/123/456",
        validate_http=True
    )

    # result = {
    #     "raw_url": "https://...",
    #     "final_url": "https://...",
    #     "status_final": 200,
    #     "url_constructed": False,
    #     "resolution_method": "api"
    # }

Autor: Claude Code
Data: 2026-01-30
"""

import logging
import time
from dataclasses import dataclass
from typing import List, Optional, Tuple
from urllib.parse import urljoin, urlparse

try:
    import httpx
except ImportError:
    httpx = None  # type: ignore

logger = logging.getLogger(__name__)


# ============================================================================
# CONFIGURAÇÃO
# ============================================================================

# Rate limiting global
_last_request_time = 0.0
REQUESTS_PER_SECOND = 3.0
REQUEST_TIMEOUT = 10


# ============================================================================
# DATACLASSES
# ============================================================================

@dataclass
class URLResolutionResult:
    """Resultado da resolução de URL."""
    raw_url: Optional[str]
    final_url: Optional[str]
    status_final: Optional[int]
    url_constructed: bool
    resolution_method: str  # "api" | "href" | "head_redirect" | "constructed_validated" | "failed"
    error: Optional[str] = None

    def to_dict(self) -> dict:
        return {
            "raw_url": self.raw_url,
            "final_url": self.final_url,
            "status_final": self.status_final,
            "url_constructed": self.url_constructed,
            "resolution_method": self.resolution_method,
            "error": self.error,
        }


# ============================================================================
# FUNÇÕES DE NORMALIZAÇÃO
# ============================================================================

def normalize_base_url(raw: Optional[str]) -> Optional[str]:
    """
    Normaliza URL base adicionando https:// se necessário.

    Args:
        raw: URL bruta (pode ser None, vazia, ou sem protocolo)

    Returns:
        URL normalizada com https:// ou None se inválida

    Exemplos:
        >>> normalize_base_url("www.example.com")
        "https://www.example.com"
        >>> normalize_base_url("http://example.com")
        "http://example.com"
        >>> normalize_base_url("")
        None
    """
    if not raw:
        return None

    url = str(raw).strip()
    if not url:
        return None

    # Remove trailing slash para consistência
    url = url.rstrip("/")

    # Adiciona protocolo se ausente
    if url.startswith("www."):
        url = f"https://{url}"
    elif not url.startswith(("http://", "https://")):
        url = f"https://{url}"

    # Valida que é uma URL parseable
    try:
        parsed = urlparse(url)
        if not parsed.scheme or not parsed.netloc:
            return None
        return url
    except Exception:
        return None


def resolve_absolute_url(base: str, href: str) -> Optional[str]:
    """
    Resolve URL relativa para absoluta usando urljoin.

    Args:
        base: URL base da página
        href: href extraído (pode ser relativo)

    Returns:
        URL absoluta ou None se inválida

    Exemplos:
        >>> resolve_absolute_url("https://example.com/page", "/lote/123")
        "https://example.com/lote/123"
        >>> resolve_absolute_url("https://example.com/dir/", "file.html")
        "https://example.com/dir/file.html"
    """
    if not base or not href:
        return None

    try:
        absolute = urljoin(base, href)
        # Valida resultado
        parsed = urlparse(absolute)
        if parsed.scheme in ("http", "https") and parsed.netloc:
            return absolute
        return None
    except Exception:
        return None


# ============================================================================
# RESOLUÇÃO HTTP
# ============================================================================

def head_resolve_final_url(
    url: str,
    timeout: int = REQUEST_TIMEOUT
) -> Tuple[Optional[str], Optional[int], Optional[int]]:
    """
    Faz HEAD request para obter URL final após redirects.

    Args:
        url: URL para testar
        timeout: Timeout em segundos

    Returns:
        Tupla (final_url, status_final, status_inicial)
        Retorna (None, None, None) se erro de conexão

    Nota:
        Aplica rate limiting global para não sobrecarregar servidores.
    """
    global _last_request_time

    if not httpx:
        logger.warning("httpx não instalado, pulando validação HTTP")
        return (url, None, None)

    if not url:
        return (None, None, None)

    # Rate limiting
    elapsed = time.time() - _last_request_time
    min_interval = 1.0 / REQUESTS_PER_SECOND
    if elapsed < min_interval:
        time.sleep(min_interval - elapsed)

    status_inicial = None
    final_url = None
    status_final = None

    try:
        # Primeiro request sem seguir redirects (para capturar status inicial)
        with httpx.Client(timeout=timeout, follow_redirects=False) as client:
            try:
                resp = client.head(url)
                status_inicial = resp.status_code
            except Exception:
                pass

        # Request seguindo redirects
        with httpx.Client(timeout=timeout, follow_redirects=True) as client:
            resp = client.head(url)
            _last_request_time = time.time()

            final_url = str(resp.url)
            status_final = resp.status_code

    except httpx.TimeoutException:
        logger.debug(f"Timeout ao acessar {url}")
    except httpx.RequestError as e:
        logger.debug(f"Erro de request em {url}: {type(e).__name__}")
    except Exception as e:
        logger.debug(f"Erro inesperado em {url}: {e}")

    return (final_url, status_final, status_inicial)


# ============================================================================
# FUNÇÃO PRINCIPAL DE RESOLUÇÃO
# ============================================================================

def _is_valid_lote_url(url: str) -> bool:
    """
    Verifica se URL é válida como URL de lote (não apenas domínio base).

    Rejeita URLs que são apenas domínios sem path, ex:
    - https://example.com (inválida - domínio puro)
    - https://example.com/ (inválida - domínio puro)
    - https://example.com/leilao/123 (válida - tem path)
    """
    if not url:
        return False

    try:
        parsed = urlparse(url)
        # Path deve ter mais que apenas "/" ou estar vazio
        path = parsed.path.strip("/")
        return bool(path)  # True se tiver path além de "/"
    except Exception:
        return False


def resolve_lote_url(
    candidate_urls: Optional[List[Optional[str]]] = None,
    fallback_constructed: Optional[str] = None,
    validate_http: bool = False,
    source_page_url: Optional[str] = None,
    candidate_labels: Optional[List[str]] = None,
) -> URLResolutionResult:
    """
    Resolve URL do lote usando estratégia em cascata.

    Ordem de preferência:
    1. URLs candidatas da API (primeiro não-nulo COM path válido)
    2. fallback_constructed (se URLs candidatas falharem)

    IMPORTANTE: Nunca retorna "domínio puro" (ex: https://example.com)
    como URL de lote. Apenas URLs com path são aceitas.

    Se validate_http=True, valida a URL final com HEAD request.

    Args:
        candidate_urls: Lista de URLs candidatas (da API, em ordem de preferência)
        fallback_constructed: URL construída como fallback (será marcada)
        validate_http: Se True, valida com HEAD request
        source_page_url: URL da página fonte (para resolver hrefs relativos)
        candidate_labels: Labels para identificar origem de cada candidato
            (ex: ["api_canonical", "href_scraped"]). Se não fornecido,
            usa "api_canonical" para todos.

    Returns:
        URLResolutionResult com informações completas

    resolution_method values:
        - "api_canonical": URL veio de campo canônico da API (url_lote, nm_url_lote, link)
        - "href_scraped": URL veio de href extraído do HTML
        - "constructed_validated": URL foi construída como fallback e validada
        - "failed": Nenhuma URL válida encontrada

    Exemplo:
        result = resolve_lote_url(
            candidate_urls=[
                api_item.get("url_lote"),      # Preferido
                api_item.get("nm_url_lote"),   # Alternativa
            ],
            candidate_labels=["api_canonical", "api_canonical"],
            fallback_constructed=f"{base_url}/lote/{leilao_id}/{lote_id}",
            validate_http=True
        )
    """
    # Normaliza candidates e filtra domínios puros, mantendo índice original
    candidates_with_labels = []
    if candidate_urls:
        labels = candidate_labels or ["api_canonical"] * len(candidate_urls)
        for i, url in enumerate(candidate_urls):
            normalized = normalize_base_url(url)
            # Só aceita URLs com path (não domínio puro)
            if normalized and _is_valid_lote_url(normalized):
                label = labels[i] if i < len(labels) else "api_canonical"
                candidates_with_labels.append((normalized, label))

    # Tenta cada candidato
    for raw_url, label in candidates_with_labels:
        # Se temos source_page_url e o candidato é relativo, resolve
        if source_page_url and not raw_url.startswith(("http://", "https://")):
            raw_url = resolve_absolute_url(source_page_url, raw_url) or raw_url

        if validate_http:
            final_url, status_final, _ = head_resolve_final_url(raw_url)

            if status_final and 200 <= status_final < 400:
                return URLResolutionResult(
                    raw_url=raw_url,
                    final_url=final_url,
                    status_final=status_final,
                    url_constructed=False,
                    resolution_method=label,
                )
        else:
            # Sem validação HTTP, assume que está OK
            return URLResolutionResult(
                raw_url=raw_url,
                final_url=raw_url,
                status_final=None,
                url_constructed=False,
                resolution_method=label,
            )

    # Fallback para URL construída
    if fallback_constructed:
        fallback_normalized = normalize_base_url(fallback_constructed)

        if fallback_normalized:
            if validate_http:
                final_url, status_final, _ = head_resolve_final_url(fallback_normalized)

                if status_final and 200 <= status_final < 400:
                    return URLResolutionResult(
                        raw_url=fallback_normalized,
                        final_url=final_url,
                        status_final=status_final,
                        url_constructed=True,
                        resolution_method="constructed_validated",
                    )
                else:
                    # Fallback construído falhou na validação
                    return URLResolutionResult(
                        raw_url=fallback_normalized,
                        final_url=final_url,
                        status_final=status_final,
                        url_constructed=True,
                        resolution_method="failed",
                        error=f"HTTP {status_final or 'connection error'}",
                    )
            else:
                # Sem validação, retorna o construído marcado
                return URLResolutionResult(
                    raw_url=fallback_normalized,
                    final_url=fallback_normalized,
                    status_final=None,
                    url_constructed=True,
                    resolution_method="constructed_validated",
                )

    # Nenhuma URL válida
    return URLResolutionResult(
        raw_url=None,
        final_url=None,
        status_final=None,
        url_constructed=False,
        resolution_method="failed",
        error="No valid URL found",
    )


# ============================================================================
# FUNÇÕES AUXILIARES PARA LOG
# ============================================================================

def should_log_resolution(result: URLResolutionResult) -> bool:
    """
    Determina se a resolução deve ser logada.

    Loga apenas quando:
    - url_constructed=True
    - status_final >= 400
    - final_url diferente de raw_url
    """
    if result.url_constructed:
        return True
    if result.status_final and result.status_final >= 400:
        return True
    if result.raw_url and result.final_url and result.raw_url != result.final_url:
        return True
    return False


def log_resolution(result: URLResolutionResult, context: str = ""):
    """Loga resolução de URL se necessário."""
    if should_log_resolution(result):
        prefix = f"[{context}] " if context else ""
        if result.resolution_method == "failed":
            logger.warning(
                f"{prefix}URL resolution failed: {result.raw_url} "
                f"(status={result.status_final}, error={result.error})"
            )
        elif result.url_constructed:
            logger.info(
                f"{prefix}URL constructed: {result.raw_url} → {result.final_url} "
                f"(status={result.status_final})"
            )
        elif result.raw_url != result.final_url:
            logger.info(
                f"{prefix}URL redirected: {result.raw_url} → {result.final_url} "
                f"(status={result.status_final})"
            )


# ============================================================================
# VALIDAÇÃO PARA TESTES
# ============================================================================

def validate_no_hardcoded_concat(code: str, filename: str = "") -> List[str]:
    """
    Verifica se código contém concatenação hardcoded de URLs de lote.

    Usado em testes para impedir regressão.

    Args:
        code: Código fonte Python
        filename: Nome do arquivo (para mensagens de erro)

    Returns:
        Lista de violações encontradas

    Padrões detectados:
        - /lote/{...}/{...}
        - f"...{base_url}/lote/..."
        - + "/lote/" +
    """
    import re

    violations = []

    # Padrões proibidos
    patterns = [
        (r'f["\'].*\{.*\}/lote/\{.*\}/\{.*\}', "f-string com /lote/{id}/{id}"),
        (r'["\']/lote/["\']', "string literal '/lote/'"),
        (r'\+\s*["\']/lote/', "concatenação com '/lote/'"),
        (r'\.format\([^)]*\).*lote/', "str.format com lote"),
    ]

    for pattern, desc in patterns:
        matches = re.finditer(pattern, code, re.IGNORECASE)
        for match in matches:
            line_num = code[:match.start()].count("\n") + 1
            violations.append(
                f"{filename}:{line_num}: {desc} - '{match.group()[:50]}...'"
            )

    return violations
