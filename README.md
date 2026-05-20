# SQL Inventory System

A normalized relational database for global supply chain inventory management, built to demonstrate **3NF schema design**, **ACID transaction guarantees**, and **optimistic concurrency control**.

---

## Architecture

```
┌──────────────┐     ┌──────────────┐     ┌──────────────┐
│   Suppliers   │────▶│  Purchase    │────▶│  PO Line     │
│              │     │  Orders      │     │  Items       │
└──────┬───────┘     └──────┬───────┘     └──────────────┘
       │                    │
       │                    ▼
       │             ┌──────────────┐     ┌──────────────┐
       │             │   Stock      │────▶│  Inventory   │
       │             │  Movements   │     │  (live qty)  │
       │             └──────────────┘     └──────┬───────┘
       │                                         │
       ▼                                         ▼
┌──────────────┐     ┌──────────────┐     ┌──────────────┐
│  Supplier    │     │  Warehouses  │     │  Products    │
│  Products    │     │              │     │              │
│  (N:M link)  │     └──────┬───────┘     └──────┬───────┘
└──────────────┘            │                    │
                            ▼                    ▼
                     ┌──────────────┐     ┌──────────────┐
                     │  Countries   │     │  Categories  │
                     │              │     │  (tree)      │
                     └──────────────┘     └──────────────┘
```

## Entity-Relationship Diagram

```
                            ┌─────────────────────────────────┐
                            │           countries              │
                            │─────────────────────────────────│
                            │ PK country_id    SERIAL          │
                            │    code           CHAR(2) UQ     │
                            │    name           VARCHAR(100)   │
                            │    currency_code  CHAR(3)        │
                            └──────────┬──────────┬───────────┘
                                       │          │
                          ┌────────────┘          └────────────┐
                          │ 1:N                           1:N  │
                          ▼                                    ▼
          ┌───────────────────────────┐      ┌───────────────────────────┐
          │        suppliers           │      │       warehouses           │
          │───────────────────────────│      │───────────────────────────│
          │ PK supplier_id   SERIAL    │      │ PK warehouse_id  SERIAL    │
          │    name          VARCHAR    │      │    name          VARCHAR    │
          │ FK country_id              │      │ FK country_id              │
          │    contact_email           │      │    city          VARCHAR    │
          │    lead_time_days INT ≥0   │      │    capacity_m3   NUM >0    │
          └─────┬──────────┬──────────┘      │    is_active     BOOL      │
                │          │                  └──────┬───────────┬─────────┘
                │          │                         │           │
                │          │                         │           │
   ┌────────────┘    ┌─────┘              ┌──────────┘     ┌─────┘
   │                 │                    │                │
   │ 1:N             │ N:M               │ 1:N            │ 1:N
   ▼                 ▼                    ▼                ▼
┌──────────────┐ ┌────────────────┐ ┌───────────────┐ ┌──────────────────┐
│ purchase_    │ │ supplier_      │ │  inventory     │ │ stock_movements   │
│ orders       │ │ products       │ │───────────────│ │──────────────────│
│──────────────│ │────────────────│ │ PK inv_id     │ │ PK movement_id    │
│ PK po_id     │ │ PK sp_id       │ │ FK warehouse  │ │ FK product_id     │
│ po_number UQ │ │ FK supplier_id │ │ FK product    │ │ FK warehouse_id   │
│ FK supplier  │ │ FK product_id  │ │ quantity ≥0   │ │ type ENUM         │
│ FK warehouse │ │ supplier_sku   │ │ min_threshold │ │ quantity (signed) │
│ status ENUM  │ │ price ≥0       │ │ version (OCC) │ │ ref_id / ref_type │
│ ordered_at   │ │ is_preferred   │ │ UQ(wh,prod)   │ │ created_at        │
│ received_at  │ │ UQ(sup,prod)   │ └───────────────┘ └──────────────────┘
└──────┬───────┘ └────────────────┘
       │ 1:N                          ┌──────────────────┐
       ▼                              │    categories     │
┌──────────────┐                      │──────────────────│
│ po_line_     │                      │ PK category_id    │
│ items        │                      │    name           │
│──────────────│                      │ FK parent_id ─────│──► self
│ PK line_id   │                      └──────────┬───────┘
│ FK po_id  ◄──│── ON DELETE CASCADE             │ 1:N
│ FK product   │                                  ▼
│ quantity >0  │                        ┌──────────────────┐
│ unit_price   │                        │    products       │
└──────────────┘                        │──────────────────│
                                        │ PK product_id     │
                                        │    sku     UQ     │
                                        │    name           │
                                        │ FK category_id    │
                                        │    unit_cost  ≥0  │
                                        │    unit_of_measure│
                                        └──────────────────┘
```

## ACID Guarantees

| Operation | Mechanism | What it protects |
|---|---|---|
| Stock adjustment | `SELECT … FOR UPDATE` + optimistic locking (`version` column) | No lost updates under concurrent writes |
| PO receive | Single transaction: status update → movement inserts → inventory upserts | Partial receives are impossible |
| Warehouse transfer | Atomic decrement + increment in one transaction | Stock is never "in transit" / double-counted |
| Inventory floor | `CHECK (quantity >= 0)` at DB level | Negative stock is structurally impossible |

## Tech Stack

| Layer | Technology |
|---|---|
| Database | PostgreSQL 16 |
| Driver | psycopg2 (connection pooling) |
| Config | python-dotenv (.env) |
| Testing | pytest + testcontainers (real Postgres in Docker) |

## Quick Start

```bash
# clone & setup
git clone <repo-url> && cd 01-sql-inventory-system
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env   # edit with your Postgres credentials

# initialize
python main.py init --seed

# operations
python main.py stock --warehouse 1 --product 1
python main.py adjust --warehouse 1 --product 1 --delta -50
python main.py transfer --product 1 --from-wh 1 --to-wh 2 --quantity 100
python main.py low-stock
python main.py create-po --po-number PO-2026-001 --supplier 1 --warehouse 1 \
    --lines '[{"product_id":1,"quantity":500,"unit_price":1.50}]'
python main.py receive-po --po-id 1
```

## Testing

Requires Docker running for testcontainers:

```bash
pytest -v
```

**30 tests** covering:
- Inventory operations (upsert, adjust, transfer, low-stock alerts)
- Purchase order lifecycle (create → receive → cancel)
- Dirty data rejection (CHECK, UNIQUE, FK, ENUM constraints)

## Project Structure

```
├── main.py              # CLI entry point
├── sql/
│   └── schema.sql       # DDL — 9 tables, ENUMs, partial indexes
├── src/
│   ├── config.py        # .env loader
│   ├── db.py            # Connection pool + transaction context manager
│   ├── inventory.py     # Stock operations with optimistic locking
│   ├── purchasing.py    # PO lifecycle with ACID guarantees
│   └── seed.py          # Demo data (5 countries, 3 warehouses, 6 products)
└── tests/
    ├── conftest.py      # Testcontainers Postgres fixtures
    ├── test_inventory.py
    ├── test_purchasing.py
    └── test_dirty_data.py
```

## Design Decisions

- **Application-level locking over DB triggers** — keeps business logic testable and explicit.
- **Append-only stock_movements** — full audit trail; inventory quantity is the materialized state, movements are the source of truth.
- **Polymorphic reference on movements** — `reference_type` + `reference_id` links back to POs or transfers without coupling tables.
- **Partial index on low stock** — `WHERE quantity <= min_threshold` makes alert queries fast without indexing every row.
