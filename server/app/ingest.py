"""Load authored episode JSON and seed data into the DB.

Tokens are computed here (not authored): content tokens point at a lexeme id,
grammar tokens with a stable code carry it. Glosses come from krdict only
(SPEC 5); a lemma with no entry gets gloss_source="none" and is reported.
"""

import re
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import datetime

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from .analyzer import analyze, grammar_codes, proper_noun_glosses, proper_nouns
from .content.schema import Episode as EpisodeDoc
from .coverage import coverage, expand_known
from .db.models import (ContextSentence, Episode, EpisodeParagraph, GrammarPoint, GrammarState, Lexeme, LexemeState,
                        Question, utcnow)
from .krdict.client import KrdictEntry
from .seed import load_flagged_vocab, load_grammar_points
from .srs import counts_known, due_now

Lookup = Callable[[str, str], KrdictEntry | None]

# Same splitter as web/src/segments.ts sentenceAt (flags, context sentences).
_SENTENCE = re.compile(r"""[^.!?]*[.!?]+["”’']*\s*|[^.!?]+$""")
# Same tap-target boundary as web/src/segments.ts: a word runs on over its endings.
_BOUNDARY = re.compile(r"""[\s.,!?'"“”‘’…·()\[\]{}:;~-]""")

# Seed rows for the codes the analyzer emits today; SYLLABUS_MAP fills the rest (Stage 8).
GRAMMAR_LABELS: dict[str, str] = {
    **{code: f"-{form}" for (form, _tag), code in grammar_codes.MORPHEME_CODES.items()},
    grammar_codes.NEG_AN: "안 + 용언",
    grammar_codes.NEG_MOT: "못 + 용언",
    grammar_codes.JI_MOTHADA: "-지 못하다",
}


def first_of(*lookups: Lookup | None) -> Lookup:
    """Try each gloss source in order (local dump, API cache, live API); first hit wins."""
    sources = [lk for lk in lookups if lk is not None]

    def lookup(lemma: str, pos: str) -> KrdictEntry | None:
        for lk in sources:
            if (entry := lk(lemma, pos)) is not None:
                return entry
        return None

    return lookup


@dataclass
class IngestReport:
    episode_id: str
    coverage: float
    content_tokens: int
    new_lexemes: list[tuple[str, str]] = field(default_factory=list)
    missing_gloss: list[tuple[str, str]] = field(default_factory=list)


def get_or_create_lexeme(session: Session, lemma: str, pos: str, lookup: Lookup | None) -> tuple[Lexeme, bool]:
    lex = session.scalar(select(Lexeme).where(Lexeme.lemma == lemma, Lexeme.pos == pos))
    created = lex is None
    if created:
        lex = Lexeme(lemma=lemma, pos=pos, gloss_en="", gloss_source="none")
        session.add(lex)
    if lex.gloss_source == "none" and pos == "NNP" and lemma in proper_noun_glosses():
        lex.gloss_en, lex.gloss_source = proper_noun_glosses()[lemma], "manual"
    if lex.gloss_source == "none" and lookup is not None:
        entry = lookup(lemma, pos)
        if entry is not None:
            lex.gloss_en = entry.gloss_en
            lex.gloss_ja = entry.gloss_ja or None
            lex.hanja = entry.hanja
            lex.krdict_id = entry.target_code
            lex.gloss_source = "krdict"
    session.flush()
    return lex, created


def known_lexeme_ids(session: Session, now: datetime | None = None) -> set[int]:
    """SPEC 7 by own state: known/ignored, or learning with retrievability >= 0.9 (app/srs.py)."""
    now = now or utcnow()
    rows = session.execute(select(LexemeState.lexeme_id, LexemeState.state, LexemeState.fsrs_card)
                           .where(LexemeState.state.in_(("known", "ignored", "learning"))))
    return {r.lexeme_id for r in rows if counts_known(r.state, r.fsrs_card, now)}


def raw_known_keys(session: Session, now: datetime | None = None) -> set[tuple[str, str]]:
    """Keys of lexemes known by their own state (no tag aliases)."""
    ids = known_lexeme_ids(session, now)
    rows = session.execute(select(Lexeme.id, Lexeme.lemma, Lexeme.pos).join(LexemeState)
                           .where(LexemeState.state.in_(("known", "ignored", "learning"))))
    return {(r.lemma, r.pos) for r in rows if r.id in ids}


