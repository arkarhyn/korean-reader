"""Load authored episode JSON and seed data into the DB.

Tokens are computed here (not authored): content tokens point at a lexeme id,
grammar tokens with a stable code carry it. Glosses come from krdict only
(SPEC 5); a lemma with no entry gets gloss_source="none" and is reported.
"""

from collections.abc import Callable
from dataclasses import dataclass, field

from sqlalchemy import select
from sqlalchemy.orm import Session

from .analyzer import analyze, grammar_codes, proper_nouns
from .content.schema import Episode as EpisodeDoc
from .coverage import coverage
from .db.models import Episode, EpisodeParagraph, GrammarPoint, GrammarState, Lexeme, LexemeState, Question, utcnow
from .krdict.client import KrdictEntry
from .seed import load_flagged_vocab, load_grammar_points

Lookup = Callable[[str, str], KrdictEntry | None]

# "Due" until FSRS exists (Stage 6): lexemes the generator should weave back in.
DUE_STATES = ("learning", "seen")

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


def known_keys(session: Session) -> set[tuple[str, str]]:
    """SPEC 7 known set. `learning` joins once FSRS retrievability exists (Stage 6)."""
    rows = session.execute(
        select(Lexeme.lemma, Lexeme.pos).join(LexemeState).where(LexemeState.state.in_(("known", "ignored"))))
    return {(r.lemma, r.pos) for r in rows}


def episode_lexeme_sets(session: Session, lexeme_ids: set[int]) -> tuple[list[int], list[int]]:
    """(new, review) lexeme ids in an episode: review = due state, new = no history (story names excluded)."""
    if not lexeme_ids:
        return [], []
    rows = dict(session.execute(select(LexemeState.lexeme_id, LexemeState.state)
                                .where(LexemeState.lexeme_id.in_(lexeme_ids))).all())
    names = set(session.scalars(select(Lexeme.id).where(Lexeme.id.in_(lexeme_ids), Lexeme.pos == "NNP",
                                                       Lexeme.lemma.in_(proper_nouns()))))
    new = sorted(i for i in lexeme_ids if rows.get(i, "new") == "new" and i not in names)
    review = sorted(i for i in lexeme_ids if rows.get(i) in DUE_STATES)
    return new, review


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
    ep.questions.clear()
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

    for idx, q in enumerate(doc.questions):
        ep.questions.append(Question(idx=idx, kind=q.kind, prompt_ko=q.prompt_ko, prompt_en=q.prompt_en,
                                     options=list(q.options), answer_idx=q.answer_idx, target_ref=q.target_ref))

    report.coverage = coverage(all_tokens, known_keys(session), proper_nouns())
    ep.coverage = report.coverage
    ep.new_lexemes, ep.review_lexemes = episode_lexeme_sets(
        session, {t["lex"] for p in ep.paragraphs for t in p.tokens if "lex" in t})
    ep.updated_at = utcnow()
    session.flush()
    return report


def seed(session: Session, lookup: Lookup | None) -> None:
    """Grammar points (analyzer codes + SYLLABUS_MAP rows) + flagged vocab (DECISIONS 20).

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
    for s in lexemes:
        lex, _ = get_or_create_lexeme(session, s.lemma, s.pos, lookup)
        if lex.state is None:
            session.add(LexemeState(lexeme_id=lex.id, state=s.state, source=s.source, first_seen_at=now))
    for g in grammar:
        if session.get(GrammarState, g.code) is None:
            session.add(GrammarState(code=g.code, state=g.state, source=g.source, first_seen_at=now))
    session.flush()
