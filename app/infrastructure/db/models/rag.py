import uuid
from datetime import datetime

from pgvector.sqlalchemy import Vector
from sqlalchemy import (
    CheckConstraint,
    Index,
    Integer,
    Text,
    UniqueConstraint,
    Uuid,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.infrastructure.db.base import (
    CORE,
    EMBEDDING_DIM,
    RAG,
    Base,
    IdMixin,
    TimestampMixin,
    in_list,
    tenant_fk,
)

SNAPSHOT_STATUSES = ("queued", "building", "ready", "failed")
EDGE_TYPES = ("call", "import", "inherit", "reference")


class RepositorySnapshot(IdMixin, TimestampMixin, Base):
    """RAG index for one repository, commit SHA and indexing profile."""

    __tablename__ = "repository_snapshots"
    __table_args__ = (
        UniqueConstraint(
            "repository_id",
            "commit_sha",
            "profile_hash",
            name="uq_repository_snapshots_repo_sha_profile",
        ),
        UniqueConstraint(
            "organization_id", "id", name="uq_repository_snapshots_org_id"
        ),
        # Target of repositories.active_snapshot_id: snapshot of the same repository.
        UniqueConstraint(
            "organization_id",
            "repository_id",
            "id",
            name="uq_repository_snapshots_org_repo_id",
        ),
        tenant_fk(
            "fk_repository_snapshots_repository",
            "repository_id",
            f"{CORE}.repositories",
        ),
        CheckConstraint(in_list("status", SNAPSHOT_STATUSES), name="status_valid"),
        Index(
            "ix_repository_snapshots_status_next_attempt", "status", "next_attempt_at"
        ),
        {"schema": RAG},
    )

    organization_id: Mapped[uuid.UUID] = mapped_column(Uuid)
    repository_id: Mapped[uuid.UUID] = mapped_column(Uuid)
    commit_sha: Mapped[str] = mapped_column(Text)
    profile_hash: Mapped[str] = mapped_column(Text)
    embedding_model: Mapped[str] = mapped_column(Text)
    embedding_dim: Mapped[int] = mapped_column(Integer)
    status: Mapped[str] = mapped_column(Text, server_default="queued")
    attempts: Mapped[int] = mapped_column(Integer, server_default="0")
    next_attempt_at: Mapped[datetime | None]
    lease_owner: Mapped[str | None] = mapped_column(Text)
    lease_expires_at: Mapped[datetime | None]
    lease_generation: Mapped[int] = mapped_column(Integer, server_default="0")


class CodeChunk(IdMixin, TimestampMixin, Base):
    __tablename__ = "code_chunks"
    __table_args__ = (
        UniqueConstraint("organization_id", "id", name="uq_code_chunks_org_id"),
        tenant_fk(
            "fk_code_chunks_snapshot", "snapshot_id", f"{RAG}.repository_snapshots"
        ),
        CheckConstraint(
            "start_line > 0 AND end_line >= start_line", name="lines_valid"
        ),
        Index("ix_code_chunks_snapshot_path", "snapshot_id", "path"),
        {"schema": RAG},
    )

    organization_id: Mapped[uuid.UUID] = mapped_column(Uuid)
    snapshot_id: Mapped[uuid.UUID] = mapped_column(Uuid)
    path: Mapped[str] = mapped_column(Text)
    start_line: Mapped[int] = mapped_column(Integer)
    end_line: Mapped[int] = mapped_column(Integer)
    symbol: Mapped[str | None] = mapped_column(Text)
    content: Mapped[str] = mapped_column(Text)
    embedding: Mapped[list[float] | None] = mapped_column(Vector(EMBEDDING_DIM))


class CodeEdge(IdMixin, TimestampMixin, Base):
    __tablename__ = "code_edges"
    __table_args__ = (
        tenant_fk(
            "fk_code_edges_snapshot", "snapshot_id", f"{RAG}.repository_snapshots"
        ),
        tenant_fk(
            "fk_code_edges_source_chunk", "source_chunk_id", f"{RAG}.code_chunks"
        ),
        tenant_fk(
            "fk_code_edges_target_chunk", "target_chunk_id", f"{RAG}.code_chunks"
        ),
        CheckConstraint(in_list("edge_type", EDGE_TYPES), name="edge_type_valid"),
        Index("ix_code_edges_snapshot_id", "snapshot_id"),
        Index("ix_code_edges_source_chunk_id", "source_chunk_id"),
        {"schema": RAG},
    )

    organization_id: Mapped[uuid.UUID] = mapped_column(Uuid)
    snapshot_id: Mapped[uuid.UUID] = mapped_column(Uuid)
    source_chunk_id: Mapped[uuid.UUID] = mapped_column(Uuid)
    target_chunk_id: Mapped[uuid.UUID | None] = mapped_column(Uuid)
    edge_type: Mapped[str] = mapped_column(Text)
    target_name: Mapped[str | None] = mapped_column(Text)
