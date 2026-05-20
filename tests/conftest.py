import os
from pathlib import Path

import psycopg2
from psycopg2 import extras
import pytest
from testcontainers.postgres import PostgresContainer

SCHEMA_PATH = Path(__file__).resolve().parent.parent / "sql" / "schema.sql"

_TRUNCATE_SQL = """
DO $$
DECLARE r RECORD;
BEGIN
    FOR r IN
        SELECT tablename FROM pg_tables WHERE schemaname = 'public'
    LOOP
        EXECUTE 'TRUNCATE TABLE ' || quote_ident(r.tablename) || ' CASCADE';
    END LOOP;
END $$;
"""


@pytest.fixture(scope="session")
def pg_container():
    with PostgresContainer("postgres:16-alpine") as pg:
        yield pg


@pytest.fixture(scope="session")
def db_url(pg_container):
    return pg_container.get_connection_url().replace("+psycopg2", "")


@pytest.fixture(scope="session")
def _init_schema(pg_container):
    conn = psycopg2.connect(
        host=pg_container.get_container_host_ip(),
        port=pg_container.get_exposed_port(5432),
        user=pg_container.username,
        password=pg_container.password,
        dbname=pg_container.dbname,
    )
    conn.autocommit = True
    with conn.cursor() as cur:
        cur.execute(SCHEMA_PATH.read_text())
    conn.close()


@pytest.fixture()
def conn(pg_container, _init_schema):
    c = psycopg2.connect(
        host=pg_container.get_container_host_ip(),
        port=pg_container.get_exposed_port(5432),
        user=pg_container.username,
        password=pg_container.password,
        dbname=pg_container.dbname,
    )
    c.autocommit = False
    yield c
    c.rollback()
    c.autocommit = True
    with c.cursor() as cur:
        cur.execute(_TRUNCATE_SQL)
    c.close()


@pytest.fixture()
def cur(conn):
    c = conn.cursor(cursor_factory=extras.RealDictCursor)
    yield c
    c.close()


@pytest.fixture()
def seed_base(cur):
    """Insert minimal reference data needed by most tests."""
    cur.execute("INSERT INTO countries (code, name, currency_code) VALUES ('DE','Germany','EUR') RETURNING country_id")
    country_id = cur.fetchone()["country_id"]

    cur.execute(
        "INSERT INTO suppliers (name, country_id, contact_email, lead_time_days) VALUES ('TestSupplier',%s,'test@test.com',5) RETURNING supplier_id",
        (country_id,),
    )
    supplier_id = cur.fetchone()["supplier_id"]

    cur.execute(
        "INSERT INTO warehouses (name, country_id, city, capacity_m3) VALUES ('WH-Alpha',%s,'Frankfurt',10000) RETURNING warehouse_id",
        (country_id,),
    )
    wh1_id = cur.fetchone()["warehouse_id"]

    cur.execute(
        "INSERT INTO warehouses (name, country_id, city, capacity_m3) VALUES ('WH-Beta',%s,'Berlin',8000) RETURNING warehouse_id",
        (country_id,),
    )
    wh2_id = cur.fetchone()["warehouse_id"]

    cur.execute("INSERT INTO categories (name) VALUES ('Electronics') RETURNING category_id")
    cat_id = cur.fetchone()["category_id"]

    cur.execute(
        "INSERT INTO products (sku, name, category_id, unit_cost) VALUES ('SKU-001','Widget A',%s,1.50) RETURNING product_id",
        (cat_id,),
    )
    prod1_id = cur.fetchone()["product_id"]

    cur.execute(
        "INSERT INTO products (sku, name, category_id, unit_cost) VALUES ('SKU-002','Widget B',%s,2.75) RETURNING product_id",
        (cat_id,),
    )
    prod2_id = cur.fetchone()["product_id"]

    return {
        "country_id": country_id,
        "supplier_id": supplier_id,
        "wh1_id": wh1_id,
        "wh2_id": wh2_id,
        "cat_id": cat_id,
        "prod1_id": prod1_id,
        "prod2_id": prod2_id,
    }
