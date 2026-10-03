import json

from sqlalchemy import func, select

from app.db.models import Episode, EpisodeParagraph, GrammarState, Lexeme, LexemeState, Question
from app.ingest import ingest_episode, seed

from .conftest import TESTS_DIR, episode, fake_lookup


def test_tokens_resolve_to_golden_lexemes(session, legacy_episode):
    report = ingest_episode(session, legacy_episode, fake_lookup, publish=True)
    gold = json.loads((TESTS_DIR / "golden" / f"{legacy_episode.id}.gold.json").read_text(encoding="utf-8"))

    got = []
    for para in session.scalars(select(EpisodeParagraph).where(EpisodeParagraph.episode_id == legacy_episode.id)
                                .order_by(EpisodeParagraph.idx)):
        for t in para.tokens:
            if "lex" in t:
                lex = session.get(Lexeme, t["lex"])
                got.append([para.ko[t["s"]:t["e"]], lex.lemma, lex.pos])
    assert got == gold
    assert report.content_tokens == len(gold)
    assert session.get(Episode, legacy_episode.id).status == "published"


def test_glosses_from_lookup_and_missing_reported(session):
    report = ingest_episode(session, episode("legacy-001"), fake_lookup)
    assert ("초코", "NNP") in report.missing_gloss
    lex = session.scalar(select(Lexeme).where(Lexeme.lemma == "강아지"))
    assert (lex.gloss_en, lex.gloss_ja, lex.gloss_source) == ("en:강아지", "ja:강아지", "krdict")
    assert session.scalar(select(Lexeme).where(Lexeme.lemma == "초코")).gloss_source == "none"


def test_reingest_replaces_without_duplicates(session):
    doc = episode("legacy-001")
    ingest_episode(session, doc, fake_lookup)
    n_lex = session.scalar(select(func.count()).select_from(Lexeme))
    first = session.get(Episode, doc.id).updated_at
    ingest_episode(session, doc, fake_lookup, publish=True)
    session.commit()
    assert session.scalar(select(func.count()).select_from(Lexeme)) == n_lex
    assert session.scalar(select(func.count()).select_from(EpisodeParagraph)) == len(doc.paragraphs)
    assert session.scalar(select(func.count()).select_from(Question)) == len(doc.questions)
    assert session.get(Episode, doc.id).updated_at >= first


def test_seed_is_idempotent(session):
    seed(session, fake_lookup)
    seed(session, fake_lookup)
    states = session.scalars(select(LexemeState)).all()
    assert len(states) == 12 and {s.state for s in states} == {"learning"}
    assert {g.code for g in session.scalars(select(GrammarState))} == {"G.HANTESEO", "G.EGESEO"}


def test_coverage_counts_known_lexemes(session):
    doc = episode("legacy-001")
    assert ingest_episode(session, doc, fake_lookup).coverage == 0.0
    for lex in session.scalars(select(Lexeme)):
        session.add(LexemeState(lexeme_id=lex.id, state="known", source="manual"))
    session.flush()
    assert ingest_episode(session, doc, fake_lookup).coverage == 1.0


def test_reingest_without_publish_keeps_status(session):
    doc = episode("legacy-001")
    ingest_episode(session, doc, fake_lookup, publish=True)
    ingest_episode(session, doc, fake_lookup)
    assert session.get(Episode, doc.id).status == "published"
