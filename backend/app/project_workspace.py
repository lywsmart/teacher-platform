import io
import json
import uuid
import zipfile
from pathlib import Path
from typing import Literal, Optional

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse, StreamingResponse
from openpyxl import Workbook
from pydantic import BaseModel, Field
from sqlalchemy import Boolean, ForeignKey, JSON, String, delete, select
from sqlalchemy.orm import Mapped, Session, mapped_column

from app.admin import require_admin
from app.awards import AwardApplication, AwardDetail, TEMPLATES, append_text, get_project
from app.core.database import Base, get_db
from app.core.security import current_user
from app.evidence import EvidenceReview, review_info
from app.materials import ApplicationMaterial
from app.models import Achievement, AchievementFile, TimestampMixin, TitleApplication, TitleApplicationCategory, TitleApplicationItem, User
from app.services.storage_service import StorageService

router = APIRouter(prefix="/api/v1/title-applications")
ReviewType = Literal["教学为主型", "教学科研并重型", "社会服务型", "思政课教师", "专职辅导员"]
Condition = Literal["待核实", "已满足", "未满足", "不适用"]


class ProjectSettings(Base):
    __tablename__ = "project_workspace_settings"
    project_id: Mapped[int] = mapped_column(ForeignKey("title_applications.id"), primary_key=True)
    settings: Mapped[dict] = mapped_column(JSON)


class ProjectSelection(Base):
    __tablename__ = "project_selections"
    project_id: Mapped[int] = mapped_column(ForeignKey("title_applications.id"), primary_key=True)
    achievement_id: Mapped[int] = mapped_column(ForeignKey("achievements.id"), primary_key=True)
    selection: Mapped[dict] = mapped_column(JSON)
    removed: Mapped[bool] = mapped_column(Boolean, default=False)


class ProjectExport(Base, TimestampMixin):
    __tablename__ = "project_exports"
    id: Mapped[int] = mapped_column(primary_key=True)
    project_id: Mapped[int] = mapped_column(ForeignKey("title_applications.id"), index=True)
    mode: Mapped[str] = mapped_column(String(16))
    filename: Mapped[str] = mapped_column(String(128))
    path: Mapped[str] = mapped_column(String(512))
    issue_count: Mapped[int] = mapped_column()


class ClauseInput(BaseModel):
    name: str = Field(min_length=1, max_length=500)
    status: Condition = "待核实"


class ConditionGroupInput(BaseModel):
    name: str = Field(min_length=1, max_length=128)
    mode: Literal["all", "any"] = "all"
    clauses: list[ClauseInput] = Field(min_length=1, max_length=40)


class SettingsInput(BaseModel):
    review_type: ReviewType
    rule_year: int = Field(ge=2000, le=2100)
    groups: list[ConditionGroupInput] = Field(default_factory=list, max_length=30)


class SelectionInput(BaseModel):
    category_id: Optional[int] = None
    use_for: Literal["待确认", "教学（工作）业绩", "科研业绩", "仅计分"] = "待确认"
    clause: str = Field(default="", max_length=500)
    condition: Condition = "待核实"
    score_group: str = Field(default="", max_length=64)
    basis: str = Field(default="", max_length=500)
    self_score: Optional[float] = Field(default=None, ge=0, le=100, allow_inf_nan=False)
    missing: str = Field(default="", max_length=500)
    evidence_ids: Optional[list[int]] = Field(default=None, max_length=200)


class ExportInput(BaseModel):
    mode: Literal["draft", "package"] = "draft"
    acknowledge_issues: bool = False


class ScoreInput(BaseModel):
    score: Optional[float] = Field(ge=0, le=100, allow_inf_nan=False)
    note: str = Field(default="", max_length=500)


def source_links(db, project_id):
    standard = db.scalars(select(TitleApplicationItem).where(TitleApplicationItem.application_id == project_id)
                          .order_by(TitleApplicationItem.sort_order, TitleApplicationItem.id)).all()
    awards = db.scalars(select(AwardApplication).where(AwardApplication.application_id == project_id)).all()
    saved = db.scalars(select(ProjectSelection).where(ProjectSelection.project_id == project_id)).all()
    return standard, awards, saved


def selected_achievement_ids(db, project_id):
    standard, awards, saved = source_links(db, project_id)
    ids = {item.achievement_id for item in standard + awards}
    ids.update(item.achievement_id for item in saved if not item.removed)
    ids.difference_update(item.achievement_id for item in saved if item.removed)
    return ids


