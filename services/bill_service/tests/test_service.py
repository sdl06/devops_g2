"""Health, request logging and behaviour when the database is down."""

import logging

from app.db import get_db
from app.main import app
from sqlalchemy.exc import OperationalError


def test_health(client):
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_one_log_line_per_request(client, caplog):
    with caplog.at_level(logging.INFO, logger="bill_service"):
        client.get("/health")
    lines = [r.getMessage() for r in caplog.records if r.name == "bill_service"]
    assert len(lines) == 1
    assert lines[0].startswith("method=GET path=/health status=200 duration_ms=")


def test_database_down_returns_503_not_a_crash(client):
    def broken_db():
        raise OperationalError("SELECT 1", {}, Exception("connection refused"))
        yield  # pragma: no cover

    app.dependency_overrides[get_db] = broken_db
    response = client.get("/tables")
    assert response.status_code == 503
    assert response.json() == {"error": "Database is unavailable. Try again shortly."}


def test_cors_allows_the_ui_origin(client):
    response = client.options(
        "/bills",
        headers={"Origin": "http://ui.test", "Access-Control-Request-Method": "POST"},
    )
    assert response.status_code == 200
    assert response.headers["access-control-allow-origin"] == "http://ui.test"


def test_cors_blocks_other_origins(client):
    response = client.options(
        "/bills",
        headers={"Origin": "http://evil.test", "Access-Control-Request-Method": "POST"},
    )
    assert "access-control-allow-origin" not in response.headers
