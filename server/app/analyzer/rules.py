"""Turn raw Kiwi morphemes into content / grammar tokens.

Adapted from legacy/Graded-Reader-Project/app.py (_base_tag, _content_lemmas):
irregular-tag stripping, compound-noun merging, noun + XSV/XSA derivation.
Unlike legacy, negation and auxiliaries become grammar tokens so lexemes stay
pure (lemma, pos).
"""

from dataclasses import dataclass

from . import grammar_codes

NOUN_RUN_TAGS = {"NNG", "NNP"}
PREDICATE_TAGS = {"VV", "VA", "VCN"}
# Content words emitted as-is (lemma = form).
PLAIN_CONTENT_TAGS = {"NNG", "NNP", "NNB", "NR", "NP", "MAG", "MAJ", "MM", "IC", "XR", "UN"}
# Morphemes that carry grammar, not vocabulary. VCP (copula) and VX
# (auxiliaries: -고 있다, -어 주다, -지 않다 ...) are grammar per SPEC 7.
GRAMMAR_TAG_PREFIXES = ("J", "E")
GRAMMAR_TAGS = {"XSN", "XSV", "XSA", "XPN", "VCP", "VX"}

# Lemmas Kiwi tags inconsistently between VV and VA; one lexeme each.
POS_CANON: dict[str, str] = {"있다": "VA"}

NEGATION_ADVERBS = {"안": grammar_codes.NEG_AN, "못": grammar_codes.NEG_MOT}


@dataclass(frozen=True)
class Morph:
    form: str
    tag: str  # base tag, -I/-R suffix stripped
    start: int
    end: int
    irr: bool = False  # Kiwi's -I suffix: an irregular predicate stem (덥 VA-I), seen or not


@dataclass(frozen=True)
class Token:
    start: int
    end: int
    surface: str
    lemma: str
    pos: str
    kind: str  # "content" | "grammar"
    grammar_code: str | None = None

    @property
    def key(self) -> tuple[str, str]:
        return (self.lemma, self.pos)


def base_tag(raw) -> str:
    """Kiwi tag with the irregular/regular suffix stripped (VV-I -> VV, VV-R -> VV).
    Without this every irregular predicate falls through the tag checks."""
    name = raw.name if hasattr(raw, "name") else str(raw)
    return name.split(".")[-1].split("-")[0]


def is_grammar_tag(tag: str) -> bool:
    return tag in GRAMMAR_TAGS or tag.startswith(GRAMMAR_TAG_PREFIXES)


def build_tokens(morphs: list[Morph], text: str) -> list[Token]:
    out: list[Token] = []
    n = len(morphs)

    def adjacent(j: int) -> bool:
        return j < n and morphs[j].start == morphs[j - 1].end

    def content(start: int, end: int, lemma: str, pos: str) -> None:
        pos = POS_CANON.get(lemma, pos) if pos in ("VV", "VA") else pos
        out.append(Token(start, end, text[start:end], lemma, pos, "content"))

    def grammar(m: Morph, tag: str | None = None, code: str | None = None) -> None:
        tag = tag or m.tag
        out.append(Token(m.start, m.end, text[m.start:m.end], m.form, tag, "grammar",
                         code or grammar_codes.code_for(m.form, tag)))

    i = 0
    while i < n:
        m = morphs[i]
        tag = m.tag

        # Kiwi reads 아는 (알다 + -는) as 아/NNG + 는/JX (or 아/IC + 는/ETM).
        if m.form == "아" and tag in ("NNG", "IC") and adjacent(i + 1) and morphs[i + 1].form == "는":
            content(m.start, m.end, "알다", "VV")
            grammar(morphs[i + 1], tag="ETM")
            i += 2
            continue

        # -지 못하다: 못 + 하 after -지 is one grammar construction.
        if (m.form == "못" and tag == "MAG" and i > 0 and morphs[i - 1].form == "지"
                and morphs[i - 1].tag == "EC" and i + 1 < n and morphs[i + 1].form == "하"):
            h = morphs[i + 1]
            out.append(Token(m.start, h.end, text[m.start:h.end], "못하다", "VX", "grammar",
                             grammar_codes.JI_MOTHADA))
            i += 2
            continue

        # Noun prefix belongs to the noun (대 + 학교 -> 대학교, 맨 + 손 -> 맨손).
        if tag == "XPN" and adjacent(i + 1) and morphs[i + 1].tag in NOUN_RUN_TAGS:
            n_ = morphs[i + 1]
            morphs = morphs[:i + 1] + [Morph(m.form + n_.form, n_.tag, m.start, n_.end)] + morphs[i + 2:]
            n = len(morphs)
            i += 1
            continue

        # Root + 하: 따뜻 + 하 -> 따뜻하다/VA.
        if tag == "XR" and adjacent(i + 1) and morphs[i + 1].tag in ("XSV", "XSA"):
            s = morphs[i + 1]
            content(m.start, s.end, m.form + s.form + "다", "VV" if s.tag == "XSV" else "VA")
            i += 2
            continue

        if tag in NOUN_RUN_TAGS:
            # Compound nouns Kiwi over-splits (애견 + 용품 -> 애견용품).
            j = i + 1
            while j < n and morphs[j].tag in NOUN_RUN_TAGS and adjacent(j):
                j += 1
            lemma = "".join(x.form for x in morphs[i:j])
            pos = "NNP" if all(x.tag == "NNP" for x in morphs[i:j]) else "NNG"
            end = morphs[j - 1].end
            # Honorific 님 is part of the word (부모님, 선생님).
            if adjacent(j) and morphs[j].form == "님" and morphs[j].tag == "XSN":
                lemma += "님"
                end = morphs[j].end
                j += 1
            nxt = morphs[j] if adjacent(j) else None
            if nxt is not None and nxt.tag in ("XSV", "XSA"):
                # Derived predicate: 생각 + 하 -> 생각하다/VV, 행복 + 하 -> 행복하다/VA.
                content(m.start, nxt.end, lemma + nxt.form + "다", "VV" if nxt.tag == "XSV" else "VA")
                j += 1
            elif nxt is not None and nxt.tag == "VV" and nxt.form == "드리":
                # Humble -드리다 verbs: 말씀드리다, 부탁드리다, 인사드리다.
                content(m.start, nxt.end, lemma + "드리다", "VV")
                j += 1
            else:
                content(m.start, end, lemma, pos)
            i = j
            continue

        if tag in PREDICATE_TAGS:
            content(m.start, m.end, m.form + "다", tag)
            i += 1
            continue

        if tag == "MAG" and m.form in NEGATION_ADVERBS:
            k = i + 1
            while k < n and morphs[k].tag == "MAG":
                k += 1
            if k < n and morphs[k].tag in PREDICATE_TAGS | {"NNG"}:
                # 안 되다, 못 일어나다, 안 좋다; 안 + 공부하다 (NNG + XSV).
                grammar(m, code=NEGATION_ADVERBS[m.form])
            else:
                content(m.start, m.end, m.form, tag)
            i += 1
            continue

        if tag in PLAIN_CONTENT_TAGS:
            content(m.start, m.end, m.form, tag)
        elif tag == "VX" and m.form == "못하" and i > 0 and morphs[i - 1].form == "지" and morphs[i - 1].tag == "EC":
            grammar(m, code=grammar_codes.JI_MOTHADA)  # Kiwi sometimes reads 못하 as one VX
        elif is_grammar_tag(tag):
            grammar(m)
        # Punctuation, foreign script, numbers (S*, W*) are dropped.
        i += 1
    return out
