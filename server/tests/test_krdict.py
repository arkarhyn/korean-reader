"""krdict client against XML recorded from the real API (scripts/record_krdict_fixtures.py)."""

import httpx
import pytest

from app.config import KRDICT_API_KEY
from app.krdict.cache import KrdictCache
from app.krdict.client import KrdictClient, KrdictError, parse_search, pick_entry

from .conftest import TESTS_DIR

FIXTURES = TESTS_DIR / "fixtures" / "krdict"


def fixture(word: str) -> str:
    return (FIXTURES / f"{word}.xml").read_text(encoding="utf-8")


@pytest.fixture
def offline_client():
    calls = []

    def handler(request: httpx.Request) -> httpx.Response:
        q = request.url.params["q"]
        calls.append(q)
        path = FIXTURES / f"{q}.xml"
        return httpx.Response(200, text=path.read_text(encoding="utf-8"))

    client = KrdictClient("test-key", KrdictCache(":memory:"),
                          http=httpx.Client(transport=httpx.MockTransport(handler)))
    client.calls = calls
    return client


def test_parse_hanja_and_glosses():
    entries = parse_search(fixture("시간"))
    e = pick_entry(entries, "시간", "NNG")
    assert e.pos == "명사" and e.grade == "초급"
    assert e.hanja == "時間"
    assert e.gloss_en == "time"
    assert "時間" in e.gloss_ja


def test_hanja_strips_hangul_suffix():
    e = pick_entry(parse_search(fixture("공부하다")), "공부하다", "VV")
    assert e.origin == "工夫하다"
    assert e.hanja == "工夫"


def test_native_word_has_no_hanja():
    e = pick_entry(parse_search(fixture("돌보다")), "돌보다", "VV")
    assert e.hanja is None
    assert e.gloss_en == "take care of"


def test_pos_selects_homograph():
    entries = parse_search(fixture("있다"))
    assert pick_entry(entries, "있다", "VA").pos == "형용사"
    assert pick_entry(entries, "있다", "VV").pos == "동사"
    assert pick_entry(entries, "있다", "VX").pos == "보조 동사"
    assert pick_entry(entries, "시간", "NNB") is None  # wrong lemma
    assert pick_entry(parse_search(fixture("시간")), "시간", "NNB").pos == "의존 명사"


def test_no_result():
    assert parse_search(fixture("없는단어")) == []


def test_api_error_raises():
    xml = "<error><error_code>020</error_code><message>등록되지 않은 인증키입니다.</message></error>"
    with pytest.raises(KrdictError, match="020"):
        parse_search(xml)


def test_cache_avoids_second_request(offline_client):
    first = offline_client.lookup("설레다", "VV")
    second = offline_client.lookup("설레다", "VV")
    assert first == second
    assert first.gloss_en == "flutter"
    assert offline_client.calls == ["설레다"]


def test_missing_key_rejected():
    with pytest.raises(KrdictError):
        KrdictClient("", KrdictCache(":memory:"))


@pytest.mark.live
@pytest.mark.skipif(not KRDICT_API_KEY, reason="KRDICT_API_KEY not set")
def test_live_lookup():
    client = KrdictClient(KRDICT_API_KEY, KrdictCache(":memory:"))
    e = client.lookup("말씀드리다", "VV")
    assert e is not None and e.pos == "동사"
    assert e.gloss_en
