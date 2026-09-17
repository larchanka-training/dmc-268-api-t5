"""A local transaction is committed only by an explicit application decision."""

from uuid import uuid4

import pytest
from sqlalchemy import select, text

from code_review.adapters.outbound.postgres import models as m
from code_review.adapters.outbound.postgres.session import create_session_factory
from code_review.adapters.outbound.postgres.unit_of_work import SqlAlchemyUnitOfWork

pytestmark = pytest.mark.postgres


async def test_commit_rollback_and_exception(database):
    with database.connect() as conn:
        schema = conn.scalar(text("SELECT current_schema()"))
    url = database.url.update_query_dict({"options": f"-csearch_path={schema}"})
    engine, factory = create_session_factory(url)
    ids = [uuid4() for _ in range(3)]
    try:
        async with SqlAlchemyUnitOfWork(factory) as uow:
            uow.session.add(m.User(id=ids[0], state="active", display_name="Committed"))
            await uow.commit()
        async with SqlAlchemyUnitOfWork(factory) as uow:
            uow.session.add(m.User(id=ids[1], state="active", display_name="Rolled back"))
            await uow.session.flush()
        with pytest.raises(ValueError, match="scenario failed"):
            async with SqlAlchemyUnitOfWork(factory) as uow:
                uow.session.add(m.User(id=ids[2], state="active", display_name="Failed"))
                await uow.session.flush()
                raise ValueError("scenario failed")
        async with factory() as session:
            actual = (await session.scalars(select(m.User.id).where(m.User.id.in_(ids)))).all()
            assert actual == [ids[0]]
    finally:
        await engine.dispose()