def known_keys(session: Session, now: datetime | None = None) -> set[tuple[str, str]]:
    """SPEC 7 known set (with tag aliases)."""
    return expand_known(raw_known_keys(session, now))


def due_lexeme_ids(session: Session, now: datetime | None = None) -> set[int]:
    now = now or utcnow()
    rows = session.execute(select(LexemeState.lexeme_id, LexemeState.state, LexemeState.fsrs_card)
                           .where(LexemeState.fsrs_card.is_not(None)))
    return {r.lexeme_id for r in rows if due_now(r.state, r.fsrs_card, now)}


def episode_lexeme_sets(session: Session, lexeme_ids: set[int]) -> tuple[list[int], list[int]]:
    """(new, review) lexeme ids in an episode: review = due now, new = no history (story names excluded)."""
    if not lexeme_ids:
        return [], []
    rows = dict(session.execute(select(LexemeState.lexeme_id, LexemeState.state)
                                .where(LexemeState.lexeme_id.in_(lexeme_ids))).all())
    names = set(session.scalars(select(Lexeme.id).where(Lexeme.id.in_(lexeme_ids), Lexeme.pos == "NNP",
                                                       Lexeme.lemma.in_(proper_nouns()))))
    new = sorted(i for i in lexeme_ids if rows.get(i, "new") == "new" and i not in names)
    review = sorted(lexeme_ids & due_lexeme_ids(session))
    return new, review


def word_end(ko: str, end: int, limit: int) -> int:
    """Extend a content token over the endings glued to it (web/src/segments.ts)."""
    while end < min(limit, len(ko)) and not _BOUNDARY.match(ko[end]):
        end += 1
    return end


def sentences(ko: str) -> list[tuple[int, int]]:
    return [(m.start(), m.end()) for m in _SENTENCE.finditer(ko) if m.group().strip()]


def context_rows(ep_id: str, paragraphs: list[EpisodeParagraph]) -> list[ContextSentence]:
    """One context sentence per (lexeme, sentence) of an episode, with the word's span."""
    out, seen = [], set()
    for p in paragraphs:
        content = sorted((t for t in p.tokens if "lex" in t), key=lambda t: t["s"])
        spans = sentences(p.ko)
        for i, t in enumerate(content):
            s0, s1 = next(((a, b) for a, b in spans if a <= t["s"] < b), (0, len(p.ko)))
            raw = p.ko[s0:s1]
            lead = len(raw) - len(raw.lstrip())
            text = raw.strip()
            limit = content[i + 1]["s"] if i + 1 < len(content) else len(p.ko)
            start = t["s"] - s0 - lead
            end = word_end(p.ko, t["e"], limit) - s0 - lead
            if (t["lex"], text) in seen or not 0 <= start < end <= len(text):
                continue
            seen.add((t["lex"], text))
            out.append(ContextSentence(lexeme_id=t["lex"], sentence_ko=text, sentence_en=p.en,
                                       origin=f"episode:{ep_id}", start=start, end=end))
    return out


def resolve_target_ref(q, lexemes: dict[str, int]) -> str | None:
    """meaning_check refs are authored as a lemma; store the lexeme id (DATA_MODEL `question.target_ref`)."""
    if q.kind != "meaning_check" or q.target_ref is None or q.target_ref.isdigit():
        return q.target_ref
    if q.target_ref not in lexemes:
        raise ValueError(f"meaning_check target_ref {q.target_ref!r} is not a word in the episode")
    return str(lexemes[q.target_ref])


