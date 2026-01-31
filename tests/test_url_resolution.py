#!/usr/bin/env python3
"""
FASE 4: Testes de URL Resolution.

Testes para garantir que:
1. Não há concatenação hardcoded de URLs de lote
2. URL resolution funciona corretamente
3. Normalize e resolve funcionam como esperado

Uso:
    pytest tests/test_url_resolution.py -v
    python -m pytest tests/test_url_resolution.py -v

Autor: Claude Code
Data: 2026-01-30
"""

import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from connectors.common.url_resolution import (
    URLResolutionResult,
    normalize_base_url,
    resolve_absolute_url,
    resolve_lote_url,
    validate_no_hardcoded_concat,
)


# ============================================================================
# TESTES DE normalize_base_url
# ============================================================================

class TestNormalizeBaseUrl:
    """Testes para normalize_base_url."""

    def test_adds_https_to_www(self):
        assert normalize_base_url("www.example.com") == "https://www.example.com"

    def test_adds_https_to_bare_domain(self):
        assert normalize_base_url("example.com") == "https://example.com"

    def test_preserves_http(self):
        assert normalize_base_url("http://example.com") == "http://example.com"

    def test_preserves_https(self):
        assert normalize_base_url("https://example.com") == "https://example.com"

    def test_removes_trailing_slash(self):
        assert normalize_base_url("https://example.com/") == "https://example.com"

    def test_returns_none_for_empty(self):
        assert normalize_base_url("") is None
        assert normalize_base_url(None) is None
        assert normalize_base_url("   ") is None


# ============================================================================
# TESTES DE resolve_absolute_url
# ============================================================================

class TestResolveAbsoluteUrl:
    """Testes para resolve_absolute_url."""

    def test_resolves_relative_path(self):
        result = resolve_absolute_url("https://example.com/page", "/lote/123")
        assert result == "https://example.com/lote/123"

    def test_resolves_relative_file(self):
        result = resolve_absolute_url("https://example.com/dir/", "file.html")
        assert result == "https://example.com/dir/file.html"

    def test_returns_none_for_invalid(self):
        assert resolve_absolute_url("", "/path") is None
        assert resolve_absolute_url("https://example.com", "") is None

    def test_handles_absolute_url(self):
        result = resolve_absolute_url(
            "https://example.com",
            "https://other.com/page"
        )
        assert result == "https://other.com/page"


# ============================================================================
# TESTES DE resolve_lote_url
# ============================================================================

