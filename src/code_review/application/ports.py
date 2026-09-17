"""Transaction boundary used by application scenarios, independent of the ORM.

Repository, GitReader, CommentPublisher, ReviewModel and PaymentGateway ports
will be introduced with their use cases; their planned responsibilities are
in BACKEND_ARCHITECTURE.md. Repositories must never commit implicitly.
"""

from typing import Protocol


class UnitOfWork(Protocol):
    async def commit(self) -> None:
        """Explicitly persist one local application transaction."""

    async def rollback(self) -> None:
        """Discard the current local transaction."""
