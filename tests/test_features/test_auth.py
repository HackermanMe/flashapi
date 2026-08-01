import pytest
from pydantic import BaseModel

from flashapi.fastapi import FlashAPI
from flashapi.core.schema import Model
from flashapi.features.auth import AuthBackend, check_access


class Task(BaseModel):
    title: str
    tenant_id: int = 0
    owner_id: int = 0


class FakeUser:
    def __init__(self, uid, role="authenticated", tenant=None):
        self.id = uid
        self.role = role
        self.tenant = tenant


class SimpleAuth(AuthBackend):
    def authenticate(self, request):
        token = request.headers.get("Authorization", "")
        if token == "Bearer user1":
            return FakeUser(1, "authenticated", tenant=10)
        elif token == "Bearer user2":
            return FakeUser(2, "authenticated", tenant=20)
        elif token == "Bearer staff":
            return FakeUser(3, "staff", tenant=10)
        elif token == "Bearer admin":
            return FakeUser(99, "admin")
        return None

    def get_role(self, user):
        return user.role

    def get_tenant_id(self, user):
        return user.tenant

    def get_owner_id(self, user):
        return user.id


@pytest.fixture
def auth_client(tmp_path):
    from fastapi.testclient import TestClient

    db_path = str(tmp_path / "auth_test.db")
    flash = FlashAPI(
        models=[Model(Task, access="authenticated", scope="tenant", tenant_field="tenant_id")],
        database=db_path,
        auth_backend=SimpleAuth(),
    )
    return TestClient(flash.app)


@pytest.fixture
def owner_client(tmp_path):
    from fastapi.testclient import TestClient

    db_path = str(tmp_path / "owner_test.db")
    flash = FlashAPI(
        models=[Model(Task, access="authenticated", scope="owner", owner_field="owner_id")],
        database=db_path,
        auth_backend=SimpleAuth(),
    )
    return TestClient(flash.app)


@pytest.fixture
def mixed_access_client(tmp_path):
    from fastapi.testclient import TestClient

    db_path = str(tmp_path / "mixed_test.db")
    flash = FlashAPI(
        models=[Model(Task, access={
            "list": "public",
            "read": "public",
            "create": "authenticated",
            "update": "staff",
            "delete": "admin",
        })],
        database=db_path,
        auth_backend=SimpleAuth(),
    )
    return TestClient(flash.app)


class TestCheckAccess:
    def test_public_access(self):
        assert check_access("public", "public", "list") is True
        assert check_access("public", None, "list") is True
        assert check_access("public", True, "list") is True

    def test_role_hierarchy(self):
        assert check_access("authenticated", "authenticated", "create") is True
        assert check_access("staff", "authenticated", "create") is True
        assert check_access("admin", "authenticated", "create") is True
        assert check_access("public", "authenticated", "create") is False

    def test_dict_access(self):
        access = {"list": "public", "create": "staff", "delete": "admin"}
        assert check_access("public", access, "list") is True
        assert check_access("authenticated", access, "create") is False
        assert check_access("staff", access, "create") is True
        assert check_access("staff", access, "delete") is False
        assert check_access("admin", access, "delete") is True

    def test_false_blocks_non_admin(self):
        assert check_access("staff", False, "delete") is False
        assert check_access("admin", False, "delete") is True


class TestAuthEnforcement:
    def test_unauthenticated_blocked(self, auth_client):
        resp = auth_client.get("/api/tasks")
        assert resp.status_code == 401

    def test_authenticated_allowed(self, auth_client):
        resp = auth_client.get("/api/tasks", headers={"Authorization": "Bearer user1"})
        assert resp.status_code == 200

    def test_create_injects_tenant(self, auth_client):
        resp = auth_client.post(
            "/api/tasks", json={"title": "Test"},
            headers={"Authorization": "Bearer user1"},
        )
        assert resp.status_code == 201
        assert resp.json()["data"]["tenant_id"] == 10


