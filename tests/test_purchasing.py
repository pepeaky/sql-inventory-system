import pytest
from src.purchasing import create_po, receive_po, cancel_po, get_po_summary
from src.inventory import get_stock, upsert_stock


class TestCreatePO:
    def test_creates_with_lines(self, cur, seed_base):
        lines = [
            {"product_id": seed_base["prod1_id"], "quantity": 500, "unit_price": 1.50},
            {"product_id": seed_base["prod2_id"], "quantity": 200, "unit_price": 2.75},
        ]
        po = create_po(cur, "PO-2026-001", seed_base["supplier_id"], seed_base["wh1_id"], lines)
        assert po["po_number"] == "PO-2026-001"
        assert po["status"] == "submitted"

    def test_duplicate_po_number_fails(self, cur, seed_base):
        lines = [{"product_id": seed_base["prod1_id"], "quantity": 100, "unit_price": 1.00}]
        create_po(cur, "PO-DUP", seed_base["supplier_id"], seed_base["wh1_id"], lines)
        with pytest.raises(Exception):
            create_po(cur, "PO-DUP", seed_base["supplier_id"], seed_base["wh1_id"], lines)


class TestReceivePO:
    def test_receive_updates_inventory(self, cur, seed_base):
        upsert_stock(cur, seed_base["wh1_id"], seed_base["prod1_id"], 100)
        lines = [{"product_id": seed_base["prod1_id"], "quantity": 250, "unit_price": 1.50}]
        po = create_po(cur, "PO-RECV-001", seed_base["supplier_id"], seed_base["wh1_id"], lines)

        result = receive_po(cur, po["po_id"])
        assert result["status"] == "received"

        stock = get_stock(cur, seed_base["wh1_id"], seed_base["prod1_id"])
        assert stock["quantity"] == 350

    def test_receive_creates_movements(self, cur, seed_base):
        lines = [
            {"product_id": seed_base["prod1_id"], "quantity": 100, "unit_price": 1.50},
            {"product_id": seed_base["prod2_id"], "quantity": 50, "unit_price": 2.75},
        ]
        po = create_po(cur, "PO-RECV-002", seed_base["supplier_id"], seed_base["wh1_id"], lines)
        receive_po(cur, po["po_id"])

        cur.execute(
            "SELECT movement_type, reference_type, reference_id FROM stock_movements WHERE reference_id = %s",
            (po["po_id"],),
        )
        movements = cur.fetchall()
        assert len(movements) == 2
        assert all(m["movement_type"] == "IN" for m in movements)
        assert all(m["reference_type"] == "PO" for m in movements)

    def test_receive_already_received_fails(self, cur, seed_base):
        lines = [{"product_id": seed_base["prod1_id"], "quantity": 100, "unit_price": 1.50}]
        po = create_po(cur, "PO-RECV-003", seed_base["supplier_id"], seed_base["wh1_id"], lines)
        receive_po(cur, po["po_id"])

        with pytest.raises(ValueError, match="cannot be received"):
            receive_po(cur, po["po_id"])

    def test_receive_nonexistent_po_fails(self, cur, seed_base):
        with pytest.raises(ValueError, match="not found"):
            receive_po(cur, 99999)


class TestCancelPO:
    def test_cancel_submitted(self, cur, seed_base):
        lines = [{"product_id": seed_base["prod1_id"], "quantity": 100, "unit_price": 1.00}]
        po = create_po(cur, "PO-CXL-001", seed_base["supplier_id"], seed_base["wh1_id"], lines)
        result = cancel_po(cur, po["po_id"])
        assert result["status"] == "cancelled"

    def test_cancel_received_fails(self, cur, seed_base):
        lines = [{"product_id": seed_base["prod1_id"], "quantity": 100, "unit_price": 1.00}]
        po = create_po(cur, "PO-CXL-002", seed_base["supplier_id"], seed_base["wh1_id"], lines)
        receive_po(cur, po["po_id"])

        with pytest.raises(ValueError, match="cannot be cancelled"):
            cancel_po(cur, po["po_id"])


class TestPOSummary:
    def test_summary_includes_totals(self, cur, seed_base):
        lines = [
            {"product_id": seed_base["prod1_id"], "quantity": 100, "unit_price": 2.00},
            {"product_id": seed_base["prod2_id"], "quantity": 50, "unit_price": 4.00},
        ]
        po = create_po(cur, "PO-SUM-001", seed_base["supplier_id"], seed_base["wh1_id"], lines)
        summary = get_po_summary(cur, po["po_id"])
        assert summary["line_count"] == 2
        assert float(summary["total_value"]) == 400.00
