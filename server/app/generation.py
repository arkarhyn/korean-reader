"""Generator support (SPEC 5): the generation context export and the draft checker.

Both run on the server's DB. "Due" comes from the FSRS cards derived from the
event log (app/srs.py): reviewed cards that are due, least retrievable first, then
never-reviewed cards (placement `seen`, "I forgot this") by frequency rank.
"""

import re
from collections import Counter
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from .analyzer import analyze, proper_nouns, story_names
from .analyzer import morphemes
from .analyzer.patterns import count_grammar, find, seed_patterns
from .config import REPO_ROOT
from .content.schema import Episode as EpisodeDoc
from .coverage import coverage
from .db.models import Episode, Event, GrammarPoint, GrammarState, Lexeme, LexemeState, utcnow
from .ingest import due_lexeme_ids, known_keys, known_lexeme_ids
from .srs import due_now, load_card, retrievability

BAND = (0.95, 0.98)
NEW_WORDS = (3, 6)
TARGET_GRAMMAR = (4, 6)
HANGUL_CHARS = (400, 700)
GRAMMAR_USABLE = ("introduced", "practicing", "solid")
CONTENT_SERIES = ("main", "side-parent", "side-folk", "primer")
NEW_WORD_CANDIDATES = 150
DOCS = {"story_bible": "docs/STORY_BIBLE.md", "learner_profile": "docs/LEARNER_PROFILE.md"}

_HANGUL = re.compile(r"[가-힣]")


def hangul_len(text: str) -> int:
    return len(_HANGUL.findall(text))


def _lexeme_row(lx: Lexeme, st: LexemeState | None = None) -> dict[str, Any]:
    row: dict[str, Any] = {"id": lx.id, "lemma": lx.lemma, "pos": lx.pos, "gloss_en": lx.gloss_en}
    if lx.freq_rank is not None:
        row["rank"] = lx.freq_rank
    if st is not None:
        row["state"] = st.state
    return row


def _due_key(lx: Lexeme, st: LexemeState, now: datetime) -> tuple:
    card = load_card(st.fsrs_card)
    if card is not None and card.last_review is not None:
        return (0, retrievability(card, now), lx.id)
    return (1, lx.freq_rank if lx.freq_rank is not None else 10**9, lx.id)


def due_lexemes(session: Session, now: datetime | None = None) -> list[tuple[Lexeme, LexemeState]]:
    """Due now, in the order the generator should weave them in."""
    now = now or utcnow()
    rows = session.execute(select(Lexeme, LexemeState).join(LexemeState)
                           .where(LexemeState.fsrs_card.is_not(None))).all()
    due = [(lx, st) for lx, st in rows if due_now(st.state, st.fsrs_card, now)]
    return sorted(due, key=lambda r: _due_key(*r, now))


def due_row(lx: Lexeme, st: LexemeState, now: datetime) -> dict[str, Any]:
    card = load_card(st.fsrs_card)
    row = _lexeme_row(lx, st)
    row["reviewed"] = card is not None and card.last_review is not None
    if row["reviewed"]:
        row["retrievability"] = round(retrievability(card, now), 2)
        row["last_review"] = card.last_review.date().isoformat()
    return row


def next_episode_id(session: Session, season: int = 1) -> str:
    prefix = f"S{season:02d}E"
    ids = session.scalars(select(Episode.id).where(Episode.id.like(f"{prefix}%"))).all()
    nums = [int(i[len(prefix):]) for i in ids if i[len(prefix):].isdigit()]
    return f"{prefix}{max(nums, default=0) + 1:03d}"


def _still_present(session: Session, episode_id: str | None, text: str | None) -> bool:
    """A flagged sentence counts as open until its episode no longer contains it (rewritten)."""
    ep = session.get(Episode, episode_id) if episode_id else None
    if ep is None or not text:
        return ep is not None
    needle = text.strip().strip("\"'").strip()
    return any(needle in p.ko for p in ep.paragraphs)


PRIMER_WORDS = 10  # top unknown words offered per requested podcast part
PRIMER_NEW_WORDS = (5, 10)


