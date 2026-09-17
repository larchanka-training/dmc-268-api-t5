"""Upgrade/rollback/re-upgrade and metadata drift against real PostgreSQL."""

import pytest
from sqlalchemy import inspect

from alembic import command
from code_review.adapters.outbound.postgres.base import Base

from .conftest import migration_config

pytestmark = pytest.mark.postgres


def test_migration_matches_models(database):
    from uuid import uuid4

    from sqlalchemy import text

    reference_schema = "metadata_" + uuid4().hex
    with database.begin() as conn:
        command.check(migration_config(conn))
        inspector = inspect(conn)
        assert set(inspector.get_table_names()) == set(Base.metadata.tables) | {"alembic_version"}
        # Alembic does not detect changes to CHECK expressions. Have PostgreSQL
        # normalize both migration and metadata definitions before comparing.
        actual = {
            table: {c["name"]: c["sqltext"] for c in inspector.get_check_constraints(table)}
            for table in Base.metadata.tables
        }
        conn.execute(text(f'CREATE SCHEMA "{reference_schema}"'))
        conn.execute(text(f'SET LOCAL search_path TO "{reference_schema}"'))
        Base.metadata.create_all(conn, checkfirst=False)
        reference = inspect(conn)
        for table in Base.metadata.tables:
            expected = {c["name"]: c["sqltext"] for c in reference.get_check_constraints(table)}
            assert actual[table] == expected, table
        conn.execute(text(f'DROP SCHEMA "{reference_schema}" CASCADE'))


def test_roundtrip_migration_in_separate_schema(database):
    # Use another isolated schema; the main test graph is never dropped.
    from uuid import uuid4

    from sqlalchemy import text

    schema = "roundtrip_" + uuid4().hex
    with database.begin() as conn:
        conn.execute(text(f'CREATE SCHEMA "{schema}"'))
        conn.execute(text(f'SET LOCAL search_path TO "{schema}"'))
        config = migration_config(conn)
        command.upgrade(config, "head")
        command.downgrade(config, "base")
        assert inspect(conn).get_table_names() == ["alembic_version"]
        command.upgrade(config, "head")
        command.check(config)
        conn.execute(text(f'DROP SCHEMA "{schema}" CASCADE'))
