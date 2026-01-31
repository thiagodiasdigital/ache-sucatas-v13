"""
Utilitários comuns para conectores.
"""

from .url_resolution import (
    URLResolutionResult,
    normalize_base_url,
    resolve_absolute_url,
    resolve_lote_url,
    head_resolve_final_url,
    should_log_resolution,
    log_resolution,
    validate_no_hardcoded_concat,
)

__all__ = [
    "URLResolutionResult",
    "normalize_base_url",
    "resolve_absolute_url",
    "resolve_lote_url",
    "head_resolve_final_url",
    "should_log_resolution",
    "log_resolution",
    "validate_no_hardcoded_concat",
]
