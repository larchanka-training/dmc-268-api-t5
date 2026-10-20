"""initial schema: core, rag, transport

Revision ID: 0001
Revises:
Create Date: 2026-10-19
"""

from collections.abc import Sequence
from typing import Any

import sqlalchemy as sa
from pgvector.sqlalchemy import Vector
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "0001"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

# Must match EMBEDDING_DIM in app/infrastructure/db/base.py. Duplicated on
# purpose: a migration must not change when application constants change.
EMBEDDING_DIM = 1536

TS = sa.DateTime(timezone=True)
EMPTY_JSON = sa.text("'{}'::jsonb")


def _base_cols() -> list[sa.Column[Any]]:
    return [
        sa.Column(
            "id", sa.Uuid(), server_default=sa.text("gen_random_uuid()"), nullable=False
        ),
        sa.Column("created_at", TS, server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", TS, server_default=sa.text("now()"), nullable=False),
    ]


def _pk(table: str) -> sa.PrimaryKeyConstraint:
    return sa.PrimaryKeyConstraint("id", name=op.f(f"pk_{table}"))


def _uq(table: str, name: str, *cols: str) -> sa.UniqueConstraint:
    return sa.UniqueConstraint(*cols, name=op.f(name))


def _tfk(name: str, column: str, target: str) -> sa.ForeignKeyConstraint:
    return sa.ForeignKeyConstraint(
        ["organization_id", column],
        [f"{target}.organization_id", f"{target}.id"],
        name=op.f(name),
    )


def _ck(table: str, name: str, sqltext: str) -> sa.CheckConstraint:
    return sa.CheckConstraint(sqltext, name=op.f(f"ck_{table}_{name}"))


def _in(column: str, values: tuple[str, ...]) -> str:
    return f"{column} IN ({', '.join(repr(v) for v in values)})"


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")
    for schema in ("core", "rag", "transport"):
        op.execute(f"CREATE SCHEMA IF NOT EXISTS {schema}")

    # ---------------------------------------------------------------- core
    op.create_table(
        "organizations",
        *_base_cols(),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("identity_subject", sa.Text(), nullable=False),
        _pk("organizations"),
        _uq("organizations", "uq_organizations_identity_subject", "identity_subject"),
        schema="core",
    )

    op.create_table(
        "subscriptions",
        *_base_cols(),
        sa.Column("organization_id", sa.Uuid(), nullable=False),
        sa.Column("status", sa.Text(), nullable=False),
        sa.Column("plan_version", sa.Text(), nullable=True),
        sa.Column(
            "allowed_operations",
            postgresql.JSONB(),
            server_default=EMPTY_JSON,
            nullable=False,
        ),
        sa.Column("valid_until", TS, nullable=True),
        sa.Column("checked_at", TS, nullable=True),
        _pk("subscriptions"),
        sa.ForeignKeyConstraint(
            ["organization_id"],
            ["core.organizations.id"],
            name=op.f("fk_subscriptions_org"),
        ),
        _uq("subscriptions", "uq_subscriptions_organization_id", "organization_id"),
        _uq("subscriptions", "uq_subscriptions_org_id", "organization_id", "id"),
        _ck(
            "subscriptions",
            "status_valid",
            _in("status", ("active", "grace", "expired", "canceled")),
        ),
        schema="core",
    )

    op.create_table(
        "token_budgets",
        *_base_cols(),
        sa.Column("organization_id", sa.Uuid(), nullable=False),
        sa.Column("subscription_id", sa.Uuid(), nullable=False),
        sa.Column("period_start", TS, nullable=False),
        sa.Column("period_end", TS, nullable=False),
        sa.Column("allowance_tokens", sa.BigInteger(), nullable=False),
        sa.Column(
            "consumed_tokens", sa.BigInteger(), server_default="0", nullable=False
        ),
        sa.Column(
            "reserved_tokens", sa.BigInteger(), server_default="0", nullable=False
        ),
        _pk("token_budgets"),
        _uq("token_budgets", "uq_token_budgets_org_id", "organization_id", "id"),
        _tfk("fk_token_budgets_subscription", "subscription_id", "core.subscriptions"),
        _ck(
            "token_budgets",
            "counters_non_negative",
            "allowance_tokens >= 0 AND consumed_tokens >= 0 AND reserved_tokens >= 0",
        ),
        _ck(
            "token_budgets",
            "within_allowance",
            "consumed_tokens + reserved_tokens <= allowance_tokens",
        ),
        _ck("token_budgets", "period_valid", "period_end > period_start"),
        schema="core",
    )

    op.create_table(
        "github_installations",
        *_base_cols(),
        sa.Column("organization_id", sa.Uuid(), nullable=False),
        sa.Column("installation_id", sa.BigInteger(), nullable=False),
        sa.Column("account_login", sa.Text(), nullable=False),
        sa.Column("status", sa.Text(), server_default="active", nullable=False),
        _pk("github_installations"),
        sa.ForeignKeyConstraint(
            ["organization_id"],
            ["core.organizations.id"],
            name=op.f("fk_github_installations_org"),
        ),
        _uq(
            "github_installations",
            "uq_github_installations_installation_id",
            "installation_id",
        ),
        _uq(
            "github_installations",
            "uq_github_installations_org_id",
            "organization_id",
            "id",
        ),
        _ck(
            "github_installations",
            "status_valid",
            _in("status", ("active", "suspended", "removed")),
        ),
        schema="core",
    )

    op.create_table(
        "repositories",
        *_base_cols(),
        sa.Column("organization_id", sa.Uuid(), nullable=False),
        sa.Column("installation_id", sa.Uuid(), nullable=False),
        sa.Column("active_snapshot_id", sa.Uuid(), nullable=True),
        sa.Column("github_repository_id", sa.BigInteger(), nullable=False),
        sa.Column("full_name", sa.Text(), nullable=False),
        sa.Column("default_branch", sa.Text(), server_default="main", nullable=False),
        sa.Column(
            "is_enabled", sa.Boolean(), server_default=sa.text("true"), nullable=False
        ),
        _pk("repositories"),
        _uq(
            "repositories",
            "uq_repositories_org_github_id",
            "organization_id",
            "github_repository_id",
        ),
        _uq("repositories", "uq_repositories_org_id", "organization_id", "id"),
        _tfk(
            "fk_repositories_installation",
            "installation_id",
            "core.github_installations",
        ),
        schema="core",
    )

    op.create_table(
        "merge_requests",
        *_base_cols(),
        sa.Column("organization_id", sa.Uuid(), nullable=False),
        sa.Column("repository_id", sa.Uuid(), nullable=False),
        sa.Column("number", sa.BigInteger(), nullable=False),
        sa.Column("title", sa.Text(), nullable=False),
        sa.Column("state", sa.Text(), server_default="open", nullable=False),
        sa.Column("base_sha", sa.Text(), nullable=False),
        sa.Column("head_sha", sa.Text(), nullable=False),
        _pk("merge_requests"),
        _uq(
            "merge_requests", "uq_merge_requests_repo_number", "repository_id", "number"
        ),
        _uq("merge_requests", "uq_merge_requests_org_id", "organization_id", "id"),
        _tfk("fk_merge_requests_repository", "repository_id", "core.repositories"),
        schema="core",
    )

    job_statuses = (
        "queued",
        "preparing",
        "running",
        "completed",
        "partial",
        "failed",
        "cancelled",
        "superseded",
    )
    op.create_table(
        "review_jobs",
        *_base_cols(),
        sa.Column("organization_id", sa.Uuid(), nullable=False),
        sa.Column("merge_request_id", sa.Uuid(), nullable=False),
        sa.Column("run_key", sa.Text(), nullable=False),
        sa.Column("head_sha", sa.Text(), nullable=False),
        sa.Column("base_sha", sa.Text(), nullable=False),
        sa.Column("status", sa.Text(), server_default="queued", nullable=False),
        sa.Column("pipeline_version", sa.Text(), nullable=False),
        sa.Column("prompt_version", sa.Text(), nullable=False),
        sa.Column("config_hash", sa.Text(), nullable=True),
        sa.Column(
            "config", postgresql.JSONB(), server_default=EMPTY_JSON, nullable=False
        ),
        sa.Column("attempts", sa.Integer(), server_default="0", nullable=False),
        sa.Column("next_attempt_at", TS, nullable=True),
        sa.Column("lease_owner", sa.Text(), nullable=True),
        sa.Column("lease_expires_at", TS, nullable=True),
        sa.Column("lease_generation", sa.Integer(), server_default="0", nullable=False),
        sa.Column(
            "dispatch_generation", sa.Integer(), server_default="0", nullable=False
        ),
        sa.Column("error_code", sa.Text(), nullable=True),
        sa.Column("started_at", TS, nullable=True),
        sa.Column("finished_at", TS, nullable=True),
        _pk("review_jobs"),
        _uq("review_jobs", "uq_review_jobs_org_run_key", "organization_id", "run_key"),
        _uq("review_jobs", "uq_review_jobs_org_id", "organization_id", "id"),
        _tfk("fk_review_jobs_merge_request", "merge_request_id", "core.merge_requests"),
        _ck("review_jobs", "status_valid", _in("status", job_statuses)),
        schema="core",
    )
    op.create_index(
        "ix_review_jobs_status_next_attempt",
        "review_jobs",
        ["status", "next_attempt_at"],
        schema="core",
    )
    op.create_index(
        "ix_review_jobs_merge_request_id",
        "review_jobs",
        ["merge_request_id"],
        schema="core",
    )

    # ----------------------------------------------------------------- rag
    op.create_table(
        "repository_snapshots",
        *_base_cols(),
        sa.Column("organization_id", sa.Uuid(), nullable=False),
        sa.Column("repository_id", sa.Uuid(), nullable=False),
        sa.Column("commit_sha", sa.Text(), nullable=False),
        sa.Column("profile_hash", sa.Text(), nullable=False),
        sa.Column("embedding_model", sa.Text(), nullable=False),
        sa.Column("embedding_dim", sa.Integer(), nullable=False),
        sa.Column("status", sa.Text(), server_default="queued", nullable=False),
        sa.Column("attempts", sa.Integer(), server_default="0", nullable=False),
        sa.Column("next_attempt_at", TS, nullable=True),
        sa.Column("lease_owner", sa.Text(), nullable=True),
        sa.Column("lease_expires_at", TS, nullable=True),
        sa.Column("lease_generation", sa.Integer(), server_default="0", nullable=False),
        _pk("repository_snapshots"),
        _uq(
            "repository_snapshots",
            "uq_repository_snapshots_repo_sha_profile",
            "repository_id",
            "commit_sha",
            "profile_hash",
        ),
        _uq(
            "repository_snapshots",
            "uq_repository_snapshots_org_id",
            "organization_id",
            "id",
        ),
        _uq(
            "repository_snapshots",
            "uq_repository_snapshots_org_repo_id",
            "organization_id",
            "repository_id",
            "id",
        ),
        _tfk(
            "fk_repository_snapshots_repository", "repository_id", "core.repositories"
        ),
        _ck(
            "repository_snapshots",
            "status_valid",
            _in("status", ("queued", "building", "ready", "failed")),
        ),
        schema="rag",
    )
    op.create_index(
        "ix_repository_snapshots_status_next_attempt",
        "repository_snapshots",
        ["status", "next_attempt_at"],
        schema="rag",
    )

    # ------------------------------------------------- core (budget, results)
    op.create_table(
        "token_reservations",
        *_base_cols(),
        sa.Column("organization_id", sa.Uuid(), nullable=False),
        sa.Column("budget_id", sa.Uuid(), nullable=False),
        sa.Column("review_job_id", sa.Uuid(), nullable=True),
        sa.Column("snapshot_id", sa.Uuid(), nullable=True),
        sa.Column("admission_key", sa.Text(), nullable=False),
        sa.Column("status", sa.Text(), server_default="open", nullable=False),
        sa.Column("granted_tokens", sa.BigInteger(), nullable=False),
        sa.Column(
            "consumed_tokens", sa.BigInteger(), server_default="0", nullable=False
        ),
        sa.Column(
            "released_tokens", sa.BigInteger(), server_default="0", nullable=False
        ),
        sa.Column("remaining_tokens", sa.BigInteger(), nullable=False),
        sa.Column(
            "inflight_tokens", sa.BigInteger(), server_default="0", nullable=False
        ),
        _pk("token_reservations"),
        _uq(
            "token_reservations",
            "uq_token_reservations_org_admission_key",
            "organization_id",
            "admission_key",
        ),
        _uq(
            "token_reservations",
            "uq_token_reservations_org_id",
            "organization_id",
            "id",
        ),
        _tfk("fk_token_reservations_budget", "budget_id", "core.token_budgets"),
        _tfk("fk_token_reservations_review_job", "review_job_id", "core.review_jobs"),
        _tfk(
            "fk_token_reservations_snapshot", "snapshot_id", "rag.repository_snapshots"
        ),
        _ck("token_reservations", "status_valid", _in("status", ("open", "closed"))),
        _ck(
            "token_reservations",
            "single_owner",
            "num_nonnulls(review_job_id, snapshot_id) = 1",
        ),
        _ck(
            "token_reservations",
            "counters_non_negative",
            "granted_tokens >= 0 AND consumed_tokens >= 0 AND released_tokens >= 0 "
            "AND remaining_tokens >= 0 AND inflight_tokens >= 0",
        ),
        _ck(
            "token_reservations",
            "inflight_within_remaining",
            "inflight_tokens <= remaining_tokens",
        ),
        _ck(
            "token_reservations",
            "balance",
            "granted_tokens = consumed_tokens + released_tokens + remaining_tokens",
        ),
        schema="core",
    )
    op.create_index(
        "uq_token_reservations_open_review_job",
        "token_reservations",
        ["review_job_id"],
        unique=True,
        schema="core",
        postgresql_where=sa.text("status = 'open' AND review_job_id IS NOT NULL"),
    )
    op.create_index(
        "uq_token_reservations_open_snapshot",
        "token_reservations",
        ["snapshot_id"],
        unique=True,
        schema="core",
        postgresql_where=sa.text("status = 'open' AND snapshot_id IS NOT NULL"),
    )

    op.create_table(
        "token_usages",
        *_base_cols(),
        sa.Column("organization_id", sa.Uuid(), nullable=False),
        sa.Column("reservation_id", sa.Uuid(), nullable=False),
        sa.Column("request_key", sa.Text(), nullable=False),
        sa.Column("request_hash", sa.Text(), nullable=False),
        sa.Column("provider_request_id", sa.Text(), nullable=True),
        sa.Column("upper_bound_tokens", sa.BigInteger(), nullable=False),
        sa.Column("actual_tokens", sa.BigInteger(), nullable=True),
        sa.Column("status", sa.Text(), server_default="reserved", nullable=False),
        _pk("token_usages"),
        _uq(
            "token_usages",
            "uq_token_usages_org_request_key",
            "organization_id",
            "request_key",
        ),
        _tfk(
            "fk_token_usages_reservation", "reservation_id", "core.token_reservations"
        ),
        _ck(
            "token_usages",
            "status_valid",
            _in("status", ("reserved", "committed", "released", "unknown")),
        ),
        _ck(
            "token_usages",
            "tokens_non_negative",
            "upper_bound_tokens >= 0 AND (actual_tokens IS NULL OR actual_tokens >= 0)",
        ),
        schema="core",
    )

    op.create_table(
        "context_payloads",
        *_base_cols(),
        sa.Column("organization_id", sa.Uuid(), nullable=False),
        sa.Column("review_job_id", sa.Uuid(), nullable=False),
        sa.Column("part_no", sa.Integer(), nullable=False),
        sa.Column("payload", postgresql.JSONB(), nullable=False),
        sa.Column("payload_hash", sa.Text(), nullable=False),
        sa.Column("model", sa.Text(), nullable=False),
        sa.Column(
            "params", postgresql.JSONB(), server_default=EMPTY_JSON, nullable=False
        ),
        sa.Column("expires_at", TS, nullable=True),
        _pk("context_payloads"),
        _uq(
            "context_payloads",
            "uq_context_payloads_job_part",
            "review_job_id",
            "part_no",
        ),
        _uq("context_payloads", "uq_context_payloads_org_id", "organization_id", "id"),
        _tfk("fk_context_payloads_review_job", "review_job_id", "core.review_jobs"),
        _ck("context_payloads", "part_no_non_negative", "part_no >= 0"),
        schema="core",
    )

    op.create_table(
        "findings",
        *_base_cols(),
        sa.Column("organization_id", sa.Uuid(), nullable=False),
        sa.Column("review_job_id", sa.Uuid(), nullable=False),
        sa.Column("context_payload_id", sa.Uuid(), nullable=True),
        sa.Column("fingerprint", sa.Text(), nullable=False),
        sa.Column("path", sa.Text(), nullable=False),
        sa.Column("side", sa.Text(), server_default="RIGHT", nullable=False),
        sa.Column("start_line", sa.Integer(), nullable=False),
        sa.Column("end_line", sa.Integer(), nullable=False),
        sa.Column("category", sa.Text(), nullable=False),
        sa.Column("severity", sa.Text(), nullable=False),
        sa.Column("body", sa.Text(), nullable=False),
        sa.Column("suggestion", sa.Text(), nullable=True),
        _pk("findings"),
        _uq("findings", "uq_findings_job_fingerprint", "review_job_id", "fingerprint"),
        _uq("findings", "uq_findings_org_id", "organization_id", "id"),
        _tfk("fk_findings_review_job", "review_job_id", "core.review_jobs"),
        _tfk(
            "fk_findings_context_payload", "context_payload_id", "core.context_payloads"
        ),
        _ck("findings", "side_valid", "side IN ('LEFT', 'RIGHT')"),
        _ck("findings", "lines_valid", "start_line > 0 AND end_line >= start_line"),
        schema="core",
    )

    op.create_table(
        "publications",
        *_base_cols(),
        sa.Column("organization_id", sa.Uuid(), nullable=False),
        sa.Column("review_job_id", sa.Uuid(), nullable=False),
        sa.Column("batch_no", sa.Integer(), nullable=False),
        sa.Column("status", sa.Text(), server_default="pending", nullable=False),
        sa.Column("payload", postgresql.JSONB(), nullable=False),
        sa.Column("github_review_id", sa.BigInteger(), nullable=True),
        sa.Column("attempts", sa.Integer(), server_default="0", nullable=False),
        sa.Column("next_attempt_at", TS, nullable=True),
        sa.Column("lease_owner", sa.Text(), nullable=True),
        sa.Column("lease_expires_at", TS, nullable=True),
        sa.Column("lease_generation", sa.Integer(), server_default="0", nullable=False),
        _pk("publications"),
        _uq("publications", "uq_publications_job_batch", "review_job_id", "batch_no"),
        _uq("publications", "uq_publications_org_id", "organization_id", "id"),
        _tfk("fk_publications_review_job", "review_job_id", "core.review_jobs"),
        _ck(
            "publications",
            "status_valid",
            _in(
                "status",
                (
                    "pending",
                    "publishing",
                    "published",
                    "retry_wait",
                    "unknown",
                    "failed",
                    "superseded",
                ),
            ),
        ),
        schema="core",
    )
    op.create_index(
        "ix_publications_status_next_attempt",
        "publications",
        ["status", "next_attempt_at"],
        schema="core",
    )

    op.create_table(
        "comments",
        *_base_cols(),
        sa.Column("organization_id", sa.Uuid(), nullable=False),
        sa.Column("publication_id", sa.Uuid(), nullable=False),
        sa.Column("finding_id", sa.Uuid(), nullable=False),
        sa.Column("github_comment_id", sa.BigInteger(), nullable=True),
        sa.Column("status", sa.Text(), server_default="pending", nullable=False),
        _pk("comments"),
        _uq("comments", "uq_comments_finding_id", "finding_id"),
        _tfk("fk_comments_publication", "publication_id", "core.publications"),
        _tfk("fk_comments_finding", "finding_id", "core.findings"),
        _ck(
            "comments",
            "status_valid",
            _in("status", ("pending", "published", "failed")),
        ),
        schema="core",
    )
    op.create_index(
        "ix_comments_publication_id", "comments", ["publication_id"], schema="core"
    )

    # ------------------------------------------------------ rag (chunks, edges)
    op.create_table(
        "code_chunks",
        *_base_cols(),
        sa.Column("organization_id", sa.Uuid(), nullable=False),
        sa.Column("snapshot_id", sa.Uuid(), nullable=False),
        sa.Column("path", sa.Text(), nullable=False),
        sa.Column("start_line", sa.Integer(), nullable=False),
        sa.Column("end_line", sa.Integer(), nullable=False),
        sa.Column("symbol", sa.Text(), nullable=True),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("embedding", Vector(EMBEDDING_DIM), nullable=True),
        _pk("code_chunks"),
        _uq("code_chunks", "uq_code_chunks_org_id", "organization_id", "id"),
        _tfk("fk_code_chunks_snapshot", "snapshot_id", "rag.repository_snapshots"),
        _ck("code_chunks", "lines_valid", "start_line > 0 AND end_line >= start_line"),
        schema="rag",
    )
    op.create_index(
        "ix_code_chunks_snapshot_path",
        "code_chunks",
        ["snapshot_id", "path"],
        schema="rag",
    )

    op.create_table(
        "code_edges",
        *_base_cols(),
        sa.Column("organization_id", sa.Uuid(), nullable=False),
        sa.Column("snapshot_id", sa.Uuid(), nullable=False),
        sa.Column("source_chunk_id", sa.Uuid(), nullable=False),
        sa.Column("target_chunk_id", sa.Uuid(), nullable=True),
        sa.Column("edge_type", sa.Text(), nullable=False),
        sa.Column("target_name", sa.Text(), nullable=True),
        _pk("code_edges"),
        _tfk("fk_code_edges_snapshot", "snapshot_id", "rag.repository_snapshots"),
        _tfk("fk_code_edges_source_chunk", "source_chunk_id", "rag.code_chunks"),
        _tfk("fk_code_edges_target_chunk", "target_chunk_id", "rag.code_chunks"),
        _ck(
            "code_edges",
            "edge_type_valid",
            _in("edge_type", ("call", "import", "inherit", "reference")),
        ),
        schema="rag",
    )
    op.create_index(
        "ix_code_edges_snapshot_id", "code_edges", ["snapshot_id"], schema="rag"
    )
    op.create_index(
        "ix_code_edges_source_chunk_id", "code_edges", ["source_chunk_id"], schema="rag"
    )

    # ------------------------------------------------------------ transport
    op.create_table(
        "webhook_receipts",
        *_base_cols(),
        sa.Column("organization_id", sa.Uuid(), nullable=False),
        sa.Column("delivery_id", sa.Text(), nullable=False),
        sa.Column("event_type", sa.Text(), nullable=False),
        sa.Column("event_hash", sa.Text(), nullable=False),
        sa.Column("outcome", sa.Text(), nullable=False),
        sa.Column("reject_reason", sa.Text(), nullable=True),
        _pk("webhook_receipts"),
        sa.ForeignKeyConstraint(
            ["organization_id"],
            ["core.organizations.id"],
            name=op.f("fk_webhook_receipts_org"),
        ),
        _uq("webhook_receipts", "uq_webhook_receipts_delivery_id", "delivery_id"),
        _ck(
            "webhook_receipts",
            "outcome_valid",
            _in("outcome", ("accepted", "rejected", "duplicate")),
        ),
        schema="transport",
    )

    op.create_table(
        "outbox_events",
        *_base_cols(),
        sa.Column("organization_id", sa.Uuid(), nullable=False),
        sa.Column("event_type", sa.Text(), nullable=False),
        sa.Column("aggregate_type", sa.Text(), nullable=False),
        sa.Column("aggregate_id", sa.Uuid(), nullable=False),
        sa.Column(
            "dispatch_generation", sa.Integer(), server_default="0", nullable=False
        ),
        sa.Column("available_at", TS, server_default=sa.text("now()"), nullable=False),
        sa.Column("published_at", TS, nullable=True),
        sa.Column("attempts", sa.Integer(), server_default="0", nullable=False),
        _pk("outbox_events"),
        sa.ForeignKeyConstraint(
            ["organization_id"],
            ["core.organizations.id"],
            name=op.f("fk_outbox_events_org"),
        ),
        schema="transport",
    )
    op.create_index(
        "ix_outbox_events_pending",
        "outbox_events",
        ["available_at"],
        schema="transport",
        postgresql_where=sa.text("published_at IS NULL"),
    )

    # Cyclic reference: repositories -> repository_snapshots -> repositories.
    op.create_foreign_key(
        "fk_repositories_active_snapshot",
        "repositories",
        "repository_snapshots",
        ["organization_id", "id", "active_snapshot_id"],
        ["organization_id", "repository_id", "id"],
        source_schema="core",
        referent_schema="rag",
    )


def downgrade() -> None:
    op.drop_constraint(
        "fk_repositories_active_snapshot",
        "repositories",
        schema="core",
        type_="foreignkey",
    )
    for schema, tables in (
        ("transport", ("outbox_events", "webhook_receipts")),
        ("rag", ("code_edges", "code_chunks")),
        (
            "core",
            (
                "comments",
                "publications",
                "findings",
                "context_payloads",
                "token_usages",
                "token_reservations",
            ),
        ),
        ("rag", ("repository_snapshots",)),
        (
            "core",
            (
                "review_jobs",
                "merge_requests",
                "repositories",
                "github_installations",
                "token_budgets",
                "subscriptions",
                "organizations",
            ),
        ),
    ):
        for table in tables:
            op.drop_table(table, schema=schema)
    for schema in ("transport", "rag", "core"):
        op.execute(f"DROP SCHEMA IF EXISTS {schema}")
    op.execute("DROP EXTENSION IF EXISTS vector")
