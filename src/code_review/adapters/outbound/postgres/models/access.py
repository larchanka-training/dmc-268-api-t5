"""PostgreSQL mappings; see docs/DATABASE_SCHEMA.md for the storage contract."""

from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import (
    BigInteger,
    CheckConstraint,
    DateTime,
    ForeignKeyConstraint,
    Index,
    Text,
    UniqueConstraint,
    Uuid,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column

from code_review.adapters.outbound.postgres.base import Base


class User(Base):
    """User storage record."""

    __tablename__ = "user"
    __table_args__ = (CheckConstraint("state IN ('active', 'suspended')", name="state"),)

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    state: Mapped[str] = mapped_column(Text)
    display_name: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=text("now()")
    )


class ExternalIdentity(Base):
    """ExternalIdentity storage record."""

    __tablename__ = "external_identity"
    __table_args__ = (
        ForeignKeyConstraint(["user_id"], ["user.id"], name="fk_external_identity_user_id"),
        UniqueConstraint("provider_host", "external_user_id"),
    )

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    user_id: Mapped[UUID] = mapped_column(Uuid)
    provider_host: Mapped[str] = mapped_column(Text)
    external_user_id: Mapped[int] = mapped_column(BigInteger)
    user_grant_ref: Mapped[str | None] = mapped_column(Text)
    access_checked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class AuthSession(Base):
    """AuthSession storage record."""

    __tablename__ = "auth_session"
    __table_args__ = (
        ForeignKeyConstraint(["user_id"], ["user.id"], name="fk_auth_session_user_id"),
        UniqueConstraint("token_hash"),
    )

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    user_id: Mapped[UUID] = mapped_column(Uuid)
    token_hash: Mapped[str] = mapped_column(Text)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class Workspace(Base):
    """Workspace storage record."""

    __tablename__ = "workspace"
    __table_args__ = (
        CheckConstraint("state IN ('active', 'disabled', 'deleting')", name="state"),
        CheckConstraint("access_epoch >= 0", name="access_epoch_nonnegative"),
    )

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    name: Mapped[str] = mapped_column(Text)
    state: Mapped[str] = mapped_column(Text)
    access_epoch: Mapped[int] = mapped_column(BigInteger)


class Membership(Base):
    """Membership storage record."""

    __tablename__ = "membership"
    __table_args__ = (
        ForeignKeyConstraint(["tenant_id"], ["workspace.id"], name="fk_membership_tenant_id"),
        UniqueConstraint("tenant_id", "id"),
        CheckConstraint(
            "role IN ('owner', 'admin', 'member', 'viewer', 'billing_manager')", name="role"
        ),
        CheckConstraint("state IN ('active', 'suspended', 'revoked')", name="state"),
        CheckConstraint("access_epoch >= 0", name="access_epoch_nonnegative"),
        ForeignKeyConstraint(["user_id"], ["user.id"], name="fk_membership_user_id"),
        UniqueConstraint("tenant_id", "user_id"),
    )

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    tenant_id: Mapped[UUID] = mapped_column(Uuid)
    user_id: Mapped[UUID] = mapped_column(Uuid)
    role: Mapped[str] = mapped_column(Text)
    state: Mapped[str] = mapped_column(Text)
    access_epoch: Mapped[int] = mapped_column(BigInteger)


class WorkspaceInvitation(Base):
    """WorkspaceInvitation storage record."""

    __tablename__ = "workspace_invitation"
    __table_args__ = (
        ForeignKeyConstraint(
            ["tenant_id"], ["workspace.id"], name="fk_workspace_invitation_tenant_id"
        ),
        UniqueConstraint("tenant_id", "id"),
        CheckConstraint("state IN ('pending', 'accepted', 'expired', 'revoked')", name="state"),
        ForeignKeyConstraint(
            ["tenant_id", "invited_by_id"],
            ["membership.tenant_id", "membership.id"],
            name="fk_workspace_invitation_invited_by_id",
        ),
        ForeignKeyConstraint(
            ["tenant_id", "accepted_membership_id"],
            ["membership.tenant_id", "membership.id"],
            name="fk_workspace_invitation_accepted_membership_id",
        ),
        UniqueConstraint("token_hash"),
    )

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    tenant_id: Mapped[UUID] = mapped_column(Uuid)
    invited_by_id: Mapped[UUID] = mapped_column(Uuid)
    expected_github_user_id: Mapped[int] = mapped_column(BigInteger)
    role: Mapped[str] = mapped_column(Text)
    token_hash: Mapped[str] = mapped_column(Text)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    accepted_membership_id: Mapped[UUID | None] = mapped_column(Uuid)
    state: Mapped[str] = mapped_column(Text)


class ServiceAccount(Base):
    """ServiceAccount storage record."""

    __tablename__ = "service_account"
    __table_args__ = (
        ForeignKeyConstraint(["tenant_id"], ["workspace.id"], name="fk_service_account_tenant_id"),
        UniqueConstraint("tenant_id", "id"),
        CheckConstraint("state IN ('active', 'disabled')", name="state"),
        CheckConstraint("access_epoch >= 0", name="access_epoch_nonnegative"),
        ForeignKeyConstraint(
            ["tenant_id", "authorized_by_id"],
            ["membership.tenant_id", "membership.id"],
            name="fk_service_account_authorized_by_id",
        ),
    )

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    tenant_id: Mapped[UUID] = mapped_column(Uuid)
    name: Mapped[str] = mapped_column(Text)
    state: Mapped[str] = mapped_column(Text)
    access_epoch: Mapped[int] = mapped_column(BigInteger)
    authorized_by_id: Mapped[UUID] = mapped_column(Uuid)


