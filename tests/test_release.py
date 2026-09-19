"""发布中心业务深化测试：环境/发布单/回滚记录全生命周期。"""
from __future__ import annotations

H = {"X-Internal-Token": "test-internal-key-12345"}


async def _mk_env(client, name="prod-east"):
    return await client.post("/api/release/environments", json={"name": name}, headers=H)


async def _mk_order(client, env_id, no="REL-0001", **extra):
    return await client.post("/api/release/orders", json={
        "release_no": no, "title": "灰度发布", "service_name": "order-svc",
        "version": "v1.0.0", "env_id": env_id, **extra,
    }, headers=H)


# ═══════════════════════════════════════════════════════════
# 目标环境
# ═══════════════════════════════════════════════════════════

class TestTargetEnvironment:
    async def test_create_env_success(self, client):
        resp = await _mk_env(client, "staging")
        assert resp.status_code == 201
        data = resp.json()
        assert data["name"] == "staging"
        assert data["status"] == "active"

    async def test_create_env_requires_token(self, client):
        resp = await client.post("/api/release/environments", json={"name": "noauth-env"})
        assert resp.status_code in (401, 403)

    async def test_create_env_duplicate_name(self, client):
        await _mk_env(client, "dup-env")
        resp = await _mk_env(client, "dup-env")
        assert resp.status_code == 409

    async def test_list_envs(self, client):
        await _mk_env(client, "list-env")
        resp = await client.get("/api/release/environments", headers=H)
        assert resp.status_code == 200
        assert resp.json()["total"] >= 1

    async def test_get_env_not_found(self, client):
        resp = await client.get("/api/release/environments/nope", headers=H)
        assert resp.status_code == 404

    async def test_update_env_status(self, client):
        create = await _mk_env(client, "maint-env")
        eid = create.json()["id"]
        resp = await client.patch(f"/api/release/environments/{eid}/status",
                                  json={"status": "maintenance"}, headers=H)
        assert resp.status_code == 200
        assert resp.json()["status"] == "maintenance"

    async def test_delete_env(self, client):
        create = await _mk_env(client, "del-env")
        eid = create.json()["id"]
        resp = await client.delete(f"/api/release/environments/{eid}", headers=H)
        assert resp.status_code == 200
        assert resp.json()["deleted"] is True


# ═══════════════════════════════════════════════════════════
# 发布单
# ═══════════════════════════════════════════════════════════

class TestReleaseOrder:
    async def test_create_order_success(self, client):
        eid = (await _mk_env(client, "ord-ok-env")).json()["id"]
        resp = await _mk_order(client, eid, no="REL-OK-001")
        assert resp.status_code == 201
        data = resp.json()
        assert data["release_no"] == "REL-OK-001"
        assert data["status"] == "draft"

    async def test_create_order_requires_token(self, client):
        eid = (await _mk_env(client, "ord-notoken-env")).json()["id"]
        resp = await client.post("/api/release/orders", json={
            "release_no": "REL-NT", "title": "x", "service_name": "s", "env_id": eid,
        })
        assert resp.status_code in (401, 403)

    async def test_create_order_nonexistent_env(self, client):
        resp = await client.post("/api/release/orders", json={
            "release_no": "REL-NE", "title": "x", "service_name": "s", "env_id": "missing",
        }, headers=H)
        assert resp.status_code == 404

    async def test_create_order_duplicate_no(self, client):
        eid = (await _mk_env(client, "ord-dup-env")).json()["id"]
        await _mk_order(client, eid, no="REL-DUP")
        resp = await _mk_order(client, eid, no="REL-DUP")
        assert resp.status_code == 409

    async def test_list_orders_filter_status(self, client):
        eid = (await _mk_env(client, "ord-list-env")).json()["id"]
        await _mk_order(client, eid, no="REL-LIST")
        resp = await client.get("/api/release/orders?status=draft", headers=H)
        assert resp.status_code == 200
        assert all(o["status"] == "draft" for o in resp.json()["items"])

    async def test_list_orders_keyword(self, client):
        eid = (await _mk_env(client, "ord-kw-env")).json()["id"]
        await _mk_order(client, eid, no="REL-KW-UNIQ", title="关键词唯一发布")
        resp = await client.get("/api/release/orders?keyword=REL-KW-UNIQ", headers=H)
        assert resp.status_code == 200
        nos = [o["release_no"] for o in resp.json()["items"]]
        assert "REL-KW-UNIQ" in nos

    async def test_order_state_machine_full(self, client):
        eid = (await _mk_env(client, "ord-sm-env")).json()["id"]
        create = await _mk_order(client, eid, no="REL-SM")
        oid = create.json()["id"]
        # draft -> approved
        r1 = await client.patch(f"/api/release/orders/{oid}/status",
                                json={"status": "approved"}, headers=H)
        assert r1.json()["status"] == "approved"
        # approved -> deploying
        r2 = await client.patch(f"/api/release/orders/{oid}/status",
                                json={"status": "deploying"}, headers=H)
        assert r2.json()["status"] == "deploying"
        # deploying -> deployed
        r3 = await client.patch(f"/api/release/orders/{oid}/status",
                                json={"status": "deployed"}, headers=H)
        assert r3.json()["status"] == "deployed"

    async def test_order_invalid_transition(self, client):
        eid = (await _mk_env(client, "ord-badsm-env")).json()["id"]
        create = await _mk_order(client, eid, no="REL-BADSM")
        oid = create.json()["id"]
        # draft 不能直接 deployed
        resp = await client.patch(f"/api/release/orders/{oid}/status",
                                  json={"status": "deployed"}, headers=H)
        assert resp.status_code == 409

    async def test_update_order(self, client):
        eid = (await _mk_env(client, "ord-upd-env")).json()["id"]
        create = await _mk_order(client, eid, no="REL-UPD")
        oid = create.json()["id"]
        resp = await client.patch(f"/api/release/orders/{oid}",
                                  json={"version": "v2.0.0", "changelog": "修bug"}, headers=H)
        assert resp.status_code == 200
        assert resp.json()["version"] == "v2.0.0"

    async def test_get_order_not_found(self, client):
        resp = await client.get("/api/release/orders/nope", headers=H)
        assert resp.status_code == 404


