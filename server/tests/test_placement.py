import math
import random
import uuid
from collections import Counter
from datetime import UTC, datetime, timedelta

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select

from app.config import KRDICT_LOCAL_PATH, NIKL_VOCAB_PATH
from app.content.schema import load_episode
from app.db import get_session, make_sessionmaker
from app.db.models import Episode, GrammarState, Lexeme, LexemeState
from app.ingest import get_or_create_lexeme, ingest_episode, seed
from app.main import app
from app.nikl import parse
from app.placement import items
from app.placement.fit import VocabParams, fit_vocab, grammar_state, lexeme_states
from app.seed import load_grammar_points

from .conftest import fake_lookup

# ---- content ----


def test_every_grammar_point_has_two_check_sentences():
    codes = {p.code for p in load_grammar_points()}
    per_code = Counter(c for it in items.grammar_items() for c in it["codes"])
    ids = [it["id"] for it in items.grammar_items()]
    assert len(ids) == len(set(ids))
    assert set(per_code) == codes
    assert set(per_code.values()) == {2}


def test_vocab_test_shape():
    vocab = items.vocab_items()
    real = [it for it in vocab if it["real"]]
    assert len(real) == 96 and len(vocab) - len(real) == 24
    assert Counter(it["quantile"] for it in real) == {q: 16 for q in range(1, 7)}
    assert len({it["id"] for it in vocab}) == len(vocab)


@pytest.mark.skipif(not NIKL_VOCAB_PATH.is_file() or not KRDICT_LOCAL_PATH.is_file(),
                    reason="needs data/nikl_vocab.txt and data/krdict_local.sqlite")
def test_pseudowords_are_not_words():
    from app.krdict.local import LocalDict

    listed = {w.lemma for w in parse(NIKL_VOCAB_PATH)}
    local = LocalDict(KRDICT_LOCAL_PATH)
    for it in items.vocab_items():
        if not it["real"]:
            assert it["word"] not in listed and not local.search(it["word"]), it["word"]


def test_calibration_passages_load():
    ids = items.calibration_ids()
    assert len(ids) == 3
    for path in items.calibration_paths():
        assert load_episode(path).series == "placement"


# ---- NIKL parsing ----


def test_nikl_parse(tmp_path):
    rows = ["순위\t단어\t품사\t풀이\t등급", "",
            "25\t가다01\t동\t\tA", "150\t가다01\t보\t\tA", "898\t가격03\t명\t價格\tB",
            "1695\t가까이\t부\t\tB", "3560\t가까이\t명\t\tB", "\t경주\t고\t慶州\tA",
            "1228\t걔\t불\t그 아이\tB", "40\t있다01\t동\t\tA", "30\t있다01\t형\t\tA"]
    path = tmp_path / "nikl.txt"
    path.write_bytes("\n".join(rows).encode("cp949"))
    words = {(w.lemma, w.pos): w for w in parse(path)}
    assert words[("가다", "VV")].rank == 25  # auxiliary 보 entry skipped
    assert words[("가격", "NNG")].band == "B"
    assert words[("가까이", "MAG")].rank == 1695  # noun/adverb homograph: best rank wins
    assert words[("경주", "NNP")].rank is None
    assert words[("있다", "VA")].rank == 30
    assert not any(w.nikl_word == "걔" for w in words.values())


# ---- model ----


def _simulate(params: VocabParams, n: int, rng: random.Random):
    out = []
    for _ in range(n):
        rank = math.exp(rng.uniform(math.log(20), math.log(30000)))
        p = params.p_known(rank)
        yes = rng.random() < p + (1 - p) * params.fa
        out.append((rank, yes))
    return out


def test_fit_recovers_parameters():
    true = VocabParams(a=1.0, b=-1.5, fa=0.0)
    data = _simulate(true, 3000, random.Random(1))
    got = fit_vocab([], data, fa=0.0)
    assert abs(got.a - true.a) < 0.25 and abs(got.b - true.b) < 0.25


