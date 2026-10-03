from fastapi.testclient import TestClient

from app.main import app
from app.seed import load_flagged_vocab

EXPECTED = {
    ("놓치다", "VV"), ("들어가다", "VV"), ("맞다", "VV"), ("경치", "NNG"),
    ("생기다", "VV"), ("챙기다", "VV"), ("돌보다", "VV"), ("자라다", "VV"),
    ("데려가다", "VV"), ("지르다", "VV"), ("설레다", "VV"), ("말씀드리다", "VV"),
}


def test_flagged_lexemes_resolve():
    lexemes, _ = load_flagged_vocab()
    assert {(s.lemma, s.pos) for s in lexemes} == EXPECTED
    assert all(s.state == "learning" and s.source == "manual" for s in lexemes)


def test_flagged_particles_route_to_grammar():
    _, grammar = load_flagged_vocab()
    assert {(g.form, g.code) for g in grammar} == {("한테서", "G.HANTESEO"), ("에게서", "G.EGESEO")}


def test_health():
    assert TestClient(app).get("/health").json() == {"status": "ok"}
