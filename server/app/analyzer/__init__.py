"""Kiwi-based analyzer: text -> content tokens (lemma, pos) and grammar morphemes."""

from functools import lru_cache

from kiwipiepy import Kiwi

from .rules import Morph, Token, base_tag, build_tokens

__all__ = ["Token", "analyze", "content_tokens", "lemmatize"]


@lru_cache(maxsize=1)
def _kiwi() -> Kiwi:
    return Kiwi()


def analyze(text: str) -> list[Token]:
    """Content and grammar tokens in text order. Spans index into `text`."""
    if not text.strip():
        return []
    morphs = [Morph(t.form, base_tag(t.tag), t.start, t.start + t.len)
              for t in _kiwi().tokenize(text)]
    return build_tokens(morphs, text)


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
