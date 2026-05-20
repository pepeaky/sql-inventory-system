"""Inventory operations with ACID guarantees.

All public functions accept a (conn, cursor) pair from db.transaction()
so callers control the transaction boundary.
"""

from __future__ import annotations
from datetime import datetime, timezone


def get_stock(cur, warehouse_id: int, product_id: int) -> dict | None:
    cur.execute(
        """
        SELECT inventory_id, quantity, min_threshold, version
        FROM inventory
        WHERE warehouse_id = %s AND product_id = %s
        FOR UPDATE
        """,
        (warehouse_id, product_id),
    )
    return cur.fetchone()


def upsert_stock(cur, warehouse_id: int, product_id: int, quantity: int, min_threshold: int = 0) -> dict:
    cur.execute(
        """
        INSERT INTO inventory (warehouse_id, product_id, quantity, min_threshold)
        VALUES (%s, %s, %s, %s)
        ON CONFLICT (warehouse_id, product_id)
        DO UPDATE SET
            quantity = inventory.quantity + EXCLUDED.quantity,
            version  = inventory.version + 1
        RETURNING inventory_id, quantity, version
        """,
        (warehouse_id, product_id, quantity, min_threshold),
    )
    return cur.fetchone()


def adjust_stock(cur, warehouse_id: int, product_id: int, delta: int, reason: str = "MANUAL") -> dict:
    """Atomically adjust stock and record the movement.

    Uses optimistic locking via the version column.
    Raises ValueError if the resulting quantity would go negative.
    """
    row = get_stock(cur, warehouse_id, product_id)
    if row is None:
        raise ValueError(f"No inventory record for warehouse={warehouse_id}, product={product_id}")

    new_qty = row["quantity"] + delta
    if new_qty < 0:
        raise ValueError(f"Insufficient stock: have {row['quantity']}, delta {delta}")

    cur.execute(
        """
        UPDATE inventory
        SET quantity = %s, version = version + 1
        WHERE inventory_id = %s AND version = %s
        RETURNING inventory_id, quantity, version
        """,
        (new_qty, row["inventory_id"], row["version"]),
    )
    updated = cur.fetchone()
    if updated is None:
        raise RuntimeError("Optimistic lock conflict — retry the transaction")

    movement_type = "IN" if delta > 0 else "OUT" if delta < 0 else "ADJUST"
    _record_movement(cur, product_id, warehouse_id, movement_type, delta, reason)
    return updated


def transfer_stock(cur, product_id: int, from_wh: int, to_wh: int, quantity: int) -> None:
    """Transfer stock between warehouses in one atomic transaction."""
    if quantity <= 0:
        raise ValueError("Transfer quantity must be positive")

    adjust_stock(cur, from_wh, product_id, -quantity, "TRANSFER")
    upsert_stock(cur, to_wh, product_id, 0)
    adjust_stock(cur, to_wh, product_id, quantity, "TRANSFER")


def get_low_stock(cur, warehouse_id: int | None = None) -> list[dict]:
    sql = """
        SELECT i.inventory_id, w.name AS warehouse, p.sku, p.name AS product,
               i.quantity, i.min_threshold
        FROM inventory i
        JOIN warehouses w ON w.warehouse_id = i.warehouse_id
        JOIN products p   ON p.product_id   = i.product_id
        WHERE i.quantity <= i.min_threshold
    """
    params: list = []
    if warehouse_id is not None:
        sql += " AND i.warehouse_id = %s"
        params.append(warehouse_id)
    sql += " ORDER BY (i.min_threshold - i.quantity) DESC"
    cur.execute(sql, params)
    return cur.fetchall()


def _record_movement(cur, product_id, warehouse_id, movement_type, quantity, reason):
    ref_type = reason if reason in ("PO", "MANUAL", "TRANSFER") else "MANUAL"
    cur.execute(
        """
        INSERT INTO stock_movements (product_id, warehouse_id, movement_type, quantity, reference_type)
        VALUES (%s, %s, %s, %s, %s)
        """,
        (product_id, warehouse_id, movement_type, quantity, ref_type),
    )
