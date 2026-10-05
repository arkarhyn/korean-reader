"""Placement from the event log: collect the latest finished attempt, fit, write states, evaluate.

State is derived from `placement_answer` events (DECISIONS 8), so a re-fit replays
the same answers. Rows with a source other than `placement` (e.g. the manually
flagged vocab) are never touched.
"""

from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime
from statistics import median
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..db.models import Episode, Event, GrammarState, Lexeme, LexemeState, utcnow
from ..ingest import known_lexeme_ids
from ..srs import derive
from . import items
from .fit import (KNOWN_THRESHOLD, VocabParams, false_alarm_rate, fit_vocab, grammar_state, lexeme_states,
                  posterior_draws, posterior_known_given_yes,
                  unknown_rate_interval)

UNLISTED_RANK_FACTOR = 1.5  # lexemes outside the NIKL list rank past its end
ACCEPT_LEVEL = 0.95  # Stage 4 acceptance: observed tap rate inside the leave-one-out 95% interval


@dataclass
class Calibration:
    tapped: set[int]
    rating: int | None
    ms: int | None


@dataclass
class Attempt:
    attempt_id: str
    started_at: datetime
    finished_at: datetime
    grammar: dict[str, bool] = field(default_factory=dict)  # item id -> got it
    vocab: dict[str, bool] = field(default_factory=dict)  # item id -> yes
    calibration: dict[str, Calibration] = field(default_factory=dict)  # episode id -> result


def latest_attempt(session: Session) -> Attempt | None:
    """Latest attempt with a `done` event. Within an attempt the last answer per item wins."""
    events = session.scalars(select(Event).where(Event.type == "placement_answer").order_by(Event.ts))
    by_attempt: dict[str, list[Event]] = defaultdict(list)
    for ev in events:
        if (aid := ev.payload.get("attempt_id")):
            by_attempt[aid].append(ev)
    done = [(next(e.ts for e in evs if e.payload.get("section") == "done"), aid)
            for aid, evs in by_attempt.items() if any(e.payload.get("section") == "done" for e in evs)]
    if not done:
        return None
    finished_at, aid = max(done)
    evs = by_attempt[aid]
    att = Attempt(aid, started_at=evs[0].ts, finished_at=finished_at)
    for ev in evs:
        p = ev.payload
        match p.get("section"):
            case "grammar":
                att.grammar[p["item_id"]] = bool(p["got_it"])
            case "vocab":
                att.vocab[p["item_id"]] = bool(p["yes"])
            case "calibration":
                att.calibration[p["episode_id"]] = Calibration(
                    set(p.get("tapped_lexeme_ids", [])), p.get("rating"), p.get("ms"))
    return att


# ---- model inputs ----

@dataclass
class Inputs:
    ranks: dict[int, float]  # every lexeme id -> rank used by the model
    listed: set[int]  # lexemes with NIKL rank or band
    pseudo: tuple[int, int]  # (yes, total)
    yes_no: dict[int, bool]  # lexeme id -> yes (real test words)
    yes_no_ranks: list[tuple[float, bool]]  # incl. test words with no lexeme row
    passages: dict[str, list[int]]  # calibration episode id -> running content lexeme ids


def gather(session: Session, att: Attempt) -> Inputs:
    lexemes = session.execute(select(Lexeme.id, Lexeme.lemma, Lexeme.pos, Lexeme.freq_rank, Lexeme.freq_band)).all()
    band_ranks: dict[str, list[int]] = defaultdict(list)
    for r in lexemes:
        if r.freq_rank is not None and r.freq_band:
            band_ranks[r.freq_band].append(r.freq_rank)
    band_median = {b: median(v) for b, v in band_ranks.items()}
    max_rank = max((r.freq_rank for r in lexemes if r.freq_rank is not None), default=10000)
    unlisted = max_rank * UNLISTED_RANK_FACTOR

    ranks: dict[int, float] = {}
    listed: set[int] = set()
    by_key: dict[tuple[str, str], int] = {}
    for r in lexemes:
        by_key[(r.lemma, r.pos)] = r.id
        if r.freq_rank is not None:
            ranks[r.id] = float(r.freq_rank)
        elif r.freq_band in band_median:  # listed without a rank (proper nouns, some numerals)
            ranks[r.id] = float(band_median[r.freq_band])
        else:
            ranks[r.id] = unlisted
            continue
        listed.add(r.id)

    pseudo_yes = pseudo_total = 0
    yes_no: dict[int, bool] = {}
    yes_no_ranks: list[tuple[float, bool]] = []
    for it in items.vocab_items():
        if it["id"] not in att.vocab:
            continue
        yes = att.vocab[it["id"]]
        if not it["real"]:
            pseudo_total += 1
            pseudo_yes += yes
            continue
        lex_id = by_key.get((it["lemma"], it["pos"]))
        yes_no_ranks.append((ranks[lex_id] if lex_id is not None else float(it["rank"]), yes))
        if lex_id is not None:
            yes_no[lex_id] = yes

    passages: dict[str, list[int]] = {}
    for ep_id in att.calibration:
        ep = session.get(Episode, ep_id)
        if ep is not None:
            passages[ep_id] = [t["lex"] for p in ep.paragraphs for t in p.tokens if "lex" in t]
    return Inputs(ranks, listed, (pseudo_yes, pseudo_total), yes_no, yes_no_ranks, passages)