class TestTenantIsolation:
    def test_tenant_sees_only_own_data(self, auth_client):
        auth_client.post("/api/tasks", json={"title": "T1"}, headers={"Authorization": "Bearer user1"})
        auth_client.post("/api/tasks", json={"title": "T2"}, headers={"Authorization": "Bearer user2"})

        r1 = auth_client.get("/api/tasks", headers={"Authorization": "Bearer user1"})
        assert r1.json()["meta"]["totalElements"] == 1
        assert r1.json()["data"][0]["title"] == "T1"

        r2 = auth_client.get("/api/tasks", headers={"Authorization": "Bearer user2"})
        assert r2.json()["meta"]["totalElements"] == 1
        assert r2.json()["data"][0]["title"] == "T2"

    def test_cross_tenant_read_blocked(self, auth_client):
        auth_client.post("/api/tasks", json={"title": "Secret"}, headers={"Authorization": "Bearer user2"})
        resp = auth_client.get("/api/tasks/1", headers={"Authorization": "Bearer user1"})
        assert resp.status_code == 404

    def test_admin_bypasses_scope(self, auth_client):
        auth_client.post("/api/tasks", json={"title": "T1"}, headers={"Authorization": "Bearer user1"})
        auth_client.post("/api/tasks", json={"title": "T2"}, headers={"Authorization": "Bearer user2"})

        resp = auth_client.get("/api/tasks", headers={"Authorization": "Bearer admin"})
        assert resp.json()["meta"]["totalElements"] == 2


class TestOwnerIsolation:
    def test_owner_sees_only_own(self, owner_client):
        owner_client.post("/api/tasks", json={"title": "Mine"}, headers={"Authorization": "Bearer user1"})
        owner_client.post("/api/tasks", json={"title": "Theirs"}, headers={"Authorization": "Bearer user2"})

        resp = owner_client.get("/api/tasks", headers={"Authorization": "Bearer user1"})
        assert resp.json()["meta"]["totalElements"] == 1
        assert resp.json()["data"][0]["title"] == "Mine"

    def test_owner_cannot_update_other(self, owner_client):
        owner_client.post("/api/tasks", json={"title": "Theirs"}, headers={"Authorization": "Bearer user2"})
        resp = owner_client.put(
            "/api/tasks/1", json={"title": "Hacked"},
            headers={"Authorization": "Bearer user1"},
        )
        assert resp.status_code == 404

    def test_owner_cannot_delete_other(self, owner_client):
        owner_client.post("/api/tasks", json={"title": "Theirs"}, headers={"Authorization": "Bearer user2"})
        resp = owner_client.delete("/api/tasks/1", headers={"Authorization": "Bearer user1"})
        assert resp.status_code == 404


class TestMixedAccess:
    def test_public_list(self, mixed_access_client):
        resp = mixed_access_client.get("/api/tasks")
        assert resp.status_code == 200

    def test_public_cannot_create(self, mixed_access_client):
        resp = mixed_access_client.post("/api/tasks", json={"title": "X"})
        assert resp.status_code == 401

    def test_authenticated_can_create(self, mixed_access_client):
        resp = mixed_access_client.post(
            "/api/tasks", json={"title": "X"},
            headers={"Authorization": "Bearer user1"},
        )
        assert resp.status_code == 201

    def test_authenticated_cannot_update(self, mixed_access_client):
        mixed_access_client.post(
            "/api/tasks", json={"title": "X"},
            headers={"Authorization": "Bearer user1"},
        )
        resp = mixed_access_client.put(
            "/api/tasks/1", json={"title": "Y"},
            headers={"Authorization": "Bearer user1"},
        )
        assert resp.status_code == 403

    def test_staff_can_update(self, mixed_access_client):
        mixed_access_client.post(
            "/api/tasks", json={"title": "X"},
            headers={"Authorization": "Bearer user1"},
        )
        resp = mixed_access_client.put(
            "/api/tasks/1", json={"title": "Y"},
            headers={"Authorization": "Bearer staff"},
        )
        assert resp.status_code == 200

    def test_staff_cannot_delete(self, mixed_access_client):
        mixed_access_client.post(
            "/api/tasks", json={"title": "X"},
            headers={"Authorization": "Bearer user1"},
        )
        resp = mixed_access_client.delete("/api/tasks/1", headers={"Authorization": "Bearer staff"})
        assert resp.status_code == 403

    def test_admin_can_delete(self, mixed_access_client):
        mixed_access_client.post(
            "/api/tasks", json={"title": "X"},
            headers={"Authorization": "Bearer user1"},
        )
        resp = mixed_access_client.delete("/api/tasks/1", headers={"Authorization": "Bearer admin"})
        assert resp.status_code == 204
