import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import (
    BigInteger,
    CheckConstraint,
    ForeignKey,
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

from app.infrastructure.db.base import (
    CORE,
    RAG,
    Base,
    IdMixin,
    TimestampMixin,
    in_list,
    tenant_fk,
)

SUBSCRIPTION_STATUSES = ("active", "grace", "expired", "canceled")
RESERVATION_STATUSES = ("open", "closed")
USAGE_STATUSES = ("reserved", "committed", "released", "unknown")
INSTALLATION_STATUSES = ("active", "suspended", "removed")
JOB_STATUSES = (
    "queued",
    "preparing",
    "running",
    "completed",
    "partial",
    "failed",
    "cancelled",
    "superseded",
)
PUBLICATION_STATUSES = (
    "pending",
    "publishing",
    "published",
    "retry_wait",
    "unknown",
    "failed",
    "superseded",
)
COMMENT_STATUSES = ("pending", "published", "failed")


class Organization(IdMixin, TimestampMixin, Base):
    """Tenant: owner of subscription, installations and all derived data."""

    __tablename__ = "organizations"
    __table_args__ = (
        UniqueConstraint("identity_subject", name="uq_organizations_identity_subject"),
        {"schema": CORE},
    )

    name: Mapped[str] = mapped_column(Text)
    identity_subject: Mapped[str] = mapped_column(Text)


class Subscription(IdMixin, TimestampMixin, Base):
    __tablename__ = "subscriptions"
    __table_args__ = (
        UniqueConstraint("organization_id", name="uq_subscriptions_organization_id"),
        UniqueConstraint("organization_id", "id", name="uq_subscriptions_org_id"),
        CheckConstraint(in_list("status", SUBSCRIPTION_STATUSES), name="status_valid"),
        {"schema": CORE},
    )

    organization_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey(f"{CORE}.organizations.id", name="fk_subscriptions_org")
    )
    status: Mapped[str] = mapped_column(Text)
    plan_version: Mapped[str | None] = mapped_column(Text)
    allowed_operations: Mapped[dict[str, Any]] = mapped_column(
        JSONB, server_default=text("'{}'::jsonb")
    )
    valid_until: Mapped[datetime | None]
    checked_at: Mapped[datetime | None]


class TokenBudget(IdMixin, TimestampMixin, Base):
    __tablename__ = "token_budgets"
    __table_args__ = (
        UniqueConstraint("organization_id", "id", name="uq_token_budgets_org_id"),
        tenant_fk(
            "fk_token_budgets_subscription", "subscription_id", f"{CORE}.subscriptions"
        ),
        CheckConstraint(
            "allowance_tokens >= 0 AND consumed_tokens >= 0 AND reserved_tokens >= 0",
            name="counters_non_negative",
        ),
        CheckConstraint(
            "consumed_tokens + reserved_tokens <= allowance_tokens",
            name="within_allowance",
        ),
        CheckConstraint("period_end > period_start", name="period_valid"),
        {"schema": CORE},
    )

    organization_id: Mapped[uuid.UUID] = mapped_column(Uuid)
    subscription_id: Mapped[uuid.UUID] = mapped_column(Uuid)
    period_start: Mapped[datetime]
    period_end: Mapped[datetime]
    allowance_tokens: Mapped[int] = mapped_column(BigInteger)
    consumed_tokens: Mapped[int] = mapped_column(BigInteger, server_default="0")
    reserved_tokens: Mapped[int] = mapped_column(BigInteger, server_default="0")


class GitHubInstallation(IdMixin, TimestampMixin, Base):
    __tablename__ = "github_installations"
    __table_args__ = (
        UniqueConstraint(
            "installation_id", name="uq_github_installations_installation_id"
        ),
        UniqueConstraint(
            "organization_id", "id", name="uq_github_installations_org_id"
        ),
        CheckConstraint(in_list("status", INSTALLATION_STATUSES), name="status_valid"),
        {"schema": CORE},
    )

    organization_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey(f"{CORE}.organizations.id", name="fk_github_installations_org")
    )
    installation_id: Mapped[int] = mapped_column(BigInteger)
    account_login: Mapped[str] = mapped_column(Text)
    status: Mapped[str] = mapped_column(Text, server_default="active")


