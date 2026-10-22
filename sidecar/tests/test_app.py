import json

import pytest
from fastapi.testclient import TestClient

from picturebook_sidecar.app import create_app

TOKEN = "t" * 32
AUTH = {"Authorization": f"Bearer {TOKEN}"}


@pytest.fixture()
def client():
    return TestClient(create_app(TOKEN))


def test_token_required_at_creation():
    with pytest.raises(ValueError):
        create_app("short")


@pytest.mark.parametrize("headers", [{}, {"Authorization": "Bearer wrong"}, {"Authorization": "Basic " + TOKEN}, {"Authorization": TOKEN}])
def test_rejects_missing_or_wrong_token(client, headers):
    assert client.get("/health", headers=headers).status_code == 401
    assert client.post("/jobs/demo", headers=headers, json={}).status_code == 401
    assert client.get("/events/abc", headers=headers).status_code == 401


def test_health_ok(client):
    r = client.get("/health", headers=AUTH)
    assert r.status_code == 200 and r.json()["status"] == "ok"


def test_rejects_foreign_host_header(client):
    r = client.get("/health", headers={**AUTH, "Host": "evil.example.com"})
    assert r.status_code == 400


def test_no_docs_or_openapi_exposed(client):
    for path in ("/docs", "/redoc", "/openapi.json"):
        assert client.get(path, headers=AUTH).status_code == 404


def test_demo_job_streams_progress_then_done(client):
    job_id = client.post("/jobs/demo", headers=AUTH, json={"steps": 4, "delay_ms": 0}).json()["job_id"]
    events = []
    with client.stream("GET", f"/events/{job_id}", headers=AUTH) as r:
        assert r.headers["content-type"].startswith("text/event-stream")
        name = None
        for line in r.iter_lines():
            if line.startswith("event: "):
                name = line[7:]
            elif line.startswith("data: "):
                events.append((name, json.loads(line[6:])))
    assert [e[0] for e in events] == ["progress"] * 4 + ["done"]
    assert events[-2][1]["fraction"] == 1.0 and events[-1][1]["result"] == {"steps": 4}


def test_late_subscriber_replays_history(client):
    job_id = client.post("/jobs/demo", headers=AUTH, json={"steps": 2, "delay_ms": 0}).json()["job_id"]
    for _ in range(2):   # second subscription starts after the job has finished
        with client.stream("GET", f"/events/{job_id}", headers=AUTH) as r:
            body = "".join(r.iter_text())
        assert body.count("event: progress") == 2 and "event: done" in body


def test_unknown_job_404(client):
    assert client.get("/events/nope", headers=AUTH).status_code == 404


def test_invalid_job_parameters_rejected(client):
    assert client.post("/jobs/demo", headers=AUTH, json={"steps": 0}).status_code == 422
    assert client.post("/jobs/demo", headers=AUTH, json={"steps": 1000}).status_code == 422


def test_shutdown_calls_callback():
    called = []
    c = TestClient(create_app(TOKEN, on_shutdown=lambda: called.append(1)))
    assert c.post("/shutdown", headers=AUTH).json() == {"ok": True} and called == [1]