class TestResolveLoteUrl:
    """Testes para resolve_lote_url."""

    def test_uses_first_valid_candidate(self):
        result = resolve_lote_url(
            candidate_urls=["https://example.com/lote/1", None, ""],
            validate_http=False
        )
        assert result.final_url == "https://example.com/lote/1"
        assert result.url_constructed is False
        assert result.resolution_method == "api_canonical"

    def test_skips_none_candidates(self):
        result = resolve_lote_url(
            candidate_urls=[None, "", "https://example.com/valid"],
            validate_http=False
        )
        assert result.final_url == "https://example.com/valid"

    def test_rejects_base_url_only(self):
        """CRÍTICO: Nunca retorna domínio puro como URL de lote."""
        result = resolve_lote_url(
            candidate_urls=["https://www.leiloesjudiciais.com.br", "https://example.com/"],
            validate_http=False
        )
        # Domínio puro deve ser rejeitado, retorna failed
        assert result.final_url is None
        assert result.resolution_method == "failed"

    def test_accepts_url_with_path(self):
        """URL com path é válida."""
        result = resolve_lote_url(
            candidate_urls=["https://www.leiloesjudiciais.com.br/leilao/veiculo-123"],
            validate_http=False
        )
        assert result.final_url == "https://www.leiloesjudiciais.com.br/leilao/veiculo-123"
        assert result.resolution_method == "api_canonical"

    def test_skips_base_url_uses_next_valid(self):
        """Pula domínio puro e usa próximo candidato válido."""
        result = resolve_lote_url(
            candidate_urls=[
                "https://www.leiloesjudiciais.com.br",  # Domínio puro - skip
                "https://www.leiloesjudiciais.com.br/leilao/real",  # Válido
            ],
            validate_http=False
        )
        assert result.final_url == "https://www.leiloesjudiciais.com.br/leilao/real"

    def test_fallback_marked_as_constructed(self):
        result = resolve_lote_url(
            candidate_urls=[None],
            fallback_constructed="https://example.com/constructed",
            validate_http=False
        )
        assert result.final_url == "https://example.com/constructed"
        assert result.url_constructed is True
        assert result.resolution_method == "constructed_validated"

    def test_returns_failed_when_no_urls(self):
        result = resolve_lote_url(
            candidate_urls=[None, "", None],
            fallback_constructed=None,
            validate_http=False
        )
        assert result.final_url is None
        assert result.resolution_method == "failed"

    @patch("connectors.common.url_resolution.head_resolve_final_url")
    def test_validates_http_when_enabled(self, mock_head):
        mock_head.return_value = ("https://final.com/page", 200, 301)

        result = resolve_lote_url(
            candidate_urls=["https://example.com/original"],
            validate_http=True
        )

        assert result.final_url == "https://final.com/page"
        assert result.status_final == 200
        mock_head.assert_called()

    @patch("connectors.common.url_resolution.head_resolve_final_url")
    def test_fallback_fails_on_404(self, mock_head):
        mock_head.return_value = ("https://example.com/404", 404, 404)

        result = resolve_lote_url(
            candidate_urls=[None],
            fallback_constructed="https://example.com/constructed",
            validate_http=True
        )

        assert result.resolution_method == "failed"
        assert result.status_final == 404
        assert result.url_constructed is True

    def test_uses_custom_label_for_href(self):
        """Labels personalizados permitem identificar origem da URL."""
        result = resolve_lote_url(
            candidate_urls=[None, "https://example.com/href/scraped"],
            candidate_labels=["api_canonical", "href_scraped"],
            validate_http=False
        )
        assert result.final_url == "https://example.com/href/scraped"
        assert result.resolution_method == "href_scraped"
        assert result.url_constructed is False

    def test_default_label_is_api_canonical(self):
        """Label padrão é api_canonical quando não especificado."""
        result = resolve_lote_url(
            candidate_urls=["https://example.com/lote/default"],
            validate_http=False
        )
        assert result.resolution_method == "api_canonical"


# ============================================================================
# TESTES DE validate_no_hardcoded_concat
# ============================================================================

class TestValidateNoHardcodedConcat:
    """Testes para detectar concatenação hardcoded."""

    def test_detects_fstring_lote_pattern(self):
        code = '''
        url_lote = f"{self.BASE_URL}/lote/{leilao_id}/{lote_id}"
        '''
        violations = validate_no_hardcoded_concat(code, "test.py")
        assert len(violations) > 0
        assert "test.py" in violations[0]

    def test_detects_string_literal(self):
        code = '''
        path = "/lote/"
        '''
        violations = validate_no_hardcoded_concat(code, "test.py")
        assert len(violations) > 0

    def test_detects_concatenation(self):
        code = '''
        url = base + "/lote/" + str(id)
        '''
        violations = validate_no_hardcoded_concat(code, "test.py")
        assert len(violations) > 0

    def test_allows_clean_code(self):
        code = '''
        from connectors.common.url_resolution import resolve_lote_url
        result = resolve_lote_url(candidate_urls=[url])
        '''
        violations = validate_no_hardcoded_concat(code, "test.py")
        assert len(violations) == 0


# ============================================================================
# TESTE DE INTEGRAÇÃO: VERIFICAR CÓDIGO CORRIGIDO
# ============================================================================

