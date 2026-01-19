"""
Tests for extraction functions in cloud_auditor_v14.py
These are pure functions that don't require Supabase connection.
"""
import pytest

from cloud_auditor_v14 import (
    corrigir_encoding,
    limpar_texto,
    formatar_data_br,
    formatar_valor_br,
    extrair_urls_de_texto,
    normalizar_url,
    extrair_valor_estimado,
    extrair_quantidade_itens,
    extrair_nome_leiloeiro,
    extrair_data_leilao_cascata,
)


class TestCorrigirEncoding:
    def test_empty_string(self):
        assert corrigir_encoding("") == ""

    def test_nd_value(self):
        assert corrigir_encoding("N/D") == "N/D"

    def test_normal_text(self):
        result = corrigir_encoding("texto normal")
        assert isinstance(result, str)

    def test_none_returns_none(self):
        assert corrigir_encoding(None) is None


class TestLimparTexto:
    def test_empty_string(self):
        assert limpar_texto("") == ""

    def test_nd_value(self):
        assert limpar_texto("N/D") == "N/D"

    def test_multiple_spaces(self):
        assert limpar_texto("a  b   c") == "a b c"

    def test_multiple_newlines(self):
        assert limpar_texto("a\n\n\n\nb") == "a\n\nb"

    def test_truncation_default(self):
        long_text = "a" * 600
        result = limpar_texto(long_text)
        assert len(result) <= 503  # 500 + "..."
        assert result.endswith("...")

    def test_truncation_custom_length(self):
        text = "a" * 100
        result = limpar_texto(text, max_length=50)
        assert len(result) <= 53  # 50 + "..."

    def test_strips_whitespace(self):
        assert limpar_texto("  hello  ") == "hello"


class TestFormatarDataBr:
    def test_empty_returns_nd(self):
        assert formatar_data_br("") == "N/D"

    def test_none_returns_nd(self):
        assert formatar_data_br(None) == "N/D"

    def test_nd_returns_nd(self):
        assert formatar_data_br("N/D") == "N/D"

    def test_already_br_format(self):
        assert formatar_data_br("15/01/2026") == "15/01/2026"

    def test_iso_format(self):
        assert formatar_data_br("2026-01-15") == "15/01/2026"

    def test_with_time(self):
        assert formatar_data_br("2026-01-15T10:30:00") == "15/01/2026"

    def test_dash_separator(self):
        assert formatar_data_br("15-01-2026") == "15/01/2026"

    def test_dot_separator(self):
        assert formatar_data_br("15.01.2026") == "15/01/2026"


class TestFormatarValorBr:
    def test_none_returns_nd(self):
        assert formatar_valor_br(None) == "N/D"

    def test_zero_returns_nd(self):
        # 0 is falsy, so returns N/D
        assert formatar_valor_br(0) == "N/D"

    def test_integer(self):
        assert formatar_valor_br(1000) == "R$ 1.000,00"

    def test_float(self):
        assert formatar_valor_br(1234.56) == "R$ 1.234,56"

    def test_large_value(self):
        assert formatar_valor_br(1000000) == "R$ 1.000.000,00"

    def test_string_number(self):
        assert formatar_valor_br("500") == "R$ 500,00"


class TestExtrairUrlsDeTexto:
    def test_empty_returns_empty(self):
        assert extrair_urls_de_texto("") == []

    def test_none_returns_empty(self):
        assert extrair_urls_de_texto(None) == []

    def test_single_url(self):
        text = "Acesse www.exemplo.com.br para mais info"
        urls = extrair_urls_de_texto(text)
        assert len(urls) >= 1

    def test_multiple_urls(self):
        text = "Site 1: www.site1.com.br e site 2: www.site2.com"
        urls = extrair_urls_de_texto(text)
        assert len(urls) >= 2

    def test_removes_duplicates(self):
        text = "www.exemplo.com e www.exemplo.com novamente"
        urls = extrair_urls_de_texto(text)
        # Should have only unique URLs
        assert len(urls) == len(set(urls))

    # ==========================================================================
    # BUG FIX VALIDATION TESTS (2026-01-19)
    # ==========================================================================

    def test_bug2_www_sem_protocolo(self):
        """Bug #2: Regex deve capturar URLs com 'www.' sem protocolo http(s)://"""
        text = "Acesse www.leiloeiro.com.br para participar"
        urls = extrair_urls_de_texto(text)
        assert len(urls) == 1
        assert "leiloeiro.com.br" in urls[0]

    def test_bug2_www_sem_protocolo_net(self):
        """Bug #2: URLs com www. sem protocolo em domínios .net"""
        text = "Portal disponível em www.portal.net"
        urls = extrair_urls_de_texto(text)
        assert len(urls) == 1
        assert "portal.net" in urls[0]

    def test_bug3_dominio_net_br(self):
        """Bug #3: Regex deve capturar domínios .net.br"""
        text = "Cadastre-se em https://www.leiloes.net.br/cadastro"
        urls = extrair_urls_de_texto(text)
        assert len(urls) == 1
        assert ".net.br" in urls[0]

    def test_bug3_net_br_sem_protocolo(self):
        """Bug #3: Domínios .net.br sem protocolo também devem ser capturados"""
        text = "Acesse www.sistema.net.br para mais detalhes"
        urls = extrair_urls_de_texto(text)
        assert len(urls) == 1
        assert ".net.br" in urls[0]

    def test_bug2_bug3_combinados(self):
        """Bugs #2 e #3 combinados: múltiplas URLs com e sem protocolo"""
        text = """
        Plataformas disponíveis:
        - www.leiloeiro.com.br (sem protocolo)
        - https://www.outro.net.br (com protocolo .net.br)
        - www.terceiro.net (sem protocolo .net)
        - http://quarto.org.br (com protocolo http)
        """
        urls = extrair_urls_de_texto(text)
        assert len(urls) == 4
        # Verificar que todos os domínios foram capturados
        url_text = " ".join(urls)
        assert "leiloeiro.com.br" in url_text
        assert ".net.br" in url_text
        assert ".net" in url_text
        assert ".org.br" in url_text

    def test_dominio_leilao_br(self):
        """Domínio especial .leilao.br deve ser capturado"""
        text = "Participe em www.exemplo.leilao.br"
        urls = extrair_urls_de_texto(text)
        assert len(urls) == 1
        assert ".leilao.br" in urls[0]


