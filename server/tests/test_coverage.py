from app.analyzer import analyze, content_tokens
from app.coverage import coverage, unknown_lemmas
from app.seed import load_flagged_vocab


def test_coverage_returns_number_for_each_reader(legacy_episode):
    tokens = analyze(legacy_episode.text_ko)
    keys = {t.key for t in tokens if t.kind == "content"}
    flagged, _ = load_flagged_vocab()
    unknown = {(s.lemma, s.pos) for s in flagged}
    known = keys - unknown
    cov = coverage(tokens, known)
    assert isinstance(cov, float)
    assert 0.0 < cov < 1.0
    # Every unknown content token is a flagged lexeme present in this reader.
    assert set(unknown_lemmas(tokens, known)) == unknown & keys


def test_all_known_is_full_coverage(legacy_episode):
    keys = {t.key for t in content_tokens(legacy_episode.text_ko)}
    assert coverage(legacy_episode.text_ko, keys) == 1.0


def test_nothing_known_is_zero():
    assert coverage("강아지를 키우고 싶어요.", set()) == 0.0


def test_empty_text_is_full_coverage():
    assert coverage("", set()) == 1.0
    assert coverage("...", set()) == 1.0


def test_grammar_tokens_do_not_count():
    # 강아지, 키우다 are the only content tokens; particles/endings/aux excluded.
    assert coverage("강아지를 키우고 싶어요.", {("강아지", "NNG")}) == 0.5


def test_proper_nouns_count_as_known():
    text = "초코라고 불러요."
    assert coverage(text, {("부르다", "VV")}) == 0.5
    assert coverage(text, {("부르다", "VV")}, proper_nouns={"초코"}) == 1.0


def test_running_tokens_not_types():
    # 강아지 x2 unknown, 좋아하다 x1 known -> 1/3.
    assert abs(coverage("강아지가 강아지를 좋아해요.", {("좋아하다", "VV")}) - 1 / 3) < 1e-9


def test_known_aliases_bridge_list_and_text_tags():
    from app.coverage import expand_known

    known = expand_known({("감사하다", "VA"), ("아니다", "VA"), ("그럼", "MAG"), ("쓰다", "VA")})
    assert coverage("감사합니다. 아니에요. 그럼 가요.", known | {("가다", "VV")}) == 1.0
    assert ("쓰다", "VV") not in known  # only -하다 predicates bridge VV/VA
