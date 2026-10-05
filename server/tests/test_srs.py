"""Stage 6: hidden SRS derived from the event log (app/srs.py)."""

import random
import uuid
from datetime import UTC, datetime, timedelta

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select

from app.content.schema import Episode as EpisodeDoc
from app.db import get_session, make_engine, make_sessionmaker
from app.db.migrate import upgrade
from app.db.models import Event, GrammarState, Lexeme, LexemeState, Question
from app.generation import build_context, due_lexemes
from app.ingest import get_or_create_lexeme, ingest_episode, known_lexeme_ids, seed
from app.main import app
from app.srs import GRADUATE_DAYS, derive, known_until, load_card

from .conftest import fake_lookup

T0 = datetime(2026, 10, 1, 9, 0, tzinfo=UTC)
TEXT = "반찬이 정말 맛있습니다. 김치도 좋습니다. 서윤아, 밥 먹었습니다."
KNOWN = [("정말", "MAG"), ("맛있다", "VA"), ("좋다", "VA"), ("밥", "NNG"), ("먹다", "VV")]


def _doc(ep_id="S01E001", series="main") -> EpisodeDoc:
    return EpisodeDoc(
        id=ep_id, series=series, title_ko="t", title_en="t", register_tags=["hasipsio"], target_grammar="G.HAMNIDA",
        paragraphs=[{"ko": TEXT, "en": "The side dishes are delicious."}],
        questions=[{"kind": "meaning_check", "prompt_ko": "김치?", "prompt_en": "?", "options": ["kimchi", "rice", "soup"],
                    "answer_idx": 0, "target_ref": "김치"},
                   {"kind": "grammar_check", "prompt_ko": "?", "prompt_en": "?", "options": ["a", "b", "c"],
                    "answer_idx": 0, "target_ref": "G.HAMNIDA"}])


def setup_db(s) -> dict[str, int]:
    seed(s, fake_lookup)
    for lemma, pos in KNOWN:
        lx, _ = get_or_create_lexeme(s, lemma, pos, fake_lookup)
        s.add(LexemeState(lexeme_id=lx.id, state="known", source="placement", base_state="known",
                          base_source="placement", first_seen_at=T0 - timedelta(days=5)))
    lx, _ = get_or_create_lexeme(s, "반찬", "NNG", fake_lookup)
    s.add(LexemeState(lexeme_id=lx.id, state="seen", source="placement", base_state="seen", base_source="placement",
                      first_seen_at=T0 - timedelta(days=5)))
    s.add(GrammarState(code="G.HAMNIDA", state="practicing", source="placement", base_state="practicing",
                       base_source="placement"))
    s.add(GrammarState(code="G.KKE", state="solid", source="placement", base_state="solid", base_source="placement"))
    ingest_episode(s, _doc(), fake_lookup, publish=True)
    ingest_episode(s, _doc("placement-x", "placement"), fake_lookup, publish=True)
    s.flush()
    return {lemma: s.scalar(select(Lexeme.id).where(Lexeme.lemma == lemma))
            for lemma in ("반찬", "정말", "맛있다", "좋다", "밥", "먹다", "김치", "서윤")}


@pytest.fixture
def db(session):
    ids = setup_db(session)
    derive(session)
    return session, ids


def ev(type_, ts, **payload) -> dict:
    return {"id": str(uuid.uuid4()), "ts": ts.isoformat(), "device": "iphone", "type": type_, "payload": payload}


def add(s, *events) -> None:
    for e in events:
        s.add(Event(id=e["id"], ts=datetime.fromisoformat(e["ts"]), device=e["device"], type=e["type"],
                    payload=e["payload"], received_at=T0))
    s.flush()
    derive(s)


def complete(ts, tapped=(), ep="S01E001") -> dict:
    return ev("episode_complete", ts, episode_id=ep, tapped_lexeme_ids=list(tapped))


def answer(s, ts, kind, correct, ms=20000, ep="S01E001") -> dict:
    q = s.scalar(select(Question).where(Question.episode_id == ep, Question.kind == kind))
    return ev("question_answer", ts, episode_id=ep, question_id=q.id, choice_idx=0 if correct else 1,
              correct=correct, ms=ms)


def st(s, lex_id) -> LexemeState:
    s.expire_all()
    return s.get(LexemeState, lex_id)


# ---- acceptance: replay reproduces identical states ----