def file_dict(file, review, application=False):
    return {"id": file.id, "name": file.name if application else file.original_name,
            "category": file.category if application else file.file_category,
            "path": file.path if application else file.file_path, **review_info(review)}


@router.get("/workspace/overview")
def project_overview(user: User = Depends(current_user), db: Session = Depends(get_db)):
    projects = db.scalars(select(TitleApplication).where(TitleApplication.user_id == user.id)
                          .order_by(TitleApplication.year.desc(), TitleApplication.id.desc()).limit(10)).all()
    items = []
    for project in projects:
        result = build_workspace(db, project)
        evidence = result["materials"] + [file for row in result["rows"] for file in row["evidence"]]
        items.append({"id": project.id, "name": project.name, "year": project.year, "target_title": project.target_title,
                      "incomplete": sum(bool(row["issues"]) for row in result["rows"]),
                      "waiting": sum(file["status"] == "待审核" and file["available"] for file in evidence),
                      "returned": sum(file["status"] == "需补充" for file in evidence)})
    return items


def build_workspace(db, project):
    standard, awards, saved = source_links(db, project.id)
    award_links = {item.achievement_id: item.review_data for item in awards}
    overrides = {item.achievement_id: item for item in saved}
    directories = {}
    for item in standard:
        directories.setdefault(item.achievement_id, []).append(item.category_id)
    ids = set(directories) | set(award_links) | set(overrides)
    ids.difference_update(item.achievement_id for item in saved if item.removed)
    cats = db.scalars(select(TitleApplicationCategory).where(TitleApplicationCategory.application_id == project.id)
                      .order_by(TitleApplicationCategory.sort_order, TitleApplicationCategory.id)).all()
    categories = {item.id: item.name for item in cats}
    project_settings = db.get(ProjectSettings, project.id)
    legacy_types = {data["review_type"] for data in award_links.values() if data.get("review_type")}
    settings = project_settings.settings if project_settings else {
        "review_type": next(iter(legacy_types)) if len(legacy_types) == 1 else None, "rule_year": None
    }
    achievements = db.execute(select(Achievement, AwardDetail).outerjoin(
        AwardDetail, AwardDetail.achievement_id == Achievement.id
    ).where(Achievement.id.in_(ids), Achievement.user_id == project.user_id).order_by(Achievement.id)).all()
    files_by_item = {}
    files = db.execute(select(AchievementFile, EvidenceReview).outerjoin(
        EvidenceReview, (EvidenceReview.kind == "achievement") & (EvidenceReview.file_id == AchievementFile.id)
    ).where(AchievementFile.achievement_id.in_(ids), AchievementFile.deleted_at.is_(None))
        .order_by(AchievementFile.id)).all()
    for file, review in files:
        files_by_item.setdefault(file.achievement_id, []).append(file_dict(file, review))
    evidence = db.execute(select(ApplicationMaterial, EvidenceReview).outerjoin(
        EvidenceReview, (EvidenceReview.kind == "application") & (EvidenceReview.file_id == ApplicationMaterial.id)
    ).where(ApplicationMaterial.application_id == project.id).order_by(ApplicationMaterial.id)).all()
    materials = [file_dict(file, review, application=True) for file, review in evidence]
    storage = StorageService()
    for file in materials + [file for batch in files_by_item.values() for file in batch]:
        file["available"] = storage.resolve(file["path"]).is_file()
    rows = []
    for item, award in achievements:
        defaults = SelectionInput().model_dump()
        if award:
            defaults["score_group"] = TEMPLATES[award.template][2]
        legacy = award_links.get(item.id, {})
        old_categories = list(dict.fromkeys(directories.get(item.id, [])))
        defaults.update({key: value for key, value in legacy.items() if key in defaults})
        if len(old_categories) == 1:
            defaults["category_id"] = old_categories[0]
        saved_item = overrides.get(item.id)
        data = {**defaults, **(saved_item.selection if saved_item else {})}
        options = files_by_item.get(item.id, [])
        requested = data["evidence_ids"]
        chosen = [file for file in options if requested is None or file["id"] in requested]
        issues = []
        if item.deleted_at:
            issues.append("成果已从成果库删除")
            chosen = []
        if not data["category_id"] or data["category_id"] not in categories:
            issues.append("材料目录待归类")
        if not saved_item and len(old_categories) > 1:
            issues.append("旧关联存在多个目录，请确认")
        if not saved_item and legacy.get("review_type") and settings.get("review_type") != legacy["review_type"]:
            issues.append("旧记录评审类型与项目设置不一致，请核对")
        if data["use_for"] == "待确认":
            issues.append("申报用途待确认")
        if data["use_for"] != "仅计分" and data["condition"] in ("待核实", "未满足"):
            issues.append("条件" + data["condition"])
        if not chosen or (requested is not None and len(chosen) != len(requested)):
            issues.append("缺少所选佐证")
        if data["missing"].strip():
            issues.append(data["missing"])
        if award and not item.level:
            issues.append("获奖级别待核实")
        if award and (award.template == "student_contest" or award.details.get("scope") == "团队") and not item.rank:
            issues.append("本人排名待核实")
        for file in chosen:
            if not file["available"]:
                issues.append(f"缺少文件 {file['name']}")
            elif file["status"] != "通过":
                issues.append(f"{file['name']} · {file['status']}" + (f" · {file['note']}" if file["note"] else ""))
        rows.append({"id": item.id, "title": item.title, "category": item.category, "year": item.year,
                     "level": item.level, "rank": item.rank, "deleted": item.deleted_at is not None,
                     "prize": award.details.get("prize") if award else None, "data": data,
                     "directory": categories.get(data["category_id"], "待归类"), "legacy_directories": [
                         categories.get(category, "未知目录") for category in old_categories],
                     "available_evidence": options, "evidence": chosen, "issues": issues})
    project_issues = []
    if not settings.get("review_type") or not settings.get("rule_year"):
        project_issues.append("请确认评审类型和规则年度")
    groups = []
    for group in settings.get("groups", []):
        statuses = [clause["status"] for clause in group["clauses"] if clause["status"] != "不适用"]
        if not statuses:
            outcome = "不适用"
        elif group["mode"] == "all":
            outcome = "未满足" if "未满足" in statuses else ("待核实" if "待核实" in statuses else "已满足")
        else:
            outcome = "已满足" if "已满足" in statuses else ("待核实" if "待核实" in statuses else "未满足")
        groups.append({**group, "outcome": outcome})
        if outcome in ("待核实", "未满足"):
            project_issues.append(f"{group['name']} · {outcome}")
    if not rows:
        project_issues.append("尚未选入成果")
    if not groups:
        project_issues.append("尚未配置资格条款清单")
    for material in materials:
        if not material["available"] or material["status"] != "通过":
            issue = material["status"] if material["available"] else "缺少文件"
            project_issues.append(f"{material['name']} · {issue}" + (f" · {material['note']}" if material["note"] else ""))
    return {"settings": settings, "directories": [{"id": key, "name": name} for key, name in categories.items()],
            "rows": rows, "materials": materials, "issues": project_issues, "groups": groups}