class GitIntegration(Base):
    """GitIntegration storage record."""

    __tablename__ = "git_integration"
    __table_args__ = (
        ForeignKeyConstraint(["tenant_id"], ["workspace.id"], name="fk_git_integration_tenant_id"),
        UniqueConstraint("tenant_id", "id"),
        CheckConstraint("state IN ('pending', 'active', 'suspended', 'removed')", name="state"),
        CheckConstraint("access_epoch >= 0", name="access_epoch_nonnegative"),
        UniqueConstraint("provider_host", "app_config_key", "installation_id"),
    )

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    tenant_id: Mapped[UUID] = mapped_column(Uuid)
    provider_host: Mapped[str] = mapped_column(Text)
    app_config_key: Mapped[str] = mapped_column(Text)
    installation_id: Mapped[int] = mapped_column(BigInteger)
    state: Mapped[str] = mapped_column(Text)
    access_epoch: Mapped[int] = mapped_column(BigInteger)
    verified_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class GitConnectionSession(Base):
    """GitConnectionSession storage record."""

    __tablename__ = "git_connection_session"
    __table_args__ = (
        ForeignKeyConstraint(
            ["tenant_id"], ["workspace.id"], name="fk_git_connection_session_tenant_id"
        ),
        UniqueConstraint("tenant_id", "id"),
        CheckConstraint(
            "state IN ('pending', 'authorized', 'completed', 'rejected')", name="state"
        ),
        ForeignKeyConstraint(
            ["tenant_id", "initiator_id"],
            ["membership.tenant_id", "membership.id"],
            name="fk_git_connection_session_initiator_id",
        ),
        UniqueConstraint("oauth_state_hash"),
    )

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    tenant_id: Mapped[UUID] = mapped_column(Uuid)
    initiator_id: Mapped[UUID] = mapped_column(Uuid)
    oauth_state_hash: Mapped[str] = mapped_column(Text)
    pkce_ref: Mapped[str] = mapped_column(Text)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    state: Mapped[str] = mapped_column(Text)


class Repository(Base):
    """Repository storage record."""

    __tablename__ = "repository"
    __table_args__ = (
        ForeignKeyConstraint(["tenant_id"], ["workspace.id"], name="fk_repository_tenant_id"),
        UniqueConstraint("tenant_id", "id"),
        CheckConstraint("state IN ('active', 'disabled', 'deleting')", name="state"),
        CheckConstraint("access_epoch >= 0", name="access_epoch_nonnegative"),
        ForeignKeyConstraint(
            ["tenant_id", "integration_id"],
            ["git_integration.tenant_id", "git_integration.id"],
            name="fk_repository_integration_id",
        ),
        UniqueConstraint("tenant_id", "integration_id", "external_id"),
    )

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    tenant_id: Mapped[UUID] = mapped_column(Uuid)
    integration_id: Mapped[UUID] = mapped_column(Uuid)
    external_id: Mapped[int] = mapped_column(BigInteger)
    full_name: Mapped[str] = mapped_column(Text)
    state: Mapped[str] = mapped_column(Text)
    access_epoch: Mapped[int] = mapped_column(BigInteger)


class RepositoryGrant(Base):
    """RepositoryGrant storage record."""

    __tablename__ = "repository_grant"
    __table_args__ = (
        ForeignKeyConstraint(["tenant_id"], ["workspace.id"], name="fk_repository_grant_tenant_id"),
        UniqueConstraint("tenant_id", "id"),
        CheckConstraint("permission IN ('read', 'review', 'manage')", name="permission"),
        CheckConstraint("state IN ('active', 'revoked')", name="state"),
        ForeignKeyConstraint(
            ["tenant_id", "repository_id"],
            ["repository.tenant_id", "repository.id"],
            name="fk_repository_grant_repository_id",
        ),
        ForeignKeyConstraint(
            ["tenant_id", "membership_id"],
            ["membership.tenant_id", "membership.id"],
            name="fk_repository_grant_membership_id",
        ),
        ForeignKeyConstraint(
            ["tenant_id", "service_account_id"],
            ["service_account.tenant_id", "service_account.id"],
            name="fk_repository_grant_service_account_id",
        ),
        CheckConstraint(
            "(membership_id IS NOT NULL) <> (service_account_id IS NOT NULL)", name="one_actor"
        ),
        Index(
            "uq_repository_grant_membership_id",
            "tenant_id",
            "repository_id",
            "membership_id",
            unique=True,
            postgresql_where=text("membership_id IS NOT NULL"),
        ),
        Index(
            "uq_repository_grant_service_account_id",
            "tenant_id",
            "repository_id",
            "service_account_id",
            unique=True,
            postgresql_where=text("service_account_id IS NOT NULL"),
        ),
    )

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    tenant_id: Mapped[UUID] = mapped_column(Uuid)
    repository_id: Mapped[UUID] = mapped_column(Uuid)
    membership_id: Mapped[UUID | None] = mapped_column(Uuid)
    service_account_id: Mapped[UUID | None] = mapped_column(Uuid)
    permission: Mapped[str] = mapped_column(Text)
    state: Mapped[str] = mapped_column(Text)