class Repository(IdMixin, TimestampMixin, Base):
    """Git repository connected through a GitHub installation."""

    __tablename__ = "repositories"
    __table_args__ = (
        UniqueConstraint(
            "organization_id",
            "github_repository_id",
            name="uq_repositories_org_github_id",
        ),
        UniqueConstraint("organization_id", "id", name="uq_repositories_org_id"),
        tenant_fk(
            "fk_repositories_installation",
            "installation_id",
            f"{CORE}.github_installations",
        ),
        # (organization_id, id) of the snapshot is the target; the snapshot must
        # belong to this very repository, hence a 3-column key.
        ForeignKeyConstraint(
            ["organization_id", "id", "active_snapshot_id"],
            [
                f"{RAG}.repository_snapshots.organization_id",
                f"{RAG}.repository_snapshots.repository_id",
                f"{RAG}.repository_snapshots.id",
            ],
            name="fk_repositories_active_snapshot",
            use_alter=True,
        ),
        {"schema": CORE},
    )

    organization_id: Mapped[uuid.UUID] = mapped_column(Uuid)
    installation_id: Mapped[uuid.UUID] = mapped_column(Uuid)
    active_snapshot_id: Mapped[uuid.UUID | None] = mapped_column(Uuid)
    github_repository_id: Mapped[int] = mapped_column(BigInteger)
    full_name: Mapped[str] = mapped_column(Text)
    default_branch: Mapped[str] = mapped_column(Text, server_default="main")
    is_enabled: Mapped[bool] = mapped_column(server_default=text("true"))


class MergeRequest(IdMixin, TimestampMixin, Base):
    """Pull request in GitHub terms."""

    __tablename__ = "merge_requests"
    __table_args__ = (
        UniqueConstraint(
            "repository_id", "number", name="uq_merge_requests_repo_number"
        ),
        UniqueConstraint("organization_id", "id", name="uq_merge_requests_org_id"),
        tenant_fk(
            "fk_merge_requests_repository", "repository_id", f"{CORE}.repositories"
        ),
        {"schema": CORE},
    )

    organization_id: Mapped[uuid.UUID] = mapped_column(Uuid)
    repository_id: Mapped[uuid.UUID] = mapped_column(Uuid)
    number: Mapped[int] = mapped_column(BigInteger)
    title: Mapped[str] = mapped_column(Text)
    state: Mapped[str] = mapped_column(Text, server_default="open")
    base_sha: Mapped[str] = mapped_column(Text)
    head_sha: Mapped[str] = mapped_column(Text)


class ReviewJob(IdMixin, TimestampMixin, Base):
    __tablename__ = "review_jobs"
    __table_args__ = (
        UniqueConstraint(
            "organization_id", "run_key", name="uq_review_jobs_org_run_key"
        ),
        UniqueConstraint("organization_id", "id", name="uq_review_jobs_org_id"),
        tenant_fk(
            "fk_review_jobs_merge_request", "merge_request_id", f"{CORE}.merge_requests"
        ),
        CheckConstraint(in_list("status", JOB_STATUSES), name="status_valid"),
        Index("ix_review_jobs_status_next_attempt", "status", "next_attempt_at"),
        Index("ix_review_jobs_merge_request_id", "merge_request_id"),
        {"schema": CORE},
    )

    organization_id: Mapped[uuid.UUID] = mapped_column(Uuid)
    merge_request_id: Mapped[uuid.UUID] = mapped_column(Uuid)
    run_key: Mapped[str] = mapped_column(Text)
    head_sha: Mapped[str] = mapped_column(Text)
    base_sha: Mapped[str] = mapped_column(Text)
    status: Mapped[str] = mapped_column(Text, server_default="queued")
    pipeline_version: Mapped[str] = mapped_column(Text)
    prompt_version: Mapped[str] = mapped_column(Text)
    config_hash: Mapped[str | None] = mapped_column(Text)
    config: Mapped[dict[str, Any]] = mapped_column(
        JSONB, server_default=text("'{}'::jsonb")
    )
    attempts: Mapped[int] = mapped_column(Integer, server_default="0")
    next_attempt_at: Mapped[datetime | None]
    lease_owner: Mapped[str | None] = mapped_column(Text)
    lease_expires_at: Mapped[datetime | None]
    lease_generation: Mapped[int] = mapped_column(Integer, server_default="0")
    dispatch_generation: Mapped[int] = mapped_column(Integer, server_default="0")
    error_code: Mapped[str | None] = mapped_column(Text)
    started_at: Mapped[datetime | None]
    finished_at: Mapped[datetime | None]


