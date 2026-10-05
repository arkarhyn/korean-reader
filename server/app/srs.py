"""Hidden SRS (SPEC 3.2): FSRS state for lexemes and grammar, derived from the event log.

`derive()` resets every state row to its baseline (what placement / the seed wrote,
`base_state`) and replays every event in (ts, id) order (DECISIONS 8). The scheduler has
no fuzzing and no minute-level steps, and every review happens at the event's client
time, so the result is a pure function of the baseline + log: replaying reproduces it
exactly. Only rows whose values change are written, so sync pull stays small.

Rules (Stage 6 plan, Austin 2026-10-05):
- episode_complete, per distinct content lexeme: tapped -> Again (a known word gets a
  soft lapse instead of a full reset); meaning check wrong -> Again, right and untapped
  -> Good (Easy if fast); untapped and due -> Good; untapped with no card and not known
  -> new card, Good; otherwise an exposure only.
- learning -> known once stability >= 21 days; grammar practicing -> solid the same way.
- grammar is graded only by grammar_check answers.
- set_state is a manual override; "I forgot this" (-> learning) soft-lapses the card.
- review_answer (Quick review) grades a due card.
"""

import zlib
from collections import defaultdict
from collections.abc import Iterable
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from typing import Any

from fsrs import Card, Rating, Scheduler, State
from sqlalchemy import select
from sqlalchemy.orm import Session

from .analyzer import proper_nouns
from .coverage import known_by_alias
from .db.models import Episode, Event, GrammarPoint, GrammarState, Lexeme, LexemeState, Question

SCHEDULER = Scheduler(learning_steps=(), relearning_steps=(), enable_fuzzing=False)
GRADUATE_DAYS = 21.0
SOFT_LAPSE_DAYS = 3.0
DEFAULT_DIFFICULTY = 5.0
EASY_MS = 8000
BASE_DUE = datetime(2000, 1, 1, tzinfo=UTC)  # unreviewed baseline cards: due since forever

LEXEME_STATES = ("new", "seen", "learning", "known", "ignored")
KNOWN = ("known", "ignored")
EXCLUDED_SERIES = ("placement",)  # calibration passages are placement's evidence, not reviews


@dataclass(frozen=True)
class Track:
    learning: str
    known: str
    carded_base: tuple[str, ...]  # baseline states that start with an (unreviewed) card
    fixed: tuple[str, ...] = ()  # never graded


LEX = Track("learning", "known", ("learning", "seen"), fixed=("ignored",))
GRAM = Track("practicing", "solid", ("introduced", "practicing"))


@dataclass
class Rec:
    state: str
    source: str
    card: Card | None = None
    exposures: int = 0
    lookups: int = 0
    first_seen_at: datetime | None = None
    last_seen_at: datetime | None = None
    card_before_manual: Card | None = None  # restored by an undo of the last set_state (not stored)


def grammar_card_id(code: str) -> int:
    return zlib.crc32(code.encode())


def new_card(card_id: int, due: datetime = BASE_DUE) -> Card:
    return Card(card_id=card_id, due=due)


def load_card(data: dict[str, Any] | None) -> Card | None:
    return Card.from_dict(data) if data else None


def dump_card(card: Card | None) -> dict[str, Any] | None:
    return card.to_dict() if card is not None else None


# ---- rules on one record ----

def soft_lapse(rec: Rec, card_id: int, ts: datetime, track: Track, due_now: bool = False) -> None:
    """Back to learning without a full reset: stability <= 3 days, difficulty unchanged."""
    s, d = SOFT_LAPSE_DAYS, DEFAULT_DIFFICULTY
    if rec.card is not None and rec.card.stability is not None:
        s, d = min(s, rec.card.stability), rec.card.difficulty
    # Due now = retrievability already at 0.9: as if last reviewed one stability ago.
    last = ts - timedelta(days=s) if due_now else ts
    rec.card = Card(card_id=card_id, state=State.Review, stability=s, difficulty=d,
                    due=ts if due_now else ts + timedelta(days=max(1, round(s))), last_review=last)
    rec.state = track.learning


