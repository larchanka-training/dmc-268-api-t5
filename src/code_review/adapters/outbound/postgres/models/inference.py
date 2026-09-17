"""PostgreSQL mappings; see docs/DATABASE_SCHEMA.md for the storage contract."""

from datetime import datetime
from typing import Any
from uuid import UUID, uuid4

from sqlalchemy import (
    BigInteger,
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


class ModelCall(Base):
    """ModelCall storage record."""

    __tablename__ = "model_call"
    __table_args__ = (
        ForeignKeyConstraint(["tenant_id"], ["workspace.id"], name="fk_model_call_tenant_id"),
        UniqueConstraint("tenant_id", "id"),
        CheckConstraint("kind IN ('chunk', 'perspective_synthesis', 'job_synthesis')", name="kind"),
        CheckConstraint(
            "state IN ('planned', 'ready', 'running', 'succeeded', 'failed', 'cancelled')",
            name="state",
        ),
        ForeignKeyConstraint(
            ["tenant_id", "job_id"],
            ["review_job.tenant_id", "review_job.id"],
            name="fk_model_call_job_id",
        ),
        ForeignKeyConstraint(
            ["tenant_id", "perspective_run_id", "job_id"],
            ["perspective_run.tenant_id", "perspective_run.id", "perspective_run.job_id"],
            name="fk_model_call_perspective_run_id_job_id",
        ),
        ForeignKeyConstraint(
            ["tenant_id", "accepted_attempt_id", "id"],
            [
                "inference_attempt.tenant_id",
                "inference_attempt.id",
                "inference_attempt.model_call_id",
            ],
            name="fk_model_call_accepted_attempt_id_id",
            use_alter=True,
        ),
        UniqueConstraint("tenant_id", "job_id", "call_key"),
        UniqueConstraint("tenant_id", "id", "job_id"),
        UniqueConstraint("tenant_id", "id", "accepted_attempt_id"),
        CheckConstraint(
            "(kind = 'job_synthesis' AND perspective_run_id IS NULL) OR (kind IN "
            "('chunk', 'perspective_synthesis') AND perspective_run_id IS NOT NULL)",
            name="perspective_kind",
        ),
    )

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    tenant_id: Mapped[UUID] = mapped_column(Uuid)
    job_id: Mapped[UUID] = mapped_column(Uuid)
    perspective_run_id: Mapped[UUID | None] = mapped_column(Uuid)
    kind: Mapped[str] = mapped_column(Text)
    call_key: Mapped[str] = mapped_column(Text)
    state: Mapped[str] = mapped_column(Text)
    accepted_attempt_id: Mapped[UUID | None] = mapped_column(Uuid)


class ContextPayload(Base):
    """ContextPayload storage record."""

    __tablename__ = "context_payload"
    __table_args__ = (
        ForeignKeyConstraint(["tenant_id"], ["workspace.id"], name="fk_context_payload_tenant_id"),
        UniqueConstraint("tenant_id", "id"),
        CheckConstraint("token_count >= 0", name="token_count_nonnegative"),
        CheckConstraint("output_reserve >= 0", name="output_reserve_nonnegative"),
        ForeignKeyConstraint(
            ["tenant_id", "model_call_id"],
            ["model_call.tenant_id", "model_call.id"],
            name="fk_context_payload_model_call_id",
        ),
        UniqueConstraint("tenant_id", "model_call_id"),
    )

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    tenant_id: Mapped[UUID] = mapped_column(Uuid)
    model_call_id: Mapped[UUID] = mapped_column(Uuid)
    request_body: Mapped[dict[str, Any]] = mapped_column(JSONB)
    content_hash: Mapped[str] = mapped_column(Text)
    token_count: Mapped[int] = mapped_column(BigInteger)
    output_reserve: Mapped[int] = mapped_column(BigInteger)
    counter_version: Mapped[str] = mapped_column(Text)


class InferenceAttempt(Base):
    """InferenceAttempt storage record."""

    __tablename__ = "inference_attempt"
    __table_args__ = (
        ForeignKeyConstraint(
            ["tenant_id"], ["workspace.id"], name="fk_inference_attempt_tenant_id"
        ),
        UniqueConstraint("tenant_id", "id"),
        CheckConstraint(
            "state IN ('prepared', 'sending', 'received', 'accepted', 'failed', "
            "'outcome_unknown', 'rejected')",
            name="state",
        ),
        CheckConstraint("attempt_no > 0", name="attempt_no_positive"),
        CheckConstraint("reserved_tokens >= 0", name="reserved_tokens_nonnegative"),
        CheckConstraint("actual_tokens >= 0", name="actual_tokens_nonnegative"),
        ForeignKeyConstraint(
            ["tenant_id", "model_call_id"],
            ["model_call.tenant_id", "model_call.id"],
            name="fk_inference_attempt_model_call_id",
        ),
        ForeignKeyConstraint(
            ["tenant_id", "work_item_id"],
            ["work_item.tenant_id", "work_item.id"],
            name="fk_inference_attempt_work_item_id",
        ),
        UniqueConstraint("tenant_id", "model_call_id", "attempt_no"),
        UniqueConstraint("tenant_id", "id", "model_call_id"),
    )

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    tenant_id: Mapped[UUID] = mapped_column(Uuid)
    model_call_id: Mapped[UUID] = mapped_column(Uuid)
    work_item_id: Mapped[UUID] = mapped_column(Uuid)
    attempt_no: Mapped[int] = mapped_column(Integer)
    owner_token: Mapped[UUID] = mapped_column(Uuid)
    state: Mapped[str] = mapped_column(Text)
    reserved_tokens: Mapped[int] = mapped_column(BigInteger)
    actual_tokens: Mapped[int | None] = mapped_column(BigInteger)
    result: Mapped[dict[str, Any] | None] = mapped_column(JSONB)


class Finding(Base):
    """Finding storage record."""

    __tablename__ = "finding"
    __table_args__ = (
        ForeignKeyConstraint(["tenant_id"], ["workspace.id"], name="fk_finding_tenant_id"),
        UniqueConstraint("tenant_id", "id"),
        ForeignKeyConstraint(
            ["tenant_id", "job_id"],
            ["review_job.tenant_id", "review_job.id"],
            name="fk_finding_job_id",
        ),
        ForeignKeyConstraint(
            ["tenant_id", "model_call_id", "job_id"],
            ["model_call.tenant_id", "model_call.id", "model_call.job_id"],
            name="fk_finding_model_call_id_job_id",
        ),
        ForeignKeyConstraint(
            ["tenant_id", "model_call_id", "attempt_id"],
            ["model_call.tenant_id", "model_call.id", "model_call.accepted_attempt_id"],
            name="fk_finding_model_call_id_attempt_id",
        ),
        ForeignKeyConstraint(
            ["tenant_id", "job_id", "duplicate_of_id"],
            ["finding.tenant_id", "finding.job_id", "finding.id"],
            name="fk_finding_job_id_duplicate_of_id",
        ),
        UniqueConstraint("tenant_id", "model_call_id", "fingerprint"),
        UniqueConstraint("tenant_id", "job_id", "id"),
        CheckConstraint(
            "duplicate_of_id IS NULL OR duplicate_of_id <> id", name="not_self_duplicate"
        ),
    )

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    tenant_id: Mapped[UUID] = mapped_column(Uuid)
    job_id: Mapped[UUID] = mapped_column(Uuid)
    model_call_id: Mapped[UUID] = mapped_column(Uuid)
    attempt_id: Mapped[UUID] = mapped_column(Uuid)
    category: Mapped[str] = mapped_column(Text)
    severity: Mapped[str] = mapped_column(Text)
    body: Mapped[str] = mapped_column(Text)
    evidence: Mapped[dict[str, Any]] = mapped_column(JSONB)
    fingerprint: Mapped[str] = mapped_column(Text)
    duplicate_of_id: Mapped[UUID | None] = mapped_column(Uuid)


class Comment(Base):
    """Comment storage record."""

    __tablename__ = "comment"
    __table_args__ = (
        ForeignKeyConstraint(["tenant_id"], ["workspace.id"], name="fk_comment_tenant_id"),
        UniqueConstraint("tenant_id", "id"),
        CheckConstraint(
            "state IN ('pending', 'publishing', 'published', 'retry_wait', "
            "'delivery_unknown', 'failed', 'skipped')",
            name="state",
        ),
        ForeignKeyConstraint(
            ["tenant_id", "job_id"],
            ["review_job.tenant_id", "review_job.id"],
            name="fk_comment_job_id",
        ),
        ForeignKeyConstraint(
            ["tenant_id", "job_id", "finding_id"],
            ["finding.tenant_id", "finding.job_id", "finding.id"],
            name="fk_comment_job_id_finding_id",
        ),
        UniqueConstraint("tenant_id", "job_id", "publication_key"),
        Index("ix_comment_available", "state", "available_at"),
        Index(
            "ix_comment_lease", "locked_until", postgresql_where=text("locked_until IS NOT NULL")
        ),
    )

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    tenant_id: Mapped[UUID] = mapped_column(Uuid)
    job_id: Mapped[UUID] = mapped_column(Uuid)
    finding_id: Mapped[UUID | None] = mapped_column(Uuid)
    publication_key: Mapped[str] = mapped_column(Text)
    target: Mapped[dict[str, Any]] = mapped_column(JSONB)
    body: Mapped[str] = mapped_column(Text)
    state: Mapped[str] = mapped_column(Text)
    provider_comment_id: Mapped[str | None] = mapped_column(Text)
    lease_token: Mapped[UUID | None] = mapped_column(Uuid)
    locked_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    available_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