class TokenReservation(IdMixin, TimestampMixin, Base):
    __tablename__ = "token_reservations"
    __table_args__ = (
        UniqueConstraint(
            "organization_id",
            "admission_key",
            name="uq_token_reservations_org_admission_key",
        ),
        UniqueConstraint("organization_id", "id", name="uq_token_reservations_org_id"),
        tenant_fk("fk_token_reservations_budget", "budget_id", f"{CORE}.token_budgets"),
        tenant_fk(
            "fk_token_reservations_review_job", "review_job_id", f"{CORE}.review_jobs"
        ),
        tenant_fk(
            "fk_token_reservations_snapshot",
            "snapshot_id",
            f"{RAG}.repository_snapshots",
        ),
        CheckConstraint(in_list("status", RESERVATION_STATUSES), name="status_valid"),
        CheckConstraint(
            "num_nonnulls(review_job_id, snapshot_id) = 1", name="single_owner"
        ),
        CheckConstraint(
            "granted_tokens >= 0 AND consumed_tokens >= 0 AND released_tokens >= 0 "
            "AND remaining_tokens >= 0 AND inflight_tokens >= 0",
            name="counters_non_negative",
        ),
        CheckConstraint(
            "inflight_tokens <= remaining_tokens", name="inflight_within_remaining"
        ),
        CheckConstraint(
            "granted_tokens = consumed_tokens + released_tokens + remaining_tokens",
            name="balance",
        ),
        Index(
            "uq_token_reservations_open_review_job",
            "review_job_id",
            unique=True,
            postgresql_where=text("status = 'open' AND review_job_id IS NOT NULL"),
        ),
        Index(
            "uq_token_reservations_open_snapshot",
            "snapshot_id",
            unique=True,
            postgresql_where=text("status = 'open' AND snapshot_id IS NOT NULL"),
        ),
        {"schema": CORE},
    )

    organization_id: Mapped[uuid.UUID] = mapped_column(Uuid)
    budget_id: Mapped[uuid.UUID] = mapped_column(Uuid)
    review_job_id: Mapped[uuid.UUID | None] = mapped_column(Uuid)
    snapshot_id: Mapped[uuid.UUID | None] = mapped_column(Uuid)
    admission_key: Mapped[str] = mapped_column(Text)
    status: Mapped[str] = mapped_column(Text, server_default="open")
    granted_tokens: Mapped[int] = mapped_column(BigInteger)
    consumed_tokens: Mapped[int] = mapped_column(BigInteger, server_default="0")
    released_tokens: Mapped[int] = mapped_column(BigInteger, server_default="0")
    remaining_tokens: Mapped[int] = mapped_column(BigInteger)
    inflight_tokens: Mapped[int] = mapped_column(BigInteger, server_default="0")


class TokenUsage(IdMixin, TimestampMixin, Base):
    __tablename__ = "token_usages"
    __table_args__ = (
        UniqueConstraint(
            "organization_id", "request_key", name="uq_token_usages_org_request_key"
        ),
        tenant_fk(
            "fk_token_usages_reservation",
            "reservation_id",
            f"{CORE}.token_reservations",
        ),
        CheckConstraint(in_list("status", USAGE_STATUSES), name="status_valid"),
        CheckConstraint(
            "upper_bound_tokens >= 0 AND (actual_tokens IS NULL OR actual_tokens >= 0)",
            name="tokens_non_negative",
        ),
        {"schema": CORE},
    )

    organization_id: Mapped[uuid.UUID] = mapped_column(Uuid)
    reservation_id: Mapped[uuid.UUID] = mapped_column(Uuid)
    request_key: Mapped[str] = mapped_column(Text)
    request_hash: Mapped[str] = mapped_column(Text)
    provider_request_id: Mapped[str | None] = mapped_column(Text)
    upper_bound_tokens: Mapped[int] = mapped_column(BigInteger)
    actual_tokens: Mapped[int | None] = mapped_column(BigInteger)
    status: Mapped[str] = mapped_column(Text, server_default="reserved")


class ContextPayload(IdMixin, TimestampMixin, Base):
    """Exact LLM input for one part of a review job (no credentials)."""

    __tablename__ = "context_payloads"
    __table_args__ = (
        UniqueConstraint(
            "review_job_id", "part_no", name="uq_context_payloads_job_part"
        ),
        UniqueConstraint("organization_id", "id", name="uq_context_payloads_org_id"),
        tenant_fk(
            "fk_context_payloads_review_job", "review_job_id", f"{CORE}.review_jobs"
        ),
        CheckConstraint("part_no >= 0", name="part_no_non_negative"),
        {"schema": CORE},
    )

    organization_id: Mapped[uuid.UUID] = mapped_column(Uuid)
    review_job_id: Mapped[uuid.UUID] = mapped_column(Uuid)
    part_no: Mapped[int] = mapped_column(Integer)
    payload: Mapped[dict[str, Any]] = mapped_column(JSONB)
    payload_hash: Mapped[str] = mapped_column(Text)
    model: Mapped[str] = mapped_column(Text)
    params: Mapped[dict[str, Any]] = mapped_column(
        JSONB, server_default=text("'{}'::jsonb")
    )
    expires_at: Mapped[datetime | None]