def scripted_log(maker, ids) -> list[dict]:
    with maker() as s:
        mc = lambda ts, ok, ms=20000: answer(s, ts, "meaning_check", ok, ms)  # noqa: E731
        gc = lambda ts, ok: answer(s, ts, "grammar_check", ok)  # noqa: E731
        log = [ev("episode_open", T0, episode_id="S01E001"),
               ev("word_tap", T0 + timedelta(minutes=1), episode_id="S01E001", lexeme_id=ids["정말"]),
               ev("word_tap", T0 + timedelta(minutes=2), episode_id="S01E001", lexeme_id=ids["밥"]),
               ev("word_untap", T0 + timedelta(minutes=3), episode_id="S01E001", lexeme_id=ids["밥"]),
               mc(T0 + timedelta(minutes=4), False), gc(T0 + timedelta(minutes=5), True),
               complete(T0 + timedelta(minutes=6), [ids["정말"]])]
        for day in (2, 5, 9, 20, 45):
            t = T0 + timedelta(days=day)
            log += [mc(t, True, 4000), gc(t, day != 9), complete(t + timedelta(minutes=1))]
        log += [ev("set_state", T0 + timedelta(days=10), lexeme_id=ids["좋다"], state="learning", prev_state="known"),
                ev("set_state", T0 + timedelta(days=10, seconds=5), lexeme_id=ids["좋다"], state="known",
                   prev_state="learning", undo=True),
                ev("set_state", T0 + timedelta(days=11), lexeme_id=ids["먹다"], state="learning", prev_state="known"),
                ev("review_answer", T0 + timedelta(days=12), lexeme_id=ids["먹다"], correct=True, ms=3000),
                complete(T0 + timedelta(days=13), [ids["반찬"]], ep="placement-x")]
    return log


def snapshot(maker) -> dict:
    """Derived columns. A baseline row's first_seen_at is the seed's wall clock, not derived from the log."""
    with maker() as s:
        lex = {r.lexeme_id: (r.state, r.source, r.fsrs_card, r.exposures, r.lookups,
                             None if r.base_source == "manual" else r.first_seen_at, r.last_seen_at)
               for r in s.scalars(select(LexemeState))}
        gram = {r.code: (r.state, r.source, r.fsrs_card, r.exposures) for r in s.scalars(select(GrammarState))}
    return {"lex": lex, "gram": gram}


def test_replay_reproduces_identical_states(engine, tmp_path):
    maker = make_sessionmaker(engine)
    with maker() as s:
        ids = setup_db(s)
        derive(s)
        s.commit()
    log = scripted_log(maker, ids)

    # Live path: events arrive through the API in random, out-of-order batches (resends included).
    shuffled = log[:]
    random.Random(6).shuffle(shuffled)
    batches = [shuffled[i:i + 3] for i in range(0, len(shuffled), 3)]

    def override():
        with maker() as s:
            yield s

    app.dependency_overrides[get_session] = override
    try:
        client = TestClient(app)
        for b in batches + batches[:2]:
            assert client.post("/api/events/batch", json={"events": b}).status_code == 200
    finally:
        app.dependency_overrides.clear()
    live = snapshot(maker)

    # Replay path: a fresh DB with the same baseline, the whole log at once, one derive.
    fresh = make_engine(tmp_path / "fresh.db")
    upgrade(fresh)
    fmaker = make_sessionmaker(fresh)
    with fmaker() as s:
        setup_db(s)
        add(s, *log)
        s.commit()
    replayed = snapshot(fmaker)
    for table in ("lex", "gram"):
        diff = {k: (live[table].get(k), replayed[table].get(k)) for k in live[table] | replayed[table]
                if live[table].get(k) != replayed[table].get(k)}
        assert not diff, f"{table} rows differ (live, replay): {diff}"

    # And deriving again changes nothing.
    with maker() as s:
        assert derive(s).changed == 0
    fresh.dispose()

    st_ = live["lex"]
    assert st_[ids["정말"]][0] == "known" and st_[ids["정말"]][2]  # soft-lapsed on day 0, regraduated since
    assert st_[ids["밥"]][4] == 0  # mistap undone
    assert st_[ids["좋다"]][0] == "known" and st_[ids["좋다"]][2] is None  # forgot + undo left no card
    assert ids["서윤"] not in st_  # story names are never graded


# ---- rules ----

def test_baseline_seen_gets_an_unreviewed_due_card(db):
    s, ids = db
    row = st(s, ids["반찬"])
    assert row.state == "seen" and load_card(row.fsrs_card).last_review is None
    assert [lx.lemma for lx, _ in due_lexemes(s)][-1] == "반찬"
    assert st(s, ids["정말"]).fsrs_card is None


def test_untapped_new_word_starts_as_good_and_counts_known_until_due(db):
    s, ids = db
    add(s, complete(T0))
    card = load_card(st(s, ids["김치"]).fsrs_card)
    assert st(s, ids["김치"]).state == "learning" and 2 <= card.stability < 3
    assert ids["김치"] in known_lexeme_ids(s, T0 + timedelta(days=1))
    assert ids["김치"] not in known_lexeme_ids(s, T0 + timedelta(days=3))
    assert st(s, ids["반찬"]).state == "learning"  # unreviewed seen card was due: Good


def test_tapped_new_word_is_again_and_not_known_hours_later(db):
    s, ids = db
    add(s, complete(T0, [ids["김치"]]))
    card = load_card(st(s, ids["김치"]).fsrs_card)
    assert card.stability < 1 and card.due >= T0 + timedelta(days=1)  # py-fsrs rounds intervals up to a day
    assert ids["김치"] not in known_lexeme_ids(s, T0 + timedelta(hours=8))  # but R < 0.9 after S
    assert ids["김치"] in {lx.id for lx, _ in due_lexemes(s, T0 + timedelta(hours=8))}


