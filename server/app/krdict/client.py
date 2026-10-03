"""한국어기초사전 (krdict) Open API client.

One exact-match search per lemma returns every homograph with English and
Japanese translations; `lookup` picks the entry matching the Kiwi POS.
Raw XML is cached so each lemma hits the API once.
"""

import re
import xml.etree.ElementTree as ET
from dataclasses import dataclass, field

import httpx

from .cache import KrdictCache

API_URL = "https://krdict.korean.go.kr/api/search"
TRANS_EN, TRANS_JA = "영어", "일본어"

# Kiwi POS -> krdict 품사
KIWI_TO_KRDICT_POS: dict[str, set[str]] = {
    "NNG": {"명사"},
    "NNP": {"명사"},
    "NNB": {"의존 명사"},
    "NR": {"수사"},
    "NP": {"대명사"},
    "VV": {"동사"},
    "VA": {"형용사"},
    "VCN": {"형용사"},
    "VX": {"보조 동사", "보조 형용사"},
    "MAG": {"부사"},
    "MAJ": {"부사"},
    "MM": {"관형사"},
    "IC": {"감탄사"},
}
GRADE_RANK = {"초급": 0, "중급": 1, "고급": 2}
_CJK = re.compile(r"[㐀-鿿豈-﫿]+")


class KrdictError(RuntimeError):
    pass


@dataclass(frozen=True)
class Sense:
    definition_ko: str
    en_word: str
    en_dfn: str
    ja_word: str
    ja_dfn: str


@dataclass(frozen=True)
class KrdictEntry:
    target_code: str
    word: str
    sup_no: int
    pos: str
    origin: str | None
    grade: str | None
    senses: list[Sense] = field(default_factory=list)

    @property
    def hanja(self) -> str | None:
        """Hanja from `origin` (工夫하다 -> 工夫); None for native/loan words."""
        parts = _CJK.findall(self.origin or "")
        return "".join(parts) or None

    @property
    def gloss_en(self) -> str:
        return next((s.en_word for s in self.senses if s.en_word), "")

    @property
    def gloss_ja(self) -> str:
        return next((s.ja_word for s in self.senses if s.ja_word), "")


def _text(el: ET.Element | None, tag: str) -> str:
    child = el.find(tag) if el is not None else None
    return (child.text or "").strip() if child is not None else ""


def parse_search(xml: str) -> list[KrdictEntry]:
    root = ET.fromstring(xml.strip())
    if root.tag == "error":
        raise KrdictError(f"{_text(root, 'error_code')}: {_text(root, 'message')}")
    entries = []
    for item in root.iter("item"):
        senses = []
        for s in item.iter("sense"):
            tr = {_text(t, "trans_lang"): t for t in s.iter("translation")}
            senses.append(Sense(
                definition_ko=_text(s, "definition"),
                en_word=_text(tr.get(TRANS_EN), "trans_word"),
                en_dfn=_text(tr.get(TRANS_EN), "trans_dfn"),
                ja_word=_text(tr.get(TRANS_JA), "trans_word"),
                ja_dfn=_text(tr.get(TRANS_JA), "trans_dfn"),
            ))
        entries.append(KrdictEntry(
            target_code=_text(item, "target_code"),
            word=_text(item, "word"),
            sup_no=int(_text(item, "sup_no") or 0),
            pos=_text(item, "pos"),
            origin=_text(item, "origin") or None,
            grade=_text(item, "word_grade") or None,
            senses=senses,
        ))
    return entries


def pick_entry(entries: list[KrdictEntry], lemma: str, pos: str | None) -> KrdictEntry | None:
    """Exact-word entry matching the Kiwi POS; easiest grade, then lowest sup_no."""
    cands = [e for e in entries if e.word == lemma]
    if pos is not None:
        wanted = KIWI_TO_KRDICT_POS.get(pos, set())
        cands = [e for e in cands if e.pos in wanted]
    cands.sort(key=lambda e: (GRADE_RANK.get(e.grade or "", 3), e.sup_no))
    return cands[0] if cands else None


class KrdictClient:
    def __init__(self, api_key: str, cache: KrdictCache, http: httpx.Client | None = None):
        if not api_key:
            raise KrdictError("KRDICT_API_KEY is not set (see .env.example)")
        self._key = api_key
        self._cache = cache
        self._http = http or httpx.Client(timeout=15)

    def search(self, word: str) -> list[KrdictEntry]:
        xml = self._cache.get(word)
        if xml is None:
            resp = self._http.get(API_URL, params={
                "key": self._key, "q": word, "part": "word", "translated": "y",
                "trans_lang": "1,2", "advanced": "y", "method": "exact", "num": 20,
            })
            resp.raise_for_status()
            xml = resp.text
            entries = parse_search(xml)  # raises on API error -> nothing cached
            self._cache.put(word, xml)
            return entries
        return parse_search(xml)

    def lookup(self, lemma: str, pos: str | None = None) -> KrdictEntry | None:
        return pick_entry(self.search(lemma), lemma, pos)
