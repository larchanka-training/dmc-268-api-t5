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


class BillingAccount(Base):
    """BillingAccount storage record."""

    __tablename__ = "billing_account"
    __table_args__ = (
        ForeignKeyConstraint(["tenant_id"], ["workspace.id"], name="fk_billing_account_tenant_id"),
        UniqueConstraint("tenant_id", "id"),
        CheckConstraint("state IN ('active', 'blocked')", name="state"),
        UniqueConstraint("tenant_id"),
    )

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    tenant_id: Mapped[UUID] = mapped_column(Uuid)
    state: Mapped[str] = mapped_column(Text)
    billing_details: Mapped[dict[str, Any]] = mapped_column(JSONB)


class Subscription(Base):
    """Subscription storage record."""

    __tablename__ = "subscription"
    __table_args__ = (
        ForeignKeyConstraint(["tenant_id"], ["workspace.id"], name="fk_subscription_tenant_id"),
        UniqueConstraint("tenant_id", "id"),
        CheckConstraint("renewal_mode IN ('automatic', 'manual')", name="renewal_mode"),
        CheckConstraint(
            "state IN ('pending', 'active', 'past_due', 'cancelled', 'expired')", name="state"
        ),
        ForeignKeyConstraint(
            ["tenant_id", "billing_account_id"],
            ["billing_account.tenant_id", "billing_account.id"],
            name="fk_subscription_billing_account_id",
        ),
        UniqueConstraint("tenant_id", "id", "billing_account_id"),
        Index(
            "uq_subscription_external",
            "provider_scope",
            "external_subscription_id",
            unique=True,
            postgresql_where=text("external_subscription_id IS NOT NULL"),
        ),
        CheckConstraint("period_end > period_start", name="period"),
    )

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    tenant_id: Mapped[UUID] = mapped_column(Uuid)
    billing_account_id: Mapped[UUID] = mapped_column(Uuid)
    provider: Mapped[str] = mapped_column(Text)
    provider_scope: Mapped[str] = mapped_column(Text)
    external_subscription_id: Mapped[str | None] = mapped_column(Text)
    renewal_mode: Mapped[str] = mapped_column(Text)
    product_snapshot: Mapped[dict[str, Any]] = mapped_column(JSONB)
    period_start: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    period_end: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    state: Mapped[str] = mapped_column(Text)


class Purchase(Base):
    """Purchase storage record."""

    __tablename__ = "purchase"
    __table_args__ = (
        ForeignKeyConstraint(["tenant_id"], ["workspace.id"], name="fk_purchase_tenant_id"),
        UniqueConstraint("tenant_id", "id"),
        CheckConstraint(
            "state IN ('awaiting_payment', 'fulfilled', 'cancelled', 'review_required')",
            name="state",
        ),
        CheckConstraint("amount_minor >= 0", name="amount_minor_nonnegative"),
        ForeignKeyConstraint(
            ["tenant_id", "billing_account_id"],
            ["billing_account.tenant_id", "billing_account.id"],
            name="fk_purchase_billing_account_id",
        ),
        ForeignKeyConstraint(
            ["tenant_id", "created_by_id"],
            ["membership.tenant_id", "membership.id"],
            name="fk_purchase_created_by_id",
        ),
        ForeignKeyConstraint(
            ["tenant_id", "subscription_id", "billing_account_id"],
            ["subscription.tenant_id", "subscription.id", "subscription.billing_account_id"],
            name="fk_purchase_subscription_id_billing_account_id",
        ),
        ForeignKeyConstraint(
            ["tenant_id", "accepted_payment_id", "id"],
            ["payment.tenant_id", "payment.id", "payment.purchase_id"],
            name="fk_purchase_accepted_payment_id_id",
            use_alter=True,
        ),
        UniqueConstraint("tenant_id", "id", "billing_account_id"),
        Index(
            "uq_purchase_renewal",
            "tenant_id",
            "subscription_id",
            "period_start",
            unique=True,
            postgresql_where=text("subscription_id IS NOT NULL AND period_start IS NOT NULL"),
        ),
    )

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    tenant_id: Mapped[UUID] = mapped_column(Uuid)
    billing_account_id: Mapped[UUID] = mapped_column(Uuid)
    created_by_id: Mapped[UUID | None] = mapped_column(Uuid)
    subscription_id: Mapped[UUID | None] = mapped_column(Uuid)
    period_start: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    product_snapshot: Mapped[dict[str, Any]] = mapped_column(JSONB)
    amount_minor: Mapped[int] = mapped_column(BigInteger)
    currency: Mapped[str] = mapped_column(Text)
    accepted_payment_id: Mapped[UUID | None] = mapped_column(Uuid)
    state: Mapped[str] = mapped_column(Text)


