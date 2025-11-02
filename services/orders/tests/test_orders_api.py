from datetime import datetime, timezone

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from services.orders.app import config, db, models
from services.orders.app.events import EventPublisher
from services.orders.app.main import app
from services.orders.app.routes import get_session


@pytest.fixture(autouse=True, scope="module")
def configure_test_db():
    settings = config.Settings(database_url="sqlite+pysqlite:///:memory:")

    def _settings_override():
        return settings

    config.get_settings.cache_clear()  # type: ignore[attr-defined]
    config.get_settings = _settings_override  # type: ignore[assignment]

    engine = create_engine(
        settings.database_url,
        future=True,
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    db.settings = settings  # type: ignore[attr-defined]
    db.engine = engine  # type: ignore[assignment]
    db.SessionLocal = sessionmaker(bind=engine, expire_on_commit=False)  # type: ignore[assignment]
    models.Base.metadata.create_all(bind=engine)

    def _session_override():
        session = db.SessionLocal()
        try:
            yield session
            session.commit()
        except Exception:
            session.rollback()
            raise
        finally:
            session.close()

    app.dependency_overrides[get_session] = _session_override
    app.state.event_publisher = EventPublisher(bootstrap_servers=None)

    yield

    app.dependency_overrides.clear()


def test_create_and_get_order(configure_test_db):
    client = TestClient(app)

    payload = {
        "customer_ref": "PO-100",
        "sku": "TSHIRT-001",
        "quantity": 120,
        "due_date": datetime.now(timezone.utc).isoformat(),
        "site_id": "bk-mill-01",
        "lots": [
            {"lot_id": "LOT-1", "quantity": 60, "cell_id": "CellA"},
            {"lot_id": "LOT-2", "quantity": 60, "cell_id": "CellB"}
        ]
    }

    response = client.post("/orders", json=payload)
    assert response.status_code == 201, response.text
    order_id = response.json()["order_id"]

    response = client.get(f"/orders/{order_id}")
    assert response.status_code == 200
    data = response.json()
    assert data["sku"] == "TSHIRT-001"
    assert len(data["lots"]) == 2


def test_state_transition_guardrails(configure_test_db):
    client = TestClient(app)
    payload = {
        "customer_ref": "PO-200",
        "sku": "HOODIE-001",
        "quantity": 50,
        "due_date": datetime.now(timezone.utc).isoformat(),
        "site_id": "bk-mill-01"
    }
    resp = client.post("/orders", json=payload)
    order_id = resp.json()["order_id"]

    # invalid transition from draft -> completed
    resp = client.post(f"/orders/{order_id}/state", json={"state": "completed"})
    assert resp.status_code == 409, resp.text

    # valid transition to firm then released
    client.patch(f"/orders/{order_id}", json={"state": "firm"})
    resp = client.post(f"/orders/{order_id}/state", json={"state": "released"})
    assert resp.status_code == 200


def test_orders_generate_unique_ids_for_same_sku(configure_test_db):
    client = TestClient(app)
    base_payload = {
        "sku": "VEST-001",
        "quantity": 10,
        "due_date": datetime.now(timezone.utc).isoformat(),
        "site_id": "bk-mill-01"
    }

    resp_one = client.post("/orders", json={**base_payload, "customer_ref": "PO-300"})
    resp_two = client.post("/orders", json={**base_payload, "customer_ref": "PO-301"})

    assert resp_one.status_code == 201, resp_one.text
    assert resp_two.status_code == 201, resp_two.text
    assert resp_one.json()["order_id"] != resp_two.json()["order_id"]


def test_list_orders_filter_by_cell_returns_distinct_orders(configure_test_db):
    client = TestClient(app)
    payload = {
        "customer_ref": "PO-400",
        "sku": "JACKET-001",
        "quantity": 25,
        "due_date": datetime.now(timezone.utc).isoformat(),
        "site_id": "bk-mill-01",
        "lots": [
            {"lot_id": "J-LOT-1", "quantity": 25, "cell_id": "CellX"},
            {"lot_id": "J-LOT-2", "quantity": 25, "cell_id": "CellX"}
        ]
    }
    client.post("/orders", json=payload)

    resp = client.get("/orders", params={"cell": "CellX"})
    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert len(data["data"]) == 1


def test_responses_include_no_store_cache_header(configure_test_db):
    client = TestClient(app)
    resp = client.get("/health/live")
    assert resp.status_code == 200
    assert resp.headers.get("cache-control") == "no-cache, no-store, must-revalidate, private"
    assert resp.headers.get("pragma") == "no-cache"
    assert resp.headers.get("expires") == "0"
    assert resp.headers.get("x-content-type-options") == "nosniff"
    assert resp.headers.get("cross-origin-opener-policy") == "same-origin"
    assert resp.headers.get("cross-origin-embedder-policy") == "require-corp"
    assert resp.headers.get("cross-origin-resource-policy") == "same-origin"


def test_root_endpoint_available(configure_test_db):
    client = TestClient(app)
    resp = client.get("/")
    assert resp.status_code == 200
    assert resp.json()["status"] == "ok"


def test_robots_and_sitemap_available(configure_test_db):
    client = TestClient(app)
    robots = client.get("/robots.txt")
    assert robots.status_code == 200
    assert "User-agent" in robots.text
    sitemap = client.get("/sitemap.xml")
    assert sitemap.status_code == 200
    assert sitemap.headers["content-type"].startswith("application/xml")
