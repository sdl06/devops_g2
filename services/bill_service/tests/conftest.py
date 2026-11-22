"""Shared test setup: a fresh in-memory SQLite database for every test."""

import os

# db.py needs a DATABASE_URL when it is imported; tests replace the session below.
os.environ.setdefault("DATABASE_URL", "sqlite://")
os.environ.setdefault("CORS_ORIGINS", "http://ui.test")

import pytest
from app.db import Base, get_db
from app.main import app
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool


@pytest.fixture
def client():
    engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )

    @event.listens_for(engine, "connect")
    def enable_foreign_keys(dbapi_connection, _):
        dbapi_connection.execute("PRAGMA foreign_keys=ON")

    Base.metadata.create_all(engine)
    TestingSession = sessionmaker(bind=engine)

    def override_get_db():
        db = TestingSession()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()
    Base.metadata.drop_all(engine)
    engine.dispose()


@pytest.fixture
def table(client):
    return client.post("/tables", json={"name": "Table 1"}).json()


@pytest.fixture
def dish(client):
    """A dish (12.50 EUR) whose recipe uses 200 g of chicken, with chicken in surplus."""
    chicken = client.post(
        "/ingredients",
        json={"name": "Chicken", "unit": "g", "stock": 5000, "surplus_level": 3000},
    ).json()
    curry = client.post("/dishes", json={"name": "Chicken curry", "price_cents": 1250}).json()
    client.put(
        f"/dishes/{curry['id']}/ingredients",
        json=[{"ingredient_id": chicken["id"], "amount": 200}],
    )
    return curry


@pytest.fixture
def bill(client, table):
    return client.post("/bills", json={"table_id": table["id"]}).json()