def primer_requests(session: Session) -> list[dict[str, Any]]:
    """Podcast parts Austin asked to be pre-taught (`primer_request`) that have no primer episode yet,
    each with its most frequent words that don't count as known (story/host names excluded)."""
    done = {src.removeprefix("primer:") for src in session.scalars(
        select(Episode.source).where(Episode.source.like("primer:%")))}
    known = known_lexeme_ids(session)
    names = proper_nouns()
    out, seen = [], set()
    for ev in session.scalars(select(Event).where(Event.type == "primer_request").order_by(Event.ts)):
        part_id = ev.payload.get("episode_id")
        if part_id in seen or part_id in done:
            continue
        seen.add(part_id)
        part = session.get(Episode, part_id)
        if part is None or part.series != "podcast":
            continue
        counts = Counter(t["lex"] for p in part.paragraphs for t in p.tokens if "lex" in t and t["lex"] not in known)
        words = []
        for lex_id, n in counts.most_common():
            lx = session.get(Lexeme, lex_id)
            if lx is None or (lx.pos == "NNP" and lx.lemma in names) or not lx.gloss_en:
                continue
            words.append({"lemma": lx.lemma, "pos": lx.pos, "gloss": lx.gloss_en, "rank": lx.freq_rank, "count": n})
            if len(words) == PRIMER_WORDS:
                break
        out.append({"part_id": part_id, "source": f"primer:{part_id}", "title_ko": part.title_ko,
                    "title_en": part.title_en, "episode_title": part.summary, "words": words,
                    "requested_at": ev.ts.isoformat()})
    return out


def build_context(session: Session, recent: int = 10) -> dict[str, Any]:
    """Everything a /generate-batch session needs, as one JSON document."""
    states = {lx.id: (lx, st) for lx, st in session.execute(select(Lexeme, LexemeState).join(LexemeState)).all()}
    known = sorted((lx.lemma, lx.pos) for lx, st in states.values() if st.state in ("known", "ignored"))
    learning = [_lexeme_row(lx, st) for lx, st in states.values() if st.state == "learning"]

    candidates = session.scalars(
        select(Lexeme).outerjoin(LexemeState)
        .where(Lexeme.freq_rank.is_not(None), Lexeme.gloss_source != "none",
               (LexemeState.state.is_(None)) | (LexemeState.state == "new"))
        .order_by(Lexeme.freq_rank).limit(NEW_WORD_CANDIDATES)).all()

    now = utcnow()
    grows = {g.code: g for g in session.scalars(select(GrammarState))}
    grammar = []
    for gp in sorted(session.scalars(select(GrammarPoint)), key=lambda gp: (gp.order, gp.code)):
        g = grows.get(gp.code)
        grammar.append({"code": gp.code, "label_ko": gp.label_ko, "lesson": gp.htsk_lesson, "order": gp.order,
                        "state": g.state if g else "new", "tested": g is not None, "has_lesson": gp.lesson is not None,
                        "ja": gp.ja_parallel, "pattern": bool(gp.kiwi_pattern),
                        "due": g is not None and due_now(g.state, g.fsrs_card, now)})

    episodes = session.scalars(select(Episode).where(Episode.series.in_(CONTENT_SERIES))
                               .order_by(Episode.created_at.desc()).limit(recent)).all()
    recent_targets = {e.target_grammar for e in episodes if e.target_grammar}
    # Due grammar first (SPEC 3.2: the generator prioritizes due items).
    suggested = [g["code"] for g in sorted(grammar, key=lambda g: not g["due"])
                 if g["state"] in ("introduced", "practicing") and g["pattern"] and g["code"] not in recent_targets]

    flags = [{"episode_id": ev.payload.get("episode_id"), "text": ev.payload.get("text"), "ts": ev.ts.isoformat()}
             for ev in session.scalars(select(Event).where(Event.type == "flag_sentence").order_by(Event.ts))
             if _still_present(session, ev.payload.get("episode_id"), ev.payload.get("text"))]

    return {
        "generated_at": utcnow().isoformat(),
        "next_episode_id": next_episode_id(session),
        "targets": {"coverage": list(BAND), "new_words": list(NEW_WORDS), "target_grammar_count": list(TARGET_GRAMMAR),
                    "hangul_chars": list(HANGUL_CHARS)},
        "proper_nouns": sorted(story_names()),
        "known": [f"{lemma}/{pos}" for lemma, pos in known],
        "learning": learning,
        "due": [due_row(lx, st, now) for lx, st in due_lexemes(session, now)],
        "new_word_candidates": [_lexeme_row(lx) for lx in candidates],
        "grammar": grammar,
        "grammar_usable": [g["code"] for g in grammar if g["state"] in GRAMMAR_USABLE],
        "grammar_avoid": [g["code"] for g in grammar if g["state"] == "new" and (g["tested"] or g["has_lesson"])],
        "grammar_untested": [g["code"] for g in grammar if g["state"] == "new" and not g["tested"] and not g["has_lesson"]],
        # Stage 8: at most one new point per batch, as one episode's target; its lesson card gates that episode.
        "next_new_targets": [g["code"] for g in grammar if g["state"] == "new" and g["has_lesson"] and g["pattern"]][:3],
        "suggested_targets": suggested,
        "recent_episodes": [{"id": e.id, "series": e.series, "title_ko": e.title_ko, "title_en": e.title_en,
                             "target_grammar": e.target_grammar, "summary": e.summary, "coverage": e.coverage,
                             "status": e.status} for e in episodes],
        "flagged_sentences": flags,
        "primer_requests": primer_requests(session),
        "docs": {k: (REPO_ROOT / v).read_text(encoding="utf-8") for k, v in DOCS.items()},
    }


