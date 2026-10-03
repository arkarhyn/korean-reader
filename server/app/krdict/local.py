"""Local copy of the 한국어기초사전 full dump (DECISIONS 42).

The dump is krdict's own LMF XML export (CC BY-SA 2.0 KR, NIKL), mirrored at
github.com/spellcheck-ko/korean-dict-nikl-krdict. scripts/build_krdict_local.py
downloads it and builds a small SQLite index; `LocalDict.lookup` returns the
same `KrdictEntry` as the live API, so glosses no longer depend on
krdict.korean.go.kr being reachable. Entry ids are krdict target_codes.
"""

import io
import re
import sqlite3
import xml.etree.ElementTree as ET
from collections.abc import Iterable, Iterator
from pathlib import Path

from .client import TRANS_EN, TRANS_JA, KrdictEntry, Sense, pick_entry

SCHEMA = """
CREATE TABLE IF NOT EXISTS entry (
    target_code TEXT PRIMARY KEY,
    word TEXT NOT NULL,
    sup_no INTEGER NOT NULL,
    pos TEXT NOT NULL,
    origin TEXT,
    grade TEXT
);
CREATE INDEX IF NOT EXISTS entry_word ON entry(word);
CREATE TABLE IF NOT EXISTS sense (
    target_code TEXT NOT NULL REFERENCES entry(target_code),
    idx INTEGER NOT NULL,
    definition_ko TEXT NOT NULL,
    en_word TEXT NOT NULL,
    en_dfn TEXT NOT NULL,
    ja_word TEXT NOT NULL,
    ja_dfn TEXT NOT NULL,
    PRIMARY KEY (target_code, idx)
);
"""


def _feats(el: ET.Element) -> dict[str, str]:
    """Direct-child <feat att=... val=...> pairs (first value wins)."""
    out: dict[str, str] = {}
    for f in el.findall("feat"):
        out.setdefault(f.get("att", ""), (f.get("val") or "").strip())
    return out


_VAL = re.compile(rb'val="([^"]*)"')


def _escape_vals(m: re.Match) -> bytes:
    return b'val="' + m.group(1).replace(b"<", b"&lt;").replace(b">", b"&gt;") + b'"'


def parse_dump(path: Path) -> Iterator[KrdictEntry]:
    """Word entries (lexicalUnit 단어) from one LMF XML file; phrases and idioms are skipped."""
    # Some translations contain a raw "<" inside val="..." (30000.xml), which is not well-formed XML.
    data = _VAL.sub(_escape_vals, path.read_bytes())
    for _, el in ET.iterparse(io.BytesIO(data), events=("end",)):
        if el.tag != "LexicalEntry":
            continue
        f = _feats(el)
        lemma = el.find("Lemma")
        word = _feats(lemma).get("writtenForm", "") if lemma is not None else ""
        if f.get("lexicalUnit") == "단어" and word:
            senses = []
            for s in el.findall("Sense"):
                eq: dict[str, dict[str, str]] = {}
                for e in s.findall("Equivalent"):
                    ef = _feats(e)
                    eq.setdefault(ef.get("language", ""), ef)
                en, ja = eq.get(TRANS_EN, {}), eq.get(TRANS_JA, {})
                senses.append(Sense(
                    definition_ko=_feats(s).get("definition", ""),
                    en_word=en.get("lemma", ""), en_dfn=en.get("definition", ""),
                    ja_word=ja.get("lemma", ""), ja_dfn=ja.get("definition", ""),
                ))
            grade = f.get("vocabularyLevel")
            yield KrdictEntry(
                target_code=el.get("val", ""),
                word=word,
                sup_no=int(f.get("homonym_number") or 0),
                pos=f.get("partOfSpeech", ""),
                origin=f.get("origin") or None,
                grade=None if grade in (None, "", "없음") else grade,
                senses=senses,
            )
        el.clear()


def build(db_path: Path, xml_paths: Iterable[Path]) -> int:
    """(Re)build the SQLite index from dump files. Returns the number of entries."""
    db_path.parent.mkdir(parents=True, exist_ok=True)
    tmp = db_path.with_suffix(".tmp")
    tmp.unlink(missing_ok=True)
    conn = sqlite3.connect(tmp)
    conn.executescript(SCHEMA)
    n = 0
    for path in xml_paths:
        for e in parse_dump(path):
            conn.execute("INSERT OR REPLACE INTO entry VALUES (?,?,?,?,?,?)",
                         (e.target_code, e.word, e.sup_no, e.pos, e.origin, e.grade))
            conn.executemany("INSERT OR REPLACE INTO sense VALUES (?,?,?,?,?,?,?)",
                             [(e.target_code, i, s.definition_ko, s.en_word, s.en_dfn, s.ja_word, s.ja_dfn)
                              for i, s in enumerate(e.senses)])
            n += 1
    conn.commit()
    conn.close()
    tmp.replace(db_path)
    return n


class LocalDict:
    def __init__(self, db_path: Path | str):
        if not Path(db_path).is_file():
            raise FileNotFoundError(f"{db_path} missing -- run scripts/build_krdict_local.py")
        self._conn = sqlite3.connect(db_path, check_same_thread=False)

    def search(self, word: str) -> list[KrdictEntry]:
        entries = []
        for code, w, sup_no, pos, origin, grade in self._conn.execute(
                "SELECT target_code, word, sup_no, pos, origin, grade FROM entry WHERE word = ?", (word,)):
            senses = [Sense(*row) for row in self._conn.execute(
                "SELECT definition_ko, en_word, en_dfn, ja_word, ja_dfn FROM sense WHERE target_code = ? "
                "ORDER BY idx", (code,))]
            entries.append(KrdictEntry(code, w, sup_no, pos, origin, grade, senses))
        return entries

    def lookup(self, lemma: str, pos: str | None = None) -> KrdictEntry | None:
        return pick_entry(self.search(lemma), lemma, pos)

    def close(self) -> None:
        self._conn.close()
