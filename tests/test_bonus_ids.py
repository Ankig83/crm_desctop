from crm_desktop.utils.bonus_ids import (
    normalize_product_external_ids_csv,
    parse_product_external_ids_csv,
)


def test_parse_empty() -> None:
    assert parse_product_external_ids_csv("") == []
    assert parse_product_external_ids_csv("  ") == []


def test_parse_comma_semicolon() -> None:
    assert parse_product_external_ids_csv("4, 5, 12") == ["4", "5", "12"]
    assert parse_product_external_ids_csv("4;5;12") == ["4", "5", "12"]


def test_parse_id_prefix() -> None:
    assert parse_product_external_ids_csv("id - 4, 5, 12") == ["4", "5", "12"]
    assert parse_product_external_ids_csv("ID – 7") == ["7"]


def test_normalize() -> None:
    assert normalize_product_external_ids_csv("4, 5") == "4,5"
