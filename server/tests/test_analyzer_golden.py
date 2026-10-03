"""Every content token in both legacy readers maps to the hand-reviewed (lemma, pos).

Gold files were drafted by scripts/make_golden.py and reviewed row by row.
If this fails, fix the analyzer -- do not regenerate the gold file.
"""

import json

from app.analyzer import content_tokens

from .conftest import TESTS_DIR


def test_golden(legacy_episode):
    gold = json.loads((TESTS_DIR / "golden" / f"{legacy_episode.id}.gold.json").read_text(encoding="utf-8"))
    got = [[t.surface, t.lemma, t.pos] for t in content_tokens(legacy_episode.text_ko)]
    mismatches = [(i, g, o) for i, (g, o) in enumerate(zip(gold, got)) if g != o]
    assert not mismatches, mismatches[:10]
    assert len(got) == len(gold)