# ---- draft checker ----

@dataclass
class Unknown:
    lemma: str
    pos: str
    count: int
    state: str | None  # None = no lexeme_state row (or no lexeme yet)
    rank: int | None
    gloss: str
    is_due: bool = False  # has an FSRS card that is due now


@dataclass
class DraftReport:
    episode_id: str
    coverage: float
    content_tokens: int
    hangul: int
    target_grammar: str | None
    target_count: int | None
    unknown: list[Unknown]
    avoid_grammar: dict[str, int] = field(default_factory=dict)
    problems: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)  # reported, not failing

    @property
    def new_words(self) -> list[Unknown]:
        return [u for u in self.unknown if not u.is_due]

    @property
    def due_words(self) -> list[Unknown]:
        return [u for u in self.unknown if u.is_due]

    @property
    def ok(self) -> bool:
        return not self.problems


def meaning_checks_wanted(due_words: int) -> int:
    return max(1, round(due_words / 5)) if due_words else 0


def batch_due_coverage(session: Session, docs: list[EpisodeDoc], top: int = 15) -> tuple[list[str], list[str]]:
    """(covered, missing) lemmas among the top-N due words across a batch of drafts."""
    due = [lx.lemma for lx, _ in due_lexemes(session)[:top]]
    used = {t.lemma for doc in docs for para in doc.paragraphs for t in analyze(para.ko) if t.kind == "content"}
    return [w for w in due if w in used], [w for w in due if w not in used]


def _inside_usable(text: str, usable: set[str]) -> Counter[str]:
    """Per code, matches lying wholly inside a match of a usable point (-기 in -기 전에): not new use."""
    patterns = seed_patterns()
    morphs = morphemes(text)
    spans = {code: find(morphs, pat) for code, pat in patterns.items()}
    cover = [sp for code in usable if code in spans for sp in spans[code]]
    out: Counter[str] = Counter()
    for code, sps in spans.items():
        if code in usable:
            continue
        n = sum(1 for s, e in sps if any(cs <= s and e <= ce and (cs, ce) != (s, e) for cs, ce in cover))
        if n:
            out[code] = n
    return out


