"""CLI entry point for the SQL Inventory System."""

import argparse
import sys
from pathlib import Path

from src.db import transaction, execute_schema, close_pool


def cmd_init(args):
    schema_path = Path(__file__).parent / "sql" / "schema.sql"
    execute_schema(str(schema_path))
    print("Schema created successfully.")

    if args.seed:
        from src.seed import seed
        with transaction() as (conn, cur):
            seed(cur)
        print("Demo data seeded.")


def cmd_stock(args):
    from src.inventory import get_stock
    with transaction() as (conn, cur):
        row = get_stock(cur, args.warehouse, args.product)
        if row:
            print(f"Quantity: {row['quantity']}  |  Threshold: {row['min_threshold']}  |  Version: {row['version']}")
        else:
            print("No inventory record found.")


def cmd_adjust(args):
    from src.inventory import adjust_stock
    with transaction() as (conn, cur):
        result = adjust_stock(cur, args.warehouse, args.product, args.delta)
        print(f"Updated → Quantity: {result['quantity']}  |  Version: {result['version']}")


def cmd_transfer(args):
    from src.inventory import transfer_stock
    with transaction() as (conn, cur):
        transfer_stock(cur, args.product, args.from_wh, args.to_wh, args.quantity)
        print(f"Transferred {args.quantity} units of product {args.product}: warehouse {args.from_wh} → {args.to_wh}")


def cmd_low_stock(args):
    from src.inventory import get_low_stock
    with transaction() as (conn, cur):
        rows = get_low_stock(cur, args.warehouse)
        if not rows:
            print("No low-stock items.")
            return
        print(f"{'Warehouse':<20} {'SKU':<18} {'Product':<30} {'Qty':>6} {'Threshold':>10}")
        print("-" * 86)
        for r in rows:
            print(f"{r['warehouse']:<20} {r['sku']:<18} {r['product']:<30} {r['quantity']:>6} {r['min_threshold']:>10}")


def cmd_create_po(args):
    from src.purchasing import create_po
    import json
    lines = json.loads(args.lines)
    with transaction() as (conn, cur):
        po = create_po(cur, args.po_number, args.supplier, args.warehouse, lines)
        print(f"PO created: {po['po_number']} (id={po['po_id']}, status={po['status']})")


def cmd_receive_po(args):
    from src.purchasing import receive_po
    with transaction() as (conn, cur):
        po = receive_po(cur, args.po_id)
        print(f"PO {po['po_id']} received at {po['received_at']}")


def main():
    parser = argparse.ArgumentParser(description="SQL Inventory System — Global Supply Chain")
    sub = parser.add_subparsers(dest="command", required=True)

    p_init = sub.add_parser("init", help="Create schema and optionally seed data")
    p_init.add_argument("--seed", action="store_true", help="Insert demo data after schema creation")

    p_stock = sub.add_parser("stock", help="Check stock level")
    p_stock.add_argument("--warehouse", type=int, required=True)
    p_stock.add_argument("--product", type=int, required=True)

    p_adjust = sub.add_parser("adjust", help="Adjust stock quantity")
    p_adjust.add_argument("--warehouse", type=int, required=True)
    p_adjust.add_argument("--product", type=int, required=True)
    p_adjust.add_argument("--delta", type=int, required=True)

    p_transfer = sub.add_parser("transfer", help="Transfer stock between warehouses")
    p_transfer.add_argument("--product", type=int, required=True)
    p_transfer.add_argument("--from-wh", type=int, required=True)
    p_transfer.add_argument("--to-wh", type=int, required=True)
    p_transfer.add_argument("--quantity", type=int, required=True)

    p_low = sub.add_parser("low-stock", help="Show items below minimum threshold")
    p_low.add_argument("--warehouse", type=int, default=None)

    p_po = sub.add_parser("create-po", help="Create a purchase order")
    p_po.add_argument("--po-number", required=True)
    p_po.add_argument("--supplier", type=int, required=True)
    p_po.add_argument("--warehouse", type=int, required=True)
    p_po.add_argument("--lines", required=True, help='JSON array: [{"product_id":1,"quantity":100,"unit_price":0.12}]')

    p_recv = sub.add_parser("receive-po", help="Receive a purchase order into inventory")
    p_recv.add_argument("--po-id", type=int, required=True)

    args = parser.parse_args()

    commands = {
        "init": cmd_init, "stock": cmd_stock, "adjust": cmd_adjust,
        "transfer": cmd_transfer, "low-stock": cmd_low_stock,
        "create-po": cmd_create_po, "receive-po": cmd_receive_po,
    }

    try:
        commands[args.command](args)
    except (ValueError, RuntimeError) as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)
    finally:
        close_pool()


if __name__ == "__main__":
    main()
