from pathlib import Path

import pytest

from app.config import CONTENT_DIR
from app.content.schema import Episode, load_episode

TESTS_DIR = Path(__file__).parent
LEGACY_EPISODES = ["legacy-001", "legacy-002"]


def episode(ep_id: str) -> Episode:
    return load_episode(CONTENT_DIR / "episodes" / "legacy" / f"{ep_id}.json")


@pytest.fixture(params=LEGACY_EPISODES)
def legacy_episode(request) -> Episode:
    return episode(request.param)


@pytest.fixture
def engine(tmp_path):
    from app.db import make_engine
    from app.db.migrate import upgrade

    eng = make_engine(tmp_path / "test.db")
    upgrade(eng)
    yield eng
    eng.dispose()


@pytest.fixture
def session(engine):
    from app.db import make_sessionmaker

    with make_sessionmaker(engine)() as s:
        yield s


def fake_lookup(lemma: str, pos: str):
    """Stand-in for KrdictClient.lookup: every lemma glosses except 초코 (proper noun)."""
    from app.krdict.client import KrdictEntry, Sense

    if lemma == "초코":
        return None
    return KrdictEntry(target_code=f"t-{lemma}", word=lemma, sup_no=0, pos="명사", origin=None, grade=None,
                       senses=[Sense("", f"en:{lemma}", "", f"ja:{lemma}", "")])