def rate(rec: Rec, card_id: int, rating: Rating, ts: datetime, track: Track) -> None:
    if rec.state in track.fixed:
        return
    if rating == Rating.Again and rec.state == track.known:
        soft_lapse(rec, card_id, ts, track)
    else:
        rec.card, _ = SCHEDULER.review_card(rec.card or new_card(card_id, ts), rating, ts)
        if rec.state != track.known:
            rec.state = track.learning
        if rec.state == track.learning and rec.card.stability >= GRADUATE_DAYS:
            rec.state = track.known
    rec.source = "episode"


def known_until(card: Card | None) -> datetime | None:
    """When retrievability falls to 0.9: FSRS stability is exactly that interval.

    Used instead of `card.due`, which py-fsrs rounds up to whole days (>= 1), so a word
    looked up today would otherwise count as remembered until tomorrow.
    """
    if card is None or card.last_review is None or card.stability is None:
        return None
    return card.last_review + timedelta(days=card.stability)


def is_due(card: Card | None, at: datetime) -> bool:
    """Has a card that was never reviewed, or whose retrievability is below 0.9 at `at`."""
    if card is None:
        return False
    until = known_until(card)
    return until is None or until <= at


# ---- replay ----

@dataclass
class EpisodeInfo:
    series: str
    lexeme_ids: list[int]
    grammar_codes: set[str]


@dataclass
class QuestionInfo:
    episode_id: str
    kind: str
    target_ref: str | None


