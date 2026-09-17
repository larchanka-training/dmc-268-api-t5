"""PostgreSQL mappings; see docs/DATABASE_SCHEMA.md for the storage contract."""

from datetime import datetime
from typing import Any
from uuid import UUID, uuid4

from sqlalchemy import (
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


class WorkItem(Base):
    """WorkItem storage record."""

    __tablename__ = "work_item"
    __table_args__ = (
        ForeignKeyConstraint(["tenant_id"], ["workspace.id"], name="fk_work_item_tenant_id"),
        UniqueConstraint("tenant_id", "id"),
        CheckConstraint(
            "kind IN ('index_repository', 'resolve_review', 'run_review', 'sync_revision')",
            name="kind",
        ),
        CheckConstraint(
            "state IN ('queued', 'running', 'retry_wait', 'waiting_external', "
            "'succeeded', 'cancelled', 'failed')",
            name="state",
        ),
        CheckConstraint("attempt_count >= 0", name="attempt_count_nonnegative"),
        CheckConstraint("max_attempts > 0", name="max_attempts_positive"),
        ForeignKeyConstraint(
            ["tenant_id", "repository_id"],
            ["repository.tenant_id", "repository.id"],
            name="fk_work_item_repository_id",
        ),
        ForeignKeyConstraint(
            ["tenant_id", "merge_request_id"],
            ["merge_request.tenant_id", "merge_request.id"],
            name="fk_work_item_merge_request_id",
        ),
        ForeignKeyConstraint(
            ["tenant_id", "review_request_id"],
            ["review_request.tenant_id", "review_request.id"],
            name="fk_work_item_review_request_id",
        ),
        ForeignKeyConstraint(
            ["tenant_id", "review_job_id"],
            ["review_job.tenant_id", "review_job.id"],
            name="fk_work_item_review_job_id",
        ),
        CheckConstraint(
            "(kind = 'index_repository' AND repository_id IS NOT NULL AND "
            "merge_request_id IS NULL AND review_request_id IS NULL AND review_job_id IS "
            "NULL) OR (kind = 'sync_revision' AND repository_id IS NULL AND "
            "merge_request_id IS NOT NULL AND review_request_id IS NULL AND "
            "review_job_id IS NULL) OR (kind = 'resolve_review' AND repository_id IS "
            "NULL AND merge_request_id IS NULL AND review_request_id IS NOT NULL AND "
            "review_job_id IS NULL) OR (kind = 'run_review' AND repository_id IS NULL "
            "AND merge_request_id IS NULL AND review_request_id IS NULL AND "
            "review_job_id IS NOT NULL)",
            name="kind_target",
        ),
        CheckConstraint(
            "state <> 'running' OR (lease_token IS NOT NULL AND locked_until IS NOT NULL)",
            name="running_lease",
        ),
        UniqueConstraint("tenant_id", "kind", "business_key"),
        Index("ix_work_item_available", "state", "available_at"),
        Index(
            "ix_work_item_lease", "locked_until", postgresql_where=text("locked_until IS NOT NULL")
        ),
    )

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    tenant_id: Mapped[UUID] = mapped_column(Uuid)
    kind: Mapped[str] = mapped_column(Text)
    repository_id: Mapped[UUID | None] = mapped_column(Uuid)
    merge_request_id: Mapped[UUID | None] = mapped_column(Uuid)
    review_request_id: Mapped[UUID | None] = mapped_column(Uuid)
    review_job_id: Mapped[UUID | None] = mapped_column(Uuid)
    business_key: Mapped[str] = mapped_column(Text)
    state: Mapped[str] = mapped_column(Text)
    attempt_count: Mapped[int] = mapped_column(Integer)
    max_attempts: Mapped[int] = mapped_column(Integer)
    available_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    lease_token: Mapped[UUID | None] = mapped_column(Uuid)
    locked_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    deadline_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    last_error_code: Mapped[str | None] = mapped_column(Text)


class WebhookInbox(Base):
    """WebhookInbox storage record."""

    __tablename__ = "webhook_inbox"
    __table_args__ = (
        ForeignKeyConstraint(["tenant_id"], ["workspace.id"], name="fk_webhook_inbox_tenant_id"),
        UniqueConstraint("tenant_id", "id"),
        CheckConstraint(
            "state IN ('received', 'processing', 'applied', 'rejected', 'manual_required')",
            name="state",
        ),
        UniqueConstraint("provider_scope", "delivery_id"),
    )

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    provider_scope: Mapped[str] = mapped_column(Text)
    delivery_id: Mapped[str] = mapped_column(Text)
    tenant_id: Mapped[UUID | None] = mapped_column(Uuid)
    payload_hash: Mapped[str] = mapped_column(Text)
    payload: Mapped[dict[str, Any]] = mapped_column(JSONB)
    state: Mapped[str] = mapped_column(Text)
    received_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=text("now()")
    )