def check_draft(session: Session, doc: EpisodeDoc, known: set[tuple[str, str]] | None = None) -> DraftReport:
    """Coverage, new/due words, target grammar density, length, and `new` grammar used."""
    known = known_keys(session) if known is None else known
    names = proper_nouns()
    text = doc.text_ko
    # Per paragraph, exactly as ingest does: Kiwi's reading depends on context.
    toks = [t for para in doc.paragraphs for t in analyze(para.ko)]
    cov = coverage(toks, known, names)
    counts: dict[tuple[str, str], int] = {}
    for t in toks:
        if t.kind == "content" and t.key not in known and not (t.pos == "NNP" and t.lemma in names):
            counts[t.key] = counts.get(t.key, 0) + 1

    unknown = []
    due_ids = due_lexeme_ids(session)
    for (lemma, pos), n in sorted(counts.items(), key=lambda kv: -kv[1]):
        row = session.execute(select(Lexeme, LexemeState).outerjoin(LexemeState)
                              .where(Lexeme.lemma == lemma, Lexeme.pos == pos)).first()
        lx, st = row if row else (None, None)
        unknown.append(Unknown(lemma, pos, n, st.state if st else None,
                               lx.freq_rank if lx else None, lx.gloss_en if lx else "",
                               is_due=lx is not None and lx.id in due_ids))

    gstates = {g.code: g.state for g in session.scalars(select(GrammarState))}
    lessons = {gp.code for gp in session.scalars(select(GrammarPoint)) if gp.lesson}  # JSON null != SQL NULL
    grammar_counts = sum((count_grammar(para.ko) for para in doc.paragraphs), Counter())
    usable = {c for c, st in gstates.items() if st in GRAMMAR_USABLE}
    inside = sum((_inside_usable(para.ko, usable) for para in doc.paragraphs), Counter())
    # Gating (SPEC 3.4, DECISIONS 92): `new` with a state row (placement said unknown) or with a lesson
    # card waiting = blocked; never tested (L29+, no row) and no lesson yet = a warning only.
    used_new = {c: n - inside[c] for c, n in grammar_counts.items()
                if gstates.get(c, "new") == "new" and c != doc.target_grammar and n > inside[c]}
    avoid = {c: n for c, n in used_new.items() if c in gstates or c in lessons}
    untested = {c: n for c, n in used_new.items() if c not in avoid}
    target_count = grammar_counts.get(doc.target_grammar, 0) if doc.target_grammar else None

    r = DraftReport(doc.id, cov, sum(1 for t in toks if t.kind == "content"), hangul_len(text),
                    doc.target_grammar, target_count, unknown, avoid)
    lo, hi = BAND
    if cov < lo:
        r.problems.append(f"coverage {cov:.1%} < {lo:.0%}")
    elif cov > hi:
        r.problems.append(f"coverage {cov:.1%} > {hi:.0%}")
    primer = doc.series == "primer"  # pre-teaches a podcast part's words (DECISIONS 87)
    lo_new, hi_new = PRIMER_NEW_WORDS if primer else NEW_WORDS
    if not lo_new <= len(r.new_words) <= hi_new:
        r.problems.append(f"{len(r.new_words)} new words (want {lo_new}-{hi_new})")
    if not r.due_words:
        r.problems.append("no due words")
    else:  # SPEC 3.2: about 1 in 5 due words also gets a meaning check
        due_lemmas = {u.lemma for u in r.due_words}
        checked = {q.target_ref for q in doc.questions if q.kind == "meaning_check"}
        want = meaning_checks_wanted(len(r.due_words))
        if len(checked & due_lemmas) < want:
            r.problems.append(f"{len(checked & due_lemmas)} meaning checks on due words (want {want}; "
                              f"target_ref = the lemma)")
    lemmas = {t.lemma for t in toks if t.kind == "content"}
    for q in doc.questions:
        if q.kind == "meaning_check" and q.target_ref not in lemmas:
            r.problems.append(f"meaning_check target_ref {q.target_ref!r} is not a word in the episode")
    if doc.target_grammar is None:
        if not primer:
            r.problems.append("no target_grammar")
    elif doc.target_grammar not in seed_patterns():
        r.problems.append(f"{doc.target_grammar} has no kiwi_pattern; cannot count it")
    elif not TARGET_GRAMMAR[0] <= (target_count or 0) <= TARGET_GRAMMAR[1]:
        r.problems.append(f"{doc.target_grammar} x{target_count} (want {TARGET_GRAMMAR[0]}-{TARGET_GRAMMAR[1]})")
    if doc.target_grammar and gstates.get(doc.target_grammar, "new") == "new":
        if doc.target_grammar in lessons:
            r.warnings.append(f"target {doc.target_grammar} is new: its lesson card opens before this episode")
        else:
            r.problems.append(f"target {doc.target_grammar} is new and has no lesson card "
                              f"(write content/grammar/lessons/{doc.target_grammar}.json)")
    if not HANGUL_CHARS[0] <= r.hangul <= HANGUL_CHARS[1]:
        r.problems.append(f"{r.hangul} hangul chars (want {HANGUL_CHARS[0]}-{HANGUL_CHARS[1]})")
    if avoid:
        r.problems.append("uses grammar at state new: " + ", ".join(f"{c} x{n}" for c, n in avoid.items()))
    if untested:
        r.warnings.append("uses untested grammar (no lesson yet; keep it light): "
                          + ", ".join(f"{c} x{n}" for c, n in sorted(untested.items(), key=lambda kv: -kv[1])))
    return r
