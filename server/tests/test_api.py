import uuid
from datetime import UTC, datetime

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import func, select

from app.db import get_session, make_sessionmaker
from app.db.models import Event
from app.ingest import ingest_episode
from app.main import app

from .conftest import episode, fake_lookup


@pytest.fixture
def client(engine):
    maker = make_sessionmaker(engine)
    with maker() as s:
        ingest_episode(s, episode("legacy-001"), fake_lookup, publish=True)
        ingest_episode(s, episode("legacy-002"), fake_lookup, publish=False)
        s.commit()

    def override():
        with maker() as s:
            yield s

    app.dependency_overrides[get_session] = override
    yield TestClient(app)
    app.dependency_overrides.clear()


def _event(type_="word_tap", **payload):
    return {"id": str(uuid.uuid4()), "ts": datetime.now(UTC).isoformat(), "device": "iphone",
            "type": type_, "payload": payload}


def test_list_only_published(client):
    assert [e["id"] for e in client.get("/api/episodes").json()] == ["legacy-001"]


def test_get_episode_is_self_contained(client):
    ep = client.get("/api/episodes/legacy-001").json()
    lex_ids = {str(t["lex"]) for p in ep["paragraphs"] for t in p["tokens"] if "lex" in t}
    assert lex_ids == set(ep["lexemes"])
    assert len(ep["questions"]) == 3 and all("id" in q for q in ep["questions"])
    assert client.get("/api/episodes/legacy-002").status_code == 404


def test_events_batch_is_idempotent(client, engine):
    batch = {"events": [_event(episode_id="legacy-001", lexeme_id=1), _event("episode_open")]}
    first = client.post("/api/events/batch", json=batch).json()
    assert len(first["accepted"]) == 2 and first["duplicate"] == []
    again = {"events": batch["events"] + [_event("episode_complete")]}
    second = client.post("/api/events/batch", json=again).json()
    assert len(second["accepted"]) == 1 and set(second["duplicate"]) == set(first["accepted"])
    with make_sessionmaker(engine)() as s:
        assert s.scalar(select(func.count()).select_from(Event)) == 3


def test_events_reject_unknown_type_and_naive_ts(client):
    assert client.post("/api/events/batch", json={"events": [_event("bogus")]}).status_code == 422
    naive = _event()
    naive["ts"] = "2026-10-03T10:00:00"
    assert client.post("/api/events/batch", json={"events": [naive]}).status_code == 422


def test_sync_pull_since(client):
    full = client.get("/api/sync/pull").json()
    assert [e["id"] for e in full["episodes"]] == ["legacy-001"]
    later = client.get("/api/sync/pull", params={"since": full["server_time"]}).json()
    assert later["episodes"] == []


def test_spa_fallback_never_shadows_api(client):
    assert client.get("/api/nope").status_code == 404


def test_sync_pull_carries_read_marks_across_devices(client):
    phone = _event("episode_complete", episode_id="legacy-001", tapped_lexeme_ids=[])
    phone["device"] = "iphone"
    client.post("/api/events/batch", json={"events": [phone]})
    full = client.get("/api/sync/pull").json()
    assert [c["episode_id"] for c in full["completed"]] == ["legacy-001"]
    # Always the full list, even after the cursor (a device that synced before still gets them).
    late = _event("episode_complete", episode_id="legacy-002", tapped_lexeme_ids=[])
    late["ts"] = "2026-01-01T00:00:00+00:00"
    client.post("/api/events/batch", json={"events": [late]})
    later = client.get("/api/sync/pull", params={"since": full["server_time"]}).json()
    assert {c["episode_id"] for c in later["completed"]} == {"legacy-001", "legacy-002"}