@dataclass
class Replay:
    lexemes: dict[int, tuple[str, str]]  # id -> (lemma, pos)
    names: set[int]  # story-name lexeme ids (always known, never graded)
    episodes: dict[str, EpisodeInfo]
    questions: dict[int, QuestionInfo]
    grammar_codes: set[str]
    lex: dict[int, Rec] = field(default_factory=dict)
    gram: dict[str, Rec] = field(default_factory=dict)
    answers: dict[str, dict[int, dict[str, Any]]] = field(default_factory=lambda: defaultdict(dict))

    # -- helpers --

    def lex_rec(self, lex_id: int, ts: datetime, state: str = "new") -> Rec:
        rec = self.lex.get(lex_id)
        if rec is None:
            rec = self.lex[lex_id] = Rec(state=state, source="episode", first_seen_at=ts)
        return rec

    def raw_known(self) -> set[tuple[str, str]]:
        return {self.lexemes[i] for i, r in self.lex.items() if r.state in KNOWN and i in self.lexemes}

    def resolve_lexeme(self, ref: Any, lex_ids: Iterable[int]) -> int | None:
        ids = sorted(set(lex_ids))
        if isinstance(ref, int) or (isinstance(ref, str) and ref.isdigit()):
            return int(ref) if int(ref) in ids else None
        return next((i for i in ids if self.lexemes.get(i, ("",))[0] == ref), None)

    # -- events --

    def apply(self, ev: Event) -> None:
        handler = getattr(self, f"on_{ev.type}", None)
        if handler is not None:
            handler(ev.ts, ev.payload or {})

    def on_set_state(self, ts: datetime, p: dict[str, Any]) -> None:
        lex_id, state = p.get("lexeme_id"), p.get("state")
        if state not in LEXEME_STATES or not isinstance(lex_id, int) or lex_id not in self.lexemes:
            return
        rec = self.lex_rec(lex_id, ts)
        if p.get("undo"):
            rec.card = rec.card_before_manual
        else:
            rec.card_before_manual = rec.card
            if state == "learning" and rec.state != "learning":
                soft_lapse(rec, lex_id, ts, LEX, due_now=True)  # "I forgot this": due again now
        rec.state, rec.source = state, "manual"
        rec.last_seen_at = max(filter(None, (rec.last_seen_at, ts)))

    def on_word_tap(self, ts: datetime, p: dict[str, Any]) -> None:
        if isinstance(lex_id := p.get("lexeme_id"), int) and lex_id in self.lexemes:
            self.lex_rec(lex_id, ts).lookups += 1

    def on_word_untap(self, ts: datetime, p: dict[str, Any]) -> None:
        if isinstance(lex_id := p.get("lexeme_id"), int) and (rec := self.lex.get(lex_id)) is not None:
            rec.lookups = max(0, rec.lookups - 1)

    def on_question_answer(self, ts: datetime, p: dict[str, Any]) -> None:
        qid, ep_id = p.get("question_id"), p.get("episode_id")
        q = self.questions.get(qid) if isinstance(qid, int) else None
        kind, ref = p.get("kind") or (q and q.kind), p.get("target_ref") or (q and q.target_ref)
        if not ep_id or not kind or qid in self.answers[ep_id]:
            return  # first answer per question per visit counts
        self.answers[ep_id][qid] = {"kind": kind, "target_ref": ref, "correct": bool(p.get("correct")),
                                    "ms": p.get("ms")}

    def on_review_answer(self, ts: datetime, p: dict[str, Any]) -> None:
        lex_id = p.get("lexeme_id")
        rec = self.lex.get(lex_id) if isinstance(lex_id, int) else None
        if rec is not None and is_due(rec.card, ts) and rec.state not in KNOWN:
            rate(rec, lex_id, Rating.Good if p.get("correct") else Rating.Again, ts, LEX)

    def on_episode_complete(self, ts: datetime, p: dict[str, Any]) -> None:
        ep_id = p.get("episode_id")
        info = self.episodes.get(ep_id)
        answers = self.answers.pop(ep_id, {})
        if info is None or info.series in EXCLUDED_SERIES:
            return
        lex_ids = [i for i in (p.get("lexeme_ids") or info.lexeme_ids) if i in self.lexemes]
        tapped = {i for i in p.get("tapped_lexeme_ids", []) if isinstance(i, int)}

        lex_checks: dict[int, dict[str, Any]] = {}
        gram_checks: dict[str, dict[str, Any]] = {}
        for a in answers.values():
            if a["kind"] == "meaning_check":
                if (lex := self.resolve_lexeme(a["target_ref"], lex_ids)) is not None:
                    lex_checks.setdefault(lex, a)
            elif a["kind"] == "grammar_check" and a["target_ref"] in self.grammar_codes:
                gram_checks.setdefault(a["target_ref"], a)

        raw_known = self.raw_known()
        for lex in sorted(set(lex_ids)):
            if lex in self.names:
                continue
            rec = self.lex.get(lex)
            alias_known = rec is None and known_by_alias(*self.lexemes[lex], raw_known)
            known_no_card = alias_known or (rec is not None and rec.state in KNOWN and rec.card is None)
            if rec is not None and rec.state in LEX.fixed:
                rec.exposures += lex not in tapped
                rec.last_seen_at = ts
                continue
            check = lex_checks.get(lex)
            if lex in tapped or (check is not None and not check["correct"]):
                rec = rec or self.lex_rec(lex, ts, "known" if alias_known else "new")
                rate(rec, lex, Rating.Again, ts, LEX)
            elif check is not None and not known_no_card:
                rec = rec or self.lex_rec(lex, ts)
                fast = isinstance(check["ms"], int | float) and check["ms"] <= EASY_MS
                rate(rec, lex, Rating.Easy if fast else Rating.Good, ts, LEX)
            elif rec is not None and is_due(rec.card, ts):
                rate(rec, lex, Rating.Good, ts, LEX)
            elif not known_no_card and (rec is None or rec.card is None):
                rec = rec or self.lex_rec(lex, ts)
                rate(rec, lex, Rating.Good, ts, LEX)  # first encounter, read without a lookup
            if rec is not None:
                rec.exposures += lex not in tapped
                rec.last_seen_at = ts

        for code in sorted(info.grammar_codes | set(gram_checks)):
            rec = self.gram.get(code)
            if (check := gram_checks.get(code)) is not None:
                if rec is None:
                    rec = self.gram[code] = Rec(state="new", source="episode", first_seen_at=ts)
                rate(rec, grammar_card_id(code), Rating.Good if check["correct"] else Rating.Again, ts, GRAM)
            if rec is not None:
                rec.exposures += 1
                rec.last_seen_at = ts


def _baseline(row: LexemeState | GrammarState, track: Track, card_id: int) -> Rec:
    card = new_card(card_id) if row.base_state in track.carded_base else None
    return Rec(state=row.base_state, source=row.base_source or "placement", card=card,
               first_seen_at=row.first_seen_at)


