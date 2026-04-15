"""Чистые функции бонусной логики (без Qt, тестируемые независимо)."""
from __future__ import annotations

import json
from datetime import date

from crm_desktop.utils.bonus_ids import parse_product_external_ids_csv
from crm_desktop.utils.dates import parse_iso

# (порог, кол-во того же, артикул фикс., кол-во фикс., список на выбор)
BonusRule = tuple[float, int, str, int, list[str]]


def promo_bonus_active(matrix_rules: dict, quote_date: date) -> bool:
    """True если бонусная акция активна на quote_date.

    Если даты не заданы — считается активной всегда.
    При ошибке парсинга — возвращает True (безопасный fallback).
    """
    from_s = str(matrix_rules.get("promo_date_from", "") or "")
    to_s   = str(matrix_rules.get("promo_date_to",   "") or "")
    try:
        if from_s and quote_date < parse_iso(from_s):
            return False
        if to_s and quote_date > parse_iso(to_s):
            return False
    except Exception:  # noqa: BLE001
        pass
    return True


def collect_bonus_thresholds(matrix_rules: dict) -> list[BonusRule]:
    """Извлекает правила бонусных порогов из matrix_rules.

    Поддерживает два формата:
    - Новый: ключ ``bonus_rules`` = JSON-массив правил
    - Старый: ключи ``promo_N_M_qty`` / ``promo_N_M_ids`` (обратная совместимость)
    """
    if "bonus_rules" in matrix_rules:
        try:
            rules = json.loads(str(matrix_rules["bonus_rules"]))
            result: list[BonusRule] = []
            for rule in rules:
                threshold = float(rule.get("threshold", 0))
                if threshold <= 0:
                    continue
                same_qty  = int(rule.get("same_qty", 0))
                fixed_id  = str(rule.get("fixed_id", "")).strip()
                fixed_qty = max(1, int(rule.get("fixed_qty", 1)))
                raw_choice = str(rule.get("choice_ids", "")).strip()
                choice_ids = parse_product_external_ids_csv(raw_choice) if raw_choice else []
                result.append((threshold, same_qty, fixed_id, fixed_qty, choice_ids))
            return result
        except Exception:  # noqa: BLE001
            pass

    # Старый формат: promo_N_M_qty
    names: set[str] = set()
    for key in matrix_rules:
        if key.startswith("promo_") and key.endswith("_qty"):
            names.add(key[len("promo_"):-len("_qty")])

    result = []
    for name in sorted(names):
        try:
            threshold = float(name.split("_")[0])
            same_qty  = int(float(matrix_rules.get(f"promo_{name}_qty", 0) or 0))
        except (ValueError, IndexError):
            continue
        raw_ids = matrix_rules.get(f"promo_{name}_ids", "")
        choice_ids = parse_product_external_ids_csv(str(raw_ids)) if raw_ids else []
        result.append((threshold, same_qty, "", 1, choice_ids))
    return result


def find_best_threshold(thresholds: list[BonusRule], qty: float) -> BonusRule | None:
    """Из правил, у которых qty >= порог, возвращает правило с наибольшим порогом.

    Если ни одно правило не подходит — возвращает None.
    """
    best: BonusRule | None = None
    for t in thresholds:
        if qty >= t[0]:
            if best is None or t[0] > best[0]:
                best = t
    return best
