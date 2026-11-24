import os
import zipfile
from uuid import uuid4
from io import BytesIO
from tempfile import TemporaryDirectory
from pathlib import Path
from unittest.mock import patch

test_directory = TemporaryDirectory()
test_path = Path(test_directory.name)
os.environ["DATABASE_URL"] = f"sqlite:///{(test_path / 'test.db').as_posix()}"
os.environ["STORAGE_ROOT"] = str(test_path / "storage")
os.environ["BOOTSTRAP_ADMIN_PASSWORD"] = "test-admin-password"
from fastapi.testclient import TestClient
from openpyxl import load_workbook
from app.main import app
from app.awards import AwardApplication
from app.core.config import get_settings
from app.core.database import SessionLocal
from app.models import TitleApplicationItem


client = TestClient(app)


def token():
    response = client.post("/api/v1/auth/login", json={"username": "admin", "password": "test-admin-password"})
    assert response.status_code == 200
    return response.json()["access_token"]


def test_six_character_password_and_temporary_reset():
    with client:
        admin = {"Authorization": f"Bearer {token()}"}
        credentials = {"username": "password-flow", "password": "a1b2c3"}
        invalid = client.post("/api/v1/auth/register", json={**credentials, "name": "测试", "password": "12345"})
        assert invalid.status_code == 422
        teacher = client.post("/api/v1/auth/register", json={**credentials, "name": "测试"})
        assert teacher.status_code == 201
        url = f"/api/v1/admin/users/{teacher.json()['id']}/reset-password"
        login = client.post("/api/v1/auth/login", json=credentials).json()
        original = {"Authorization": f"Bearer {login['access_token']}"}
        assert client.post(url, headers=original).status_code == 403
        assert client.post(url, headers=admin).status_code == 200
        assert client.get("/api/v1/profile", headers=original).status_code == 401
        assert client.post("/api/v1/auth/login", json=credentials).status_code == 401

        login = client.post("/api/v1/auth/login", json={**credentials, "password": "888888"}).json()
        assert login["password_change_required"]
        temporary = {"Authorization": f"Bearer {login['access_token']}"}
        assert client.get("/api/v1/auth/me", headers=temporary).json()["password_change_required"]
        assert client.get("/api/v1/profile", headers=temporary).status_code == 403
        assert client.get("/api/v1/admin/ai-config", headers=temporary).status_code == 403
        assert client.put("/api/v1/auth/password", headers=temporary, json={
            "current_password": "888888", "new_password": "888888",
        }).status_code == 422
        assert client.put("/api/v1/auth/password", headers=temporary, json={
            "current_password": "888888", "new_password": "654321",
        }).status_code == 200
        assert client.get("/api/v1/auth/me", headers=temporary).status_code == 401
        login = client.post("/api/v1/auth/login", json={**credentials, "password": "654321"}).json()
        assert not login["password_change_required"]
        auth = {"Authorization": f"Bearer {login['access_token']}"}
        assert client.get("/api/v1/profile", headers=auth).status_code == 200


def test_admin_ai_configuration():
    with client, patch.object(get_settings(), "deepseek_api_key", "fallback-test-key"):
        admin = {"Authorization": f"Bearer {token()}"}
        url = "/api/v1/admin/ai-config"
        assert client.get(url, headers=admin).json() == {"configured": True, "source": "environment"}
        key = "fake-deepseek-key-for-test"
        result = client.put(url, headers=admin, json={"api_key": key})
        assert result.status_code == 200
        assert result.json() == {"configured": True, "source": "admin"}
        assert client.get(url, headers=admin).json() == result.json()
        secret = test_path / "storage" / ".private" / "deepseek.key"
        assert secret.read_text() == key
        assert client.put(url, headers=admin, json={"api_key": "bad key"}).status_code == 422
        assert secret.read_text() == key
        assert client.delete(url, headers=admin).json() == {"configured": True, "source": "environment"}
        assert not secret.exists()


