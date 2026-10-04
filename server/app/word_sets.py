"""Themed word sets for confirming known vocabulary by hand (DECISIONS 67).

Items are dictionary forms from content/seed/word_sets.json. An item's lexeme
keys default to lemmatize(ko); an explicit `keys` list covers analyzer splits
(일월 in running text is 일/NR + 월/NNB). Confirming an item marks every key known.
State changes go through ordinary `set_state` events (app/events.py).
"""

import json
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.orm import Session

from .analyzer import lemmatize
from .config import CONTENT_DIR
from .coverage import known_by_alias
from .db.models import Lexeme, LexemeState

WORD_SETS = CONTENT_DIR / "seed" / "word_sets.json"
KNOWN_STATES = ("known", "ignored")


@dataclass(frozen=True)
class SetItem:
    ko: str
    en: str
    keys: tuple[tuple[str, str], ...]


@dataclass(frozen=True)
class WordSet:
    id: str
    title_ko: str
    title_en: str
    items: tuple[SetItem, ...]


def _parse_key(key: str) -> tuple[str, str]:
    lemma, sep, pos = key.rpartition("/")
    if not sep or not lemma or not pos:
        raise ValueError(f"bad key {key!r} (want lemma/POS)")
    return lemma, pos


def load_word_sets(path: Path = WORD_SETS) -> list[WordSet]:
    """Parse and resolve every set. Raises ValueError for an item that doesn't resolve."""
    data = json.loads(path.read_text(encoding="utf-8"))
    sets, ids = [], set()
    for s in data["sets"]:
        if s["id"] in ids:
            raise ValueError(f"duplicate set id {s['id']!r}")
        ids.add(s["id"])
        items = []
        for it in s["items"]:
            if "keys" in it:
                keys = tuple(_parse_key(k) for k in it["keys"])
            elif (key := lemmatize(it["ko"])) is not None:
                keys = (key,)
            else:
                raise ValueError(f"set {s['id']}: {it['ko']!r} does not resolve to one (lemma, pos); add keys")
            items.append(SetItem(it["ko"], it["en"], keys))
        sets.append(WordSet(s["id"], s["title_ko"], s["title_en"], tuple(items)))
    return sets


@lru_cache(maxsize=1)
def word_sets() -> tuple[WordSet, ...]:
    return tuple(load_word_sets())


def seed_word_sets(session: Session, lookup) -> int:
    """Create missing lexemes for every set key (glossed via lookup). Returns how many were created."""
    from .ingest import get_or_create_lexeme

    created = 0
    for s in word_sets():
        for it in s.items:
            for lemma, pos in it.keys:
                created += get_or_create_lexeme(session, lemma, pos, lookup)[1]
    session.flush()
    return created


def _states(session: Session) -> tuple[dict[tuple[str, str], tuple[int, str | None]], set[tuple[str, str]]]:
    """(lemma, pos) -> (lexeme id, state) for every lexeme, and the raw known keys."""
    rows = session.execute(select(Lexeme.id, Lexeme.lemma, Lexeme.pos, LexemeState.state)
                           .outerjoin(LexemeState)).all()
    by_key = {(r.lemma, r.pos): (r.id, r.state) for r in rows}
    raw_known = {k for k, (_, st) in by_key.items() if st in KNOWN_STATES}
    return by_key, raw_known


def _item_out(ko: str, en: str, keys, by_key, raw_known) -> dict:
    ids = [by_key[k][0] for k in keys if k in by_key]
    known = all(k in raw_known or known_by_alias(*k, raw_known) for k in keys)
    return {"ko": ko, "en": en, "lexeme_ids": ids, "known": known}


def sets_out(session: Session) -> list[dict]:
    """Every set with its items and whether each is already known."""
    by_key, raw_known = _states(session)
    return [{"id": s.id, "title_ko": s.title_ko, "title_en": s.title_en,
             "items": [_item_out(it.ko, it.en, it.keys, by_key, raw_known) for it in s.items]}
            for s in word_sets()]


def common_out(session: Session, offset: int = 0, limit: int = 40) -> dict:
    """NIKL-ranked, glossed lexemes not yet known, in rank order (the frequency walk)."""
    q = (select(Lexeme).outerjoin(LexemeState)
         .where(Lexeme.freq_rank.is_not(None), Lexeme.gloss_source != "none",
                LexemeState.state.is_(None) | LexemeState.state.not_in(KNOWN_STATES))
         .order_by(Lexeme.freq_rank, Lexeme.id))
    _, raw_known = _states(session)
    rows = [lx for lx in session.scalars(q) if not known_by_alias(lx.lemma, lx.pos, raw_known)]
    page = rows[offset:offset + limit]
    return {"offset": offset, "total": len(rows),
            "items": [{"ko": lx.lemma, "en": lx.gloss_en.split(";")[0], "lexeme_ids": [lx.id], "known": False,
                       "rank": lx.freq_rank} for lx in page]}
