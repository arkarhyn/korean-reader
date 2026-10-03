"""Verify context-aware lemmatization + the frontend offset-alignment it feeds.

Covers the two bugs found: (a) irregular predicates were tagged VV-I/VA-I and
silently dropped; (b) isolated-token analysis mis-reads forms like 한, 추워, 걸어서.
Analysing the whole passage fixes both."""
import re, sys
sys.path.insert(0, ".")

import app
from fastapi.testclient import TestClient

TEXT = ("저는 매일 학교에 걸어서 가요.\n"
        "오늘은 날씨가 추워서 집에 있었어요.\n"
        "어제 친구가 노래를 불렀어요.")

# What the on-screen token should resolve to (the user's cases: irregulars + particles)
EXPECT = {
    "학교에": "학교",     # noun + 에
    "걸어서": "걷다",     # ㄷ-irregular (걷→걸)  ← "rieul instead of nieun"
    "가요": "가다",
    "추워서": "춥다",     # ㅂ-irregular (춥→추워)
    "집에": "집",
    "있었어요": "있다",
    "노래를": "노래",
    "불렀어요": "부르다",  # 르-irregular
}

def clean_lookup(tok):  # mirror of JS cleanLookup
    return re.sub(r'^[^가-힣ㄱ-ㅎㅏ-ㅣa-zA-Z0-9]+|[^가-힣ㄱ-ㅎㅏ-ㅣa-zA-Z0-9]+$', '', tok)

def token_offsets(text):  # mirror of JS renderPassage offset tracking
    out = []  # (surface_token, start, len)
    line_start = 0
    for line in text.split("\n"):
        if line.strip():
            col = 0
            for part in re.split(r'(\s+)', line):
                if not part:
                    continue
                start = line_start + col
                col += len(part)
                if part.isspace():
                    continue
                if clean_lookup(part):
                    out.append((part, start, len(part)))
        line_start += len(line) + 1
    return out

with TestClient(app.app) as client:
    spans = client.post("/api/lemmatize", json={"text": TEXT}).json()["spans"]
    print(f"endpoint returned {len(spans)} content spans")

    # Frontend alignment: first content span starting inside each on-screen token
    ordered = sorted(spans, key=lambda s: s["start"])
    resolved = {}
    for surface, start, length in token_offsets(TEXT):
        end = start + length
        hit = next((s for s in ordered if start <= s["start"] < end), None)
        # key by the cleaned form (dataset.lookup), matching how the browser keys tokens
        resolved[clean_lookup(surface)] = hit["lemma"] if hit else clean_lookup(surface)

    print("\n=== on-screen token -> resolved lemma ===")
    bad = []
    for surface, want in EXPECT.items():
        got = resolved.get(surface)
        ok = got == want
        print(f"[{'OK ' if ok else 'FAIL'}] {surface} -> {got}   (want {want})")
        if not ok:
            bad.append((surface, got, want))
    assert not bad, f"misaligned: {bad}"

    # The whole point: marking the lemma once covers every conjugation.
    # 걷다 appears as 걸어서 here; if a second form existed it'd share the lemma.
    assert resolved["걸어서"] == "걷다" and resolved["추워서"] == "춥다", "irregulars must collapse"
    print("\nAll irregular + particle tokens resolve to their dictionary form.")

    # Long-form -지 / negation constructions resolve to their grammar pattern or expression
    def resolve_one(text, surf):
        spans = sorted(client.post("/api/lemmatize", json={"text": text}).json()["spans"],
                       key=lambda s: s["start"])
        for s2, st, ln in token_offsets(text):
            if clean_lookup(s2) == surf:
                hit = next((s for s in spans if st <= s["start"] < st + ln), None)
                return hit["lemma"] if hit else clean_lookup(s2)
        return None
    NEG = [
        ("긴장하지 마.", "긴장하지", "긴장하다"),   # 하다-verb + ...
        ("긴장하지 마.", "마", "-지 말다"),          # negative imperative
        ("밥을 먹지 않아요.", "않아요", "-지 않다"),  # long negation
        ("저는 가지 못해요.", "못해요", "-지 못하다"), # inability ("mot for can't")
        ("밥을 못 먹어요.", "못", "못 먹다"),         # forward negation still works
    ]
    negbad = []
    for text, surf, want in NEG:
        got = resolve_one(text, surf)
        ok = got == want
        print(f"[{'OK ' if ok else 'FAIL'}] {surf:8} in {text!r} -> {got}   (want {want})")
        if not ok:
            negbad.append((surf, got, want))
    assert not negbad, f"negation/-지 constructions wrong: {negbad}"
    print("Negation and -지 constructions resolve correctly.")

# Bonus: the tag fix also improves isolated get_lemma (used by mark/import fallbacks)
for surface, want in [("추웠어요", "춥다"), ("걸었어요", "걷다"), ("불러요", "부르다")]:
    got = app.get_lemma(surface)
    print(f"get_lemma({surface}) = {got}  (want {want})", "OK" if got == want else "(isolated diff)")

print("\nALL CHECKS PASSED")
