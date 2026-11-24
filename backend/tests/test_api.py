import os
from io import BytesIO
from tempfile import TemporaryDirectory
from pathlib import Path

test_directory = TemporaryDirectory()
test_path = Path(test_directory.name)
os.environ["DATABASE_URL"] = f"sqlite:///{(test_path / 'test.db').as_posix()}"
os.environ["STORAGE_ROOT"] = str(test_path / "storage")
os.environ["BOOTSTRAP_ADMIN_PASSWORD"] = "test-admin-password"
from fastapi.testclient import TestClient
from openpyxl import load_workbook
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


def test_registration_award_and_evidence_review():
    with client:
        admin = {"Authorization": f"Bearer {token()}"}
        credentials = {"username": "Teacher-New", "password": "new-teacher-password"}
        registration = client.post("/api/v1/auth/register", json={
            **credentials, "name": "新教师", "is_admin": True,
        })
        assert registration.status_code == 201
        assert registration.json()["is_admin"] is False
        assert client.post("/api/v1/auth/register", json={**credentials, "name": "重复"}).status_code == 409
        login = client.post("/api/v1/auth/login", json=credentials)
        assert login.status_code == 200
        auth = {"Authorization": "Bearer " + login.json()["access_token"]}
        assert client.get("/api/v1/admin/evidence", headers=auth).status_code == 403
        assert len(client.get("/api/v1/awards/templates", headers=auth).json()) == 5

        payload = {"template": "student_contest", "title": "学生技能赛", "achievement_date": "2026-06-01",
                   "organization": "竞赛主办方", "scope": "团队", "role": "指导教师", "rank": 2,
                   "prize": "二等奖", "extras": {"student": "参赛团队"}}
        award = client.post("/api/v1/awards", headers=auth, json=payload)
        assert award.status_code == 201, award.text
        award_id = award.json()["id"]
        award_url = f"/api/v1/awards/{award_id}"
        assert client.put(award_url, headers=admin, json=payload).status_code == 404
        assert client.put(award_url, headers=auth, json={**payload, "extras": {"research": "不适用"}}).status_code == 422

        upload = client.post(f"/api/v1/achievements/{award_id}/files", headers=auth,
                             files={"file": ("证书.pdf", b"%PDF-1.4 mock", "application/pdf")})
        assert upload.status_code == 200
        evidence_url = f"/api/v1/admin/evidence/achievement/{upload.json()['id']}"
        assert client.get("/api/v1/admin/evidence", headers=admin, params={"owner": "teacher-new"}).json()["items"][0]["teacher"] == "新教师"
        assert client.get(evidence_url + "/download", headers=admin).content == b"%PDF-1.4 mock"
        assert client.put(evidence_url, headers=admin, json={"status": "需补充"}).status_code == 422
        assert client.put(evidence_url, headers=admin, json={"status": "需补充", "note": "补指导名单"}).status_code == 200
        assert client.get(award_url + "/evidence", headers=auth).json()[0]["note"] == "补指导名单"

        project = client.post("/api/v1/title-applications", headers=auth, json={
            "name": "教师申报", "year": 2026, "target_title": "讲师"
        }).json()["id"]
        use_url = f"{award_url}/applications/{project}"
        assert client.put(use_url, headers=auth, json={
            "review_type": "教学为主型", "use_for": "教学（工作）业绩", "self_score": 2,
        }).status_code == 200
        report = client.get("/api/v1/awards/export", headers=auth, params={"project_id": project})
        assert report.status_code == 200, report.text[:150]
        workbook = load_workbook(BytesIO(report.content))
        assert workbook.sheetnames == ["获奖成果汇总", "附件18获奖计分明细", "附件2业绩条件对照"]
        assert workbook.worksheets[1]["D2"].value == 2
        assert workbook.worksheets[2]["D2"].value == "教学（工作）业绩"
        assert client.delete(use_url, headers=auth).status_code == 204