@router.get("/{project_id}/workspace")
def workspace(project_id: int, user: User = Depends(current_user), db: Session = Depends(get_db)):
    return public_workspace(build_workspace(db, get_project(project_id, user, db)))


def public_workspace(result):
    for row in result["rows"]:
        for file in row["available_evidence"] + row["evidence"]:
            file.pop("path", None)
    for file in result["materials"]:
        file.pop("path", None)
    return result


@router.get("/workspace/admin/projects", dependencies=[Depends(require_admin)])
def audit_projects(username: str = "", db: Session = Depends(get_db)):
    query = select(TitleApplication, User).join(User, TitleApplication.user_id == User.id)
    if username.strip():
        query = query.where(User.username == username.strip().lower())
    rows = db.execute(query.order_by(TitleApplication.id.desc()).limit(50))
    return [{"id": project.id, "name": project.name, "year": project.year, "username": owner.username,
             "teacher": owner.name, "college": owner.college} for project, owner in rows]


@router.get("/{project_id}/workspace/audit", dependencies=[Depends(require_admin)])
def audit_workspace(project_id: int, db: Session = Depends(get_db)):
    project = db.get(TitleApplication, project_id)
    if not project:
        raise HTTPException(404, "申报项目不存在")
    return public_workspace(build_workspace(db, project))


@router.put("/{project_id}/workspace/settings")
def save_settings(project_id: int, payload: SettingsInput, user: User = Depends(current_user), db: Session = Depends(get_db)):
    get_project(project_id, user, db)
    db.merge(ProjectSettings(project_id=project_id, settings=payload.model_dump()))
    db.commit()
    return payload


