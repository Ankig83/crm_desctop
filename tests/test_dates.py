"""Тесты утилит работы с датами."""
from datetime import date

import pytest

from crm_desktop.utils.dates import format_dmY, iso, parse_dmY, parse_iso


class TestParseDmY:
    def test_standard_format(self):
        assert parse_dmY("15.03.2026") == date(2026, 3, 15)

    def test_first_day_of_year(self):
        assert parse_dmY("01.01.2026") == date(2026, 1, 1)

    def test_last_day_of_year(self):
        assert parse_dmY("31.12.2026") == date(2026, 12, 31)

    def test_single_digit_day_month(self):
        """Ведущий ноль необязателен."""
        assert parse_dmY("1.4.2026") == date(2026, 4, 1)

    def test_with_surrounding_spaces(self):
        assert parse_dmY("  05.06.2026  ") == date(2026, 6, 5)

    def test_empty_string_raises(self):
        with pytest.raises(ValueError):
            parse_dmY("")

    def test_iso_format_raises(self):
        with pytest.raises(ValueError):
            parse_dmY("2026-03-15")

    def test_invalid_text_raises(self):
        with pytest.raises(ValueError):
            parse_dmY("не дата")

    def test_partial_date_raises(self):
        with pytest.raises(ValueError):
            parse_dmY("15.03")


class TestFormatDmY:
    def test_formats_with_leading_zeros(self):
        assert format_dmY(date(2026, 4, 7)) == "07.04.2026"

    def test_formats_december_31(self):
        assert format_dmY(date(2026, 12, 31)) == "31.12.2026"

    def test_round_trip(self):
        d = date(2026, 7, 19)
        assert parse_dmY(format_dmY(d)) == d


class TestIsoAndParseIso:
    def test_iso_format(self):
        assert iso(date(2026, 3, 15)) == "2026-03-15"

    def test_parse_iso(self):
        assert parse_iso("2026-03-15") == date(2026, 3, 15)

    def test_round_trip(self):
        d = date(2026, 11, 1)
        assert parse_iso(iso(d)) == d
