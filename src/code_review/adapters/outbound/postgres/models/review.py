"""PostgreSQL mappings; see docs/DATABASE_SCHEMA.md for the storage contract."""

from datetime import datetime
from typing import Any
from uuid import UUID, uuid4

from sqlalchemy import (
    BigInteger,
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKeyConstraint,
    Index,
    Integer,
    Text,
    UniqueConstraint,
    Uuid,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from code_review.adapters.outbound.postgres.base import Base


class MergeRequest(Base):
    """MergeRequest storage record."""

    __tablename__ = "merge_request"
    __table_args__ = (
        ForeignKeyConstraint(["tenant_id"], ["workspace.id"], name="fk_merge_request_tenant_id"),
        UniqueConstraint("tenant_id", "id"),
        CheckConstraint("external_number > 0", name="external_number_positive"),
        CheckConstraint("revision_epoch >= 0", name="revision_epoch_nonnegative"),
        CheckConstraint("refresh_requested_seq >= 0", name="refresh_requested_seq_nonnegative"),
        CheckConstraint("refresh_applied_seq >= 0", name="refresh_applied_seq_nonnegative"),
        ForeignKeyConstraint(
            ["tenant_id", "repository_id"],
            ["repository.tenant_id", "repository.id"],
            name="fk_merge_request_repository_id",
        ),
        UniqueConstraint("tenant_id", "repository_id", "external_number"),
        CheckConstraint("refresh_applied_seq <= refresh_requested_seq", name="refresh_sequence"),
    )

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    tenant_id: Mapped[UUID] = mapped_column(Uuid)
    repository_id: Mapped[UUID] = mapped_column(Uuid)
    external_number: Mapped[int] = mapped_column(BigInteger)
    revision_descriptor: Mapped[dict[str, Any]] = mapped_column(JSONB)
    revision_epoch: Mapped[int] = mapped_column(BigInteger)
    refresh_requested_seq: Mapped[int] = mapped_column(BigInteger)
    refresh_applied_seq: Mapped[int] = mapped_column(BigInteger)
    refresh_lease_token: Mapped[UUID | None] = mapped_column(Uuid)
    refresh_locked_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_confirmed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class ReviewProfile(Base):
    """ReviewProfile storage record."""

    __tablename__ = "review_profile"
    __table_args__ = (
        ForeignKeyConstraint(["tenant_id"], ["workspace.id"], name="fk_review_profile_tenant_id"),
        UniqueConstraint("tenant_id", "id"),
        UniqueConstraint("tenant_id", "name"),
        Index(
            "uq_review_profile_default",
            "tenant_id",
            unique=True,
            postgresql_where=text("is_default"),
        ),
    )

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    tenant_id: Mapped[UUID] = mapped_column(Uuid)
    name: Mapped[str] = mapped_column(Text)
    is_default: Mapped[bool] = mapped_column(Boolean)
    settings: Mapped[dict[str, Any]] = mapped_column(JSONB)


class Perspective(Base):
    """Perspective storage record."""

    __tablename__ = "perspective"
    __table_args__ = (
        ForeignKeyConstraint(["tenant_id"], ["workspace.id"], name="fk_perspective_tenant_id"),
        UniqueConstraint("tenant_id", "id"),
        CheckConstraint("state IN ('active', 'archived')", name="state"),
        UniqueConstraint("tenant_id", "key"),
    )

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    tenant_id: Mapped[UUID] = mapped_column(Uuid)
    key: Mapped[str] = mapped_column(Text)
    name: Mapped[str] = mapped_column(Text)
    state: Mapped[str] = mapped_column(Text)


class ProfilePerspective(Base):
    """ProfilePerspective storage record."""

    __tablename__ = "profile_perspective"
    __table_args__ = (
        ForeignKeyConstraint(
            ["tenant_id"], ["workspace.id"], name="fk_profile_perspective_tenant_id"
        ),
        ForeignKeyConstraint(
            ["tenant_id", "profile_id"],
            ["review_profile.tenant_id", "review_profile.id"],
            name="fk_profile_perspective_profile_id",
        ),
        ForeignKeyConstraint(
            ["tenant_id", "perspective_id"],
            ["perspective.tenant_id", "perspective.id"],
            name="fk_profile_perspective_perspective_id",
        ),
        UniqueConstraint("tenant_id", "profile_id", "position"),
        CheckConstraint("position >= 0", name="position_nonnegative"),
    )

    tenant_id: Mapped[UUID] = mapped_column(Uuid, primary_key=True)
    profile_id: Mapped[UUID] = mapped_column(Uuid, primary_key=True)
    perspective_id: Mapped[UUID] = mapped_column(Uuid, primary_key=True)
    position: Mapped[int] = mapped_column(Integer)


class PromptVersion(Base):
    """PromptVersion storage record."""

    __tablename__ = "prompt_version"
    __table_args__ = (
        ForeignKeyConstraint(["tenant_id"], ["workspace.id"], name="fk_prompt_version_tenant_id"),
        UniqueConstraint("tenant_id", "id"),
        CheckConstraint("version > 0", name="version_positive"),
        ForeignKeyConstraint(
            ["tenant_id", "perspective_id"],
            ["perspective.tenant_id", "perspective.id"],
            name="fk_prompt_version_perspective_id",
        ),
        UniqueConstraint("tenant_id", "perspective_id", "version"),
        UniqueConstraint("tenant_id", "id", "perspective_id"),
    )

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    tenant_id: Mapped[UUID] = mapped_column(Uuid)
    perspective_id: Mapped[UUID] = mapped_column(Uuid)
    version: Mapped[int] = mapped_column(Integer)
    instructions: Mapped[str] = mapped_column(Text)
    settings: Mapped[dict[str, Any]] = mapped_column(JSONB)
    content_hash: Mapped[str] = mapped_column(Text)


class ReviewRequest(Base):
    """ReviewRequest storage record."""

    __tablename__ = "review_request"
    __table_args__ = (
        ForeignKeyConstraint(["tenant_id"], ["workspace.id"], name="fk_review_request_tenant_id"),
        UniqueConstraint("tenant_id", "id"),
        CheckConstraint(
            "state IN ('accepted', 'running', 'succeeded', 'partial', 'failed', "
            "'cancelled', 'expired')",
            name="state",
        ),
        CheckConstraint("reserved_tokens >= 0", name="reserved_tokens_nonnegative"),
        CheckConstraint("accounted_tokens >= 0", name="accounted_tokens_nonnegative"),
        ForeignKeyConstraint(
            ["tenant_id", "merge_request_id"],
            ["merge_request.tenant_id", "merge_request.id"],
            name="fk_review_request_merge_request_id",
        ),
        ForeignKeyConstraint(
            ["tenant_id", "actor_membership_id"],
            ["membership.tenant_id", "membership.id"],
            name="fk_review_request_actor_membership_id",
        ),
        ForeignKeyConstraint(
            ["tenant_id", "actor_service_id"],
            ["service_account.tenant_id", "service_account.id"],
            name="fk_review_request_actor_service_id",
        ),
        CheckConstraint(
            "(actor_membership_id IS NOT NULL) <> (actor_service_id IS NOT NULL)", name="one_actor"
        ),
        Index(
            "uq_review_request_actor_membership_id",
            "tenant_id",
            "actor_membership_id",
            "idempotency_key",
            unique=True,
            postgresql_where=text("actor_membership_id IS NOT NULL"),
        ),
        Index(
            "uq_review_request_actor_service_id",
            "tenant_id",
            "actor_service_id",
            "idempotency_key",
            unique=True,
            postgresql_where=text("actor_service_id IS NOT NULL"),
        ),
        UniqueConstraint("tenant_id", "id", "merge_request_id"),
    )

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    tenant_id: Mapped[UUID] = mapped_column(Uuid)
    merge_request_id: Mapped[UUID] = mapped_column(Uuid)
    actor_membership_id: Mapped[UUID | None] = mapped_column(Uuid)
    actor_service_id: Mapped[UUID | None] = mapped_column(Uuid)
    idempotency_key: Mapped[str] = mapped_column(Text)
    request_hash: Mapped[str] = mapped_column(Text)
    config_snapshot: Mapped[dict[str, Any]] = mapped_column(JSONB)
    config_hash: Mapped[str] = mapped_column(Text)
    budget: Mapped[dict[str, Any]] = mapped_column(JSONB)
    reserved_tokens: Mapped[int] = mapped_column(BigInteger)
    accounted_tokens: Mapped[int] = mapped_column(BigInteger)
    track_latest: Mapped[bool] = mapped_column(Boolean)
    deadline_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    state: Mapped[str] = mapped_column(Text)


class RepositoryIndex(Base):
    """RepositoryIndex storage record."""

    __tablename__ = "repository_index"
    __table_args__ = (
        ForeignKeyConstraint(["tenant_id"], ["workspace.id"], name="fk_repository_index_tenant_id"),
        UniqueConstraint("tenant_id", "id"),
        CheckConstraint("state IN ('building', 'ready', 'failed')", name="state"),
        ForeignKeyConstraint(
            ["tenant_id", "repository_id"],
            ["repository.tenant_id", "repository.id"],
            name="fk_repository_index_repository_id",
        ),
        UniqueConstraint("tenant_id", "repository_id", "commit_oid", "config_hash"),
    )

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    tenant_id: Mapped[UUID] = mapped_column(Uuid)
    repository_id: Mapped[UUID] = mapped_column(Uuid)
    commit_oid: Mapped[str] = mapped_column(Text)
    config_hash: Mapped[str] = mapped_column(Text)
    state: Mapped[str] = mapped_column(Text)
    manifest: Mapped[dict[str, Any]] = mapped_column(JSONB)
    graph: Mapped[dict[str, Any] | None] = mapped_column(JSONB)
    artifact_hash: Mapped[str | None] = mapped_column(Text)


class ReviewJob(Base):
    """ReviewJob storage record."""

    __tablename__ = "review_job"
    __table_args__ = (
        ForeignKeyConstraint(["tenant_id"], ["workspace.id"], name="fk_review_job_tenant_id"),
        UniqueConstraint("tenant_id", "id"),
        CheckConstraint(
            "state IN ('queued', 'running', 'succeeded', 'partial', 'failed', "
            "'cancelled', 'superseded', 'expired')",
            name="state",
        ),
        CheckConstraint("revision_epoch >= 0", name="revision_epoch_nonnegative"),
        ForeignKeyConstraint(
            ["tenant_id", "request_id", "merge_request_id"],
            ["review_request.tenant_id", "review_request.id", "review_request.merge_request_id"],
            name="fk_review_job_request_id_merge_request_id",
        ),
        ForeignKeyConstraint(
            ["tenant_id", "index_id"],
            ["repository_index.tenant_id", "repository_index.id"],
            name="fk_review_job_index_id",
        ),
        UniqueConstraint(
            "tenant_id", "request_id", "revision_epoch", "revision_fingerprint", "config_hash"
        ),
        Index(
            "uq_review_job_active_request",
            "request_id",
            unique=True,
            postgresql_where=text("state IN ('queued', 'running')"),
        ),
    )

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    tenant_id: Mapped[UUID] = mapped_column(Uuid)
    request_id: Mapped[UUID] = mapped_column(Uuid)
    merge_request_id: Mapped[UUID] = mapped_column(Uuid)
    index_id: Mapped[UUID | None] = mapped_column(Uuid)
    revision_fingerprint: Mapped[str] = mapped_column(Text)
    revision_epoch: Mapped[int] = mapped_column(BigInteger)
    config_hash: Mapped[str] = mapped_column(Text)
    state: Mapped[str] = mapped_column(Text)
    phase: Mapped[str] = mapped_column(Text)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class PerspectiveRun(Base):
    """PerspectiveRun storage record."""

    __tablename__ = "perspective_run"
    __table_args__ = (
        ForeignKeyConstraint(["tenant_id"], ["workspace.id"], name="fk_perspective_run_tenant_id"),
        UniqueConstraint("tenant_id", "id"),
        CheckConstraint(
            "state IN ('queued', 'running', 'succeeded', 'not_applicable', "
            "'insufficient_context', 'failed', 'cancelled')",
            name="state",
        ),
        ForeignKeyConstraint(
            ["tenant_id", "job_id"],
            ["review_job.tenant_id", "review_job.id"],
            name="fk_perspective_run_job_id",
        ),
        ForeignKeyConstraint(
            ["tenant_id", "perspective_id"],
            ["perspective.tenant_id", "perspective.id"],
            name="fk_perspective_run_perspective_id",
        ),
        ForeignKeyConstraint(
            ["tenant_id", "prompt_version_id", "perspective_id"],
            ["prompt_version.tenant_id", "prompt_version.id", "prompt_version.perspective_id"],
            name="fk_perspective_run_prompt_version_id_perspective_id",
        ),
        UniqueConstraint("tenant_id", "job_id", "perspective_id"),
        UniqueConstraint("tenant_id", "id", "job_id"),
    )

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    tenant_id: Mapped[UUID] = mapped_column(Uuid)
    job_id: Mapped[UUID] = mapped_column(Uuid)
    perspective_id: Mapped[UUID] = mapped_column(Uuid)
    prompt_version_id: Mapped[UUID] = mapped_column(Uuid)
    state: Mapped[str] = mapped_column(Text)
    coverage: Mapped[dict[str, Any]] = mapped_column(JSONB)
