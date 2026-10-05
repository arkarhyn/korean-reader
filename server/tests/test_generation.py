"""Stage 5: proper nouns, grammar patterns, set_state on receipt, generation context, draft checker."""

import uuid
from datetime import UTC, datetime, timedelta

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select

from app.analyzer import analyze
from app.analyzer.patterns import count_grammar
from app.content.schema import Episode as EpisodeDoc
from app.db import get_session, make_sessionmaker
from app.db.models import Episode, GrammarState, Lexeme, LexemeState
from app.srs import derive
from app.generation import build_context, check_draft, next_episode_id
from app.ingest import get_or_create_lexeme, ingest_episode, seed
from app.main import app

from .conftest import episode, fake_lookup


def test_cast_names_stay_whole():
    toks = [(t.lemma, t.pos) for t in analyze("서윤아, 이선 씨 왔어. 준수가 했어.") if t.kind == "content"]
    assert ("서윤", "NNP") in toks and ("이선", "NNP") in toks and ("준수", "NNP") in toks


@pytest.mark.parametrize("text,code,n", [
    ("처음 뵙겠습니다. 감사합니다. 어디 가십니까? 맛있게 드십시오.", "G.HAMNIDA", 4),
    ("감사해요. 갑시다.", "G.HAMNIDA", 0),
    ("제가 할게요. 저희 집. 나도 몰라. 내 친구.", "G.HUMBLE_PRON", 4),
    ("저보다 커요. 더 먹어. 제일 좋아.", "G.BODA", 3),
    ("아버지가 쓰시던 삽. 좋았던 것 같아. 가 보던데.", "G.DEON", 2),
    ("공부하지 못했어요. 못 갔어요.", "G.JI_MOTHADA", 1),
    ("가지 못할 수도 있어. 받지 못할 거야.", "G.JI_MOTHADA", 2),
    ("친해졌어요. 일 년 동안. 일에 대해. 가족을 위해. 자랑스러워요.", "G.EOJIDA", 1),
])
def test_grammar_patterns(text, code, n):
    assert count_grammar(text, codes=[code]).get(code, 0) == n


def test_new_grammar_points_detected():
    found = count_grammar("친해졌어요. 일 년 동안. 일에 대해. 가족을 위해. 자랑스러워요.")
    assert {"G.EOJIDA", "G.DONGAN", "G.E_DAEHAE", "G.WIHAE", "G.SEUREOPDA"} <= set(found)


@pytest.fixture
def seeded(session):
    seed(session, fake_lookup)
    for lemma, pos in [("밥", "NNG"), ("먹다", "VV"), ("많이", "MAG"), ("좋다", "VA"), ("저", "NP"),
                       ("오늘", "NNG"), ("정말", "MAG"), ("맛있다", "VA")]:
        lx, _ = get_or_create_lexeme(session, lemma, pos, fake_lookup)
        session.add(LexemeState(lexeme_id=lx.id, state="known", source="placement",
                                base_state="known", base_source="placement"))
    lx, _ = get_or_create_lexeme(session, "반찬", "NNG", fake_lookup)
    session.add(LexemeState(lexeme_id=lx.id, state="seen", source="placement",
                            base_state="seen", base_source="placement"))
    session.flush()
    derive(session)  # baseline `seen` -> an unreviewed card, due now
    return session


def _doc(ko: str, target="G.HAMNIDA", ep_id="S01E001") -> EpisodeDoc:
    return EpisodeDoc(id=ep_id, series="main", title_ko="t", title_en="t", register_tags=["haeyo"],
                      target_grammar=target, paragraphs=[{"ko": ko, "en": "x"}])


def test_check_draft_counts_names_known_and_splits_new_from_due(seeded):
    r = check_draft(seeded, _doc("서윤아, 밥 먹었어? 반찬 정말 맛있습니다. 김치 좋습니다."))
    keys = {(u.lemma, u.pos): u for u in r.unknown}
    assert ("서윤", "NNP") not in keys  # story-bible name counts as known
    assert keys[("반찬", "NNG")].is_due and [u.lemma for u in r.new_words] == ["김치"]
    assert r.target_count == 2
    assert any("coverage" in p for p in r.problems) and any("new words" in p for p in r.problems)


def test_check_draft_flags_new_grammar_and_unpatterned_target(seeded):
    r = check_draft(seeded, _doc("저는 밥을 먹기 위해 왔어요.", target="G.TOPIC"))
    assert any("no kiwi_pattern" in p for p in r.problems)
    assert any("G.WIHAE" in p for p in r.problems)


def test_ingest_fills_new_and_review_lexemes(seeded):
    ingest_episode(seeded, _doc("반찬이 정말 맛있습니다. 김치도 좋아요. 서윤아!"), fake_lookup, publish=True)
    name = seeded.scalar(select(Lexeme).where(Lexeme.lemma == "서윤"))
    assert (name.gloss_en, name.gloss_source) == ("Seoyun (name)", "manual")
    ep = seeded.get(Episode, "S01E001")
    lemma = {i: seeded.get(Lexeme, i).lemma for i in ep.new_lexemes + ep.review_lexemes}
    assert [lemma[i] for i in ep.review_lexemes] == ["반찬"]
    assert [lemma[i] for i in ep.new_lexemes] == ["김치"]