def test_tapped_known_word_soft_lapses_then_regraduates(db):
    s, ids = db
    add(s, complete(T0, [ids["정말"]]))
    row = st(s, ids["정말"])
    card = load_card(row.fsrs_card)
    assert row.state == "learning" and card.stability == 3 and card.difficulty == 5
    assert known_until(card) == T0 + timedelta(days=3)
    add(s, complete(known_until(card)))
    card = load_card(st(s, ids["정말"]).fsrs_card)
    assert st(s, ids["정말"]).state == "learning" and card.stability < GRADUATE_DAYS
    add(s, complete(known_until(card)))
    assert st(s, ids["정말"]).state == "known"  # two untapped encounters


def test_known_untapped_is_exposure_only_and_not_due_card_untouched(db):
    s, ids = db
    add(s, complete(T0))
    before = st(s, ids["김치"]).fsrs_card
    add(s, complete(T0 + timedelta(hours=5)))
    assert st(s, ids["김치"]).fsrs_card == before and st(s, ids["김치"]).exposures == 2
    assert st(s, ids["밥"]).fsrs_card is None and st(s, ids["밥"]).exposures == 2


def test_meaning_check_overrides(db):
    s, ids = db
    add(s, answer(s, T0, "meaning_check", False), complete(T0 + timedelta(minutes=1)))
    assert load_card(st(s, ids["김치"]).fsrs_card).stability < 1  # wrong -> Again even untapped
    t = T0 + timedelta(days=1)
    add(s, answer(s, t, "meaning_check", True, ms=3000), complete(t + timedelta(minutes=1)))
    assert load_card(st(s, ids["김치"]).fsrs_card).stability > 2  # right + fast -> Easy (reviewed early)


def test_grammar_graded_only_by_checks(db):
    s, ids = db
    add(s, complete(T0))
    g = s.get(GrammarState, "G.HAMNIDA")
    assert load_card(g.fsrs_card).last_review is None and g.exposures == 1  # present, no check: exposure
    add(s, answer(s, T0 + timedelta(days=1), "grammar_check", True), complete(T0 + timedelta(days=1, minutes=1)))
    s.expire_all()
    assert load_card(s.get(GrammarState, "G.HAMNIDA").fsrs_card).last_review is not None


def test_placement_series_completion_is_not_a_review(db):
    s, ids = db
    add(s, complete(T0, [ids["정말"]], ep="placement-x"))
    assert st(s, ids["정말"]).state == "known" and st(s, ids["김치"]) is None


def test_forgot_is_due_now_and_review_answer_grades_due_cards(db):
    s, ids = db
    add(s, ev("set_state", T0, lexeme_id=ids["밥"], state="learning", prev_state="known"))
    row = st(s, ids["밥"])
    assert row.source == "manual" and known_until(load_card(row.fsrs_card)) == T0
    assert ids["밥"] not in known_lexeme_ids(s, T0)
    assert ids["밥"] in {lx.id for lx, _ in due_lexemes(s, T0 + timedelta(minutes=1))}
    add(s, ev("review_answer", T0 + timedelta(hours=1), lexeme_id=ids["밥"], correct=True))
    assert load_card(st(s, ids["밥"]).fsrs_card).due > T0 + timedelta(days=1)
    before = st(s, ids["밥"]).fsrs_card
    add(s, ev("review_answer", T0 + timedelta(hours=2), lexeme_id=ids["밥"], correct=False))  # not due: ignored
    assert st(s, ids["밥"]).fsrs_card == before


def test_context_lists_due_with_retrievability(db):
    s, ids = db
    add(s, complete(T0, [ids["김치"]]))
    due = build_context(s)["due"]
    assert due[0]["lemma"] == "김치" and due[0]["reviewed"] and due[0]["retrievability"] < 0.9
    assert not due[-1]["reviewed"]  # never-reviewed cards (baseline / forgot) come after reviewed ones


def test_ingest_resolves_meaning_check_and_builds_context_sentences(db):
    s, ids = db
    from app.db.models import ContextSentence
    q = s.scalar(select(Question).where(Question.episode_id == "S01E001", Question.kind == "meaning_check"))
    assert q.target_ref == str(ids["김치"])
    ctx = s.scalar(select(ContextSentence).where(ContextSentence.lexeme_id == ids["김치"],
                                                 ContextSentence.origin == "episode:S01E001"))
    assert ctx.sentence_ko == "김치도 좋습니다." and ctx.sentence_ko[ctx.start:ctx.end] == "김치도"
    with pytest.raises(ValueError):
        bad = _doc("S01E002")
        bad.questions[0].target_ref = "없는말"
        ingest_episode(s, bad, fake_lookup)
