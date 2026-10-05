"""Stage 8: SYLLABUS_MAP patterns, lesson cards, lesson completion in the replay, generator gating."""

import uuid
from datetime import UTC, datetime, timedelta

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select

from app.analyzer.patterns import count_grammar, final_consonant, seed_patterns
from app.content.schema import Episode as EpisodeDoc
from app.db import get_session, make_sessionmaker
from app.db.models import Event, GrammarPoint, GrammarState
from app.generation import build_context, check_draft
from app.ingest import seed
from app.main import app
from app.seed import load_grammar_points, load_lessons, validate_lesson
from app.srs import derive

from .conftest import fake_lookup

T0 = datetime(2026, 10, 5, 9, tzinfo=UTC)


def test_every_point_has_a_pattern():
    points = load_grammar_points()
    assert len(points) >= 90
    assert {p.code for p in points} == set(seed_patterns())


def test_final_consonant():
    assert [final_consonant(f) for f in ("덥", "듣", "빨갛", "가", "", "ᆫ")] == ["ㅂ", "ㄷ", "ㅎ", "", "", ""]


@pytest.mark.parametrize("text,code,n", [
    ("더워요. 추웠어요. 입어요. 덥다.", "G.IRREG_B", 2),
    ("들었어요. 듣고. 지었어요.", "G.IRREG_D_S", 1),
    ("빨개요. 하얀 눈. 좋아요.", "G.IRREG_H", 2),
    ("책 읽기가 좋아요. 가기 싫어요.", "G.GI_NOMINAL", 2),
    ("그가 오는지 몰라요. 어디 갔는지 알아요?", "G.NEUNJI", 2),
    ("사려고 왔어요. 밥 먹으러 가요.", "G.RYEOGO", 1),
    ("먹어 봤어요. 입어 보세요.", "G.A_BODA", 2),
    ("비가 올 것 같아요. 아픈 것 같아. 자는 것 같아요.", "G.EUL_GEOT_GATDA", 3),
    ("배가 고파서 먹었어요. 가서 봐요.", "G.A_SEO", 2),
    ("아버지가 오셨어요. 앉으세요.", "G.SI_HON", 2),
    ("사 줄게요. 도와주세요. 읽어 줘.", "G.A_JUDA", 3),
    ("어릴 때 살았어요. 갈 때 전화해.", "G.EUL_TTAE", 2),
    ("비가 오면 안 가요.", "G.MYEON", 1),
    ("수영할 수 있어요. 갈 수 없어. 그럴 수도 있지.", "G.EUL_SU_ITDA", 3),
    ("가야 해요. 공부해야 돼.", "G.A_YA_HADA", 2),
    ("비싸지만 샀어요.", "G.JIMAN", 1),
    ("들어가도 돼요? 먹어도 괜찮아.", "G.A_DO_DOEDA", 2),
    ("바쁜데 왜 왔어? 비가 오는데 우산 있어? 학생인데요.", "G.NEUNDE", 3),
    ("늦었으니까 자자.", "G.NIKKA", 1),
    ("아침에는 춥더니 지금은 덥네.", "G.DEONI", 1),
    ("같이 가기로 했어요. 안 먹기로 해.", "G.KIRO_HADA", 2),
])
def test_syllabus_patterns(text, code, n):
    assert count_grammar(text, codes=[code]).get(code, 0) == n


def test_lessons_are_valid_and_match_points():
    lessons = load_lessons()
    codes = {p.code for p in load_grammar_points()}
    assert lessons and set(lessons) <= codes
    # The six points placement left at `new` are the first lessons (DECISIONS 61: they waited for Stage 8).
    assert {"G.DONGAN", "G.E_DAEHAE", "G.EOJIDA", "G.WIHAE", "G.SEUREOPDA", "G.IRREG_H"} <= set(lessons)


def test_validate_lesson_rejects_bad_drills():
    lesson = dict(next(iter(load_lessons().values())))
    validate_lesson(lesson)
    bad = dict(lesson, drills=[dict(d, answer=7) for d in lesson["drills"]])
    with pytest.raises(ValueError):
        validate_lesson(bad)
    with pytest.raises(ValueError):
        validate_lesson(dict(lesson, examples=lesson["examples"][:1]))


@pytest.fixture
def seeded(session):
    seed(session, fake_lookup)
    session.flush()
    return session


def test_seed_stores_lessons_and_order(seeded):
    gp = seeded.get(GrammarPoint, "G.DONGAN")
    assert gp.lesson and gp.lesson["code"] == "G.DONGAN"
    assert seeded.get(GrammarPoint, "G.NEUNDE").order == 37.5  # priority thread before HTSK L76
    assert seeded.get(GrammarPoint, "G.TOPIC").order == 1.0


def _lesson_done(s, ts, code, correct, total=4):
    s.add(Event(id=str(uuid.uuid4()), ts=ts, device="iphone", type="grammar_lesson_complete",
                payload={"code": code, "correct": correct, "total": total, "visit": "v"}, received_at=ts))
    s.flush()
    derive(s)
    return s.scalar(select(GrammarState).where(GrammarState.code == code))