def ingest_episode(session: Session, doc: EpisodeDoc, lookup: Lookup | None, publish: bool = False) -> IngestReport:
    """Insert or replace one episode. Caller commits."""
    ep = session.get(Episode, doc.id)
    if ep is None:
        ep = Episode(id=doc.id, created_at=utcnow(), status=doc.status)
        session.add(ep)
    ep.series = doc.series
    ep.title_ko, ep.title_en = doc.title_ko, doc.title_en
    ep.register_tags = list(doc.register_tags)
    ep.target_grammar = doc.target_grammar
    ep.source = doc.source
    ep.summary = doc.summary
    if publish:
        ep.status = "published"  # re-ingest without --publish keeps the current status
    ep.paragraphs.clear()
    session.flush()

    report = IngestReport(doc.id, coverage=1.0, content_tokens=0)
    all_tokens = []
    for idx, para in enumerate(doc.paragraphs):
        toks = analyze(para.ko)
        all_tokens.extend(toks)
        stored = []
        for t in toks:
            if t.kind == "content":
                lex, created = get_or_create_lexeme(session, t.lemma, t.pos, lookup)
                if created:
                    report.new_lexemes.append(t.key)
                if lex.gloss_source == "none" and t.key not in report.missing_gloss:
                    report.missing_gloss.append(t.key)
                stored.append({"s": t.start, "e": t.end, "lex": lex.id})
                report.content_tokens += 1
            elif t.grammar_code is not None:
                stored.append({"s": t.start, "e": t.end, "g": t.grammar_code})
        ep.paragraphs.append(EpisodeParagraph(idx=idx, ko=para.ko, en=para.en, tokens=stored))

    lemma_ids: dict[str, int] = {}
    ep_lex_ids = {t["lex"] for p in ep.paragraphs for t in p.tokens if "lex" in t}
    for lx in session.scalars(select(Lexeme).where(Lexeme.id.in_(ep_lex_ids)).order_by(Lexeme.id)):
        lemma_ids.setdefault(lx.lemma, lx.id)
    # Questions are updated in place by idx so their ids stay stable: question_answer events
    # point at them, and the SRS replay reads older answers through them.
    existing = {q.idx: q for q in ep.questions}
    for idx, q in enumerate(doc.questions):
        row = existing.pop(idx, None)
        if row is None:
            row = Question(idx=idx)
            ep.questions.append(row)
        row.kind, row.prompt_ko, row.prompt_en = q.kind, q.prompt_ko, q.prompt_en
        row.options, row.answer_idx = list(q.options), q.answer_idx
        row.target_ref = resolve_target_ref(q, lemma_ids)
    for row in existing.values():
        ep.questions.remove(row)

    session.execute(delete(ContextSentence).where(ContextSentence.origin == f"episode:{doc.id}"))
    session.add_all(context_rows(doc.id, ep.paragraphs))

    report.coverage = coverage(all_tokens, known_keys(session), proper_nouns())
    ep.coverage = report.coverage
    ep.new_lexemes, ep.review_lexemes = episode_lexeme_sets(
        session, {t["lex"] for p in ep.paragraphs for t in p.tokens if "lex" in t})
    ep.updated_at = utcnow()
    session.flush()
    return report


def seed(session: Session, lookup: Lookup | None) -> None:
    from .word_sets import seed_word_sets

    """Grammar points (analyzer codes + SYLLABUS_MAP rows) + flagged vocab (DECISIONS 20) + word-set lexemes.

    Idempotent; grammar_points.json fields overwrite earlier values. Caller commits.
    """
    for code, label in GRAMMAR_LABELS.items():
        if session.get(GrammarPoint, code) is None:
            session.add(GrammarPoint(code=code, label_ko=label))
    session.flush()
    for p in load_grammar_points():
        gp = session.get(GrammarPoint, p.code)
        if gp is None:
            gp = GrammarPoint(code=p.code)
            session.add(gp)
        gp.label_ko, gp.htsk_lesson = p.label_ko, p.htsk_lesson
        gp.ja_parallel, gp.ja_diff_note = p.ja_parallel, p.ja_diff_note
        gp.kiwi_pattern = p.kiwi_pattern
    session.flush()

    lexemes, grammar = load_flagged_vocab()
    now = utcnow()
    # Flagged items are a replay baseline (source "manual"); app/srs.py derives the rest.
    for s in lexemes:
        lex, _ = get_or_create_lexeme(session, s.lemma, s.pos, lookup)
        if lex.state is None:
            session.add(LexemeState(lexeme_id=lex.id, state=s.state, source=s.source, first_seen_at=now))
            session.flush()
            session.refresh(lex)
        lex.state.base_state, lex.state.base_source = s.state, s.source
    for g in grammar:
        row = session.get(GrammarState, g.code)
        if row is None:
            row = GrammarState(code=g.code, state=g.state, source=g.source, first_seen_at=now)
            session.add(row)
        row.base_state, row.base_source = g.state, g.source
    session.flush()
    seed_word_sets(session, lookup)  # lexemes for the word-set checklists (DECISIONS 67)