class Payment(Base):
    """Payment storage record."""

    __tablename__ = "payment"
    __table_args__ = (
        ForeignKeyConstraint(["tenant_id"], ["workspace.id"], name="fk_payment_tenant_id"),
        UniqueConstraint("tenant_id", "id"),
        CheckConstraint(
            "state IN ('creating', 'pending', 'processing', 'payment_unknown', "
            "'succeeded', 'failed', 'cancelled')",
            name="state",
        ),
        CheckConstraint("sequence_no > 0", name="sequence_no_positive"),
        CheckConstraint("expected_amount >= 0", name="expected_amount_nonnegative"),
        Index("ix_payment_available", "state", "available_at"),
        Index(
            "ix_payment_lease", "locked_until", postgresql_where=text("locked_until IS NOT NULL")
        ),
        ForeignKeyConstraint(
            ["tenant_id", "purchase_id"],
            ["purchase.tenant_id", "purchase.id"],
            name="fk_payment_purchase_id",
        ),
        UniqueConstraint("tenant_id", "id", "purchase_id"),
        UniqueConstraint("tenant_id", "purchase_id", "sequence_no"),
        UniqueConstraint("provider_scope", "idempotency_key"),
        Index(
            "uq_payment_external",
            "provider_scope",
            "external_payment_id",
            unique=True,
            postgresql_where=text("external_payment_id IS NOT NULL"),
        ),
        Index(
            "uq_payment_open_purchase",
            "tenant_id",
            "purchase_id",
            unique=True,
            postgresql_where=text(
                "state IN ('creating', 'pending', 'processing', 'payment_unknown')"
            ),
        ),
    )

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    tenant_id: Mapped[UUID] = mapped_column(Uuid)
    purchase_id: Mapped[UUID] = mapped_column(Uuid)
    sequence_no: Mapped[int] = mapped_column(Integer)
    provider: Mapped[str] = mapped_column(Text)
    provider_scope: Mapped[str] = mapped_column(Text)
    external_payment_id: Mapped[str | None] = mapped_column(Text)
    idempotency_key: Mapped[str] = mapped_column(Text)
    request_hash: Mapped[str] = mapped_column(Text)
    expected_amount: Mapped[int] = mapped_column(BigInteger)
    currency: Mapped[str] = mapped_column(Text)
    state: Mapped[str] = mapped_column(Text)
    lease_token: Mapped[UUID | None] = mapped_column(Uuid)
    locked_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    available_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class Entitlement(Base):
    """Entitlement storage record."""

    __tablename__ = "entitlement"
    __table_args__ = (
        ForeignKeyConstraint(["tenant_id"], ["workspace.id"], name="fk_entitlement_tenant_id"),
        UniqueConstraint("tenant_id", "id"),
        CheckConstraint("state IN ('active', 'revoked', 'expired')", name="state"),
        CheckConstraint("total_units >= 0", name="total_units_nonnegative"),
        CheckConstraint("reserved_units >= 0", name="reserved_units_nonnegative"),
        CheckConstraint("consumed_units >= 0", name="consumed_units_nonnegative"),
        ForeignKeyConstraint(
            ["tenant_id", "billing_account_id"],
            ["billing_account.tenant_id", "billing_account.id"],
            name="fk_entitlement_billing_account_id",
        ),
        ForeignKeyConstraint(
            ["tenant_id", "source_purchase_id", "billing_account_id"],
            ["purchase.tenant_id", "purchase.id", "purchase.billing_account_id"],
            name="fk_entitlement_source_purchase_id_billing_account_id",
        ),
        UniqueConstraint("tenant_id", "source_purchase_id"),
        UniqueConstraint("tenant_id", "id", "billing_account_id"),
        CheckConstraint("reserved_units + consumed_units <= total_units", name="capacity"),
    )

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    tenant_id: Mapped[UUID] = mapped_column(Uuid)
    billing_account_id: Mapped[UUID] = mapped_column(Uuid)
    source_purchase_id: Mapped[UUID] = mapped_column(Uuid)
    total_units: Mapped[int] = mapped_column(BigInteger)
    reserved_units: Mapped[int] = mapped_column(BigInteger)
    consumed_units: Mapped[int] = mapped_column(BigInteger)
    valid_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    state: Mapped[str] = mapped_column(Text)