def _calibration_evidence(att: Attempt, inp: Inputs, exclude: str | None = None) -> dict[int, bool]:
    out: dict[int, bool] = {}
    for ep_id, lex_ids in inp.passages.items():
        if ep_id == exclude:
            continue
        tapped = att.calibration[ep_id].tapped
        for lex_id in lex_ids:
            out[lex_id] = lex_id not in tapped
    return out


def _observed(inp: Inputs, calib: dict[int, bool]) -> list[tuple[float, bool]]:
    return [(inp.ranks[i], k) for i, k in calib.items()]


def fit(att: Attempt, inp: Inputs, exclude: str | None = None) -> tuple[VocabParams, dict[int, str]]:
    calib = _calibration_evidence(att, inp, exclude)
    params = fit_vocab(inp.yes_no_ranks, _observed(inp, calib), false_alarm_rate(*inp.pseudo))
    model_ranks = {i: r for i, r in inp.ranks.items() if i in inp.listed}
    return params, lexeme_states(params, model_ranks, inp.yes_no, calib)


# ---- apply ----

def apply_states(session: Session, states: dict[int, str]) -> dict[str, int]:
    """Write placement lexeme states as the replay baseline (`base_state`); the seed's (manual) baseline wins.

    Earlier placement baselines not in `states` are dropped. `srs.derive` turns baselines into states.
    """
    now = utcnow()
    rows = {s.lexeme_id: s for s in session.scalars(select(LexemeState))}
    counts: dict[str, int] = defaultdict(int)
    for lex_id, st in states.items():
        row = rows.get(lex_id)
        if row is None:
            session.add(LexemeState(lexeme_id=lex_id, state=st, source="placement", first_seen_at=now,
                                    base_state=st, base_source="placement"))
        elif row.base_source not in (None, "placement"):
            continue
        else:
            row.base_state, row.base_source = st, "placement"
            row.first_seen_at = row.first_seen_at or now
        counts[st] += 1
    for lex_id, row in rows.items():
        if row.base_source == "placement" and lex_id not in states:
            row.base_state = row.base_source = None
    session.flush()
    return dict(counts)


def apply_grammar(session: Session, att: Attempt) -> dict[str, list[str]]:
    got: dict[str, int] = defaultdict(int)
    total: dict[str, int] = defaultdict(int)
    for it in items.grammar_items():
        if it["id"] not in att.grammar:
            continue
        for code in it["codes"]:
            total[code] += 1
            got[code] += att.grammar[it["id"]]
    now = utcnow()
    result: dict[str, list[str]] = defaultdict(list)
    for code in total:
        st = grammar_state(got[code], total[code])
        row = session.get(GrammarState, code)
        if row is None:
            session.add(GrammarState(code=code, state=st, source="placement", first_seen_at=now,
                                     base_state=st, base_source="placement"))
        elif row.base_source not in (None, "placement"):
            continue
        else:
            row.base_state, row.base_source = st, "placement"
        result[st].append(code)
    session.flush()
    return {k: sorted(v) for k, v in result.items()}


def refresh_coverage(session: Session) -> None:
    """Episode.coverage was set at ingest; recompute from current states and bump updated_at for sync."""
    known = known_lexeme_ids(session)
    now = utcnow()
    for ep in session.scalars(select(Episode)):
        ids = [t["lex"] for p in ep.paragraphs for t in p.tokens if "lex" in t]
        cov = sum(i in known for i in ids) / len(ids) if ids else 1.0
        if ep.coverage is None or abs(ep.coverage - cov) > 1e-9:
            ep.coverage = cov
            ep.updated_at = now
    session.flush()


