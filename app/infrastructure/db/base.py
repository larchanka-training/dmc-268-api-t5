import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKeyConstraint, MetaData, Uuid, func
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

# Embedding vector size. Must match the chosen embedding model
# (BACKEND_ARCHITECTURE §8.1).
EMBEDDING_DIM = 1536

CORE = "core"
RAG = "rag"
TRANSPORT = "transport"
SCHEMAS = (CORE, RAG, TRANSPORT)

NAMING_CONVENTION = {
    "ix": "ix_%(column_0_label)s",
    "uq": "uq_%(table_name)s_%(column_0_name)s",
    "ck": "ck_%(table_name)s_%(constraint_name)s",
    "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
    "pk": "pk_%(table_name)s",
}


class Base(DeclarativeBase):
    metadata = MetaData(naming_convention=NAMING_CONVENTION)
    type_annotation_map = {datetime: DateTime(timezone=True)}


class IdMixin:
    id: Mapped[uuid.UUID] = mapped_column(
        Uuid,
        primary_key=True,
        default=uuid.uuid4,
        server_default=func.gen_random_uuid(),
    )


class TimestampMixin:
    created_at: Mapped[datetime] = mapped_column(
        server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        server_default=func.now(), onupdate=func.now(), nullable=False
    )


def tenant_fk(name: str, column: str, target: str) -> ForeignKeyConstraint:
    """Composite FK ``(organization_id, <column>)`` to ``<target>``.

    Forbids linking rows that belong to different organizations. ``target`` is
    ``"schema.table"``; the parent needs UNIQUE ``(organization_id, id)``.
    """
    return ForeignKeyConstraint(
        ["organization_id", column],
        [f"{target}.organization_id", f"{target}.id"],
        name=name,
    )


def in_list(column: str, values: tuple[str, ...]) -> str:
    quoted = ", ".join(f"'{v}'" for v in values)
    return f"{column} IN ({quoted})"
