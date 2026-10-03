import pytest

from app.analyzer import analyze, content_tokens, lemmatize


@pytest.mark.parametrize("text", ["했어요", "했어요.", "했어요!", "어제 숙제를 했어요."])
def test_haesseoyo_resolves_to_hada(text):
    keys = [t.key for t in content_tokens(text)]
    assert keys[-1] == ("하다", "VV")
    assert ("했어요", "VV") not in keys and ("했어요.", "VV") not in keys


@pytest.mark.parametrize("text,key", [
    ("걸어요", ("걷다", "VV")),          # ㄷ-irregular
    ("추워요", ("춥다", "VA")),          # ㅂ-irregular
    ("불러요", ("부르다", "VV")),        # 르-irregular
    ("말씀드렸어요", ("말씀드리다", "VV")),
    ("산책시킬게요", ("산책시키다", "VV")),
    ("따뜻해요", ("따뜻하다", "VA")),
    ("따뜻하다", ("따뜻하다", "VA")),     # XR + XSA
    ("대학교", ("대학교", "NNG")),        # XPN prefix kept
    ("부모님", ("부모님", "NNG")),
    ("애견용품", ("애견용품", "NNG")),     # compound noun
    ("그냥 아는 것", ("알다", "VV")),     # Kiwi misreads 아는 as 아/NNG
])
def test_lemma(text, key):
    assert key in [t.key for t in content_tokens(text)]


def test_iteda_canonical_pos():
    # Kiwi tags 있다 as VV or VA by context; one lexeme either way.
    keys = {t.key for t in content_tokens("시험이 있어요. 오래 있으면 안 돼요.") if t.lemma == "있다"}
    assert keys == {("있다", "VA")}


def test_particles_and_negation_are_grammar():
    toks = analyze("친구한테서 들었는데 숙제를 안 했어요. 공부하지 못했어요.")
    by_surface = {t.surface: t for t in toks}
    assert by_surface["한테서"].kind == "grammar"
    assert by_surface["한테서"].grammar_code == "G.HANTESEO"
    assert by_surface["안"].grammar_code == "G.NEG_AN"
    assert any(t.grammar_code == "G.JI_MOTHADA" for t in toks)
    assert ("한테서", "JKB") not in {t.key for t in toks if t.kind == "content"}


def test_auxiliary_and_copula_are_grammar():
    toks = analyze("밥을 챙겨 줘야 해요. 학생이에요.")
    content = {t.lemma for t in toks if t.kind == "content"}
    assert content == {"밥", "챙기다", "학생"}


def test_spans_round_trip(legacy_episode):
    text = legacy_episode.text_ko
    for t in analyze(text):
        assert text[t.start:t.end] == t.surface
        # Contracted copula (거예요) is a zero-width grammar token; content never is.
        assert t.surface or (t.kind == "grammar" and t.pos == "VCP")


@pytest.mark.parametrize("word,key", [
    ("자다", ("자다", "VV")), ("있다", ("있다", "VA")), ("놓다", ("놓다", "VV")),
    ("저는", ("저", "NP")), ("걸으면서", ("걷다", "VV")),
])
def test_lemmatize_single_words(word, key):
    assert lemmatize(word) == key


def test_lemmatize_rejects_phrases():
    assert lemmatize("사진을 찍다") is None
    assert lemmatize("싶다") is None  # auxiliary only -> grammar