class TestNoHardcodedConcatInConnectors:
    """
    Testa que os conectores não têm concatenação hardcoded.

    Este teste impede regressão - se alguém adicionar
    concatenação de volta, o teste falha.
    """

    def test_normalize_api_no_hardcoded(self):
        """Verifica normalize_api.py não tem padrão /lote/{id}/{id}."""
        filepath = project_root / "connectors" / "leiloesjudiciais" / "normalize_api.py"

        if not filepath.exists():
            pytest.skip("normalize_api.py não encontrado")

        with open(filepath, "r", encoding="utf-8") as f:
            code = f.read()

        violations = validate_no_hardcoded_concat(code, str(filepath))

        # Filtrar falsos positivos (comentários, strings de documentação)
        real_violations = [
            v for v in violations
            if not any(x in v.lower() for x in ["comment", "docstring", "# "])
        ]

        assert len(real_violations) == 0, f"Concatenação hardcoded encontrada: {real_violations}"

    def test_playwright_scraper_no_hardcoded(self):
        """Verifica playwright_scraper.py não tem padrão /lote/{id}/{id}."""
        filepath = project_root / "connectors" / "leiloesjudiciais" / "playwright_scraper.py"

        if not filepath.exists():
            pytest.skip("playwright_scraper.py não encontrado")

        with open(filepath, "r", encoding="utf-8") as f:
            code = f.read()

        violations = validate_no_hardcoded_concat(code, str(filepath))

        # Filtrar falsos positivos
        real_violations = [
            v for v in violations
            if not any(x in v.lower() for x in ["comment", "docstring", "# "])
        ]

        assert len(real_violations) == 0, f"Concatenação hardcoded encontrada: {real_violations}"


# ============================================================================
# GOLDEN TESTS (FIXTURES)
# ============================================================================

class TestGoldenUrlResolution:
    """
    Golden tests com casos conhecidos.

    Estes testes verificam comportamento esperado com URLs reais.
    """

    @pytest.fixture
    def mock_http_responses(self):
        """Fixture que simula respostas HTTP conhecidas."""
        responses = {
            # URL inventada → redireciona para URL real
            "https://www.leiloesjudiciais.com.br/lote/123/456": (
                "https://www.leiloesjudiciais.com.br/leilao/veiculo-abc",
                200,
                301
            ),
            # URL inventada → 404
            "https://www.leiloesjudiciais.com.br/lote/999/999": (
                None,
                404,
                404
            ),
            # URL real → funciona direto
            "https://www.leiloesjudiciais.com.br/leilao/veiculo-real": (
                "https://www.leiloesjudiciais.com.br/leilao/veiculo-real",
                200,
                200
            ),
        }
        return responses

    @patch("connectors.common.url_resolution.head_resolve_final_url")
    def test_invented_url_redirects(self, mock_head, mock_http_responses):
        """URL inventada que redireciona deve retornar URL final."""
        mock_head.side_effect = lambda url: mock_http_responses.get(
            url, (None, None, None)
        )

        result = resolve_lote_url(
            candidate_urls=[],
            fallback_constructed="https://www.leiloesjudiciais.com.br/lote/123/456",
            validate_http=True
        )

        assert result.final_url == "https://www.leiloesjudiciais.com.br/leilao/veiculo-abc"
        assert result.status_final == 200
        assert result.url_constructed is True
        assert result.resolution_method == "constructed_validated"

    @patch("connectors.common.url_resolution.head_resolve_final_url")
    def test_invented_url_404_fails(self, mock_head, mock_http_responses):
        """URL inventada com 404 deve falhar."""
        mock_head.side_effect = lambda url: mock_http_responses.get(
            url, (None, None, None)
        )

        result = resolve_lote_url(
            candidate_urls=[],
            fallback_constructed="https://www.leiloesjudiciais.com.br/lote/999/999",
            validate_http=True
        )

        assert result.resolution_method == "failed"
        assert result.status_final == 404
        assert result.url_constructed is True

    @patch("connectors.common.url_resolution.head_resolve_final_url")
    def test_real_url_works(self, mock_head, mock_http_responses):
        """URL real deve funcionar sem construção."""
        mock_head.side_effect = lambda url: mock_http_responses.get(
            url, (None, None, None)
        )

        result = resolve_lote_url(
            candidate_urls=["https://www.leiloesjudiciais.com.br/leilao/veiculo-real"],
            validate_http=True
        )

        assert result.final_url == "https://www.leiloesjudiciais.com.br/leilao/veiculo-real"
        assert result.url_constructed is False
        assert result.resolution_method == "api_canonical"


# ============================================================================
# MAIN
# ============================================================================

if __name__ == "__main__":
    pytest.main([__file__, "-v"])
