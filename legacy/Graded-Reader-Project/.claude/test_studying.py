"""Verify the 'studying' tag feature against a COPY of the real DB."""
import shutil, sqlite3, sys

sys.path.insert(0, ".")
shutil.copy("data/vocab.db", ".claude/test_vocab.db")

import app
app.DB_PATH = ".claude/test_vocab.db"
app.init_db()  # runs migration on the copy

from fastapi.testclient import TestClient

with TestClient(app.app) as client:
    # 1. Migration + GET /api/vocab exposes status
    vocab = client.get("/api/vocab").json()
    assert "status" in vocab[0], "status field missing"
    n_studying = sum(1 for v in vocab if v["status"] == "studying")
    n_bank = sum(1 for v in vocab if v["status"] == "")
    print(f"1. migration ok: {n_studying} studying / {n_bank} bank of {len(vocab)} total")

    # 2. A lookup must PRESERVE an existing word's status (peeking a known word
    #    keeps it known; it no longer force-tags studying).
    con = sqlite3.connect(".claude/test_vocab.db")
    con.execute("UPDATE vocab SET status='' WHERE word='가족'"); con.commit()
    r = client.post("/api/define", json={"word": "가족"}).json()
    assert r["status"] == "", r  # known stays known
    assert con.execute("SELECT status FROM vocab WHERE word='가족'").fetchone()[0] == ""
    con.execute("UPDATE vocab SET status='studying' WHERE word='가족'"); con.commit()
    r = client.post("/api/define", json={"word": "가족"}).json()
    assert r["status"] == "studying", r  # studying stays studying
    print("2. define preserves status (known stays known, studying stays studying)")

    # 2b. A brand-new word still enters as 'studying' (first-lookup behavior)
    async def _fake(w):
        return {"word": w, "reading": "", "definition": "x", "pos": "", "grade": "", "japanese": None}
    app.lookup_definition = _fake
    r = client.post("/api/define", json={"word": "신조어테스트"}).json()
    assert r["status"] == "studying", r
    assert con.execute("SELECT status FROM vocab WHERE word='신조어테스트'").fetchone()[0] == "studying"
    print("2b. brand-new word enters as studying ok")

    # 2c. refresh=True bypasses the cache to regenerate a wrong definition,
    #     while still preserving the word's status.
    con.execute("UPDATE vocab SET definition='OLD', status='' WHERE word='가족'"); con.commit()
    async def _fake2(w):
        return {"word": w, "reading": "", "definition": "NEW", "pos": "", "grade": "", "japanese": None}
    app.lookup_definition = _fake2
    r = client.post("/api/define", json={"word": "가족", "refresh": True}).json()
    assert r["definition"] == "NEW", r
    assert con.execute("SELECT definition, status FROM vocab WHERE word='가족'").fetchone() == ("NEW", "")
    # ...and a normal (non-refresh) lookup still returns the cached copy
    r = client.post("/api/define", json={"word": "가족"}).json()
    assert r["definition"] == "NEW", r
    print("2c. refresh regenerates def + preserves status; normal lookup uses cache")

    # 3. Manual toggle endpoint
    vid = next(v["id"] for v in vocab if v["word"] == "가족")
    assert client.put(f"/api/vocab/{vid}/status", json={"status": ""}).status_code == 200
    row = con.execute("SELECT status FROM vocab WHERE word='가족'").fetchone()
    assert row[0] == "", row
    assert client.put(f"/api/vocab/{vid}/status", json={"status": "studying"}).status_code == 200
    assert client.put(f"/api/vocab/{vid}/status", json={"status": "bogus"}).status_code == 400
    assert client.put("/api/vocab/999999/status", json={"status": ""}).status_code == 404
    print("3. manual toggle ok (set, unset, 400 on bad value, 404 on bad id)")

    # 4. Coverage returns studying words, including inflected forms via lemma
    cov = client.post("/api/coverage", json={"words": ["가족", "없는단어입니다"]}).json()
    assert "가족" in cov["known"] and "가족" in cov["studying"], cov
    assert "없는단어입니다" not in cov["known"], cov
    print(f"4. coverage ok: known={len(cov['known'])}, studying={len(cov['studying'])}")

    # 5. Auto-graduation: idle words lose the tag on next vocab fetch
    con.execute("UPDATE vocab SET last_seen = datetime('now','-30 days','localtime') WHERE word='가족'")
    con.commit()
    vocab2 = client.get("/api/vocab").json()
    g = next(v for v in vocab2 if v["word"] == "가족")
    assert g["status"] == "", g["status"]
    print("5. auto-graduate ok (idle 30 days -> tag cleared)")

    # 6. SRS graduation: correct answer at high interval clears tag
    con.execute("UPDATE vocab SET status='studying', review_interval=8 WHERE word='가족'")
    con.commit()
    client.post("/api/review/answer", json={"word_id": vid, "correct": True})  # 8 -> 16
    row = con.execute("SELECT status, review_interval FROM vocab WHERE word='가족'").fetchone()
    assert row == ("", 16), row
    print("6. SRS graduate ok (interval 8 -> 16, tag cleared)")
    con.close()

print("\nALL CHECKS PASSED")
