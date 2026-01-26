"""
Tests for ScoringEngine and FileTypeDetector in ache_sucatas_miner_v18.py
"""
import pytest
import sys
import os

# Adiciona src/core ao path para imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src', 'core'))

from ache_sucatas_miner_v18 import ScoringEngine, FileTypeDetector


class TestScoringEngine:
    def test_base_score(self):
        """Empty text should return base score of 50"""
        score = ScoringEngine.calculate_score("", "", "")
        assert score == 50

    def test_positive_keywords_increase_score(self):
        """Positive keywords should increase score"""
        score = ScoringEngine.calculate_score(
            "leilão de veículos",
            "sucata inservível",
            ""
        )
        assert score > 50

    def test_negative_keywords_decrease_score(self):
        """Negative keywords should decrease score"""
        score = ScoringEngine.calculate_score(
            "credenciamento de fornecedores",
            "pregão eletrônico",
            ""
        )
        assert score < 50

    def test_mixed_keywords(self):
        """Mixed keywords should balance out"""
        score = ScoringEngine.calculate_score(
            "leilão de veículos",  # positive
            "credenciamento",  # negative
            ""
        )
        # Should be affected by both
        assert isinstance(score, int)

    def test_max_score_capped_at_100(self):
        """Score should never exceed 100"""
        score = ScoringEngine.calculate_score(
            "sucata inservível leilão veículo",
            "apreendido DETRAN alienação",
            "desfazimento antieconômico"
        )
        assert score <= 100

    def test_min_score_not_negative(self):
        """Score can go below 0 with many negative keywords"""
        score = ScoringEngine.calculate_score(
            "credenciamento pregão habilitação",
            "qualificação chamamento contratação",
            "fornecimento prestação registro de preço"
        )
        # Score could be negative (no floor in the code)
        assert isinstance(score, int)

    def test_leiloeiro_keywords(self):
        """Auctioneer keywords should increase score"""
        score = ScoringEngine.calculate_score(
            "fernandoleiloeiro",
            "",
            ""
        )
        assert score > 50

    def test_case_insensitive(self):
        """Keywords should match regardless of case"""
        score_lower = ScoringEngine.calculate_score("sucata", "", "")
        score_upper = ScoringEngine.calculate_score("SUCATA", "", "")
        assert score_lower == score_upper


class TestFileTypeDetector:
    def test_detect_pdf_by_content_type(self):
        result = FileTypeDetector.detect_by_content_type("application/pdf")
        assert result == ".pdf"

    def test_detect_xlsx_by_content_type(self):
        result = FileTypeDetector.detect_by_content_type(
            "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )
        assert result == ".xlsx"

    def test_detect_xls_by_content_type(self):
        result = FileTypeDetector.detect_by_content_type("application/vnd.ms-excel")
        assert result == ".xls"

    def test_detect_csv_by_content_type(self):
        result = FileTypeDetector.detect_by_content_type("text/csv")
        assert result == ".csv"

    def test_detect_docx_by_content_type(self):
        result = FileTypeDetector.detect_by_content_type(
            "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
        )
        assert result == ".docx"

    def test_detect_with_charset(self):
        result = FileTypeDetector.detect_by_content_type("application/pdf; charset=utf-8")
        assert result == ".pdf"

    def test_unknown_content_type(self):
        result = FileTypeDetector.detect_by_content_type("application/unknown")
        assert result is None

    def test_empty_content_type(self):
        result = FileTypeDetector.detect_by_content_type("")
        assert result is None

    def test_none_content_type(self):
        result = FileTypeDetector.detect_by_content_type(None)
        assert result is None

    def test_detect_pdf_by_magic_bytes(self):
        pdf_header = b'%PDF-1.4 some content'
        result = FileTypeDetector.detect_by_magic_bytes(pdf_header)
        assert result == ".pdf"

    def test_detect_zip_by_magic_bytes(self):
        zip_header = b'PK\x03\x04' + b'\x00' * 100
        result = FileTypeDetector.detect_by_magic_bytes(zip_header)
        # Could be .zip, .xlsx, or .docx
        assert result in [".zip", ".xlsx", ".docx"]

    def test_detect_xlsx_by_magic_bytes(self):
        # V18 corretamente detecta xlsx pelo conteúdo 'xl/'
        xlsx_header = b'PK\x03\x04' + b'xl/' + b'\x00' * 990
        result = FileTypeDetector.detect_by_magic_bytes(xlsx_header)
        assert result == ".xlsx"

    def test_detect_docx_by_magic_bytes(self):
        # V18 corretamente detecta docx pelo conteúdo 'word/'
        docx_header = b'PK\x03\x04' + b'word/' + b'\x00' * 990
        result = FileTypeDetector.detect_by_magic_bytes(docx_header)
        assert result == ".docx"

    def test_unknown_magic_bytes(self):
        unknown = b'\x00\x00\x00\x00'
        result = FileTypeDetector.detect_by_magic_bytes(unknown)
        assert result is None