# ═══════════════════════════════════════════════════════════
# 回滚
# ═══════════════════════════════════════════════════════════

class TestRollback:
    async def _deployed_order(self, client, no="REL-RB"):
        # 每次用唯一环境名，避免跨用例唯一约束冲突
        eid = (await _mk_env(client, f"rb-env-{no}")).json()["id"]
        create = await _mk_order(client, eid, no=no)
        oid = create.json()["id"]
        for st in ("approved", "deploying", "deployed"):
            await client.patch(f"/api/release/orders/{oid}/status",
                               json={"status": st}, headers=H)
        return oid

    async def test_rollback_deployed_order(self, client):
        oid = await self._deployed_order(client, "REL-RB-OK")
        resp = await client.post(f"/api/release/orders/{oid}/rollback", json={
            "reason": "线上告警", "target_version": "v0.9.0", "operator": "ops",
        }, headers=H)
        assert resp.status_code == 200
        body = resp.json()
        assert body["order"]["status"] == "rolled_back"
        assert body["rollback"]["target_version"] == "v0.9.0"

    async def test_rollback_requires_token(self, client):
        oid = await self._deployed_order(client, "REL-RB-NT")
        resp = await client.post(f"/api/release/orders/{oid}/rollback", json={"reason": "x"})
        assert resp.status_code in (401, 403)

    async def test_rollback_draft_forbidden(self, client):
        eid = (await _mk_env(client, "rb-draft-env")).json()["id"]
        create = await _mk_order(client, eid, no="REL-RB-DRAFT")
        oid = create.json()["id"]
        # draft 状态不可回滚
        resp = await client.post(f"/api/release/orders/{oid}/rollback",
                                 json={"reason": "x"}, headers=H)
        assert resp.status_code == 409

    async def test_list_rollback_records(self, client):
        oid = await self._deployed_order(client, "REL-RB-LIST")
        await client.post(f"/api/release/orders/{oid}/rollback",
                           json={"reason": "list"}, headers=H)
        resp = await client.get("/api/release/rollback-records", headers=H)
        assert resp.status_code == 200
        assert resp.json()["total"] >= 1

    async def test_list_records_filter_by_order(self, client):
        oid = await self._deployed_order(client, "REL-RB-FILT")
        await client.post(f"/api/release/orders/{oid}/rollback",
                           json={"reason": "filt"}, headers=H)
        resp = await client.get(f"/api/release/rollback-records?release_order_id={oid}", headers=H)
        assert resp.status_code == 200
        assert all(r["release_order_id"] == oid for r in resp.json()["items"])

    async def test_delete_env_blocked_by_orders(self, client):
        eid = (await _mk_env(client, "ord-block-env")).json()["id"]
        await _mk_order(client, eid, no="REL-BLOCK")
        resp = await client.delete(f"/api/release/environments/{eid}", headers=H)
        assert resp.status_code == 409
