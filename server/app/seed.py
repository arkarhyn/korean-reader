"""Seed data from content/seed/ (DECISIONS 20)."""

import json
from dataclasses import dataclass
from pathlib import Path

from .analyzer import analyze, lemmatize
from .config import CONTENT_DIR

FLAGGED_VOCAB = CONTENT_DIR / "seed" / "flagged_vocab.json"
GRAMMAR_POINTS = CONTENT_DIR / "seed" / "grammar_points.json"


@dataclass(frozen=True)
class SeedLexeme:
    lemma: str
    pos: str
    state: str = "learning"
    source: str = "manual"


@dataclass(frozen=True)
class SeedGrammar:
    form: str
    code: str
    state: str = "introduced"
    source: str = "manual"


def load_flagged_vocab(path: Path = FLAGGED_VOCAB) -> tuple[list[SeedLexeme], list[SeedGrammar]]:
    """Flagged lexemes -> (lemma, pos) at state learning; particles -> grammar codes.

    Raises ValueError for any entry that does not resolve cleanly, so a bad seed
    file fails loudly instead of creating surface-form lexemes.
    """
    data = json.loads(path.read_text(encoding="utf-8"))
    lexemes = []
    for word in data["lexemes"]:
        key = lemmatize(word)
        if key is None:
            raise ValueError(f"seed lexeme {word!r} does not resolve to one (lemma, pos)")
        lexemes.append(SeedLexeme(*key))
    grammar = []
    for form in data["grammar"]:
        # Analyze in a carrier phrase so Kiwi sees the particle attached to a noun.
        toks = [t for t in analyze("친구" + form) if t.kind == "grammar"]
        if len(toks) != 1 or toks[0].grammar_code is None:
            raise ValueError(f"seed grammar {form!r} has no grammar code")
        grammar.append(SeedGrammar(form, toks[0].grammar_code))
    return lexemes, grammar


@dataclass(frozen=True)
class SeedGrammarPoint:
    code: str
    htsk_lesson: int | None
    label_ko: str
    ja_parallel: str | None
    ja_diff_note: str | None


def load_grammar_points(path: Path = GRAMMAR_POINTS) -> list[SeedGrammarPoint]:
    """HTSK 1-28 grammar points (docs/SYLLABUS_MAP.md)."""
    data = json.loads(path.read_text(encoding="utf-8"))
    points = [SeedGrammarPoint(**p) for p in data["points"]]
    codes = [p.code for p in points]
    if len(codes) != len(set(codes)):
        raise ValueError("duplicate grammar point code")
    return points
