"""Verify inline 'mark known/studying' (POST /api/vocab/mark) on a DB copy."""
import shutil, sqlite3, sys

sys.path.insert(0, ".")
shutil.copy("data/vocab.db", ".claude/test_vocab.db")

import app
app.DB_PATH = ".claude/test_vocab.db"
app.init_db()

from fastapi.testclient import TestClient

with TestClient(app.app) as client:
    con = sqlite3.connect(".claude/test_vocab.db")

    # 1. Mark an existing studying word known -> status cleared, row kept
    con.execute("UPDATE vocab SET status='studying' WHERE word='아침'"); con.commit()
    r = client.post("/api/vocab/mark", json={"word": "아침", "status": ""}).json()
    assert r["ok"] and r["word"] == "아침", r
    assert con.execute("SELECT status FROM vocab WHERE word='아침'").fetchone()[0] == "", "not cleared"
    print("1. existing studying -> known ok")

    # 2. Mark an unknown word (not in bank) known -> bare row created
    assert not con.execute("SELECT 1 FROM vocab WHERE word='의자'").fetchone(), "의자 unexpectedly present"
    r = client.post("/api/vocab/mark", json={"word": "의자", "status": ""}).json()
    row = con.execute("SELECT definition, status, lookup_count FROM vocab WHERE word='의자'").fetchone()
    assert row == ("", "", 0), row
    print("2. unknown word -> known (bare row, lookup_count 0) ok")

    # 3. Reverse: mark a word studying again
    r = client.post("/api/vocab/mark", json={"word": "아침", "status": "studying"}).json()
    assert con.execute("SELECT status FROM vocab WHERE word='아침'").fetchone()[0] == "studying", "not re-studying"
    print("3. known -> studying (reverse) ok")

    # 4. Lemma resolution: inflected surface form updates its dictionary-form row
    con.execute("UPDATE vocab SET status='studying' WHERE word='가다'"); con.commit()
    lemma = app.get_lemma("갔어요")
    assert lemma == "가다", f"kiwi lemma unexpected: {lemma}"
    r = client.post("/api/vocab/mark", json={"word": "갔어요", "status": ""}).json()
    assert r["word"] == "가다", r
    assert con.execute("SELECT status FROM vocab WHERE word='가다'").fetchone()[0] == "", "lemma not updated"
    assert not con.execute("SELECT 1 FROM vocab WHERE word='갔어요'").fetchone(), "surface form wrongly inserted"
    print("4. inflected form resolves to lemma row ok")

    # 5. Bad status rejected
    assert client.post("/api/vocab/mark", json={"word": "아침", "status": "nope"}).status_code == 400
    print("5. bad status -> 400 ok")

    con.close()

print("\nALL CHECKS PASSED")
