"""Purchase order lifecycle with ACID transaction support."""

from __future__ import annotations
from datetime import datetime, timezone


def create_po(cur, po_number: str, supplier_id: int, warehouse_id: int, lines: list[dict]) -> dict:
    """Create a purchase order with line items.

    lines: [{"product_id": int, "quantity": int, "unit_price": Decimal}, ...]
    """
    cur.execute(
        """
        INSERT INTO purchase_orders (po_number, supplier_id, warehouse_id, status, ordered_at)
        VALUES (%s, %s, %s, 'submitted', NOW())
        RETURNING po_id, po_number, status
        """,
        (po_number, supplier_id, warehouse_id),
    )
    po = cur.fetchone()

    for line in lines:
        cur.execute(
            """
            INSERT INTO po_line_items (po_id, product_id, quantity, unit_price)
            VALUES (%s, %s, %s, %s)
            """,
            (po["po_id"], line["product_id"], line["quantity"], line["unit_price"]),
        )
    return po


def receive_po(cur, po_id: int) -> dict:
    """Receive a PO: update status, create stock movements, update inventory.

    This is the critical ACID operation — either everything commits or nothing does.
    """
    cur.execute(
        """
        SELECT po_id, supplier_id, warehouse_id, status
        FROM purchase_orders
        WHERE po_id = %s
        FOR UPDATE
        """,
        (po_id,),
    )
    po = cur.fetchone()
    if po is None:
        raise ValueError(f"PO {po_id} not found")
    if po["status"] != "submitted":
        raise ValueError(f"PO {po_id} cannot be received — status is '{po['status']}'")

    cur.execute(
        """
        UPDATE purchase_orders
        SET status = 'received', received_at = NOW()
        WHERE po_id = %s
        RETURNING po_id, status, received_at
        """,
        (po_id,),
    )
    updated_po = cur.fetchone()

    cur.execute("SELECT product_id, quantity, unit_price FROM po_line_items WHERE po_id = %s", (po_id,))
    lines = cur.fetchall()

    from src.inventory import upsert_stock

    for line in lines:
        upsert_stock(cur, po["warehouse_id"], line["product_id"], line["quantity"])
        cur.execute(
            """
            INSERT INTO stock_movements
                (product_id, warehouse_id, movement_type, quantity, reference_id, reference_type)
            VALUES (%s, %s, 'IN', %s, %s, 'PO')
            """,
            (line["product_id"], po["warehouse_id"], line["quantity"], po_id),
        )

    return updated_po


def cancel_po(cur, po_id: int) -> dict:
    cur.execute(
        """
        UPDATE purchase_orders
        SET status = 'cancelled'
        WHERE po_id = %s AND status IN ('draft', 'submitted')
        RETURNING po_id, status
        """,
        (po_id,),
    )
    result = cur.fetchone()
    if result is None:
        raise ValueError(f"PO {po_id} cannot be cancelled")
    return result


def get_po_summary(cur, po_id: int) -> dict:
    cur.execute(
        """
        SELECT po.po_id, po.po_number, po.status, s.name AS supplier,
               w.name AS warehouse, po.ordered_at, po.received_at,
               COUNT(li.line_item_id) AS line_count,
               SUM(li.quantity * li.unit_price) AS total_value
        FROM purchase_orders po
        JOIN suppliers s  ON s.supplier_id  = po.supplier_id
        JOIN warehouses w ON w.warehouse_id = po.warehouse_id
        LEFT JOIN po_line_items li ON li.po_id = po.po_id
        WHERE po.po_id = %s
        GROUP BY po.po_id, po.po_number, po.status, s.name, w.name, po.ordered_at, po.received_at
        """,
        (po_id,),
    )
    return cur.fetchone()
