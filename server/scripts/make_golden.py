"""Draft a golden file from the current analyzer output.

Gold files are hand-reviewed after drafting; never regenerate them to make a
failing test pass -- fix the analyzer instead.
"""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.analyzer import content_tokens  # noqa: E402
from app.config import CONTENT_DIR  # noqa: E402
from app.content.schema import load_episode  # noqa: E402

GOLDEN = Path(__file__).resolve().parents[1] / "tests" / "golden"

for ep_id in sys.argv[1:]:
    ep = load_episode(CONTENT_DIR / "episodes" / "legacy" / f"{ep_id}.json")
    rows = [[t.surface, t.lemma, t.pos] for t in content_tokens(ep.text_ko)]
    lines = ",\n".join("  " + json.dumps(r, ensure_ascii=False) for r in rows)
    (GOLDEN / f"{ep_id}.gold.json").write_text(f"[\n{lines}\n]\n", encoding="utf-8")
    print(ep_id, len(rows), "content tokens")
