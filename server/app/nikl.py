"""NIKL 한국어 학습용 어휘 목록 (2003): 5,965 words, frequency rank + grade A/B/C.

Source file is cp949 TSV with columns 순위 단어 품사 풀이 등급 (scripts/fetch_nikl_vocab.py).
Words map to the analyzer's (lemma, pos) keys so they match episode tokens.
"""

import re
from dataclasses import dataclass
from pathlib import Path

from .analyzer import lemmatize

# NIKL POS -> Kiwi tags the analyzer may emit for that word class (first = default).
POS_MAP: dict[str, tuple[str, ...]] = {
    "명": ("NNG", "NNP", "XR"),
    "동": ("VV",),
    "형": ("VA",),
    "부": ("MAG", "MAJ"),
    "대": ("NP",),
    "수": ("NR", "MM"),
    "관": ("MM",),
    "의": ("NNB",),
    "감": ("IC",),
    "고": ("NNP",),
}
# 보 (auxiliary verbs/adjectives) is grammar; 불 marks contractions (걔, 뭘) with no lemma of their own.
SKIP_POS = {"보", "불"}

_HOMOGRAPH = re.compile(r"\d+$")


@dataclass(frozen=True)
class NiklWord:
    lemma: str
    pos: str
    rank: int | None  # 순위; blank for proper nouns and some numerals
    band: str  # A / B / C
    nikl_word: str  # as listed, e.g. 가다01
    nikl_pos: str


def _keys(word: str, nikl_pos: str) -> list[tuple[str, str]]:
    """Analyzer keys for a listed word: the listed word class, plus Kiwi's tag when it differs only
    between noun and adverb (결국, 가까이, 안 are tagged either way depending on context)."""
    allowed = POS_MAP[nikl_pos]
    if word == "있다":  # always VA (DECISIONS 26), listed as both 동 and 형
        return [(word, "VA")]
    key = lemmatize(word)
    if key is not None and key[0] == word:
        if key[1] in allowed:
            return [key]
        if nikl_pos in ("명", "부") and key[1] in ("NNG", "MAG"):
            return [(word, allowed[0]), key]
    # Otherwise the listed word class wins. Derived forms the analyzer splits (가능성 -> 가능 + 성,
    # 경제적 -> 경제 + 적) keep their own key and so never match a token; their bases rank on their own.
    return [(word, allowed[0])]


def parse(path: Path) -> list[NiklWord]:
    """One NiklWord per distinct (lemma, pos), keeping the best (lowest) rank and easiest band."""
    best: dict[tuple[str, str], NiklWord] = {}
    for line in path.read_bytes().decode("cp949").splitlines()[1:]:
        cols = line.split("\t")
        if len(cols) < 5 or not cols[1].strip():
            continue
        rank_s, word_s, nikl_pos, _gloss, band = (c.strip() for c in cols[:5])
        if nikl_pos in SKIP_POS or nikl_pos not in POS_MAP:
            continue
        word = _HOMOGRAPH.sub("", word_s)
        for lemma, pos in _keys(word, nikl_pos):
            w = NiklWord(lemma, pos, int(rank_s) if rank_s else None, band, word_s, nikl_pos)
            old = best.get((lemma, pos))
            if old is None or _better(w, old):
                best[(lemma, pos)] = w
    return list(best.values())


def _better(a: NiklWord, b: NiklWord) -> bool:
    ra = a.rank if a.rank is not None else 10**9
    rb = b.rank if b.rank is not None else 10**9
    return (ra, a.band) < (rb, b.band)


def import_words(session, words: list[NiklWord], lookup) -> tuple[int, int]:
    """Upsert lexemes with freq_rank / freq_band (also on existing rows). Returns (created, updated). Caller commits."""
    from .ingest import get_or_create_lexeme

    created = updated = 0
    for w in words:
        lex, new = get_or_create_lexeme(session, w.lemma, w.pos, lookup)
        created += new
        updated += not new
        lex.freq_rank, lex.freq_band = w.rank, w.band
    session.flush()
    return created, updated