# ---- evaluate ----

def evaluate(session: Session, att: Attempt, inp: Inputs) -> list[dict[str, Any]]:
    """Leave-one-passage-out: refit without passage k and predict its tapped-token rate.

    `predicted` is the share of tokens whose lexeme would not be `known` (what coverage sees);
    `expected` and the interval come from per-lexeme P(known), using the yes/no answers and the
    other passages as direct evidence. Acceptance: observed rate inside the interval.
    """
    fixed = {s.lexeme_id: s.state for s in session.scalars(select(LexemeState).where(LexemeState.source != "placement"))}
    rows = []
    for ep_id, lex_ids in inp.passages.items():
        params, states = fit(att, inp, exclude=ep_id)
        calib = _calibration_evidence(att, inp, exclude=ep_id)
        tapped = att.calibration[ep_id].tapped

        def p_known(prm: VocabParams, i: int) -> float:
            if i in calib:
                return 1.0 if calib[i] else 0.0
            p = prm.p_known(inp.ranks[i])
            if i in inp.yes_no:
                return posterior_known_given_yes(p, prm.fa) if inp.yes_no[i] else 0.0
            return p

        distinct = set(lex_ids)
        probs = {i: p_known(params, i) for i in distinct}
        draws = posterior_draws(inp.yes_no_ranks, _observed(inp, calib), params)
        n = len(lex_ids)
        lo, hi = unknown_rate_interval([{i: p_known(d, i) for i in distinct} for d in draws], lex_ids,
                                       level=ACCEPT_LEVEL)
        observed = sum(i in tapped for i in lex_ids) / n
        rows.append({
            "episode_id": ep_id, "tokens": n, "observed": observed,
            "predicted": sum(fixed.get(i, states.get(i)) not in ("known", "ignored") for i in lex_ids) / n,
            "expected": sum(1 - probs[i] for i in lex_ids) / n,
            "interval": [lo, hi], "rating": att.calibration[ep_id].rating,
            "ok": lo - 1e-9 <= observed <= hi + 1e-9,
        })
    return rows


def band_rates(att: Attempt, fa: float) -> list[dict[str, Any]]:
    by_q: dict[int, list[bool]] = defaultdict(list)
    for it in items.vocab_items():
        if it["real"] and it["id"] in att.vocab:
            by_q[it["quantile"]].append(att.vocab[it["id"]])
    out = []
    for q in sorted(by_q):
        ys = by_q[q]
        raw = sum(ys) / len(ys)
        out.append({"quantile": q, "n": len(ys), "yes": raw, "corrected": max(0.0, (raw - fa) / (1 - fa))})
    return out


def run(session: Session) -> dict[str, Any] | None:
    """Fit the latest finished attempt, write states, refresh coverage. Caller commits."""
    att = latest_attempt(session)
    if att is None:
        return None
    inp = gather(session, att)
    params, states = fit(att, inp)
    lexeme_counts = apply_states(session, states)
    grammar = apply_grammar(session, att)
    derive(session)  # baselines -> states, replaying reading evidence on top
    refresh_coverage(session)
    calibration = evaluate(session, att, inp)
    return {
        "attempt_id": att.attempt_id,
        "started_at": att.started_at.isoformat(),
        "finished_at": att.finished_at.isoformat(),
        "minutes": round((att.finished_at - att.started_at).total_seconds() / 60, 1),
        "params": {"a": params.a, "b": params.b, "fa": params.fa},
        "vocab_edge_rank": params.rank_at(KNOWN_THRESHOLD),
        "known_lexemes": lexeme_counts.get("known", 0),
        "seen_lexemes": lexeme_counts.get("seen", 0),
        "pseudo": {"yes": inp.pseudo[0], "total": inp.pseudo[1]},
        "bands": band_rates(att, params.fa),
        "grammar": grammar,
        "calibration": calibration,
        "pooled_error": (sum((r["expected"] - r["observed"]) * r["tokens"] for r in calibration)
                         / max(1, sum(r["tokens"] for r in calibration))),
        "accepted": bool(calibration) and all(r["ok"] for r in calibration),
    }
