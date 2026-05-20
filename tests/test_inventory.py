import pytest
from src.inventory import upsert_stock, adjust_stock, get_stock, transfer_stock, get_low_stock


class TestUpsertStock:
    def test_insert_new_record(self, cur, seed_base):
        result = upsert_stock(cur, seed_base["wh1_id"], seed_base["prod1_id"], 100, min_threshold=20)
        assert result["quantity"] == 100
        assert result["version"] == 1

    def test_upsert_adds_to_existing(self, cur, seed_base):
        upsert_stock(cur, seed_base["wh1_id"], seed_base["prod1_id"], 100)
        result = upsert_stock(cur, seed_base["wh1_id"], seed_base["prod1_id"], 50)
        assert result["quantity"] == 150
        assert result["version"] == 2


class TestAdjustStock:
    def test_positive_adjustment(self, cur, seed_base):
        upsert_stock(cur, seed_base["wh1_id"], seed_base["prod1_id"], 100)
        result = adjust_stock(cur, seed_base["wh1_id"], seed_base["prod1_id"], 25)
        assert result["quantity"] == 125

    def test_negative_adjustment(self, cur, seed_base):
        upsert_stock(cur, seed_base["wh1_id"], seed_base["prod1_id"], 100)
        result = adjust_stock(cur, seed_base["wh1_id"], seed_base["prod1_id"], -30)
        assert result["quantity"] == 70

    def test_negative_adjustment_insufficient_stock(self, cur, seed_base):
        upsert_stock(cur, seed_base["wh1_id"], seed_base["prod1_id"], 10)
        with pytest.raises(ValueError, match="Insufficient stock"):
            adjust_stock(cur, seed_base["wh1_id"], seed_base["prod1_id"], -20)

    def test_adjust_nonexistent_record(self, cur, seed_base):
        with pytest.raises(ValueError, match="No inventory record"):
            adjust_stock(cur, seed_base["wh1_id"], seed_base["prod1_id"], 10)

    def test_version_increments(self, cur, seed_base):
        upsert_stock(cur, seed_base["wh1_id"], seed_base["prod1_id"], 100)
        r1 = adjust_stock(cur, seed_base["wh1_id"], seed_base["prod1_id"], 10)
        r2 = adjust_stock(cur, seed_base["wh1_id"], seed_base["prod1_id"], -5)
        assert r2["version"] == r1["version"] + 1

    def test_creates_stock_movement(self, cur, seed_base):
        upsert_stock(cur, seed_base["wh1_id"], seed_base["prod1_id"], 100)
        adjust_stock(cur, seed_base["wh1_id"], seed_base["prod1_id"], -10)

        cur.execute(
            "SELECT movement_type, quantity, reference_type FROM stock_movements WHERE product_id = %s ORDER BY movement_id",
            (seed_base["prod1_id"],),
        )
        movements = cur.fetchall()
        assert len(movements) == 1
        assert movements[0]["movement_type"] == "OUT"
        assert movements[0]["quantity"] == -10


class TestTransferStock:
    def test_successful_transfer(self, cur, seed_base):
        upsert_stock(cur, seed_base["wh1_id"], seed_base["prod1_id"], 200)
        upsert_stock(cur, seed_base["wh2_id"], seed_base["prod1_id"], 50)

        transfer_stock(cur, seed_base["prod1_id"], seed_base["wh1_id"], seed_base["wh2_id"], 75)

        src = get_stock(cur, seed_base["wh1_id"], seed_base["prod1_id"])
        dst = get_stock(cur, seed_base["wh2_id"], seed_base["prod1_id"])
        assert src["quantity"] == 125
        assert dst["quantity"] == 125

    def test_transfer_insufficient_stock(self, cur, seed_base):
        upsert_stock(cur, seed_base["wh1_id"], seed_base["prod1_id"], 30)
        with pytest.raises(ValueError, match="Insufficient stock"):
            transfer_stock(cur, seed_base["prod1_id"], seed_base["wh1_id"], seed_base["wh2_id"], 50)

    def test_transfer_zero_quantity(self, cur, seed_base):
        with pytest.raises(ValueError, match="positive"):
            transfer_stock(cur, seed_base["prod1_id"], seed_base["wh1_id"], seed_base["wh2_id"], 0)

    def test_transfer_creates_movements(self, cur, seed_base):
        upsert_stock(cur, seed_base["wh1_id"], seed_base["prod1_id"], 200)

        transfer_stock(cur, seed_base["prod1_id"], seed_base["wh1_id"], seed_base["wh2_id"], 50)

        cur.execute(
            "SELECT movement_type, quantity, reference_type FROM stock_movements ORDER BY movement_id"
        )
        movements = cur.fetchall()
        out = [m for m in movements if m["movement_type"] == "OUT"]
        ins = [m for m in movements if m["movement_type"] == "IN"]
        assert len(out) == 1
        assert len(ins) == 1
        assert out[0]["reference_type"] == "TRANSFER"
        assert ins[0]["reference_type"] == "TRANSFER"


class TestLowStock:
    def test_detects_below_threshold(self, cur, seed_base):
        upsert_stock(cur, seed_base["wh1_id"], seed_base["prod1_id"], 5, min_threshold=50)
        rows = get_low_stock(cur)
        assert len(rows) == 1
        assert rows[0]["sku"] == "SKU-001"

    def test_ignores_above_threshold(self, cur, seed_base):
        upsert_stock(cur, seed_base["wh1_id"], seed_base["prod1_id"], 200, min_threshold=50)
        rows = get_low_stock(cur)
        assert len(rows) == 0

    def test_filters_by_warehouse(self, cur, seed_base):
        upsert_stock(cur, seed_base["wh1_id"], seed_base["prod1_id"], 5, min_threshold=50)
        upsert_stock(cur, seed_base["wh2_id"], seed_base["prod2_id"], 3, min_threshold=50)

        rows = get_low_stock(cur, warehouse_id=seed_base["wh1_id"])
        assert len(rows) == 1
        assert rows[0]["sku"] == "SKU-001"
