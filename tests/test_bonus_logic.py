"""Тесты чистой бонусной логики (без Qt)."""
from __future__ import annotations

import json
from datetime import date

import pytest

from crm_desktop.services.bonus import (
    BonusRule,
    collect_bonus_thresholds,
    find_best_threshold,
    promo_bonus_active,
)


# ─────────────────────────────────────────────────────────────────
# find_best_threshold
# ─────────────────────────────────────────────────────────────────

class TestFindBestThreshold:
    T10: BonusRule = (10.0, 1, "", 1, [])
    T15: BonusRule = (15.0, 2, "", 1, [])
    T20: BonusRule = (20.0, 3, "bonus_art", 2, ["P1", "P2"])

    def test_below_all_thresholds_returns_none(self):
        assert find_best_threshold([self.T10, self.T15], 9.0) is None

    def test_exactly_at_lower_threshold(self):
        result = find_best_threshold([self.T10, self.T15], 10.0)
        assert result == self.T10

    def test_between_thresholds_returns_lower(self):
        """12 коробок → срабатывает порог 10, не 15."""
        result = find_best_threshold([self.T10, self.T15], 12.0)
        assert result == self.T10

    def test_exactly_at_higher_threshold(self):
        result = find_best_threshold([self.T10, self.T15], 15.0)
        assert result == self.T15

    def test_above_all_thresholds_returns_highest(self):
        """301 коробка → срабатывает наибольший подходящий порог."""
        result = find_best_threshold([self.T10, self.T15, self.T20], 301.0)
        assert result == self.T20

    def test_single_threshold_matches(self):
        assert find_best_threshold([self.T10], 10.0) == self.T10

    def test_single_threshold_no_match(self):
        assert find_best_threshold([self.T10], 5.0) is None

    def test_empty_thresholds(self):
        assert find_best_threshold([], 100.0) is None

    def test_order_independent(self):
        """Порядок списка не влияет на результат."""
        result_asc  = find_best_threshold([self.T10, self.T15, self.T20], 16.0)
        result_desc = find_best_threshold([self.T20, self.T15, self.T10], 16.0)
        assert result_asc == result_desc == self.T15

    def test_fractional_qty(self):
        """Дробное количество тоже сравнивается корректно."""
        result = find_best_threshold([self.T10], 10.5)
        assert result == self.T10


# ─────────────────────────────────────────────────────────────────
# collect_bonus_thresholds — новый формат
# ─────────────────────────────────────────────────────────────────

class TestCollectBonusThresholdsNewFormat:
    def _mr(self, rules: list) -> dict:
        return {"bonus_rules": json.dumps(rules)}

    def test_single_rule_same_qty(self):
        mr = self._mr([{"threshold": 10, "same_qty": 1, "fixed_id": "", "fixed_qty": 1, "choice_ids": ""}])
        result = collect_bonus_thresholds(mr)
        assert len(result) == 1
        thr, same, fid, fqty, cids = result[0]
        assert thr == 10.0
        assert same == 1
        assert fid == ""
        assert cids == []

    def test_two_rules(self):
        mr = self._mr([
            {"threshold": 10, "same_qty": 1, "fixed_id": "", "fixed_qty": 1, "choice_ids": ""},
            {"threshold": 15, "same_qty": 2, "fixed_id": "", "fixed_qty": 1, "choice_ids": ""},
        ])
        result = collect_bonus_thresholds(mr)
        assert len(result) == 2
        assert result[0][0] == 10.0
        assert result[1][0] == 15.0

    def test_rule_with_fixed_id(self):
        mr = self._mr([{"threshold": 50, "same_qty": 0, "fixed_id": "batonic", "fixed_qty": 2, "choice_ids": ""}])
        result = collect_bonus_thresholds(mr)
        thr, same, fid, fqty, cids = result[0]
        assert fid == "batonic"
        assert fqty == 2
        assert same == 0

    def test_rule_with_choice_ids(self):
        mr = self._mr([{"threshold": 100, "same_qty": 0, "fixed_id": "", "fixed_qty": 1, "choice_ids": "P1,P2,P3"}])
        result = collect_bonus_thresholds(mr)
        _, _, _, _, cids = result[0]
        assert cids == ["P1", "P2", "P3"]

    def test_zero_threshold_skipped(self):
        mr = self._mr([
            {"threshold": 0, "same_qty": 1, "fixed_id": "", "fixed_qty": 1, "choice_ids": ""},
            {"threshold": 10, "same_qty": 1, "fixed_id": "", "fixed_qty": 1, "choice_ids": ""},
        ])
        result = collect_bonus_thresholds(mr)
        assert len(result) == 1
        assert result[0][0] == 10.0

    def test_empty_rules_list(self):
        assert collect_bonus_thresholds({"bonus_rules": "[]"}) == []

    def test_fixed_qty_minimum_1(self):
        """fixed_qty < 1 должен быть приведён к 1."""
        mr = self._mr([{"threshold": 10, "same_qty": 0, "fixed_id": "X", "fixed_qty": 0, "choice_ids": ""}])
        _, _, _, fqty, _ = collect_bonus_thresholds(mr)[0]
        assert fqty == 1


