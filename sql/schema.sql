BEGIN;

-- ============================================================
-- GLOBAL SUPPLY CHAIN INVENTORY — NORMALIZED SCHEMA (3NF)
-- ============================================================

CREATE TABLE countries (
    country_id   SERIAL PRIMARY KEY,
    code         CHAR(2) NOT NULL UNIQUE,
    name         VARCHAR(100) NOT NULL,
    currency_code CHAR(3) NOT NULL
);

CREATE TABLE suppliers (
    supplier_id    SERIAL PRIMARY KEY,
    name           VARCHAR(200) NOT NULL,
    country_id     INT NOT NULL REFERENCES countries(country_id),
    contact_email  VARCHAR(254),
    lead_time_days INT NOT NULL DEFAULT 0 CHECK (lead_time_days >= 0)
);

CREATE TABLE warehouses (
    warehouse_id SERIAL PRIMARY KEY,
    name         VARCHAR(200) NOT NULL,
    country_id   INT NOT NULL REFERENCES countries(country_id),
    city         VARCHAR(100) NOT NULL,
    capacity_m3  NUMERIC(12,2) NOT NULL CHECK (capacity_m3 > 0),
    is_active    BOOLEAN NOT NULL DEFAULT TRUE
);

CREATE TABLE categories (
    category_id SERIAL PRIMARY KEY,
    name        VARCHAR(100) NOT NULL,
    parent_id   INT REFERENCES categories(category_id)
);

CREATE TABLE products (
    product_id      SERIAL PRIMARY KEY,
    sku             VARCHAR(50) NOT NULL UNIQUE,
    name            VARCHAR(200) NOT NULL,
    category_id     INT NOT NULL REFERENCES categories(category_id),
    unit_cost       NUMERIC(10,2) NOT NULL CHECK (unit_cost >= 0),
    unit_of_measure VARCHAR(20) NOT NULL DEFAULT 'unit'
);

CREATE TABLE supplier_products (
    supplier_product_id SERIAL PRIMARY KEY,
    supplier_id         INT NOT NULL REFERENCES suppliers(supplier_id),
    product_id          INT NOT NULL REFERENCES products(product_id),
    supplier_sku        VARCHAR(50),
    price               NUMERIC(10,2) NOT NULL CHECK (price >= 0),
    is_preferred        BOOLEAN NOT NULL DEFAULT FALSE,
    UNIQUE (supplier_id, product_id)
);

CREATE TABLE inventory (
    inventory_id    SERIAL PRIMARY KEY,
    warehouse_id    INT NOT NULL REFERENCES warehouses(warehouse_id),
    product_id      INT NOT NULL REFERENCES products(product_id),
    quantity        INT NOT NULL DEFAULT 0 CHECK (quantity >= 0),
    min_threshold   INT NOT NULL DEFAULT 0 CHECK (min_threshold >= 0),
    last_counted_at TIMESTAMPTZ,
    version         INT NOT NULL DEFAULT 1,
    UNIQUE (warehouse_id, product_id)
);

CREATE TYPE po_status AS ENUM ('draft', 'submitted', 'shipped', 'received', 'cancelled');

CREATE TABLE purchase_orders (
    po_id        SERIAL PRIMARY KEY,
    po_number    VARCHAR(30) NOT NULL UNIQUE,
    supplier_id  INT NOT NULL REFERENCES suppliers(supplier_id),
    warehouse_id INT NOT NULL REFERENCES warehouses(warehouse_id),
    status       po_status NOT NULL DEFAULT 'draft',
    ordered_at   TIMESTAMPTZ,
    expected_at  TIMESTAMPTZ,
    received_at  TIMESTAMPTZ
);

CREATE TABLE po_line_items (
    line_item_id SERIAL PRIMARY KEY,
    po_id        INT NOT NULL REFERENCES purchase_orders(po_id) ON DELETE CASCADE,
    product_id   INT NOT NULL REFERENCES products(product_id),
    quantity     INT NOT NULL CHECK (quantity > 0),
    unit_price   NUMERIC(10,2) NOT NULL CHECK (unit_price >= 0)
);

CREATE TYPE movement_type AS ENUM ('IN', 'OUT', 'ADJUST', 'TRANSFER');
CREATE TYPE reference_type AS ENUM ('PO', 'MANUAL', 'TRANSFER');

CREATE TABLE stock_movements (
    movement_id    SERIAL PRIMARY KEY,
    product_id     INT NOT NULL REFERENCES products(product_id),
    warehouse_id   INT NOT NULL REFERENCES warehouses(warehouse_id),
    movement_type  movement_type NOT NULL,
    quantity       INT NOT NULL,
    reference_id   INT,
    reference_type reference_type,
    created_at     TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- ============================================================
-- INDEXES
-- ============================================================

CREATE INDEX idx_inventory_warehouse ON inventory(warehouse_id);
CREATE INDEX idx_inventory_product   ON inventory(product_id);
CREATE INDEX idx_inventory_low_stock ON inventory(warehouse_id, product_id)
    WHERE quantity <= min_threshold;

CREATE INDEX idx_movements_product   ON stock_movements(product_id);
CREATE INDEX idx_movements_warehouse ON stock_movements(warehouse_id);
CREATE INDEX idx_movements_created   ON stock_movements(created_at);
CREATE INDEX idx_movements_reference ON stock_movements(reference_type, reference_id)
    WHERE reference_id IS NOT NULL;

CREATE INDEX idx_po_supplier ON purchase_orders(supplier_id);
CREATE INDEX idx_po_status   ON purchase_orders(status);

CREATE INDEX idx_categories_parent ON categories(parent_id);

COMMIT;
