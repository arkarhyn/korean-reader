"""Seed data from content/seed/ (DECISIONS 20)."""

import json
from dataclasses import dataclass
from pathlib import Path

from .analyzer import analyze, lemmatize
from .config import CONTENT_DIR

FLAGGED_VOCAB = CONTENT_DIR / "seed" / "flagged_vocab.json"
GRAMMAR_POINTS = CONTENT_DIR / "seed" / "grammar_points.json"
LESSONS_DIR = CONTENT_DIR / "grammar" / "lessons"


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
    kiwi_pattern: list | None = None
    teach_order: float | None = None


def load_grammar_points(path: Path = GRAMMAR_POINTS) -> list[SeedGrammarPoint]:
    """HTSK grammar points (docs/SYLLABUS_MAP.md)."""
    data = json.loads(path.read_text(encoding="utf-8"))
    points = [SeedGrammarPoint(**p) for p in data["points"]]
    codes = [p.code for p in points]
    if len(codes) != len(set(codes)):
        raise ValueError("duplicate grammar point code")
    return points


LESSON_KEYS = {"code", "title_en", "summary_en", "ja_parallel", "ja_diff_note", "notes", "examples", "drills"}


def validate_lesson(lesson: dict) -> None:
    """A lesson card (SPEC 3.4): Japanese parallel + difference, 2 examples, 3-5 select-only drills."""
    code = lesson.get("code")
    if missing := LESSON_KEYS - lesson.keys():
        raise ValueError(f"lesson {code}: missing {sorted(missing)}")
    if len(lesson["examples"]) != 2 or not all(e.get("ko") and e.get("en") for e in lesson["examples"]):
        raise ValueError(f"lesson {code}: needs 2 examples with ko + en")
    if not 3 <= len(lesson["drills"]) <= 5:
        raise ValueError(f"lesson {code}: needs 3-5 drills")
    for i, d in enumerate(lesson["drills"]):
        if "__" not in d.get("prompt_ko", ""):
            raise ValueError(f"lesson {code} drill {i}: prompt_ko has no ___ blank")
        if not 2 <= len(d.get("options", [])) <= 4 or not 0 <= d.get("answer", -1) < len(d["options"]):
            raise ValueError(f"lesson {code} drill {i}: bad options/answer")


def load_lessons(directory: Path = LESSONS_DIR) -> dict[str, dict]:
    """code -> lesson card from content/grammar/lessons/<code>.json."""
    lessons = {}
    for path in sorted(directory.glob("*.json")):
        lesson = json.loads(path.read_text(encoding="utf-8"))
        validate_lesson(lesson)
        if lesson["code"] != path.stem:
            raise ValueError(f"{path.name}: code {lesson['code']} does not match the file name")
        lessons[lesson["code"]] = lesson
    return lessons