# ─────────────────────────────────────────────────────────────────
# collect_bonus_thresholds — старый (legacy) формат
# ─────────────────────────────────────────────────────────────────

class TestCollectBonusThresholdsLegacyFormat:
    def test_basic_legacy(self):
        mr = {"promo_15_2_qty": 2}
        result = collect_bonus_thresholds(mr)
        assert len(result) == 1
        thr, same, fid, fqty, cids = result[0]
        assert thr == 15.0
        assert same == 2
        assert fid == ""
        assert cids == []

    def test_legacy_with_other_ids(self):
        mr = {"promo_10_1_qty": 1, "promo_10_1_ids": "P1,P2"}
        result = collect_bonus_thresholds(mr)
        _, _, _, _, cids = result[0]
        assert cids == ["P1", "P2"]

    def test_legacy_multiple_rules(self):
        mr = {"promo_10_1_qty": 1, "promo_20_3_qty": 3}
        result = collect_bonus_thresholds(mr)
        thresholds = [r[0] for r in result]
        assert 10.0 in thresholds
        assert 20.0 in thresholds

    def test_empty_returns_empty(self):
        assert collect_bonus_thresholds({}) == []

    def test_new_format_takes_priority(self):
        """Если есть bonus_rules, legacy-ключи игнорируются."""
        mr = {
            "bonus_rules": json.dumps([{"threshold": 10, "same_qty": 1,
                                         "fixed_id": "", "fixed_qty": 1, "choice_ids": ""}]),
            "promo_99_1_qty": 1,   # legacy — должен быть проигнорирован
        }
        result = collect_bonus_thresholds(mr)
        assert len(result) == 1
        assert result[0][0] == 10.0


# ─────────────────────────────────────────────────────────────────
# promo_bonus_active
# ─────────────────────────────────────────────────────────────────

class TestPromoBonusActive:
    D = date(2026, 4, 15)

    def test_no_dates_always_active(self):
        assert promo_bonus_active({}, self.D) is True

    def test_within_date_range(self):
        mr = {"promo_date_from": "2026-04-01", "promo_date_to": "2026-04-30"}
        assert promo_bonus_active(mr, self.D) is True

    def test_before_start_date(self):
        mr = {"promo_date_from": "2026-05-01", "promo_date_to": "2026-05-31"}
        assert promo_bonus_active(mr, self.D) is False

    def test_after_end_date(self):
        mr = {"promo_date_from": "2026-03-01", "promo_date_to": "2026-04-01"}
        assert promo_bonus_active(mr, self.D) is False

    def test_on_start_date(self):
        mr = {"promo_date_from": "2026-04-15", "promo_date_to": "2026-04-30"}
        assert promo_bonus_active(mr, self.D) is True

    def test_on_end_date(self):
        mr = {"promo_date_from": "2026-04-01", "promo_date_to": "2026-04-15"}
        assert promo_bonus_active(mr, self.D) is True

    def test_only_from_date(self):
        mr = {"promo_date_from": "2026-04-01"}
        assert promo_bonus_active(mr, self.D) is True

    def test_only_to_date(self):
        mr = {"promo_date_to": "2026-04-30"}
        assert promo_bonus_active(mr, self.D) is True

    def test_invalid_date_format_safe_fallback(self):
        """При некорректной дате → True (безопасный fallback)."""
        mr = {"promo_date_from": "not-a-date", "promo_date_to": "also-bad"}
        assert promo_bonus_active(mr, self.D) is True

    def test_empty_string_dates(self):
        mr = {"promo_date_from": "", "promo_date_to": ""}
        assert promo_bonus_active(mr, self.D) is True
