"""Verify the vocab-list import feature against a COPY of the real DB."""
import shutil, sqlite3, sys

sys.path.insert(0, ".")
shutil.copy("data/vocab.db", ".claude/test_vocab.db")

import app
app.DB_PATH = ".claude/test_vocab.db"
app.init_db()

# ── Parser unit checks (no DB) ──────────────────────────────────────────────
HTSK_SAMPLE = """Vocabulary
Click on the English word to see information and examples of that word in use.

음식 = food
Common Usages: 음식점 = restaurant
먹다 = to eat
Examples: 저는 음식을 먹었어요 = I ate food
노래를 부르다 = to sing
1. 가다 = to go
달리기 (running) = the act of running
"""
entries, residual = app.parse_vocab_import(HTSK_SAMPLE)
words = {e["word"]: e for e in entries}
assert set(words) == {"음식", "음식점", "먹다", "노래를 부르다", "가다", "달리기"}, set(words)
assert words["음식"]["definition"] == "food"
assert "먹었어요" in words["먹다"]["example_sentence"], words["먹다"]
assert not residual, residual
print(f"1. parser ok: {len(entries)} entries, example attached to 먹다")

PASSAGE_SAMPLE = "오늘 도서관에 갔어요.\n특별한 강아지가 의자 아래에 숨었어요."
entries2, residual2 = app.parse_vocab_import(PASSAGE_SAMPLE)
assert not entries2 and len(residual2) == 2, (entries2, residual2)
print("2. passage mode ok: all lines residual")

# ── Endpoint checks ─────────────────────────────────────────────────────────
async def fake_lookup(word):
    return {"word": word, "reading": "", "definition": f"fake def of {word}",
            "pos": "noun", "grade": "", "japanese": None}
app.lookup_definition = fake_lookup
app.GEMINI_API_KEY = "test-key"  # satisfy the LLM-configured check

from fastapi.testclient import TestClient

with TestClient(app.app) as client:
    con = sqlite3.connect(".claude/test_vocab.db")

    # 3. List import: new + existing words, all tagged studying, defs preserved.
    # Clear 먹다's example first — the real DB may already hold one from actual reading,
    # and import intentionally won't overwrite an existing example (that's tested below).
    con.execute("UPDATE vocab SET example_sentence='' WHERE word='먹다'"); con.commit()
    old_def = con.execute("SELECT definition FROM vocab WHERE word='가다'").fetchone()[0]
    r = client.post("/api/vocab/import", json={"text": HTSK_SAMPLE, "lookup_missing": False}).json()
    assert "음식점" in r["pairs_added"], r
    assert "가다" in r["pairs_updated"], r
    row = con.execute("SELECT definition, status, lookup_count FROM vocab WHERE word='가다'").fetchone()
    assert row[0] == old_def and row[1] == "studying", row
    row = con.execute("SELECT definition, status, example_sentence FROM vocab WHERE word='먹다'").fetchone()
    assert row[1] == "studying" and "먹었어요" in row[2], row
    new = con.execute("SELECT definition, status, lookup_count FROM vocab WHERE word='음식점'").fetchone()
    assert new == ("restaurant", "studying", 0), new
    print(f"3. list import ok: {len(r['pairs_added'])} added, {len(r['pairs_updated'])} re-tagged, existing defs kept")

    # 의자 is a clean sentinel: confirmed absent from the real DB (강아지 already
    # exists in the bank, so it can't be used to prove non-insertion)
    SENTINEL = "의자"
    assert not con.execute("SELECT 1 FROM vocab WHERE word=?", (SENTINEL,)).fetchone(), \
        f"{SENTINEL} unexpectedly already in DB"

    # 4. Passage import without LLM: unknown words reported, not inserted
    r = client.post("/api/vocab/import", json={"text": PASSAGE_SAMPLE, "lookup_missing": False}).json()
    assert r["skipped"], r
    assert SENTINEL in r["skipped"], r
    assert not con.execute("SELECT 1 FROM vocab WHERE word=?", (SENTINEL,)).fetchone()
    print(f"4. passage no-LLM ok: skipped={r['skipped']}")

    # 5. Passage import with (fake) LLM: unknown words defined + tagged studying
    r = client.post("/api/vocab/import", json={"text": PASSAGE_SAMPLE, "lookup_missing": True}).json()
    assert SENTINEL in r["defined"], r
    row = con.execute("SELECT definition, status, lookup_count FROM vocab WHERE word=?", (SENTINEL,)).fetchone()
    assert row == (f"fake def of {SENTINEL}", "studying", 0), row
    print(f"5. passage with LLM ok: defined={r['defined']}")
    con.close()

print("\nALL CHECKS PASSED")
