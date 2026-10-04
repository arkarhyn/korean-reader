"""Known-word coverage over content tokens (SPEC 7).

Running-token count: particles, endings, copula and auxiliaries are grammar
tokens and excluded. Retrievability and Hanja weighting arrive with the DB.
"""

from collections.abc import Collection, Iterable

from .analyzer import Token, analyze

# Same word, different tag between the NIKL list and Kiwi's reading in running text:
# noun/XR + 하 is VV or VA by context (감사합니다 -> VV, list has VA), 아니다 is VCN in
# text but 형 (VA) in the list, 그럼/그래 drift between adverb, conjunction, interjection,
# and nouns between NNG and NNP.
_PARTICLE_LIKE = ("MAG", "MAJ", "IC")


def known_aliases(lemma: str, pos: str) -> set[tuple[str, str]]:
    """Keys that count as the same known word (for coverage only; lexemes stay separate)."""
    keys = {(lemma, pos)}
    if pos in ("VV", "VA") and lemma.endswith("하다"):
        keys |= {(lemma, "VV"), (lemma, "VA")}
    if lemma == "아니다" and pos in ("VA", "VCN"):
        keys |= {(lemma, "VA"), (lemma, "VCN")}
    if pos in _PARTICLE_LIKE:
        keys |= {(lemma, p) for p in _PARTICLE_LIKE}
    if pos in ("NNG", "NNP"):  # 한국 is 고유명사 in the list but often NNG in text
        keys |= {(lemma, "NNG"), (lemma, "NNP")}
    return keys


def expand_known(known: Collection[tuple[str, str]]) -> set[tuple[str, str]]:
    return {k for lemma, pos in known for k in known_aliases(lemma, pos)}


def coverage(
    tokens: Iterable[Token] | str,
    known: Collection[tuple[str, str]],
    proper_nouns: Collection[str] = (),
) -> float:
    """Fraction of content tokens that are known. No content tokens -> 1.0."""
    if isinstance(tokens, str):
        tokens = analyze(tokens)
    total = hits = 0
    for t in tokens:
        if t.kind != "content":
            continue
        total += 1
        if t.key in known or (t.pos == "NNP" and t.lemma in proper_nouns):
            hits += 1
    return hits / total if total else 1.0


def unknown_lemmas(tokens: Iterable[Token] | str,
                   known: Collection[tuple[str, str]],
                   proper_nouns: Collection[str] = ()) -> dict[tuple[str, str], int]:
    """Unknown (lemma, pos) -> occurrence count, most frequent first."""
    if isinstance(tokens, str):
        tokens = analyze(tokens)
    counts: dict[tuple[str, str], int] = {}
    for t in tokens:
        if t.kind == "content" and t.key not in known and not (t.pos == "NNP" and t.lemma in proper_nouns):
            counts[t.key] = counts.get(t.key, 0) + 1
    return dict(sorted(counts.items(), key=lambda kv: -kv[1]))
