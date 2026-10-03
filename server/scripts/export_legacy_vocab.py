"""Export the legacy Graded-Reader-Project vocab table to content/seed/legacy_vocab.json.

Read-only on the legacy DB. Each legacy entry (often a surface form like 저는 or
걸으며) is re-analyzed and grouped by (lemma, pos). Glosses are not copied: they
were LLM-generated; krdict fills them at import time.
"""

import json
import sqlite3
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.analyzer import lemmatize  # noqa: E402
from app.config import CONTENT_DIR, LEGACY_DB  # noqa: E402

OUT = CONTENT_DIR / "seed" / "legacy_vocab.json"


def main() -> None:
    conn = sqlite3.connect(f"file:{LEGACY_DB}?mode=ro", uri=True)
    rows = conn.execute(
        "SELECT word, lookup_count, status, first_seen, last_seen FROM vocab ORDER BY id"
    ).fetchall()
    grouped: dict[tuple[str, str], dict] = {}
    unresolved = []
    for word, lookups, status, first_seen, last_seen in rows:
        key = lemmatize(word)
        if key is None:
            unresolved.append({"word": word, "lookups": lookups, "legacy_status": status or ""})
            continue
        g = grouped.setdefault(key, {
            "lemma": key[0], "pos": key[1], "lookups": 0, "state": "seen",
            "first_seen": first_seen, "last_seen": last_seen, "surfaces": [],
        })
        g["lookups"] += lookups or 0
        if status == "studying":
            g["state"] = "learning"
        g["first_seen"] = min(g["first_seen"], first_seen)
        g["last_seen"] = max(g["last_seen"], last_seen)
        g["surfaces"].append(word)

    lexemes = sorted(grouped.values(), key=lambda g: (-g["lookups"], g["lemma"]))
    doc = {
        "_note": ("Exported from legacy/Graded-Reader-Project/data/vocab.db by "
                  "server/scripts/export_legacy_vocab.py. Not imported yet; "
                  "state: learning = legacy 'studying', else seen. Review 'unresolved' by hand."),
        "lexemes": lexemes,
        "unresolved": unresolved,
    }
    OUT.write_text(json.dumps(doc, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    print(f"{len(rows)} legacy rows -> {len(lexemes)} lexemes, {len(unresolved)} unresolved -> {OUT}")


if __name__ == "__main__":
    main()
