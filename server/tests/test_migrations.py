from sqlalchemy import inspect

from app.db.models import Base


def test_upgrade_head_creates_every_table(engine):
    assert set(Base.metadata.tables) <= set(inspect(engine).get_table_names())


def test_upgrade_is_rerunnable(engine):
    from app.db.migrate import upgrade

    upgrade(engine)  # already at head -> no-op
