"""Seed the database with realistic demo data."""


def seed(cur) -> None:
    cur.execute(
        """
        INSERT INTO countries (code, name, currency_code) VALUES
            ('IT', 'Italy',         'EUR'),
            ('DE', 'Germany',       'EUR'),
            ('US', 'United States', 'USD'),
            ('CN', 'China',         'CNY'),
            ('JP', 'Japan',         'JPY')
        ON CONFLICT (code) DO NOTHING
        """
    )

    cur.execute(
        """
        INSERT INTO suppliers (name, country_id, contact_email, lead_time_days) VALUES
            ('Milano Components SRL',  (SELECT country_id FROM countries WHERE code='IT'), 'supply@milanocomp.it',   7),
            ('Shenzhen Electronics Co', (SELECT country_id FROM countries WHERE code='CN'), 'sales@szelectronics.cn', 21),
            ('Berlin Industrial GmbH',  (SELECT country_id FROM countries WHERE code='DE'), 'orders@berlinindustrial.de', 10)
        ON CONFLICT DO NOTHING
        """
    )

    cur.execute(
        """
        INSERT INTO warehouses (name, country_id, city, capacity_m3) VALUES
            ('EU Central Hub',   (SELECT country_id FROM countries WHERE code='DE'), 'Frankfurt', 50000.00),
            ('US East Coast',    (SELECT country_id FROM countries WHERE code='US'), 'Newark',    35000.00),
            ('Asia Distribution',(SELECT country_id FROM countries WHERE code='CN'), 'Shanghai',  60000.00)
        ON CONFLICT DO NOTHING
        """
    )

    cur.execute(
        """
        INSERT INTO categories (name, parent_id) VALUES
            ('Electronics', NULL),
            ('Mechanical',  NULL),
            ('Raw Materials', NULL)
        ON CONFLICT DO NOTHING
        """
    )

    cur.execute("SELECT category_id FROM categories WHERE name = 'Electronics' LIMIT 1")
    elec_id = cur.fetchone()["category_id"]
    cur.execute("SELECT category_id FROM categories WHERE name = 'Mechanical' LIMIT 1")
    mech_id = cur.fetchone()["category_id"]

    cur.execute(
        """
        INSERT INTO categories (name, parent_id) VALUES
            ('Capacitors',  %s),
            ('Resistors',   %s),
            ('Bearings',    %s)
        ON CONFLICT DO NOTHING
        """,
        (elec_id, elec_id, mech_id),
    )

    cur.execute("SELECT category_id FROM categories WHERE name = 'Capacitors' LIMIT 1")
    cap_id = cur.fetchone()["category_id"]
    cur.execute("SELECT category_id FROM categories WHERE name = 'Resistors' LIMIT 1")
    res_id = cur.fetchone()["category_id"]
    cur.execute("SELECT category_id FROM categories WHERE name = 'Bearings' LIMIT 1")
    bear_id = cur.fetchone()["category_id"]

    cur.execute(
        """
        INSERT INTO products (sku, name, category_id, unit_cost, unit_of_measure) VALUES
            ('CAP-100UF-16V',  '100µF Electrolytic Capacitor', %s,  0.12, 'unit'),
            ('CAP-10UF-50V',   '10µF Ceramic Capacitor',       %s,  0.08, 'unit'),
            ('RES-10K-0805',   '10kΩ Resistor 0805',           %s,  0.02, 'unit'),
            ('RES-4K7-0603',   '4.7kΩ Resistor 0603',          %s,  0.02, 'unit'),
            ('BRG-6205-2RS',   '6205-2RS Ball Bearing',        %s,  3.50, 'unit'),
            ('BRG-6305-ZZ',    '6305-ZZ Ball Bearing',         %s,  4.20, 'unit')
        ON CONFLICT (sku) DO NOTHING
        """,
        (cap_id, cap_id, res_id, res_id, bear_id, bear_id),
    )

    cur.execute(
        """
        INSERT INTO inventory (warehouse_id, product_id, quantity, min_threshold)
        SELECT w.warehouse_id, p.product_id, 500, 100
        FROM warehouses w
        CROSS JOIN products p
        ON CONFLICT (warehouse_id, product_id) DO NOTHING
        """
    )
