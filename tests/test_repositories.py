"""Тесты CRUD-репозиториев: клиенты, товары, акции."""
from __future__ import annotations

import pytest

from crm_desktop.repositories import clients, products, promotions


# ─────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────

def _client(conn, *, name="ООО Тест", inn="7700000001", ext=None, client_type="regular"):
    """Создаёт клиента с разумными значениями по умолчанию."""
    return clients.insert(
        conn,
        external_id=ext,
        name=name,
        inn=inn,
        contacts="",
        addresses="",
        unload_points="",
        client_type=client_type,
    )


def _product(conn, *, ext="P-1", name="Товар", price=100.0):
    return products.insert(conn, external_id=ext, name=name, base_price=price)


# ─────────────────────────────────────────────────────────────────
# Клиенты
# ─────────────────────────────────────────────────────────────────

class TestClientsRepo:
    def test_insert_and_get(self, conn):
        cid = _client(conn, name="ООО Ромашка", inn="7700000001")
        c = clients.get(conn, cid)
        assert c is not None
        assert c.name == "ООО Ромашка"
        assert c.inn == "7700000001"
        # is_new по умолчанию False (новые клиенты создаются вручную, не импортом)
        assert c.is_new is False

    def test_list_all_empty(self, conn):
        assert clients.list_all(conn) == []

    def test_list_all_returns_all(self, conn):
        _client(conn, name="Клиент А", inn="1234567890", ext="C-1")
        _client(conn, name="Клиент Б", inn="0987654321", ext="C-2")
        lst = clients.list_all(conn)
        assert len(lst) == 2

    def test_update_name(self, conn):
        cid = _client(conn, name="Старое", inn="1111111111", ext="C-1")
        c = clients.get(conn, cid)
        clients.update(conn, cid,
                       external_id=c.external_id, name="Новое", inn=c.inn,
                       contacts=c.contacts, addresses=c.addresses, unload_points=c.unload_points)
        updated = clients.get(conn, cid)
        assert updated.name == "Новое"

    def test_delete(self, conn):
        cid = _client(conn, name="Удаляемый", inn="2222222222", ext="C-D")
        clients.delete(conn, cid)
        assert clients.get(conn, cid) is None

    def test_client_type_discount_distributor(self, conn):
        cid = _client(conn, name="Дистрибьютор", inn="3333333333", client_type="distributor")
        c = clients.get(conn, cid)
        assert c.type_discount_pct == 5.0
        assert "Дистрибьютор" in c.client_type_label

    def test_client_type_discount_retail_chain(self, conn):
        cid = _client(conn, name="Сеть", inn="4444444444", client_type="retail_chain")
        c = clients.get(conn, cid)
        assert c.type_discount_pct == 15.0

    def test_client_type_discount_wholesaler(self, conn):
        cid = _client(conn, name="Оптовик", inn="5555555555", client_type="wholesaler")
        c = clients.get(conn, cid)
        assert c.type_discount_pct == 2.0

    def test_client_type_regular_no_discount(self, conn):
        cid = _client(conn, name="Обычный", inn="6666666666", client_type="regular")
        c = clients.get(conn, cid)
        assert c.type_discount_pct == 0.0

    def test_update_is_new_flag(self, conn):
        cid = _client(conn, name="Новый", inn="7777777777", ext="C-N")
        c = clients.get(conn, cid)
        clients.update(conn, cid,
                       external_id=c.external_id, name=c.name, inn=c.inn,
                       contacts=c.contacts, addresses=c.addresses,
                       unload_points=c.unload_points, is_new=False)
        updated = clients.get(conn, cid)
        assert updated.is_new is False


# ─────────────────────────────────────────────────────────────────
# Товары
# ─────────────────────────────────────────────────────────────────