def test_guessing_correction():
    true = VocabParams(a=0.0, b=-1.5, fa=0.3)
    data = _simulate(true, 3000, random.Random(2))
    naive = fit_vocab([], data, fa=0.0)  # treats every yes as known
    corrected = fit_vocab(data, [], fa=0.3)
    assert abs(corrected.a - true.a) < 0.3
    assert naive.rank_at(0.5) > corrected.rank_at(0.5) * 1.5  # overclaiming inflates the naive edge


def test_fit_is_finite_under_perfect_separation():
    got = fit_vocab([(100, True)] * 10 + [(10000, False)] * 10, [], fa=0.04)
    assert math.isfinite(got.a) and got.b < 0


def test_grammar_state_mapping():
    assert grammar_state(2, 2) == "solid"
    assert grammar_state(1, 2) == "practicing"
    assert grammar_state(0, 2) == "new"


def test_lexeme_state_priority():
    params = VocabParams(a=0.0, b=-2.0, fa=0.5)  # P = 0.5 at rank 1000
    ranks = {1: 100.0, 2: 100.0, 3: 100.0, 4: 100000.0, 5: 100000.0, 6: 100.0}
    states = lexeme_states(params, ranks, yes_no={2: False, 3: True, 4: True}, calibration={5: True, 6: False})
    assert states[1] == "known"  # model
    assert 2 not in states  # said no
    assert states[3] == "known"  # yes on a likely word
    assert 4 not in states  # yes on a rare word with fa=0.5: posterior < 0.5
    assert states[5] == "known" and states[6] == "seen"  # calibration wins


# ---- service + API ----

TRUE = VocabParams(a=1.2, b=-1.4, fa=0.1)


@pytest.fixture
def client(engine):
    """Seeded DB with ranked lexemes for every vocab item and calibration word."""
    maker = make_sessionmaker(engine)
    rng = random.Random(7)
    with maker() as s:
        seed(s, fake_lookup)
        for it in items.vocab_items():
            if it["real"]:
                lex, _ = get_or_create_lexeme(s, it["lemma"], it["pos"], None)
                lex.freq_rank, lex.freq_band = it["rank"], it["band"]
        s.flush()
        for path in items.calibration_paths():
            ingest_episode(s, load_episode(path), fake_lookup, publish=True)
        for lex in s.scalars(select(Lexeme).where(Lexeme.freq_rank.is_(None))):
            lex.freq_rank, lex.freq_band = int(math.exp(rng.uniform(math.log(20), math.log(20000)))), "B"
        s.commit()

    def override():
        with maker() as s:
            yield s

    app.dependency_overrides[get_session] = override
    yield TestClient(app), maker
    app.dependency_overrides.clear()


def _answers(client, maker, attempt_id: str, rng: random.Random, grammar_got=True, start=None):
    """Simulated learner following TRUE; returns the events posted."""
    t = start or datetime(2026, 10, 3, 12, tzinfo=UTC)
    events = []

    def ev(**payload):
        nonlocal t
        t += timedelta(seconds=5)
        events.append({"id": str(uuid.uuid4()), "ts": t.isoformat(), "device": "iphone",
                       "type": "placement_answer", "payload": {"attempt_id": attempt_id, **payload}})

    for it in items.grammar_items():
        ev(section="grammar", item_id=it["id"], got_it=grammar_got if it["id"] != "g-topic-1" else False)
    for it in items.vocab_items():
        if it["real"]:
            p = TRUE.p_known(it["rank"])
            yes = rng.random() < p + (1 - p) * TRUE.fa
        else:
            yes = rng.random() < TRUE.fa
        ev(section="vocab", item_id=it["id"], yes=yes)
    with maker() as s:
        for ep_id in items.calibration_ids():
            ep = s.get(Episode, ep_id)
            lex_ids = {t["lex"] for p in ep.paragraphs for t in p.tokens if "lex" in t}
            tapped = [i for i in lex_ids if rng.random() >= TRUE.p_known(s.get(Lexeme, i).freq_rank)]
            ev(section="calibration", episode_id=ep_id, tapped_lexeme_ids=tapped, rating=4, ms=60000)
    ev(section="done")
    r = client.post("/api/events/batch", json={"events": events})
    assert r.status_code == 200 and len(r.json()["accepted"]) == len(events)
    return events


