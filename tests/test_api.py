"""End-to-end API tests: upload -> poll -> export, against an isolated DB.

Uses the `test_db` fixture (tests/conftest.py) to swap the job store onto
an in-memory SQLite DB, and constructs TestClient WITHOUT the `with`
context manager so the app's lifespan (which touches the *real* engine/db
file) never runs — the fixture already creates the schema the app
actually needs on the patched engine.
"""

import time

from fastapi.testclient import TestClient

from app.main import app

SAMPLE_TXT = """\
1. What is 2+2?
A) 3
+ B) 4
C) 5
"""


def _upload(client: TestClient, filename: str, content: bytes):
    return client.post(
        "/api/upload",
        files={"file": (filename, content, "text/plain")},
        data={"delimiter_mode": "auto"},
    )


def _poll_until_done(client: TestClient, job_id: str, timeout: float = 2.0):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        resp = client.get(f"/api/parse/{job_id}")
        body = resp.json()
        if body["status"] in ("done", "failed"):
            return body
        time.sleep(0.05)
    raise AssertionError(f"job {job_id} did not finish within {timeout}s")


def test_upload_rejects_unsupported_extension(test_db):
    client = TestClient(app)
    resp = _upload(client, "quiz.rtf", b"whatever")
    assert resp.status_code == 400


def test_upload_parse_flow_returns_questions(test_db):
    client = TestClient(app)
    resp = _upload(client, "quiz.txt", SAMPLE_TXT.encode("utf-8"))
    assert resp.status_code == 200
    job_id = resp.json()["job_id"]

    body = _poll_until_done(client, job_id)

    assert body["status"] == "done"
    assert len(body["questions"]) == 1
    assert body["questions"][0]["question"] == "What is 2+2?"
    assert body["questions"][0]["correct_option_index"] == 1


def test_parse_unknown_job_returns_404(test_db):
    client = TestClient(app)
    resp = client.get("/api/parse/00000000-0000-0000-0000-000000000000")
    assert resp.status_code == 404


def test_export_json_returns_downloadable_file(test_db):
    client = TestClient(app)
    resp = client.post(
        "/api/export",
        json={
            "format": "json",
            "questions": [
                {
                    "question": "2+2?",
                    "options": ["3", "4"],
                    "correct_option_index": 1,
                }
            ],
        },
    )
    assert resp.status_code == 200
    assert resp.headers["content-type"] == "application/json"
    assert resp.json()[0]["question"] == "2+2?"


def test_export_unknown_format_returns_400(test_db):
    client = TestClient(app)
    resp = client.post("/api/export", json={"format": "yaml", "questions": []})
    assert resp.status_code == 400


def test_upload_is_rate_limited_past_threshold(test_db):
    """/api/upload is capped at 10/minute per client — the 11th call in the
    same window should be rejected rather than accepted indefinitely."""
    client = TestClient(app)
    for _ in range(10):
        resp = _upload(client, "quiz.txt", SAMPLE_TXT.encode("utf-8"))
        assert resp.status_code == 200
    resp = _upload(client, "quiz.txt", SAMPLE_TXT.encode("utf-8"))
    assert resp.status_code == 429


def test_unexpected_parse_error_does_not_leak_internal_details(test_db, monkeypatch):
    """An unhandled exception in the pipeline must not hand the client the
    raw exception text (which can contain internal paths/library internals)."""
    import app.api.upload as upload_module

    async def _boom(*args, **kwargs):
        raise RuntimeError("/etc/secret/internal/path.py leaked traceback detail")

    monkeypatch.setattr(upload_module, "run_pipeline", _boom)

    client = TestClient(app)
    resp = _upload(client, "quiz.txt", SAMPLE_TXT.encode("utf-8"))
    assert resp.status_code == 200
    job_id = resp.json()["job_id"]

    body = _poll_until_done(client, job_id)
    assert body["status"] == "failed"
    assert "secret" not in body["error"]
    assert "RuntimeError" not in body["error"]
