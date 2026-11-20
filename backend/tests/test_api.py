import os
from tempfile import TemporaryDirectory
from pathlib import Path

test_directory = TemporaryDirectory()
test_path = Path(test_directory.name)
os.environ["DATABASE_URL"] = f"sqlite:///{(test_path / 'test.db').as_posix()}"
os.environ["STORAGE_ROOT"] = str(test_path / "storage")
os.environ["BOOTSTRAP_ADMIN_PASSWORD"] = "test-admin-password"
from fastapi.testclient import TestClient
from app.main import app


client = TestClient(app)


def token():
    response = client.post("/api/v1/auth/login", json={"username": "admin", "password": "test-admin-password"})
    assert response.status_code == 200
    return response.json()["access_token"]


def test_health_and_core_flow():
    with client:
        assert client.get("/api/v1/health").status_code == 200
        headers = {"Authorization": f"Bearer {token()}"}
        created = client.post("/api/v1/achievements", headers=headers, json={"achievement_type": "科研成果", "category": "论文", "title": "测试成果", "year": 2026, "level": "校级", "rank": 1, "score": 3})
        assert created.status_code == 200
        item_id = created.json()["id"]
        assert client.get("/api/v1/achievements", headers=headers).json()["total"] >= 1
        assert client.get("/api/v1/annual/2026", headers=headers).status_code == 200
        copied = client.post(f"/api/v1/achievements/{item_id}/copy", headers=headers)
        assert copied.status_code == 200
        assert client.delete(f"/api/v1/achievements/{item_id}", headers=headers).status_code == 200


def test_teacher_material_ownership_and_admin_controls():
    with client:
        admin = {"Authorization": f"Bearer {token()}"}
        credentials = {"username": "teacher-a", "password": "teacher-test-password"}
        teacher = client.post("/api/v1/admin/users", headers=admin, json={**credentials, "name": "教师甲"})
        assert teacher.status_code == 201
        login = client.post("/api/v1/auth/login", json=credentials)
        auth = {"Authorization": "Bearer " + login.json()["access_token"]}
        assert client.get("/api/v1/admin/users", headers=auth).status_code == 403
        assert client.post("/api/v1/backups", headers=auth).status_code == 403
        project = client.post("/api/v1/title-applications", headers=auth, json={
            "name": "测试申报", "year": 2026, "target_title": "讲师",
        })
        assert project.status_code == 200
        url = f"/api/v1/title-applications/{project.json()['id']}/materials"
        payload = b"%PDF-1.4 test evidence"
        upload = client.post(url, headers=auth, data={"category": "学历学位与任职资历"},
                             files={"file": ("证书.pdf", payload, "application/pdf")})
        assert upload.status_code == 201
        file_url = f"{url}/{upload.json()['id']}"
        assert client.get(file_url, headers=auth).content == payload
        assert client.get(file_url, headers=admin).status_code == 404
        assert client.patch(f"/api/v1/admin/users/{teacher.json()['id']}", headers=admin,
                            json={"is_active": False}).status_code == 200
        assert client.get(file_url, headers=auth).status_code == 401
