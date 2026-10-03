"""Grammar-point codes for single morphemes.

Only morphemes with a stable code live here. Multi-morpheme patterns
(e.g. G.KIRO_HADA) are matched later from SYLLABUS_MAP (Stage 8); until then
unmapped grammar tokens carry grammar_code=None.
"""

# (form, base tag) -> code
MORPHEME_CODES: dict[tuple[str, str], str] = {
    ("한테서", "JKB"): "G.HANTESEO",
    ("에게서", "JKB"): "G.EGESEO",
    ("한테", "JKB"): "G.HANTE",
    ("에게", "JKB"): "G.EGE",
    ("께", "JKB"): "G.KKE",
}

# Constructions the analyzer builds itself (see rules.py).
NEG_AN = "G.NEG_AN"            # 안 + predicate
NEG_MOT = "G.NEG_MOT"          # 못 + predicate
JI_MOTHADA = "G.JI_MOTHADA"    # -지 못하다


def code_for(form: str, tag: str) -> str | None:
    return MORPHEME_CODES.get((form, tag))
