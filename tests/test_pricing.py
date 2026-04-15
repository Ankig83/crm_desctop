"""Тесты сервиса ценообразования и скидок."""
from datetime import date

import pytest

from crm_desktop.services.pricing import DiscountResult, calculate_line, line_total


# ─────────────────────────────────────────────────────────────────
# DiscountResult: свойства
# ─────────────────────────────────────────────────────────────────

class TestDiscountResult:
    def test_total_pct_sum_of_components(self):
        r = DiscountResult(base_price=100, qty=1, gross=100,
                           client_type_pct=5, promo_pct=10, prepay_pct=2)
        assert r.total_pct == pytest.approx(17.0)

    def test_total_pct_capped_at_100(self):
        r = DiscountResult(base_price=100, qty=1, gross=100,
                           client_type_pct=50, promo_pct=40, prepay_pct=30)
        assert r.total_pct == 100.0

    def test_net_equals_gross_minus_discount(self):
        r = DiscountResult(base_price=100, qty=2, gross=200, promo_pct=10)
        assert r.net == pytest.approx(180.0)

    def test_net_zero_discount(self):
        r = DiscountResult(base_price=50, qty=4, gross=200)
        assert r.net == 200.0

    def test_discount_amount(self):
        r = DiscountResult(base_price=100, qty=1, gross=100, promo_pct=25)
        assert r.discount_amount == pytest.approx(25.0)


# ─────────────────────────────────────────────────────────────────
# line_total: базовые случаи
# ─────────────────────────────────────────────────────────────────

D_IN  = date(2026, 3, 15)   # внутри периода
D_BEF = date(2026, 2, 28)   # до начала
D_AFT = date(2026, 4, 1)    # после окончания
VF    = date(2026, 3, 1)
VT    = date(2026, 3, 31)


def test_no_promo():
    assert line_total(100.0, 2, 10, D_IN, None, None) == 200.0


def test_promo_in_period():
    assert line_total(100.0, 2, 10, D_IN, VF, VT) == pytest.approx(180.0)


def test_promo_outside_period():
    assert line_total(100.0, 2, 10, D_AFT, VF, VT) == 200.0


def test_zero_percent():
    assert line_total(100.0, 2, 0, D_IN, VF, VT) == 200.0


def test_promo_boundary_first_day():
    """Первый день периода — скидка должна применяться."""
    assert line_total(100.0, 1, 10, VF, VF, VT) == pytest.approx(90.0)


def test_promo_boundary_last_day():
    """Последний день периода — скидка должна применяться."""
    assert line_total(100.0, 1, 10, VT, VF, VT) == pytest.approx(90.0)


def test_promo_day_before_start():
    """День до начала — скидки нет."""
    assert line_total(100.0, 1, 10, D_BEF, VF, VT) == 100.0


def test_zero_qty():
    assert line_total(100.0, 0, 10, D_IN, VF, VT) == 0.0


# ─────────────────────────────────────────────────────────────────
# calculate_line: стек скидок
# ─────────────────────────────────────────────────────────────────

class TestCalculateLineStacked:
    def test_client_type_only(self):
        r = calculate_line(100.0, 1, D_IN, client_type_pct=5)
        assert r.net == pytest.approx(95.0)

    def test_prepay_only(self):
        r = calculate_line(100.0, 1, D_IN, prepay_pct=2)
        assert r.net == pytest.approx(98.0)

    def test_volume_only(self):
        r = calculate_line(100.0, 1, D_IN, volume_pct=6)
        assert r.net == pytest.approx(94.0)

    def test_product_pct_only(self):
        r = calculate_line(100.0, 1, D_IN, product_pct=8)
        assert r.net == pytest.approx(92.0)

    def test_all_discounts_stacked(self):
        """Клиент 5% + акция 10% + предоплата 2% + объём 6% = 23%."""
        r = calculate_line(
            100.0, 1, D_IN,
            client_type_pct=5,
            promo_discount_pct=10,
            promo_valid_from=VF,
            promo_valid_to=VT,
            prepay_pct=2,
            volume_pct=6,
        )
        assert r.total_pct == pytest.approx(23.0)
        assert r.net == pytest.approx(77.0)

    def test_stacked_capped_at_100(self):
        """Сумма скидок 120% → не должна давать отрицательную цену."""
        r = calculate_line(100.0, 1, D_IN, client_type_pct=60, volume_pct=60)
        assert r.total_pct == 100.0
        assert r.net == 0.0

    def test_negative_input_clamped(self):
        """Отрицательный процент скидки приводится к 0."""
        r = calculate_line(100.0, 1, D_IN, client_type_pct=-5)
        assert r.client_type_pct == 0.0
        assert r.net == 100.0

    def test_over_100_input_clamped_per_component(self):
        """Компонент > 100% обрезается до 100% (итого тоже 100%)."""
        r = calculate_line(100.0, 1, D_IN, client_type_pct=150)
        assert r.client_type_pct == 100.0
        assert r.net == 0.0

    def test_promo_not_applied_without_dates(self):
        """Акция без дат — скидка не применяется."""
        r = calculate_line(100.0, 1, D_IN, promo_discount_pct=10)
        assert r.promo_pct == 0.0
        assert r.net == 100.0

    def test_large_qty(self):
        r = calculate_line(50.0, 1000, D_IN)
        assert r.gross == pytest.approx(50_000.0)
        assert r.net == pytest.approx(50_000.0)
