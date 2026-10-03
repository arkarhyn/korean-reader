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
