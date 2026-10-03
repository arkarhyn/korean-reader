import re
import sqlite3

import pytest

from app.config import LEGACY_DB

LEGACY_IDS = {"legacy-001": 20, "legacy-002": 21}


def norm(s: str) -> str:
    return re.sub(r"\s+", " ", s).strip()


def test_schema(legacy_episode):
    assert legacy_episode.series == "legacy"
    assert len(legacy_episode.paragraphs) >= 1
    assert 3 <= len(legacy_episode.questions) <= 6
    assert legacy_episode.source == f"legacy:passage/{LEGACY_IDS[legacy_episode.id]}"


@pytest.mark.skipif(not LEGACY_DB.exists(), reason="legacy vocab.db not present (gitignored)")
def test_korean_matches_legacy_db(legacy_episode):
    conn = sqlite3.connect(f"file:{LEGACY_DB}?mode=ro", uri=True)
    (content,) = conn.execute("SELECT content FROM passages WHERE id = ?",
                              (LEGACY_IDS[legacy_episode.id],)).fetchone()
    assert norm(legacy_episode.text_ko) == norm(content)