def set_selection(db, project, achievement_id, payload):
    item = db.get(Achievement, achievement_id)
    if item is None or item.user_id != project.user_id or item.deleted_at:
        raise HTTPException(404, "成果不存在")
    if payload.category_id is not None:
        cat = db.get(TitleApplicationCategory, payload.category_id)
        if cat is None or cat.application_id != project.id:
            raise HTTPException(422, "材料目录不属于该项目")
    if payload.evidence_ids is not None:
        ids = set(payload.evidence_ids)
        found = set(db.scalars(select(AchievementFile.id).where(
            AchievementFile.id.in_(ids), AchievementFile.achievement_id == achievement_id,
            AchievementFile.deleted_at.is_(None))))
        if found != ids:
            raise HTTPException(422, "所选佐证不属于该成果或已删除")
        payload.evidence_ids = list(dict.fromkeys(payload.evidence_ids))
    previous = db.get(ProjectSelection, (project.id, achievement_id))
    selection = payload.model_dump()
    if "score_group" not in payload.model_fields_set:
        award = db.get(AwardDetail, achievement_id)
        if award:
            selection["score_group"] = TEMPLATES[award.template][2]
    if previous and not previous.removed and previous.selection.get("audited_score") is not None:
        if all(selection[key] == previous.selection.get(key) for key in ("basis", "self_score", "score_group", "evidence_ids")):
            selection.update({key: previous.selection[key] for key in ("audited_score", "audit_note", "auditor")})
    db.merge(ProjectSelection(project_id=project.id, achievement_id=achievement_id, selection=selection, removed=False))
    db.commit()
    return selection


@router.put("/{project_id}/workspace/items/{achievement_id}")
def save_item(project_id: int, achievement_id: int, payload: SelectionInput,
              user: User = Depends(current_user), db: Session = Depends(get_db)):
    return set_selection(db, get_project(project_id, user, db), achievement_id, payload)


@router.delete("/{project_id}/workspace/items/{achievement_id}", status_code=204)
def remove_item(project_id: int, achievement_id: int, user: User = Depends(current_user), db: Session = Depends(get_db)):
    get_project(project_id, user, db)
    if achievement_id not in selected_achievement_ids(db, project_id):
        return
    db.merge(ProjectSelection(project_id=project_id, achievement_id=achievement_id, selection={}, removed=True))
    db.commit()


@router.put("/{project_id}/workspace/items/{achievement_id}/score")
def audit_score(project_id: int, achievement_id: int, payload: ScoreInput,
                admin: User = Depends(require_admin), db: Session = Depends(get_db)):
    project = db.get(TitleApplication, project_id)
    if project is None:
        raise HTTPException(404, "申报项目不存在")
    row = next((row for row in build_workspace(db, project)["rows"] if row["id"] == achievement_id and not row["deleted"]), None)
    if row is None:
        raise HTTPException(404, "申报成果不存在")
    data = {**row["data"], "audited_score": payload.score, "audit_note": payload.note.strip(), "auditor": admin.name}
    db.merge(ProjectSelection(project_id=project_id, achievement_id=achievement_id, selection=data, removed=False))
    db.commit()
    return data


def make_reports(project, result):
    workbook = Workbook()
    conditions = workbook.active
    conditions.title = "附件2业绩条件对照"
    score = workbook.create_sheet("附件18计分明细")
    checklist = workbook.create_sheet("导出检查")
    append_text(conditions, ["申报项目", "目标职称", "规则年度", "评审类型", "成果", "级别", "排名", "用途", "条款", "条件核对", "待处理"])
    append_text(score, ["计分栏目", "成果", "计分依据", "自评分", "审核分", "审核意见", "审核人"])
    append_text(checklist, ["条目", "待处理"])
    for issue in result["issues"]:
        append_text(checklist, [project.name, issue])
    if result["groups"]:
        rules = workbook.create_sheet("资格条件分组")
        append_text(rules, ["条件组", "组合关系", "组结果", "条件条款", "人工核对结果"])
        for group in result["groups"]:
            for clause in group["clauses"]:
                append_text(rules, [group["name"], "同时满足" if group["mode"] == "all" else "满足其中一项",
                                    group["outcome"], clause["name"], clause["status"]])
    for row in result["rows"]:
        data = row["data"]
        for issue in row["issues"]:
            append_text(checklist, [row["title"], issue])
        if row["deleted"]:
            continue
        append_text(conditions, [project.name, project.target_title, result["settings"]["rule_year"],
                                 result["settings"]["review_type"], row["title"], row["level"], row["rank"],
                                 data["use_for"], data["clause"], data["condition"], "；".join(row["issues"])])
        append_text(score, [data["score_group"], row["title"], data["basis"], data["self_score"],
                            data.get("audited_score"), data.get("audit_note"), data.get("auditor")])
    for sheet in workbook:
        sheet.freeze_panes = "A2"
        sheet.auto_filter.ref = sheet.dimensions
    output = io.BytesIO()
    workbook.save(output)
    return output.getvalue()


