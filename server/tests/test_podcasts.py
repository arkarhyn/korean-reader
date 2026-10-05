"""Stage 7 podcast parts: schema, conversion, ingest, due-only grading, API (DECISIONS 84-88)."""

from datetime import timedelta

import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError
from sqlalchemy import select

from app.content.schema import Episode as EpisodeDoc
from app.db import get_session, make_sessionmaker
from app.db.models import ContextSentence, Episode, EpisodeParagraph
from app.ingest import ingest_episode
from app.main import app
from app.podcasts import part_docs, turn_paragraph
from app.review import review_items
from app.srs import known_until, load_card

from .conftest import fake_lookup
from .test_srs import T0, add, complete, ev, setup_db, st

LINES = ["반찬이 정말 맛있습니다", "김치도 좋습니다", "서윤아 밥 먹었습니다"]


def prepared(order=7, show_no=7) -> dict:
    turn = {"speaker": "디디", "start_ms": 0, "end_ms": 9000, "en": "The side dishes are good. Kimchi too.",
            "lines": [{"start_ms": i * 3000, "end_ms": i * 3000 + 2500, "ko": ko, "en": f"line {i}"}
                      for i, ko in enumerate(LINES)]}
    other = {"speaker": "태웅", "uncertain": True, "start_ms": 9000, "end_ms": 11000, "en": "",
             "lines": [{"start_ms": 9000, "end_ms": 11000, "ko": "정말요", "en": ""}]}
    return {"id": "abc", "title": "Episode title", "url": "https://www.youtube.com/watch?v=VIDEO123", "order": order,
            "show_no": show_no,
            "parts": [{"part": 1, "title_ko": "반찬 이야기", "title_en": "Side dishes", "start_ms": 0, "end_ms": 11000,
                       "turns": [turn, other]}]}


def podcast_doc(order=7) -> EpisodeDoc:
    return part_docs("didi-taewoong", prepared(order))[0]


def test_turn_paragraph_keeps_line_offsets():
    p = turn_paragraph(prepared()["parts"][0]["turns"][0])
    assert p["ko"] == "\n".join(LINES)
    assert [ln["s"] for ln in p["meta"]["lines"]] == [0, len(LINES[0]) + 1, len(LINES[0]) + len(LINES[1]) + 2]
    assert p["meta"]["speaker"] == "디디" and "uncertain" not in p["meta"]


def test_part_docs():
    doc = podcast_doc()
    assert doc.id == "pod-dt-07-p1" and doc.series == "podcast" and doc.source == "youtube:VIDEO123"
    assert doc.media["video_id"] == "VIDEO123" and doc.media["parts"] == 1 and doc.media["order"] == 7
    assert doc.paragraphs[1].meta["uncertain"] is True and doc.paragraphs[1].en == ""
    assert part_docs("didi-taewoong", prepared(order=16))[0].register_tags == ["banmal"]


def test_en_required_without_meta():
    with pytest.raises(ValidationError):
        EpisodeDoc(id="x", series="main", title_ko="t", title_en="t", register_tags=[],
                   paragraphs=[{"ko": "밥", "en": ""}])


def test_ingest_stores_media_meta_and_line_contexts(session):
    ingest_episode(session, podcast_doc(), fake_lookup, publish=True)
    ep = session.get(Episode, "pod-dt-07-p1")
    assert ep.media["video_id"] == "VIDEO123"
    para = session.get(EpisodeParagraph, ("pod-dt-07-p1", 0))
    assert para.meta["lines"][1]["en"] == "line 1"
    rows = session.scalars(select(ContextSentence).where(ContextSentence.origin == "episode:pod-dt-07-p1")).all()
    assert rows and {r.sentence_ko for r in rows} <= set(LINES) | {"정말요"}
    kimchi = next(r for r in rows if r.sentence_ko == LINES[1])
    assert kimchi.sentence_en == "line 1" and kimchi.sentence_ko[kimchi.start:kimchi.end].startswith("김치")


@pytest.fixture
def db(session):
    ids = setup_db(session)
    ingest_episode(session, podcast_doc(), fake_lookup, publish=True)
    session.flush()
    return session, ids


def test_podcast_untapped_new_word_gets_no_card(db):
    s, ids = db
    add(s, complete(T0, [], ep="pod-dt-07-p1"))
    assert st(s, ids["김치"]) is None  # a story completion would make this a Good card