def test_achievement_attachment_retry_and_scoped_listing():
    with client:
        admin = {"Authorization": f"Bearer {token()}"}
        credentials = {"username": "evidence-owner", "password": "a1b2c3"}
        assert client.post("/api/v1/auth/register", json={**credentials, "name": "佐证测试"}).status_code == 201
        login = client.post("/api/v1/auth/login", json=credentials).json()
        auth = {"Authorization": f"Bearer {login['access_token']}"}
        achievement = client.post("/api/v1/achievements", headers=auth, json={
            "achievement_type": "教学成果", "category": "课程建设", "title": "课程建设证明", "year": 2026,
        })
        item_id = achievement.json()["id"]
        url = f"/api/v1/achievements/{item_id}/files"
        upload = {"upload_id": str(uuid4()), "file_category": "证书"}
        assert client.post(url, headers=auth, data=upload, files={"file": ("invalid.exe", b"invalid")}).status_code == 400
        content = b"%PDF-1.4 attachment"
        first = client.post(url, headers=auth, data=upload, files={"file": ("证书.pdf", content)})
        assert first.status_code == 200, first.text
        retry = client.post(url, headers=auth, data=upload, files={"file": ("证书.pdf", content)})
        assert retry.json()["id"] == first.json()["id"]
        files = client.get("/api/v1/files", headers=auth, params={"achievement_id": item_id}).json()
        assert len(files) == 1 and files[0]["file_category"] == "证书"
        assert client.get("/api/v1/files", headers=admin, params={"achievement_id": item_id}).json() == []
        assert client.get(f"/api/v1/files/{files[0]['id']}/download", headers=auth).content == content
        assert client.get("/api/v1/admin/ai-config", headers=auth).status_code == 403


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
        workspace = f"/api/v1/title-applications/{project}/workspace"
        state = client.get(workspace, headers=auth).json()
        with SessionLocal() as database:
            database.add(AwardApplication(application_id=project, achievement_id=award_id,
                                          review_data={"use_for": "教学（工作）业绩", "review_type": "教学为主型"}))
            for directory in state["directories"][:2]:
                database.add(TitleApplicationItem(application_id=project, category_id=directory["id"], achievement_id=award_id))
            database.commit()
        state = client.get(workspace, headers=auth).json()
        assert len(state["rows"]) == 1
        assert state["rows"][0]["evidence"][0]["status"] == "需补充"
        original = client.post(workspace + "/exports", headers=auth, json={"mode": "draft"})
        assert original.status_code == 201, original.text
        original_url = f"{workspace}/exports/{original.json()['id']}"
        draft = client.get(original_url, headers=auth).content
        with zipfile.ZipFile(BytesIO(draft)) as archive:
            assert "申报对照与计分.xlsx" in archive.namelist()
            assert any(name.endswith("证书.pdf") for name in archive.namelist())
        assert client.get(original_url, headers=admin).status_code == 404
        assert client.post(workspace + "/exports", headers=auth, json={"mode": "package"}).status_code == 409

        assert client.put(workspace + "/settings", headers=auth, json={
            "review_type": "教学为主型", "rule_year": 2026, "groups": [{
                "name": "任选其一", "mode": "any", "clauses": [
                    {"name": "条款A", "status": "未满足"}, {"name": "条款B", "status": "已满足"}
                ]
            }]
        }).status_code == 200
        assert client.get(workspace, headers=auth).json()["groups"][0]["outcome"] == "已满足"
        replacement = client.post(f"/api/v1/achievements/{award_id}/files", headers=auth,
                                  files={"file": ("指导名单.pdf", b"%PDF-1.4 replacement", "application/pdf")}).json()
        item_url = f"{workspace}/items/{award_id}"
        assert client.put(item_url, headers=auth, json={
            "category_id": state["directories"][0]["id"], "use_for": "教学（工作）业绩",
            "condition": "已满足", "clause": "已人工核对", "evidence_ids": [replacement["id"]],
            "self_score": 2,
        }).status_code == 200
        assert client.get(workspace, headers=auth).json()["rows"][0]["evidence"][0]["status"] == "待审核"
        assert client.put(item_url + "/score", headers=auth, json={"score": 3}).status_code == 403
        assert client.put(item_url + "/score", headers=admin, json={"score": 1.5}).status_code == 200
        assert client.put(f"/api/v1/admin/evidence/achievement/{replacement['id']}",
                          headers=admin, json={"status": "通过"}).status_code == 200
        package = client.post(workspace + "/exports", headers=auth, json={"mode": "package", "acknowledge_issues": True})
        assert package.status_code == 201
        second_url = f"{workspace}/exports/{package.json()['id']}"
        with zipfile.ZipFile(BytesIO(client.get(second_url, headers=auth).content)) as archive:
            assert any(name.endswith("指导名单.pdf") for name in archive.namelist())
            assert not any(name.endswith("证书.pdf") for name in archive.namelist())
            assert load_workbook(BytesIO(archive.read("申报对照与计分.xlsx"))).worksheets[1]["E2"].value == 1.5
        assert client.get(original_url, headers=auth).content == draft
        assert client.delete(use_url, headers=auth).status_code == 204
        assert client.get(workspace, headers=auth).json()["rows"] == []
        assert client.get(f"/api/v1/achievements/{award_id}", headers=auth).status_code == 200
