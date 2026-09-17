"""Online/offline migrations with explicit configuration and shared metadata."""

import os
from logging.config import fileConfig

from sqlalchemy import create_engine, pool
from sqlalchemy.engine import make_url

from alembic import context
from code_review.adapters.outbound.postgres import models  # noqa: F401
from code_review.adapters.outbound.postgres.base import Base

config = context.config
if config.config_file_name is not None:
    fileConfig(config.config_file_name)


def database_url():
    value = os.environ.get("DATABASE_URL")
    if not value:
        raise RuntimeError("DATABASE_URL is required; migrations never use an implicit database")
    url = make_url(value)
    if url.drivername != "postgresql+psycopg":
        raise ValueError("DATABASE_URL must use postgresql+psycopg")
    return url


def run_with_connection(connection):
    context.configure(
        connection=connection,
        target_metadata=Base.metadata,
        compare_type=True,
        compare_server_default=True,
    )
    with context.begin_transaction():
        context.run_migrations()


if context.is_offline_mode():
    context.configure(
        url=database_url(),
        target_metadata=Base.metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )
    with context.begin_transaction():
        context.run_migrations()
elif config.attributes.get("connection") is not None:
    # Tests provide a connection with their own isolated search_path.
    run_with_connection(config.attributes["connection"])
else:
    with create_engine(database_url(), poolclass=pool.NullPool).connect() as conn:
        run_with_connection(conn)
