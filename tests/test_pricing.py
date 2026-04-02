from datetime import date

from crm_desktop.services.pricing import line_total


def test_no_promo():
    assert line_total(100.0, 2, 10, date(2026, 3, 1), None, None) == 200.0


def test_promo_in_period():
    assert (
        line_total(100.0, 2, 10, date(2026, 3, 15), date(2026, 3, 1), date(2026, 3, 31))
        == 180.0
    )


def test_promo_outside_period():
    assert (
        line_total(100.0, 2, 10, date(2026, 4, 1), date(2026, 3, 1), date(2026, 3, 31))
        == 200.0
    )


def test_zero_percent():
    assert (
        line_total(100.0, 2, 0, date(2026, 3, 15), date(2026, 3, 1), date(2026, 3, 31))
        == 200.0
    )
