"""PostgreSQL tests own a unique schema, never an existing application schema."""

import os
from pathlib import Path
from uuid import uuid4

import pytest
from alembic.config import Config
from sqlalchemy import create_engine, text

from alembic import command

ROOT = Path(__file__).resolve().parents[1]


def migration_config(connection):
    config = Config(str(ROOT / "alembic.ini"))
    config.attributes["connection"] = connection
    return config


@pytest.fixture(scope="session")
def database():
    url = os.environ.get("TEST_DATABASE_URL")
    if not url:
        pytest.skip("Set TEST_DATABASE_URL to run real PostgreSQL tests")
    admin = create_engine(url)
    schema = "test_" + uuid4().hex
    with admin.begin() as conn:
        conn.execute(text(f'CREATE SCHEMA "{schema}"'))
    engine = create_engine(url, connect_args={"options": f"-csearch_path={schema}"})
    try:
        with engine.begin() as conn:
            command.upgrade(migration_config(conn), "head")
        yield engine
    finally:
        engine.dispose()
        with admin.begin() as conn:
            conn.execute(text(f'DROP SCHEMA "{schema}" CASCADE'))
        admin.dispose()


@pytest.fixture
def db(database):
    with database.connect() as conn, conn.begin() as transaction:
        yield conn
        transaction.rollback()
