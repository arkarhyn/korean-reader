"""
One-shot script: imports Teuida vocabulary into the graded reader vocab DB.
Run from the project root: python import_teuida.py
"""
import re
import sqlite3
import sys
from pathlib import Path

REFERENCE_FILE = Path(r"E:\OneDrive\scripts\teuida\teuida-vocabulary-grammar-reference.md")
DB_PATH = Path("data/vocab.db")

# Matches heading lines like:
#   ### 가다 (ga-da) — to go
#   ### 김밥 / 삼각김밥 (sam-gak-gim-bap) — triangular kimbap
HEADING_RE = re.compile(r"^### (.+?)\s+\(([^)]+)\)\s+—\s+(.+)$")


def parse_entries(text: str) -> list[dict]:
    entries = []
    current = None

    for line in text.splitlines():
        # Stop at the Grammar section — only import vocabulary entries
        if line.strip() == "## Grammar Patterns":
            break
        m = HEADING_RE.match(line)
        if m:
            if current:
                entries.append(current)
            korean_raw, romanization, gloss = m.group(1), m.group(2), m.group(3)
            # If there's a slash, take the first word as the primary key
            korean = korean_raw.split("/")[0].strip()
            current = {
                "word": korean,
                "reading": romanization.strip(),
                "definition": gloss.strip(),
                "pos": "",
            }
            continue

        if current is None:
            continue

        stripped = line.strip()
        if stripped.startswith("**English:**"):
            val = stripped[len("**English:**"):].strip()
            if val:
                current["definition"] = val
        elif stripped.startswith("**Part of speech:**"):
            val = stripped[len("**Part of speech:**"):].strip()
            if val:
                current["pos"] = val

    if current:
        entries.append(current)

    return entries


def import_vocab(entries: list[dict], db_path: Path) -> tuple[int, int]:
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    inserted = 0
    skipped = 0

    for e in entries:
        existing = conn.execute(
            "SELECT id FROM vocab WHERE word = ?", (e["word"],)
        ).fetchone()
        if existing:
            skipped += 1
            continue
        conn.execute(
            """INSERT INTO vocab (word, reading, definition, part_of_speech, grade,
               first_seen, last_seen, lookup_count)
               VALUES (?, ?, ?, ?, '', datetime('now','localtime'), datetime('now','localtime'), 0)""",
            (e["word"], e["reading"], e["definition"], e["pos"]),
        )
        inserted += 1

    conn.commit()
    conn.close()
    return inserted, skipped


def main():
    if not REFERENCE_FILE.exists():
        print(f"ERROR: reference file not found: {REFERENCE_FILE}")
        sys.exit(1)
    if not DB_PATH.exists():
        print(f"ERROR: database not found at {DB_PATH} — start the app once first to create it.")
        sys.exit(1)

    text = REFERENCE_FILE.read_text(encoding="utf-8")
    entries = parse_entries(text)
    print(f"Parsed {len(entries)} vocabulary entries from reference file.")

    inserted, skipped = import_vocab(entries, DB_PATH)
    print(f"Done: {inserted} words imported, {skipped} already in DB (skipped).")


if __name__ == "__main__":
    main()