def archive_name(value):
    return "".join("_" if char in '<>:"/\\|?*' or ord(char) < 32 else char for char in value).strip(" .")[:100] or "材料"


def export_info(record):
    return {"id": record.id, "mode": record.mode, "filename": record.filename,
            "issue_count": record.issue_count, "created_at": record.created_at}


@router.get("/{project_id}/workspace/exports")
def exports(project_id: int, user: User = Depends(current_user), db: Session = Depends(get_db)):
    get_project(project_id, user, db)
    records = db.scalars(select(ProjectExport).where(ProjectExport.project_id == project_id)
                         .order_by(ProjectExport.id.desc())).all()
    return [export_info(record) for record in records]


@router.post("/{project_id}/workspace/exports", status_code=201)
def create_export(project_id: int, payload: ExportInput, user: User = Depends(current_user), db: Session = Depends(get_db)):
    project = get_project(project_id, user, db)
    result = build_workspace(db, project)
    issues = len(result["issues"]) + sum(len(row["issues"]) for row in result["rows"])
    if issues and payload.mode == "package" and not payload.acknowledge_issues:
        raise HTTPException(409, "请确认待处理事项后再生成材料包，或导出缺件草稿")
    storage = StorageService()
    relative = Path("exports", "projects", str(project_id), f"{uuid.uuid4().hex}.zip").as_posix()
    path = storage.resolve(relative)
    path.parent.mkdir(parents=True, exist_ok=True)
    try:
        with zipfile.ZipFile(path, "x", zipfile.ZIP_DEFLATED) as archive:
            archive.writestr("申报对照与计分.xlsx", make_reports(project, result))
            manifest = []
            for row in result["rows"]:
                for file in row["evidence"]:
                    if file["available"]:
                        entry = f"成果佐证/{archive_name(row['directory'])}/{row['id']}_{archive_name(row['title'])}/{file['id']}_{archive_name(file['name'])}"
                        archive.write(storage.resolve(file["path"]), entry)
                        manifest.append(entry)
            for file in result["materials"]:
                if file["available"]:
                    entry = f"申报材料/{archive_name(file['category'])}/{file['id']}_{archive_name(file['name'])}"
                    archive.write(storage.resolve(file["path"]), entry)
                    manifest.append(entry)
            archive.writestr("导出清单.json", json.dumps({
                "project": project.name, "mode": payload.mode, "files": manifest,
                "project_issues": result["issues"],
                "achievements": [{"id": row["id"], "title": row["title"], "issues": row["issues"]} for row in result["rows"]],
            }, ensure_ascii=False, indent=2))
        filename = f"职称申报-{project_id}-{'草稿' if payload.mode == 'draft' else '材料包'}.zip"
        record = ProjectExport(project_id=project_id, mode=payload.mode, filename=filename, path=relative, issue_count=issues)
        db.add(record)
        db.commit()
    except Exception:
        db.rollback()
        path.unlink(missing_ok=True)
        raise
    return export_info(record)


@router.get("/{project_id}/workspace/exports/{export_id}")
def download_export(project_id: int, export_id: int, user: User = Depends(current_user), db: Session = Depends(get_db)):
    get_project(project_id, user, db)
    record = db.get(ProjectExport, export_id)
    if record is None or record.project_id != project_id:
        raise HTTPException(404, "导出记录不存在")
    path = StorageService().resolve(record.path)
    if not path.is_file():
        raise HTTPException(404, "导出文件不存在")
    return FileResponse(path, filename=record.filename, media_type="application/zip", headers={"Cache-Control": "private, no-store"})


@router.get("/{project_id}/workspace/reports")
def download_reports(project_id: int, user: User = Depends(current_user), db: Session = Depends(get_db)):
    project = get_project(project_id, user, db)
    return StreamingResponse(io.BytesIO(make_reports(project, build_workspace(db, project))),
                             media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                             headers={"Content-Disposition": "attachment; filename=application-reports.xlsx"})