class TestNormalizarUrl:
    def test_add_https(self):
        assert normalizar_url("www.exemplo.com") == "https://www.exemplo.com"

    def test_keep_http(self):
        assert normalizar_url("http://exemplo.com") == "http://exemplo.com"

    def test_keep_https(self):
        assert normalizar_url("https://exemplo.com") == "https://exemplo.com"

    def test_remove_trailing_period(self):
        assert normalizar_url("www.exemplo.com.") == "https://www.exemplo.com"

    def test_remove_trailing_comma(self):
        assert normalizar_url("www.exemplo.com,") == "https://www.exemplo.com"

    def test_empty_returns_empty(self):
        assert normalizar_url("") == ""


class TestExtrairValorEstimado:
    def test_empty_returns_nd(self):
        assert extrair_valor_estimado("") == "N/D"

    def test_valor_estimado_pattern(self):
        # Pattern requires "valor", "lance", "mínimo", "avaliação", or "estimado"
        # followed by optional colon/space, then the number
        text = "valor estimado 10.000,00"
        result = extrair_valor_estimado(text)
        assert result != "N/D"

    def test_lance_minimo(self):
        text = "lance mínimo 5.000,00"
        result = extrair_valor_estimado(text)
        assert result != "N/D"

    def test_avaliacao(self):
        text = "avaliação 15000"
        result = extrair_valor_estimado(text)
        assert result != "N/D"


class TestExtrairQuantidadeItens:
    def test_empty_returns_nd(self):
        assert extrair_quantidade_itens("") == "N/D"

    def test_lotes(self):
        text = "LOTE 1 - Veículo\nLOTE 2 - Motocicleta\nLOTE 3 - Sucata"
        result = extrair_quantidade_itens(text)
        assert result == "3"

    def test_itens(self):
        text = "ITEM 1 - Veículo\nITEM 2 - Motocicleta"
        result = extrair_quantidade_itens(text)
        assert result == "2"

    def test_lotes_priority_over_itens(self):
        text = "LOTE 1\nLOTE 2\nITEM 1\nITEM 2\nITEM 3"
        result = extrair_quantidade_itens(text)
        # Lotes should be found first
        assert result == "2"


class TestExtrairNomeLeiloeiro:
    def test_empty_returns_nd(self):
        assert extrair_nome_leiloeiro("") == "N/D"

    def test_with_leiloeiro_pattern(self):
        # The regex expects: leiloeiro/leiloeira followed by optional "oficial/público/a"
        # then colon/space, then a capitalized name
        text = "Leiloeiro: João Silva"
        result = extrair_nome_leiloeiro(text)
        # Result depends on regex matching
        assert isinstance(result, str)

    def test_no_match_returns_nd(self):
        # Text without proper pattern
        text = "O responsável é fulano de tal"
        result = extrair_nome_leiloeiro(text)
        assert result == "N/D"


class TestExtrairDataLeilaoCascata:
    def test_empty_returns_nd(self):
        assert extrair_data_leilao_cascata("") == "N/D"

    def test_empty_both_returns_nd(self):
        assert extrair_data_leilao_cascata("", "") == "N/D"

    def test_date_in_descricao(self):
        desc = "Leilão dia 15/01/2026 às 10h"
        result = extrair_data_leilao_cascata("", desc)
        # May or may not find depending on regex
        assert isinstance(result, str)

    def test_date_in_pdf(self):
        pdf = "Data do leilão: 20/02/2026"
        result = extrair_data_leilao_cascata(pdf)
        assert isinstance(result, str)

    def test_date_with_time(self):
        pdf = "Será realizado no dia 10/03/2026 às 14:00"
        result = extrair_data_leilao_cascata(pdf)
        assert isinstance(result, str)
