"""SM Release Center 领域测试：流水线、发布、部署、回滚与统计。"""

import pytest
from fastapi.testclient import TestClient

from app import base
from app.main import VERSION, app


@pytest.fixture()
def client(monkeypatch):
    monkeypatch.setattr(base, "internal_api_key", lambda: "TEST")
    base.reset_state()
    from app.main import _init as init_db
    init_db()
    with TestClient(app) as c:
        c.headers["X-Internal-Token"] = "TEST"
        yield c


def _pipeline(client, name="订单服务"):
    return client.post("/api/release/pipelines", json={"name": name, "repo": "luoshitianchen/order-svc", "environments": ["staging", "prod"]}).json()["id"]


def _release(client, pipeline_id, version="v2.0.0"):
    return client.post("/api/release/releases", json={"pipeline_id": pipeline_id, "version": version, "created_by": "发布工程师"}).json()["id"]


def test_health_and_version(client):
    r = client.get("/health", headers={"X-Request-Id": "suite-test"})
    assert r.status_code == 200
    assert r.json()["version"] == VERSION


def test_pipeline_and_release(client):
    pipeline_id = _pipeline(client)
    assert client.post("/api/release/pipelines", json={"name": "订单服务", "repo": "rr"}).status_code == 409
    release_id = _release(client, pipeline_id)
    assert client.post("/api/release/releases", json={"pipeline_id": pipeline_id, "version": "v2.0.0", "created_by": "x"}).status_code == 409
    assert client.get("/api/release/pipelines").json()["total"] == 1
    assert client.get("/api/release/releases").json()["total"] == 1
    assert client.get(f"/api/release/releases/{release_id}").json()["status"] == "draft"


def test_release_requires_pipeline(client):
    assert client.post("/api/release/releases", json={"pipeline_id": "no-such-pipe", "version": "v1", "created_by": "x"}).status_code == 404


def test_deploy_and_rollback(client):
    pipeline_id = _pipeline(client)
    release_id = _release(client, pipeline_id)
    deploy = client.post(f"/api/release/releases/{release_id}/deploy", json={"environment": "staging", "deployed_by": "发布工程师"})
    assert deploy.status_code == 201
    assert deploy.json()["status"] == "success"
    assert client.post(f"/api/release/releases/{release_id}/deploy", json={"environment": "qa", "deployed_by": "x"}).status_code == 404
    assert client.post(f"/api/release/releases/{release_id}/rollback").json()["status"] == "rolled_back"
    assert client.post(f"/api/release/releases/{release_id}/deploy", json={"environment": "staging", "deployed_by": "x"}).status_code == 409


def test_stats(client):
    pipeline_id = _pipeline(client)
    release_id = _release(client, pipeline_id)
    client.post(f"/api/release/releases/{release_id}/deploy", json={"environment": "prod", "deployed_by": "发布工程师"})
    stats = client.get("/api/release/stats").json()
    assert stats["pipelines"] == 1
    assert stats["deployed"] == 1
    assert stats["successful_deployments"] == 1


def test_manifest_and_crypto(client):
    assert client.get("/api/integration/manifest").json()["version"] == VERSION
    enc = client.post("/api/crypto/encrypt", json={"value": "x"}).json()["ciphertext"]
    assert client.post("/api/crypto/decrypt", json={"value": enc}).json()["plaintext"] == "x"


def test_write_requires_auth(client):
    del client.headers["X-Internal-Token"]
    assert client.post("/api/release/pipelines", json={"name": "p", "repo": "r"}).status_code == 401
