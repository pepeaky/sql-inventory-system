"""Tests for constraint enforcement and dirty-data resilience.

Verifies that the schema and application layer correctly reject
invalid, malformed, or out-of-bounds data.
"""

import pytest
import psycopg2


class TestSchemaConstraints:
    def test_negative_unit_cost_rejected(self, cur, seed_base):
        with pytest.raises(psycopg2.errors.CheckViolation):
            cur.execute(
                "INSERT INTO products (sku, name, category_id, unit_cost) VALUES ('BAD-001','Bad',%s,-5.00)",
                (seed_base["cat_id"],),
            )

    def test_negative_capacity_rejected(self, cur, seed_base):
        with pytest.raises(psycopg2.errors.CheckViolation):
            cur.execute(
                "INSERT INTO warehouses (name, country_id, city, capacity_m3) VALUES ('Bad WH',%s,'Nowhere',-100)",
                (seed_base["country_id"],),
            )

    def test_zero_po_line_quantity_rejected(self, cur, seed_base):
        cur.execute(
            "INSERT INTO purchase_orders (po_number, supplier_id, warehouse_id) VALUES ('PO-BAD',%s,%s) RETURNING po_id",
            (seed_base["supplier_id"], seed_base["wh1_id"]),
        )
        po_id = cur.fetchone()["po_id"]
        with pytest.raises(psycopg2.errors.CheckViolation):
            cur.execute(
                "INSERT INTO po_line_items (po_id, product_id, quantity, unit_price) VALUES (%s,%s,0,1.00)",
                (po_id, seed_base["prod1_id"]),
            )

    def test_negative_lead_time_rejected(self, cur, seed_base):
        with pytest.raises(psycopg2.errors.CheckViolation):
            cur.execute(
                "INSERT INTO suppliers (name, country_id, lead_time_days) VALUES ('Bad Supplier',%s,-3)",
                (seed_base["country_id"],),
            )

    def test_negative_inventory_quantity_rejected(self, cur, seed_base):
        with pytest.raises(psycopg2.errors.CheckViolation):
            cur.execute(
                "INSERT INTO inventory (warehouse_id, product_id, quantity) VALUES (%s,%s,-1)",
                (seed_base["wh1_id"], seed_base["prod1_id"]),
            )


class TestUniqueConstraints:
    def test_duplicate_sku_rejected(self, cur, seed_base):
        with pytest.raises(psycopg2.errors.UniqueViolation):
            cur.execute(
                "INSERT INTO products (sku, name, category_id, unit_cost) VALUES ('SKU-001','Duplicate',%s,1.00)",
                (seed_base["cat_id"],),
            )

    def test_duplicate_country_code_rejected(self, cur, seed_base):
        with pytest.raises(psycopg2.errors.UniqueViolation):
            cur.execute("INSERT INTO countries (code, name, currency_code) VALUES ('DE','Deutschland','EUR')")

    def test_duplicate_inventory_slot_rejected(self, cur, seed_base):
        cur.execute(
            "INSERT INTO inventory (warehouse_id, product_id, quantity) VALUES (%s,%s,10)",
            (seed_base["wh1_id"], seed_base["prod1_id"]),
        )
        with pytest.raises(psycopg2.errors.UniqueViolation):
            cur.execute(
                "INSERT INTO inventory (warehouse_id, product_id, quantity) VALUES (%s,%s,20)",
                (seed_base["wh1_id"], seed_base["prod1_id"]),
            )

    def test_duplicate_supplier_product_rejected(self, cur, seed_base):
        cur.execute(
            "INSERT INTO supplier_products (supplier_id, product_id, price) VALUES (%s,%s,1.00)",
            (seed_base["supplier_id"], seed_base["prod1_id"]),
        )
        with pytest.raises(psycopg2.errors.UniqueViolation):
            cur.execute(
                "INSERT INTO supplier_products (supplier_id, product_id, price) VALUES (%s,%s,2.00)",
                (seed_base["supplier_id"], seed_base["prod1_id"]),
            )


class TestForeignKeyIntegrity:
    def test_product_with_invalid_category_rejected(self, cur, seed_base):
        with pytest.raises(psycopg2.errors.ForeignKeyViolation):
            cur.execute(
                "INSERT INTO products (sku, name, category_id, unit_cost) VALUES ('FK-BAD','Bad',99999,1.00)"
            )

    def test_inventory_with_invalid_warehouse_rejected(self, cur, seed_base):
        with pytest.raises(psycopg2.errors.ForeignKeyViolation):
            cur.execute(
                "INSERT INTO inventory (warehouse_id, product_id, quantity) VALUES (99999,%s,10)",
                (seed_base["prod1_id"],),
            )

    def test_po_with_invalid_supplier_rejected(self, cur, seed_base):
        with pytest.raises(psycopg2.errors.ForeignKeyViolation):
            cur.execute(
                "INSERT INTO purchase_orders (po_number, supplier_id, warehouse_id) VALUES ('PO-FK',99999,%s)",
                (seed_base["wh1_id"],),
            )

    def test_cascade_delete_po_removes_lines(self, cur, seed_base):
        cur.execute(
            "INSERT INTO purchase_orders (po_number, supplier_id, warehouse_id) VALUES ('PO-CASCADE',%s,%s) RETURNING po_id",
            (seed_base["supplier_id"], seed_base["wh1_id"]),
        )
        po_id = cur.fetchone()["po_id"]
        cur.execute(
            "INSERT INTO po_line_items (po_id, product_id, quantity, unit_price) VALUES (%s,%s,10,1.00)",
            (po_id, seed_base["prod1_id"]),
        )
        cur.execute("DELETE FROM purchase_orders WHERE po_id = %s", (po_id,))
        cur.execute("SELECT COUNT(*) AS cnt FROM po_line_items WHERE po_id = %s", (po_id,))
        assert cur.fetchone()["cnt"] == 0


class TestEnumValidation:
    def test_invalid_movement_type_rejected(self, cur, seed_base):
        with pytest.raises(psycopg2.errors.InvalidTextRepresentation):
            cur.execute(
                "INSERT INTO stock_movements (product_id, warehouse_id, movement_type, quantity) VALUES (%s,%s,'INVALID',10)",
                (seed_base["prod1_id"], seed_base["wh1_id"]),
            )

    def test_invalid_po_status_rejected(self, cur, seed_base):
        with pytest.raises(psycopg2.errors.InvalidTextRepresentation):
            cur.execute(
                "INSERT INTO purchase_orders (po_number, supplier_id, warehouse_id, status) VALUES ('PO-ENUM',%s,%s,'fake_status')",
                (seed_base["supplier_id"], seed_base["wh1_id"]),
            )
