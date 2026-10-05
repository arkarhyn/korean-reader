"""Kiwi-based analyzer: text -> content tokens (lemma, pos) and grammar morphemes."""

import json
from functools import lru_cache

from kiwipiepy import Kiwi

from ..config import CONTENT_DIR
from .rules import Morph, Token, base_tag, build_tokens

__all__ = ["Token", "analyze", "content_tokens", "lemmatize", "morphemes", "proper_noun_glosses", "proper_nouns",
           "story_names"]

PROPER_NOUNS = CONTENT_DIR / "seed" / "proper_nouns.json"
PODCAST_NAMES = CONTENT_DIR / "seed" / "podcast_names.json"


def _names(path) -> dict[str, str]:
    return json.loads(path.read_text(encoding="utf-8"))["names"] if path.exists() else {}


@lru_cache(maxsize=1)
def proper_noun_glosses() -> dict[str, str]:
    """Story-bible and podcast-host name -> English gloss."""
    return _names(PROPER_NOUNS) | _names(PODCAST_NAMES)


def proper_nouns() -> frozenset[str]:
    """Names counted as known by coverage (SPEC 7) and never graded: story cast + podcast hosts."""
    return frozenset(proper_noun_glosses())


def story_names() -> frozenset[str]:
    """Story-bible names only (what the generator may use)."""
    return frozenset(_names(PROPER_NOUNS))


@lru_cache(maxsize=1)
def _kiwi() -> Kiwi:
    kiwi = Kiwi()
    # Without these Kiwi splits cast names (서윤아 -> 서/윤/아, 이선 -> 이/MM 선).
    for name in proper_nouns():
        kiwi.add_user_word(name, "NNP", 0)
    return kiwi


def morphemes(text: str) -> list[Morph]:
    """Raw Kiwi morphemes with base tags (grammar pattern matching works on these)."""
    if not text.strip():
        return []
    return [Morph(t.form, base_tag(t.tag), t.start, t.start + t.len, str(t.tag).endswith("-I"))
            for t in _kiwi().tokenize(text)]


def analyze(text: str) -> list[Token]:
    """Content and grammar tokens in text order. Spans index into `text`."""
    if not text.strip():
        return []
    return build_tokens(morphemes(text), text)


def content_tokens(text: str) -> list[Token]:
    return [t for t in analyze(text) if t.kind == "content"]


_CARRIER = "그는 "


def lemmatize(word: str) -> tuple[str, str] | None:
    """(lemma, pos) of a single word, or None unless it has exactly one content token.

    Bare dictionary forms are ambiguous to Kiwi (자다 -> 자/IC 다/MAG, 있다 -> VX),
    so a -다 word that does not resolve alone is retried in a short sentence.
    """
    toks = content_tokens(word)
    if len(toks) != 1 and word.endswith("다"):
        toks = [t for t in content_tokens(f"{_CARRIER}{word}.") if t.start >= len(_CARRIER)]
    return toks[0].key if len(toks) == 1 else None
