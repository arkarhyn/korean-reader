"""Word sets (DECISIONS 67): every item resolves to keys the analyzer emits; endpoints flag known items."""

import uuid
from datetime import UTC, datetime

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select

from app.analyzer import analyze
from app.db import get_session, make_sessionmaker
from app.db.models import Lexeme, LexemeState
from app.ingest import get_or_create_lexeme, seed
from app.main import app
from app.word_sets import load_word_sets, word_sets

from .conftest import fake_lookup

# Carrier sentences: the key must be what the analyzer reads in running text, or
# confirming the item would never change coverage.
IN_TEXT = {
    "일월": "일월에 가요.", "삼월": "삼월에 가요.", "유월": "유월에 가요.", "달": "다음 달에 가요.",
    "배우다": "한국어를 배워요.", "오래되다": "오래된 집이에요.", "봄": "봄이 왔어요.", "그날": "그날 밤에 갔어요.",
    "월요일": "월요일에 만나요.", "떡볶이": "떡볶이 먹자.", "보고 싶다": "보고 싶어.", "어떻게": "어떻게 해요?",
}


def test_every_item_resolves():
    sets = load_word_sets()
    assert len(sets) >= 15
    assert all(it.keys for s in sets for it in s.items)


@pytest.mark.parametrize("ko,sentence", IN_TEXT.items())
def test_keys_match_running_text(ko, sentence):
    item = next(it for s in word_sets() for it in s.items if it.ko == ko)
    got = {t.key for t in analyze(sentence) if t.kind == "content"}
    assert set(item.keys) & got, (ko, item.keys, got)


@pytest.fixture
def client(engine):
    maker = make_sessionmaker(engine)
    with maker() as s:
        seed(s, fake_lookup)  # creates lexemes for every set key
        known, _ = get_or_create_lexeme(s, "월요일", "NNG", fake_lookup)
        s.add(LexemeState(lexeme_id=known.id, state="known", source="placement"))
        rank1, _ = get_or_create_lexeme(s, "것", "NNB", fake_lookup)
        rank1.freq_rank = 1
        rank2, _ = get_or_create_lexeme(s, "하다", "VV", fake_lookup)
        rank2.freq_rank = 2
        s.add(LexemeState(lexeme_id=rank2.id, state="known", source="placement"))
        s.commit()

    def override():
        with maker() as s:
            yield s

    app.dependency_overrides[get_session] = override
    yield TestClient(app)
    app.dependency_overrides.clear()


def test_sets_endpoint_flags_known_items(client):
    sets = {s["id"]: s for s in client.get("/api/word-sets").json()}
    days = {it["ko"]: it for it in sets["days"]["items"]}
    assert days["월요일"]["known"] and not days["화요일"]["known"]
    assert len(days["화요일"]["lexeme_ids"]) == 1
    months = {it["ko"]: it for it in sets["months"]["items"]}
    assert len(months["일월"]["lexeme_ids"]) == 2  # 일월/NNG + 월/NNB


def test_common_walk_skips_known_and_pages(client):
    page = client.get("/api/word-sets/common", params={"limit": 5}).json()
    assert page["items"][0]["ko"] == "것"  # rank 1, unknown
    assert all(it["ko"] != "하다" for it in page["items"])  # rank 2, known


def test_confirming_through_set_state_marks_known(client, engine):
    item = next(it for s in client.get("/api/word-sets").json() if s["id"] == "days"
                for it in s["items"] if it["ko"] == "금요일")
    ev = {"id": str(uuid.uuid4()), "ts": datetime.now(UTC).isoformat(), "device": "iphone", "type": "set_state",
          "payload": {"lexeme_id": item["lexeme_ids"][0], "state": "known"}}
    client.post("/api/events/batch", json={"events": [ev]})
    days = next(s for s in client.get("/api/word-sets").json() if s["id"] == "days")
    assert next(it for it in days["items"] if it["ko"] == "금요일")["known"]
    with make_sessionmaker(engine)() as s:
        st = s.scalar(select(LexemeState).join(Lexeme).where(Lexeme.lemma == "금요일"))
        assert (st.state, st.source) == ("known", "manual")
