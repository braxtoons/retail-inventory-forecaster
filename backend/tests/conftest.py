"""Shared fixtures.

DB tests run inside a throwaway schema of the database named by TEST_DATABASE_URL
(falling back to DATABASE_URL), so they never touch the real tables and need no
CREATEDB privilege. The schema is dropped at the end of the session.
"""
import os
import uuid
from pathlib import Path

import psycopg2
import pytest
from dotenv import load_dotenv

load_dotenv()

SCHEMA_SQL = Path(__file__).resolve().parents[2] / 'database' / 'schema.sql'


def pytest_collection_modifyitems(items):
    # Tests without an explicit tier marker are treated as unit tests.
    for item in items:
        if not any(item.get_closest_marker(m) for m in ('unit', 'db', 'slow')):
            item.add_marker(pytest.mark.unit)


def _test_url():
    return os.getenv('TEST_DATABASE_URL') or os.getenv('DATABASE_URL')


@pytest.fixture(scope='session')
def db_schema():
    url = _test_url()
    if not url:
        pytest.skip('no TEST_DATABASE_URL / DATABASE_URL configured')
    schema = f'test_{uuid.uuid4().hex[:10]}'
    try:
        admin = psycopg2.connect(url)
    except psycopg2.OperationalError as exc:
        pytest.skip(f'database unavailable: {exc}')
    admin.autocommit = True
    with admin.cursor() as cur:
        cur.execute(f'CREATE SCHEMA {schema}')
    admin.close()

    # Point the app at the schema before database.py builds its pool.
    from config import Config
    sep = '&' if '?' in url else '?'
    Config.DATABASE_URL = f'{url}{sep}options=-csearch_path%3D{schema}'
    import database
    database.reset_pool()
    with database.get_cursor() as cur:
        cur.execute(SCHEMA_SQL.read_text())

    yield schema

    database.reset_pool()
    admin = psycopg2.connect(url)
    admin.autocommit = True
    with admin.cursor() as cur:
        cur.execute(f'DROP SCHEMA {schema} CASCADE')
    admin.close()


@pytest.fixture()
def db(db_schema):
    """Clean tables before each test; yields the database module."""
    import database
    with database.get_cursor() as cur:
        cur.execute(
            'TRUNCATE forecast_run_samples, forecasts, forecast_runs, evaluation_service_level, '
            'evaluation_metrics, evaluation_runs, planned_promotions, sales_data, oil_prices, '
            'holidays, products RESTART IDENTITY CASCADE'
        )
    return database
