"""
Tests for parsing functions in supabase_repository.py
These are internal methods tested via an instance with Supabase disabled.
"""
import pytest
from supabase_repository import SupabaseRepository


class TestParseValor:
    """Test _parse_valor method"""

    @pytest.fixture
    def repo(self):
        """Create repo instance with Supabase disabled"""
        return SupabaseRepository(enable_supabase=False)

    def test_none_returns_none(self, repo):
        assert repo._parse_valor(None) is None

    def test_empty_returns_none(self, repo):
        assert repo._parse_valor("") is None

    def test_nd_returns_none(self, repo):
        assert repo._parse_valor("N/D") is None

    def test_simple_value(self, repo):
        assert repo._parse_valor("1000") == 1000.0

    def test_with_currency_symbol(self, repo):
        assert repo._parse_valor("R$ 1.234,56") == 1234.56

    def test_with_thousands_separator(self, repo):
        assert repo._parse_valor("1.000.000,00") == 1000000.0

    def test_decimal_only(self, repo):
        assert repo._parse_valor("99,99") == 99.99


class TestParseInt:
    """Test _parse_int method"""

    @pytest.fixture
    def repo(self):
        return SupabaseRepository(enable_supabase=False)

    def test_none_returns_none(self, repo):
        assert repo._parse_int(None) is None

    def test_empty_returns_none(self, repo):
        assert repo._parse_int("") is None

    def test_nd_returns_none(self, repo):
        assert repo._parse_int("N/D") is None

    def test_simple_int(self, repo):
        assert repo._parse_int("42") == 42

    def test_with_whitespace(self, repo):
        assert repo._parse_int("  123  ") == 123

    def test_zero(self, repo):
        assert repo._parse_int("0") == 0


class TestParseData:
    """Test _parse_data method"""

    @pytest.fixture
    def repo(self):
        return SupabaseRepository(enable_supabase=False)

    def test_none_returns_none(self, repo):
        assert repo._parse_data(None) is None

    def test_empty_returns_none(self, repo):
        assert repo._parse_data("") is None

    def test_nd_returns_none(self, repo):
        assert repo._parse_data("N/D") is None

    def test_br_format(self, repo):
        assert repo._parse_data("15/01/2026") == "2026-01-15"

    def test_iso_format_passthrough(self, repo):
        assert repo._parse_data("2026-01-15") == "2026-01-15"

    def test_single_digit_day_month(self, repo):
        assert repo._parse_data("5/1/2026") == "2026-01-05"


class TestParseDatetime:
    """Test _parse_datetime method"""

    @pytest.fixture
    def repo(self):
        return SupabaseRepository(enable_supabase=False)

    def test_none_returns_none(self, repo):
        assert repo._parse_datetime(None) is None

    def test_empty_returns_none(self, repo):
        assert repo._parse_datetime("") is None

    def test_nd_returns_none(self, repo):
        assert repo._parse_datetime("N/D") is None

    def test_date_only(self, repo):
        result = repo._parse_datetime("15/01/2026")
        assert result == "2026-01-15T00:00:00"

    def test_with_time(self, repo):
        result = repo._parse_datetime("15/01/2026 14:30")
        assert result == "2026-01-15T14:30:00"