class Finding(IdMixin, TimestampMixin, Base):
    __tablename__ = "findings"
    __table_args__ = (
        UniqueConstraint(
            "review_job_id", "fingerprint", name="uq_findings_job_fingerprint"
        ),
        UniqueConstraint("organization_id", "id", name="uq_findings_org_id"),
        tenant_fk("fk_findings_review_job", "review_job_id", f"{CORE}.review_jobs"),
        tenant_fk(
            "fk_findings_context_payload",
            "context_payload_id",
            f"{CORE}.context_payloads",
        ),
        CheckConstraint("side IN ('LEFT', 'RIGHT')", name="side_valid"),
        CheckConstraint(
            "start_line > 0 AND end_line >= start_line", name="lines_valid"
        ),
        {"schema": CORE},
    )

    organization_id: Mapped[uuid.UUID] = mapped_column(Uuid)
    review_job_id: Mapped[uuid.UUID] = mapped_column(Uuid)
    context_payload_id: Mapped[uuid.UUID | None] = mapped_column(Uuid)
    fingerprint: Mapped[str] = mapped_column(Text)
    path: Mapped[str] = mapped_column(Text)
    side: Mapped[str] = mapped_column(Text, server_default="RIGHT")
    start_line: Mapped[int] = mapped_column(Integer)
    end_line: Mapped[int] = mapped_column(Integer)
    category: Mapped[str] = mapped_column(Text)
    severity: Mapped[str] = mapped_column(Text)
    body: Mapped[str] = mapped_column(Text)
    suggestion: Mapped[str | None] = mapped_column(Text)


class Publication(IdMixin, TimestampMixin, Base):
    """One batch of comments sent to GitHub as a single review."""

    __tablename__ = "publications"
    __table_args__ = (
        UniqueConstraint("review_job_id", "batch_no", name="uq_publications_job_batch"),
        UniqueConstraint("organization_id", "id", name="uq_publications_org_id"),
        tenant_fk("fk_publications_review_job", "review_job_id", f"{CORE}.review_jobs"),
        CheckConstraint(in_list("status", PUBLICATION_STATUSES), name="status_valid"),
        Index("ix_publications_status_next_attempt", "status", "next_attempt_at"),
        {"schema": CORE},
    )

    organization_id: Mapped[uuid.UUID] = mapped_column(Uuid)
    review_job_id: Mapped[uuid.UUID] = mapped_column(Uuid)
    batch_no: Mapped[int] = mapped_column(Integer)
    status: Mapped[str] = mapped_column(Text, server_default="pending")
    payload: Mapped[dict[str, Any]] = mapped_column(JSONB)
    github_review_id: Mapped[int | None] = mapped_column(BigInteger)
    attempts: Mapped[int] = mapped_column(Integer, server_default="0")
    next_attempt_at: Mapped[datetime | None]
    lease_owner: Mapped[str | None] = mapped_column(Text)
    lease_expires_at: Mapped[datetime | None]
    lease_generation: Mapped[int] = mapped_column(Integer, server_default="0")


class Comment(IdMixin, TimestampMixin, Base):
    __tablename__ = "comments"
    __table_args__ = (
        UniqueConstraint("finding_id", name="uq_comments_finding_id"),
        tenant_fk("fk_comments_publication", "publication_id", f"{CORE}.publications"),
        tenant_fk("fk_comments_finding", "finding_id", f"{CORE}.findings"),
        CheckConstraint(in_list("status", COMMENT_STATUSES), name="status_valid"),
        Index("ix_comments_publication_id", "publication_id"),
        {"schema": CORE},
    )

    organization_id: Mapped[uuid.UUID] = mapped_column(Uuid)
    publication_id: Mapped[uuid.UUID] = mapped_column(Uuid)
    finding_id: Mapped[uuid.UUID] = mapped_column(Uuid)
    github_comment_id: Mapped[int | None] = mapped_column(BigInteger)
    status: Mapped[str] = mapped_column(Text, server_default="pending")