class UsageReservation(Base):
    """UsageReservation storage record."""

    __tablename__ = "usage_reservation"
    __table_args__ = (
        ForeignKeyConstraint(
            ["tenant_id"], ["workspace.id"], name="fk_usage_reservation_tenant_id"
        ),
        UniqueConstraint("tenant_id", "id"),
        CheckConstraint("state IN ('reserved', 'consumed', 'released')", name="state"),
        CheckConstraint("units > 0", name="units_positive"),
        ForeignKeyConstraint(
            ["tenant_id", "request_id"],
            ["review_request.tenant_id", "review_request.id"],
            name="fk_usage_reservation_request_id",
        ),
        ForeignKeyConstraint(
            ["tenant_id", "entitlement_id"],
            ["entitlement.tenant_id", "entitlement.id"],
            name="fk_usage_reservation_entitlement_id",
        ),
        UniqueConstraint("tenant_id", "request_id"),
        UniqueConstraint("tenant_id", "id", "entitlement_id"),
        CheckConstraint(
            "(state = 'reserved' AND settled_at IS NULL) OR (state IN ('consumed', "
            "'released') AND settled_at IS NOT NULL)",
            name="settlement",
        ),
    )

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    tenant_id: Mapped[UUID] = mapped_column(Uuid)
    request_id: Mapped[UUID] = mapped_column(Uuid)
    entitlement_id: Mapped[UUID] = mapped_column(Uuid)
    units: Mapped[int] = mapped_column(BigInteger)
    state: Mapped[str] = mapped_column(Text)
    settled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class BillingEntry(Base):
    """BillingEntry storage record."""

    __tablename__ = "billing_entry"
    __table_args__ = (
        ForeignKeyConstraint(["tenant_id"], ["workspace.id"], name="fk_billing_entry_tenant_id"),
        UniqueConstraint("tenant_id", "id"),
        CheckConstraint(
            "kind IN ('grant', 'reserve', 'consume', 'release', 'adjustment')", name="kind"
        ),
        ForeignKeyConstraint(
            ["tenant_id", "billing_account_id"],
            ["billing_account.tenant_id", "billing_account.id"],
            name="fk_billing_entry_billing_account_id",
        ),
        ForeignKeyConstraint(
            ["tenant_id", "entitlement_id", "billing_account_id"],
            ["entitlement.tenant_id", "entitlement.id", "entitlement.billing_account_id"],
            name="fk_billing_entry_entitlement_id_billing_account_id",
        ),
        ForeignKeyConstraint(
            ["tenant_id", "reservation_id", "entitlement_id"],
            [
                "usage_reservation.tenant_id",
                "usage_reservation.id",
                "usage_reservation.entitlement_id",
            ],
            name="fk_billing_entry_reservation_id_entitlement_id",
        ),
        UniqueConstraint("tenant_id", "billing_account_id", "business_key"),
        Index(
            "uq_billing_entry_settlement",
            "tenant_id",
            "reservation_id",
            unique=True,
            postgresql_where=text("kind IN ('consume', 'release')"),
        ),
        CheckConstraint(
            "kind NOT IN ('reserve', 'consume', 'release') OR reservation_id IS NOT NULL",
            name="reservation_kind",
        ),
    )

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    tenant_id: Mapped[UUID] = mapped_column(Uuid)
    billing_account_id: Mapped[UUID] = mapped_column(Uuid)
    entitlement_id: Mapped[UUID] = mapped_column(Uuid)
    reservation_id: Mapped[UUID | None] = mapped_column(Uuid)
    kind: Mapped[str] = mapped_column(Text)
    quantity: Mapped[int] = mapped_column(BigInteger)
    business_key: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=text("now()")
    )
