"""Local krdict dump index (app/krdict/local.py) against a hand-made LMF sample."""

import pytest

from app.ingest import first_of
from app.krdict.local import LocalDict, build, parse_dump

from .conftest import TESTS_DIR

SAMPLE = TESTS_DIR / "fixtures" / "krdict_dump" / "sample.xml"


@pytest.fixture
def local(tmp_path):
    db = tmp_path / "local.sqlite"
    assert build(db, [SAMPLE]) == 3  # the idiom is skipped
    d = LocalDict(db)
    yield d
    d.close()


def test_parse_tolerates_raw_angle_brackets_and_skips_phrases():
    entries = list(parse_dump(SAMPLE))
    assert [e.word for e in entries] == ["시간", "쓰다", "쓰다"]


def test_lookup_matches_api_shape(local):
    e = local.lookup("시간", "NNG")
    assert (e.target_code, e.gloss_en, e.gloss_ja, e.hanja, e.grade, e.sup_no) == \
        ("62841", "time", "じかん【時間】", "時間", "초급", 0)


def test_lookup_picks_homograph_by_pos(local):
    assert local.lookup("쓰다", "VV").gloss_en == "write"
    bitter = local.lookup("쓰다", "VA")
    assert bitter.gloss_en == "bitter" and bitter.grade is None and bitter.sup_no == 3


def test_missing_word(local):
    assert local.lookup("없는단어", "NNG") is None


def test_first_of_falls_through(local):
    calls = []

    def fallback(lemma, pos):
        calls.append(lemma)
        return local.lookup("시간", "NNG")

    lookup = first_of(local.lookup, None, fallback)
    assert lookup("쓰다", "VV").gloss_en == "write" and calls == []
    assert lookup("말씀드리다", "VV").gloss_en == "time" and calls == ["말씀드리다"]


def test_missing_index_says_how_to_build(tmp_path):
    with pytest.raises(FileNotFoundError, match="build_krdict_local"):
        LocalDict(tmp_path / "nope.sqlite")