def load_replay(session: Session) -> Replay:
    lexemes = {r.id: (r.lemma, r.pos) for r in session.execute(select(Lexeme.id, Lexeme.lemma, Lexeme.pos))}
    names_set = proper_nouns()
    names = {i for i, (lemma, pos) in lexemes.items() if pos == "NNP" and lemma in names_set}
    episodes: dict[str, EpisodeInfo] = {}
    for ep in session.scalars(select(Episode)):
        toks = [t for p in ep.paragraphs for t in p.tokens]
        codes = {t["g"] for t in toks if "g" in t}
        if ep.target_grammar:
            codes.add(ep.target_grammar)
        episodes[ep.id] = EpisodeInfo(ep.series, [t["lex"] for t in toks if "lex" in t], codes)
    questions = {q.id: QuestionInfo(q.episode_id, q.kind, q.target_ref) for q in session.scalars(select(Question))}
    grammar_codes = set(session.scalars(select(GrammarPoint.code)))
    rp = Replay(lexemes, names, episodes, questions, grammar_codes)
    for row in session.scalars(select(LexemeState).where(LexemeState.base_state.is_not(None))):
        rp.lex[row.lexeme_id] = _baseline(row, LEX, row.lexeme_id)
    for row in session.scalars(select(GrammarState).where(GrammarState.base_state.is_not(None))):
        rp.gram[row.code] = _baseline(row, GRAM, grammar_card_id(row.code))
    return rp


def replay(session: Session) -> Replay:
    rp = load_replay(session)
    for ev in session.scalars(select(Event).where(Event.type != "placement_answer").order_by(Event.ts, Event.id)):
        rp.apply(ev)
    return rp


def _write(row: LexemeState | GrammarState, rec: Rec, keep_first_seen: bool) -> bool:
    values = {"state": rec.state, "source": rec.source, "fsrs_card": dump_card(rec.card),
              "exposures": rec.exposures, "lookups": rec.lookups, "last_seen_at": rec.last_seen_at}
    if not keep_first_seen:
        values["first_seen_at"] = rec.first_seen_at
    changed = False
    for k, v in values.items():
        if getattr(row, k) != v:
            setattr(row, k, v)
            changed = True
    return changed


@dataclass
class DeriveResult:
    changed: int
    created: int
    transitions: dict[tuple[str, str], int]  # (old state, new state) -> lexeme count


def derive(session: Session) -> DeriveResult:
    """Rebuild every lexeme_state / grammar_state row from baseline + event log. Caller commits."""
    rp = replay(session)
    result = DeriveResult(0, 0, defaultdict(int))
    reset = Rec(state="new", source="episode")

    for model, recs, key, track in ((LexemeState, rp.lex, "lexeme_id", LEX), (GrammarState, rp.gram, "code", GRAM)):
        rows = {getattr(r, key): r for r in session.scalars(select(model))}
        for k, row in rows.items():
            rec = recs.get(k)
            if rec is None:  # no baseline and no events (any more): back to new, never deleted
                rec = Rec(state=reset.state, source=row.base_source or reset.source)
            old = row.state
            if _write(row, rec, keep_first_seen=row.base_state is not None):
                result.changed += 1
                if model is LexemeState and old != rec.state:
                    result.transitions[(old, rec.state)] += 1
        for k, rec in recs.items():
            if k in rows:
                continue
            row = model(**{key: k}, state=rec.state, source=rec.source, exposures=0, lookups=0)
            _write(row, rec, keep_first_seen=False)
            session.add(row)
            result.created += 1
            if model is LexemeState:
                result.transitions[("-", rec.state)] += 1
    session.flush()
    return result


# ---- reading derived state ----

def retrievability(card: Card | None, now: datetime) -> float:
    if card is None or card.last_review is None:
        return 0.0
    return SCHEDULER.get_card_retrievability(card, now)


def counts_known(state: str, card_data: dict[str, Any] | None, now: datetime) -> bool:
    """SPEC 7: known/ignored, or learning with retrievability >= 0.9."""
    if state in KNOWN:
        return True
    until = known_until(load_card(card_data))
    return state == "learning" and until is not None and now < until


def due_now(state: str, card_data: dict[str, Any] | None, now: datetime) -> bool:
    """Due for review: has a card that is due, and is not graduated / ignored."""
    return state not in KNOWN and state != "solid" and is_due(load_card(card_data), now)