def test_lesson_complete_introduces_and_grades_first_review(seeded):
    seeded.add(GrammarState(code="G.DONGAN", state="new", source="placement", base_state="new", base_source="placement"))
    seeded.flush()
    derive(seeded)
    st = _lesson_done(seeded, T0, "G.DONGAN", 4)
    assert st.state == "introduced" and st.source == "lesson" and st.fsrs_card["last_review"]
    s1 = st.fsrs_card["stability"]
    # A redo before it is due changes nothing but exposures.
    st = _lesson_done(seeded, T0 + timedelta(hours=1), "G.DONGAN", 0)
    assert st.state == "introduced" and st.fsrs_card["stability"] == s1 and st.exposures == 2
    # A point with no row (never tested) gets one; a bad score is still introduced, with a weaker card.
    weak = _lesson_done(seeded, T0, "G.GI_NOMINAL", 1)
    assert weak.state == "introduced" and weak.fsrs_card["stability"] < s1
    # Replay is stable.
    assert derive(seeded).changed == 0


def test_lesson_complete_ignores_garbage(seeded):
    assert _lesson_done(seeded, T0, "G.NOPE", 3) is None
    assert _lesson_done(seeded, T0, "G.DONGAN", 3, total=0) is None


def _doc(ko: str, target: str) -> EpisodeDoc:
    return EpisodeDoc(id="S01E006", series="main", title_ko="t", title_en="t", register_tags=["haeyo"],
                      target_grammar=target, paragraphs=[{"ko": ko, "en": "x"}])


def test_gating_blocks_tested_new_warns_untested(seeded):
    seeded.add(GrammarState(code="G.WIHAE", state="new", source="placement"))
    seeded.flush()
    r = check_draft(seeded, _doc("가족을 위해 일해요. 배가 고파서 먹었어요. 회의 중이에요.", target="G.HAMNIDA"))
    assert any("state new" in p and "G.WIHAE" in p for p in r.problems)
    assert not any("G.A_SEO" in p for p in r.problems)
    assert any("untested" in w and "G.A_SEO" in w and "G.JUNG" in w for w in r.warnings)


def test_part_of_a_usable_point_is_not_new_use(seeded):
    seeded.add(GrammarState(code="G.GI_JEONE", state="solid", source="placement"))
    seeded.flush()
    r = check_draft(seeded, _doc("집에 가기 전에 밥 먹어요.", target="G.HAMNIDA"))
    assert not any("G.GI_NOMINAL" in p for p in r.problems)
    r = check_draft(seeded, _doc("책 읽기가 좋아요.", target="G.HAMNIDA"))
    assert any("G.GI_NOMINAL" in p for p in r.problems)  # lesson waiting -> blocked


def test_new_target_needs_a_lesson(seeded):
    with_lesson = check_draft(seeded, _doc("방학 동안 쉬었어요.", target="G.DONGAN"))
    assert any("lesson card opens" in w for w in with_lesson.warnings)
    assert not any("G.DONGAN" in p and "lesson" in p for p in with_lesson.problems)
    without = check_draft(seeded, _doc("비싸지만 샀어요.", target="G.JIMAN"))
    assert any("no lesson card" in p for p in without.problems)


def test_context_lists_next_new_targets(seeded):
    seeded.add(GrammarState(code="G.DONGAN", state="new", source="placement"))
    seeded.add(GrammarState(code="G.TOPIC", state="solid", source="placement"))
    seeded.flush()
    ctx = build_context(seeded)
    assert ctx["next_new_targets"][0] == "G.DONGAN"  # L11, the earliest lesson-backed new point
    assert "G.DONGAN" in ctx["grammar_avoid"] and "G.A_SEO" in ctx["grammar_untested"]
    assert "G.TOPIC" not in ctx["grammar_avoid"] + ctx["grammar_untested"]
    orders = [g["order"] for g in ctx["grammar"]]
    assert orders == sorted(orders)


def test_sync_pull_sends_grammar_and_lesson_event_is_accepted(engine):
    maker = make_sessionmaker(engine)
    with maker() as s:
        seed(s, fake_lookup)
        s.commit()

    def override():
        with maker() as s:
            yield s

    app.dependency_overrides[get_session] = override
    try:
        client = TestClient(app)
        grammar = {g["code"]: g for g in client.get("/api/sync/pull").json()["grammar"]}
        assert grammar["G.DONGAN"]["lesson"]["drills"] and grammar["G.DONGAN"]["state"] == "new"
        assert grammar["G.JIMAN"]["lesson"] is None
        ev = {"id": str(uuid.uuid4()), "ts": T0.isoformat(), "device": "iphone", "type": "grammar_lesson_complete",
              "payload": {"code": "G.DONGAN", "correct": 3, "total": 4, "visit": "v1"}}
        drill = dict(ev, id=str(uuid.uuid4()), type="grammar_drill_answer",
                     payload={"code": "G.DONGAN", "drill_idx": 0, "correct": True, "ms": 3000, "visit": "v1"})
        assert len(client.post("/api/events/batch", json={"events": [drill, ev]}).json()["accepted"]) == 2
        grammar = {g["code"]: g for g in client.get("/api/sync/pull").json()["grammar"]}
        assert grammar["G.DONGAN"]["state"] == "introduced"
    finally:
        app.dependency_overrides.clear()
