import uuid
from datetime import datetime

from sqlalchemy import (
    CheckConstraint,
    ForeignKey,
    Index,
    Integer,
    Text,
    UniqueConstraint,
    Uuid,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.infrastructure.db.base import (
    CORE,
    TRANSPORT,
    Base,
    IdMixin,
    TimestampMixin,
    in_list,
)

RECEIPT_OUTCOMES = ("accepted", "rejected", "duplicate")


class WebhookReceipt(IdMixin, TimestampMixin, Base):
    """Accepted or rejected GitHub delivery; protects against redelivery."""

    __tablename__ = "webhook_receipts"
    __table_args__ = (
        UniqueConstraint("delivery_id", name="uq_webhook_receipts_delivery_id"),
        CheckConstraint(in_list("outcome", RECEIPT_OUTCOMES), name="outcome_valid"),
        {"schema": TRANSPORT},
    )

    organization_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey(f"{CORE}.organizations.id", name="fk_webhook_receipts_org")
    )
    delivery_id: Mapped[str] = mapped_column(Text)
    event_type: Mapped[str] = mapped_column(Text)
    event_hash: Mapped[str] = mapped_column(Text)
    outcome: Mapped[str] = mapped_column(Text)
    reject_reason: Mapped[str | None] = mapped_column(Text)


class OutboxEvent(IdMixin, TimestampMixin, Base):
    """Message to be sent to RabbitMQ, written in the same transaction as the job.

    ``aggregate_id`` points to different job types, so it has no FK; dispatch
    checks the type, owner and existence of the record.
    """

    __tablename__ = "outbox_events"
    __table_args__ = (
        Index(
            "ix_outbox_events_pending",
            "available_at",
            postgresql_where=text("published_at IS NULL"),
        ),
        {"schema": TRANSPORT},
    )

    organization_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey(f"{CORE}.organizations.id", name="fk_outbox_events_org")
    )
    event_type: Mapped[str] = mapped_column(Text)
    aggregate_type: Mapped[str] = mapped_column(Text)
    aggregate_id: Mapped[uuid.UUID] = mapped_column(Uuid)
    dispatch_generation: Mapped[int] = mapped_column(Integer, server_default="0")
    available_at: Mapped[datetime] = mapped_column(server_default=text("now()"))
    published_at: Mapped[datetime | None]
    attempts: Mapped[int] = mapped_column(Integer, server_default="0")