class TestProductsRepo:
    def test_insert_and_get(self, conn):
        pid = _product(conn, ext="ART-001", name="Кофе", price=250.0)
        p = products.get(conn, pid)
        assert p is not None
        assert p.external_id == "ART-001"
        assert p.name == "Кофе"
        assert p.base_price == pytest.approx(250.0)

    def test_list_all_empty(self, conn):
        assert products.list_all(conn) == []

    def test_by_external_id(self, conn):
        _product(conn, ext="X-99", name="Тест", price=10.0)
        p = products.by_external_id(conn, "X-99")
        assert p is not None
        assert p.name == "Тест"

    def test_by_external_id_not_found(self, conn):
        assert products.by_external_id(conn, "NONEXISTENT") is None

    def test_update_price(self, conn):
        pid = _product(conn, ext="P1", name="Товар", price=100.0)
        products.update(conn, pid, external_id="P1", name="Товар", base_price=150.0)
        p = products.get(conn, pid)
        assert p.base_price == pytest.approx(150.0)

    def test_update_partial_keeps_other_fields(self, conn):
        """Обновление цены не затирает штрихкод."""
        pid = products.insert(conn, external_id="P2", name="Товар", base_price=100.0,
                              box_barcode="1234567890")
        products.update(conn, pid, external_id="P2", name="Товар", base_price=200.0)
        p = products.get(conn, pid)
        assert p.box_barcode == "1234567890"
        assert p.base_price == pytest.approx(200.0)

    def test_delete(self, conn):
        pid = _product(conn, ext="DEL", name="Удалить", price=0)
        products.delete(conn, pid)
        assert products.get(conn, pid) is None

    def test_list_all_multiple(self, conn):
        _product(conn, ext="A", name="А", price=1.0)
        _product(conn, ext="B", name="Б", price=2.0)
        _product(conn, ext="C", name="В", price=3.0)
        lst = products.list_all(conn)
        assert len(lst) == 3


# ─────────────────────────────────────────────────────────────────
# Акции
# ─────────────────────────────────────────────────────────────────

class TestPromotionsRepo:
    def test_upsert_creates_new(self, conn):
        pid = _product(conn)
        promotions.upsert(conn, pid,
                          promo_type="Сезон",
                          discount_percent=10.0,
                          valid_from_iso="2026-01-01",
                          valid_to_iso="2026-12-31")
        row = promotions.get_for_product(conn, pid)
        assert row is not None
        assert row.discount_percent == pytest.approx(10.0)
        assert row.promo_type == "Сезон"

    def test_upsert_updates_existing(self, conn):
        pid = _product(conn)
        promotions.upsert(conn, pid, promo_type="А", discount_percent=5.0,
                          valid_from_iso="2026-01-01", valid_to_iso="2026-06-30")
        promotions.upsert(conn, pid, promo_type="Б", discount_percent=15.0,
                          valid_from_iso="2026-04-01", valid_to_iso="2026-12-31")
        row = promotions.get_for_product(conn, pid)
        assert row.discount_percent == pytest.approx(15.0)
        assert row.promo_type == "Б"

    def test_get_for_product_none_if_missing(self, conn):
        pid = _product(conn)
        assert promotions.get_for_product(conn, pid) is None

    def test_list_all(self, conn):
        pid1 = _product(conn, ext="P-1")
        pid2 = _product(conn, ext="P-2")
        promotions.upsert(conn, pid1, promo_type="", discount_percent=5,
                          valid_from_iso="2026-01-01", valid_to_iso="2026-12-31")
        promotions.upsert(conn, pid2, promo_type="", discount_percent=8,
                          valid_from_iso="2026-01-01", valid_to_iso="2026-12-31")
        lst = promotions.list_all(conn)
        assert len(lst) == 2

    def test_delete_for_product(self, conn):
        pid = _product(conn)
        promotions.upsert(conn, pid, promo_type="", discount_percent=5,
                          valid_from_iso="2026-01-01", valid_to_iso="2026-12-31")
        promotions.delete_for_product(conn, pid)
        assert promotions.get_for_product(conn, pid) is None

    def test_cascade_delete_with_product(self, conn):
        """Удаление товара каскадно удаляет акцию."""
        pid = _product(conn)
        promotions.upsert(conn, pid, promo_type="", discount_percent=5,
                          valid_from_iso="2026-01-01", valid_to_iso="2026-12-31")
        products.delete(conn, pid)
        assert promotions.get_for_product(conn, pid) is None

    def test_upsert_saves_matrix_rules_json(self, conn):
        import json
        pid = _product(conn)
        rules = json.dumps([{"threshold": 10, "same_qty": 1, "fixed_id": "", "fixed_qty": 1, "choice_ids": ""}])
        promotions.upsert(conn, pid, promo_type="", discount_percent=0,
                          valid_from_iso="2026-01-01", valid_to_iso="2026-12-31",
                          matrix_rules_json=json.dumps({"bonus_rules": rules}))
        row = promotions.get_for_product(conn, pid)
        assert "bonus_rules" in row.matrix_rules_json