def test_podcast_tap_is_again_and_due_word_is_good(db):
    s, ids = db
    add(s, ev("set_state", T0, lexeme_id=ids["밥"], state="learning", prev_state="known"),
        complete(T0 + timedelta(hours=1), [ids["김치"]], ep="pod-dt-07-p1"))
    assert st(s, ids["김치"]).state == "learning"  # tapped -> Again
    assert known_until(load_card(st(s, ids["밥"]).fsrs_card)) > T0 + timedelta(days=1)  # due, untapped -> Good


def test_review_prefers_story_sentences(db):
    s, ids = db
    add(s, ev("set_state", T0, lexeme_id=ids["반찬"], state="learning", prev_state="seen"))
    items = {it["lexeme_id"]: it for it in review_items(s)}
    if ids["반찬"] in items:  # needs distractors; when present it must come from the story
        assert items[ids["반찬"]]["sentence_ko"] != LINES[0]


@pytest.fixture
def client(engine):
    maker = make_sessionmaker(engine)
    with maker() as s:
        setup_db(s)
        ingest_episode(s, podcast_doc(), fake_lookup, publish=True)
        s.commit()

    def override():
        with maker() as s:
            yield s

    app.dependency_overrides[get_session] = override
    yield TestClient(app)
    app.dependency_overrides.clear()


def test_podcasts_are_not_synced_or_listed(client):
    pulled = {e["id"] for e in client.get("/api/sync/pull").json()["episodes"]}
    listed = {e["id"] for e in client.get("/api/episodes").json()}
    assert "S01E001" in pulled and "pod-dt-07-p1" not in pulled | listed


def test_podcast_part_fetch_and_listing(client):
    full = client.get("/api/episodes/pod-dt-07-p1").json()
    assert full["media"]["video_id"] == "VIDEO123" and full["paragraphs"][1]["meta"]["speaker"] == "태웅"
    shows = client.get("/api/podcasts").json()
    assert shows[0]["id"] == "didi-taewoong"
    part = shows[0]["episodes"][0]["parts"][0]
    assert part["id"] == "pod-dt-07-p1" and part["primer"] is None and part["coverage"] is not None
    r = client.post("/api/events/batch", json={"events": [ev("primer_request", T0, episode_id="pod-dt-07-p1")]})
    assert r.status_code == 200
    assert client.get("/api/podcasts").json()[0]["episodes"][0]["parts"][0]["primer"] == "requested"


def test_podcast_coverage_is_live(client):
    def cov():
        return client.get("/api/podcasts").json()[0]["episodes"][0]["parts"][0]["coverage"]

    before = cov()
    kimchi = next(lx_id for lx_id, lx in client.get("/api/episodes/pod-dt-07-p1").json()["lexemes"].items()
                  if lx["lemma"] == "김치")
    client.post("/api/events/batch", json={"events": [
        ev("set_state", T0, lexeme_id=int(kimchi), state="known", prev_state="new")]})
    assert cov() > before  # no re-ingest needed


def primer_doc(part_id="pod-dt-07-p1") -> EpisodeDoc:
    return EpisodeDoc(id=f"primer-{part_id}", series="primer", title_ko="김치", title_en="Kimchi",
                      register_tags=["haeyo"], source=f"primer:{part_id}",
                      paragraphs=[{"ko": "김치가 정말 맛있어요.", "en": "Kimchi is good."}])


def test_primer_request_flows_to_context_until_a_primer_exists(db):
    from app.generation import build_context, check_draft

    s, ids = db
    add(s, ev("primer_request", T0, episode_id="pod-dt-07-p1"),
        ev("primer_request", T0, episode_id="pod-dt-07-p1"))  # a second tap is not a second request
    reqs = build_context(s)["primer_requests"]
    assert [r["part_id"] for r in reqs] == ["pod-dt-07-p1"] and reqs[0]["source"] == "primer:pod-dt-07-p1"
    words = {w["lemma"] for w in reqs[0]["words"]}
    assert "김치" in words and "정말" not in words and "디디" not in words
    assert "no target_grammar" not in check_draft(s, primer_doc()).problems
    ingest_episode(s, primer_doc(), fake_lookup, publish=True)
    s.flush()
    assert build_context(s)["primer_requests"] == []
