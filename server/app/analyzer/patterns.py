"""Multi-morpheme grammar patterns over raw Kiwi morphemes.

A pattern (grammar_point.kiwi_pattern) is a list of alternatives; each
alternative is a list of matchers for consecutive morphemes. A matcher has
optional "form" (str or list), "tag" (str or list) and "form_re" keys.
Only the codes a generation batch needs have patterns so far; the rest are
filled with SYLLABUS_MAP in Stage 8.
"""

import json
import re
from collections import Counter
from collections.abc import Iterable, Mapping
from functools import lru_cache
from typing import Any

from ..config import CONTENT_DIR
from .rules import Morph

Matcher = Mapping[str, Any]
Pattern = list[list[Matcher]]

GRAMMAR_POINTS = CONTENT_DIR / "seed" / "grammar_points.json"


def _one_of(value: str | list[str], actual: str) -> bool:
    return actual in value if isinstance(value, list) else actual == value


def _matches(m: Morph, matcher: Matcher) -> bool:
    if "form" in matcher and not _one_of(matcher["form"], m.form):
        return False
    if "tag" in matcher and not _one_of(matcher["tag"], m.tag):
        return False
    if "form_re" in matcher and not re.search(matcher["form_re"], m.form):
        return False
    return True


def find(morphs: list[Morph], pattern: Pattern) -> list[tuple[int, int]]:
    """Non-overlapping (start, end) text spans where any alternative matches."""
    spans: list[tuple[int, int]] = []
    i = 0
    while i < len(morphs):
        for alt in pattern:
            k = len(alt)
            if i + k <= len(morphs) and all(_matches(morphs[i + j], alt[j]) for j in range(k)):
                spans.append((morphs[i].start, morphs[i + k - 1].end))
                i += k
                break
        else:
            i += 1
    return spans


@lru_cache(maxsize=1)
def seed_patterns() -> dict[str, Pattern]:
    """code -> kiwi_pattern from content/seed/grammar_points.json (codes without one are skipped)."""
    data = json.loads(GRAMMAR_POINTS.read_text(encoding="utf-8"))
    return {p["code"]: p["kiwi_pattern"] for p in data["points"] if p.get("kiwi_pattern")}


def count_grammar(text: str, patterns: Mapping[str, Pattern] | None = None,
                  codes: Iterable[str] | None = None) -> Counter[str]:
    """Occurrences per grammar code in text (codes with a pattern only)."""
    from . import morphemes

    patterns = seed_patterns() if patterns is None else patterns
    wanted = patterns.keys() if codes is None else [c for c in codes if c in patterns]
    morphs = morphemes(text)
    return Counter({code: n for code in wanted if (n := len(find(morphs, patterns[code])))})