def test_context_has_due_targets_and_next_id(seeded):
    seeded.add(GrammarState(code="G.HAMNIDA", state="practicing", source="placement"))
    seeded.add(GrammarState(code="G.WIHAE", state="new", source="placement"))
    seeded.flush()
    ctx = build_context(seeded)
    assert ctx["next_episode_id"] == "S01E001"
    assert [d["lemma"] for d in ctx["due"]][-1] == "반찬"
    assert "G.HAMNIDA" in ctx["suggested_targets"] and "G.WIHAE" in ctx["grammar_avoid"]
    assert "밥/NNG" in ctx["known"] and "서윤" in ctx["proper_nouns"]
    assert "Canon log" in ctx["docs"]["story_bible"]

    ingest_episode(seeded, _doc("밥 먹었습니다.", ep_id="S01E001"), fake_lookup, publish=True)
    assert next_episode_id(seeded) == "S01E002"
    assert "G.HAMNIDA" not in build_context(seeded)["suggested_targets"]  # just targeted


@pytest.fixture
def client(engine):
    maker = make_sessionmaker(engine)
    with maker() as s:
        ingest_episode(s, episode("legacy-001"), fake_lookup, publish=True)
        s.commit()

    def override():
        with maker() as s:
            yield s

    app.dependency_overrides[get_session] = override
    yield TestClient(app)
    app.dependency_overrides.clear()


def _event(type_, ts=None, **payload):
    return {"id": str(uuid.uuid4()), "ts": (ts or datetime.now(UTC)).isoformat(), "device": "iphone",
            "type": type_, "payload": payload}


def _state(engine, lemma):
    with make_sessionmaker(engine)() as s:
        st = s.scalar(select(LexemeState).join(Lexeme).where(Lexeme.lemma == lemma))
        return (st.state, st.source) if st else None


def test_set_state_applies_on_receipt_once_and_replays(client, engine):
    with make_sessionmaker(engine)() as s:
        lex_id = s.scalar(select(Lexeme.id).where(Lexeme.lemma == "강아지"))
    t0 = datetime.now(UTC)
    known = _event("set_state", t0, lexeme_id=lex_id, state="known", episode_id="legacy-001")
    assert client.post("/api/events/batch", json={"events": [known]}).json()["accepted"]
    assert _state(engine, "강아지") == ("known", "manual")
    pulled = client.get("/api/sync/pull").json()["lexeme_states"]
    assert {"lexeme_id": lex_id, "state": "known"}.items() <= next(
        p for p in pulled if p["lexeme_id"] == lex_id).items()

    undo = _event("set_state", t0 + timedelta(seconds=5), lexeme_id=lex_id, state="new")
    client.post("/api/events/batch", json={"events": [undo, known]})  # resent `known` is a duplicate
    assert _state(engine, "강아지") == ("new", "manual")

    with make_sessionmaker(engine)() as s:
        s.get(LexemeState, lex_id).state = "seen"
        derive(s)
        assert s.get(LexemeState, lex_id).state == "new"


def test_bad_set_state_and_untap_are_stored_without_effect(client, engine):
    batch = [_event("set_state", lexeme_id=999999, state="known"), _event("set_state", lexeme_id=1, state="bogus"),
             _event("word_untap", episode_id="legacy-001", paragraph_idx=0, start=0, end=2, lexeme_id=1)]
    assert len(client.post("/api/events/batch", json={"events": batch}).json()["accepted"]) == 3
    with make_sessionmaker(engine)() as s:
        assert s.scalar(select(LexemeState).where(LexemeState.lexeme_id == 1)) is None


def test_generation_context_endpoint(client):
    ctx = client.get("/api/export/generation-context").json()
    assert ctx["next_episode_id"] == "S01E001" and "docs" in ctx


def test_episode_lexemes_flag_names_and_alias_known(engine):
    maker = make_sessionmaker(engine)
    with maker() as s:
        seed(s, fake_lookup)
        lx, _ = get_or_create_lexeme(s, "감사하다", "VA", fake_lookup)  # the list's tag
        s.add(LexemeState(lexeme_id=lx.id, state="known", source="placement"))
        ingest_episode(s, _doc("서윤아, 감사합니다. 김치 좋아요."), fake_lookup, publish=True)
        s.commit()

    def override():
        with maker() as s:
            yield s

    app.dependency_overrides[get_session] = override
    try:
        lexemes = TestClient(app).get("/api/episodes/S01E001").json()["lexemes"].values()
    finally:
        app.dependency_overrides.clear()
    flags = {(l["lemma"], l["pos"]): l["counts_known"] for l in lexemes}
    assert flags[("서윤", "NNP")] and flags[("감사하다", "VV")]
    assert not flags[("김치", "NNG")]


def test_flags_drop_out_once_the_sentence_is_rewritten(seeded):
    from app.db.models import Event

    ingest_episode(seeded, _doc("밥 먹었습니다. 정말 맛있습니다."), fake_lookup, publish=True)
    seeded.add(Event(id=str(uuid.uuid4()), ts=datetime.now(UTC), device="iphone", type="flag_sentence",
                     payload={"episode_id": "S01E001", "text": '정말 맛있습니다."'}))
    seeded.flush()
    assert len(build_context(seeded)["flagged_sentences"]) == 1
    ingest_episode(seeded, _doc("밥 먹었습니다. 진짜 맛있어요."), fake_lookup, publish=True)
    assert build_context(seeded)["flagged_sentences"] == []