def test_get_placement(client):
    c, _ = client
    body = c.get("/api/placement").json()
    assert len(body["grammar"]) == 104 and len(body["vocab"]) == 120
    assert set(body["vocab"][0]) == {"id", "word"}  # real/pseudo not leaked
    assert body["calibration"] == items.calibration_ids()
    assert body["completed_attempt"] is None and body["fitted"] is False


def test_fit_requires_finished_attempt(client):
    c, _ = client
    assert c.post("/api/placement/fit").status_code == 409


def test_fit_end_to_end(client):
    c, maker = client
    _answers(c, maker, "att-1", random.Random(3))
    s = c.post("/api/placement/fit").json()

    assert s["attempt_id"] == "att-1"
    assert s["known_lexemes"] > 0
    assert s["grammar"]["practicing"] == ["G.TOPIC"]
    assert len(s["calibration"]) == 3
    for row in s["calibration"]:
        assert 0 <= row["observed"] <= 1 and 0 <= row["predicted"] <= 1
    assert c.get("/api/placement").json() | {"grammar": None, "vocab": None} == {
        "grammar": None, "vocab": None, "calibration": items.calibration_ids(),
        "completed_attempt": "att-1", "fitted": True}

    with maker() as db:
        manual = db.scalars(select(LexemeState).where(LexemeState.source == "manual")).all()
        assert manual and all(st.state == "learning" for st in manual)  # flagged vocab untouched
        assert db.get(GrammarState, "G.EGESEO").source == "manual"
        assert db.get(GrammarState, "G.KKE").state == "solid"
        cal = db.get(Episode, "placement-cal-1")
        assert cal.coverage > 0
    # states reach the client through sync pull
    pulled = c.get("/api/sync/pull").json()["lexeme_states"]
    assert any(st["state"] == "known" for st in pulled)


def test_refit_is_idempotent_and_latest_attempt_wins(client):
    c, maker = client
    _answers(c, maker, "att-1", random.Random(3))
    first = c.post("/api/placement/fit").json()
    again = c.post("/api/placement/fit").json()
    assert first["known_lexemes"] == again["known_lexemes"]

    # A later attempt where every grammar sentence is fuzzy replaces the first.
    _answers(c, maker, "att-2", random.Random(4), grammar_got=False, start=datetime(2026, 10, 4, tzinfo=UTC))
    s = c.post("/api/placement/fit").json()
    assert s["attempt_id"] == "att-2"
    with maker() as db:
        assert db.get(GrammarState, "G.TOPIC").state == "new"
        placement_rows = db.scalars(select(LexemeState).where(LexemeState.source == "placement")).all()
        assert {r.state for r in placement_rows} <= {"known", "seen", "new"}


def test_unfinished_attempt_is_ignored(client):
    c, maker = client
    _answers(c, maker, "att-1", random.Random(3))
    late = {"id": str(uuid.uuid4()), "ts": datetime(2026, 10, 5, tzinfo=UTC).isoformat(), "device": "iphone",
            "type": "placement_answer",
            "payload": {"attempt_id": "att-9", "section": "grammar", "item_id": "g-topic-1", "got_it": True}}
    c.post("/api/events/batch", json={"events": [late]})
    assert c.post("/api/placement/fit").json()["attempt_id"] == "att-1"


def test_unknown_rate_interval():
    from app.placement.fit import unknown_rate_interval

    certain = [{1: 1.0, 2: 0.0}]
    assert unknown_rate_interval(certain, [1, 1, 2, 1]) == (0.25, 0.25)  # token-weighted
    lo, hi = unknown_rate_interval([{i: 0.5 for i in range(100)}], list(range(100)))
    assert 0.35 < lo < 0.5 < hi < 0.65
