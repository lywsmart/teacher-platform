import io
import json
import shutil
import sqlite3
import tempfile
import uuid
import zipfile
from collections import Counter, defaultdict
from datetime import datetime
from pathlib import Path
from typing import Optional

from docx import Document
from fastapi import Depends, FastAPI, File, Form, HTTPException, Query, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, StreamingResponse
from openpyxl import Workbook, load_workbook
from sqlalchemy import and_, func, or_, select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.admin import router as account_router, require_admin
from app.awards import AwardDetail, router as award_router
from app.evidence import router as evidence_router
from app.project_workspace import build_workspace, router as workspace_router, selected_achievement_ids
from app.materials import ApplicationMaterial, router as material_router
from app.core.database import Base, SessionLocal, engine, get_db
from app.core.security import create_token, current_user, verify_password
from app.models import (AISummary, AISummaryVersion, Achievement, AchievementCategory,
                        AchievementFile, AchievementLevel, BackupRecord,
                        TitleApplication, TitleApplicationCategory,
                        TitleApplicationItem, TitleRequirementRule, User)
from app.schemas import (AchievementIn, AchievementOut, LoginIn, ProfileUpdate,
                         RequirementIn, SummaryEditIn, SummaryGenerateIn,
                         TitleApplicationIn, TitleCategoryIn, TitleItemIn)
from app.seed import seed
from app.services.llm_service import LLMService, SYSTEM_PROMPT
from app.services.storage_service import StorageService


settings = get_settings()
app = FastAPI(title=settings.app_name, version="2.2.0")
app.include_router(account_router)
app.include_router(material_router)
app.include_router(award_router)
app.include_router(evidence_router)
app.include_router(workspace_router)
app.add_middleware(CORSMiddleware, allow_origins=settings.cors_list, allow_credentials=True, allow_methods=["*"], allow_headers=["*"])


@app.on_event("startup")
def startup():
    Path("data").mkdir(exist_ok=True)
    Base.metadata.create_all(engine)
    with SessionLocal() as db:
        seed(db)


@app.get("/api/v1/health")
def health():
    return {"status": "ok", "version": app.version}


@app.post("/api/v1/auth/login")
def login(payload: LoginIn, db: Session = Depends(get_db)):
    user = db.scalar(select(User).where(User.username == payload.username.strip().lower()))
    if not user or not user.is_active or not verify_password(payload.password, user.password_hash):
        raise HTTPException(401, "用户名或密码错误")
    return {"access_token": create_token(user.id, user.password_hash), "token_type": "bearer", "user": {"id": user.id, "name": user.name, "username": user.username}}


@app.get("/api/v1/profile")
def get_profile(user=Depends(current_user)):
    return {column.name: getattr(user, column.name) for column in User.__table__.columns if column.name != "password_hash"}


@app.put("/api/v1/profile")
def update_profile(payload: ProfileUpdate, user=Depends(current_user), db: Session = Depends(get_db)):
    for key, value in payload.model_dump().items():
        setattr(user, key, value)
    db.commit(); db.refresh(user)
    return get_profile(user)


def achievement_query(user_id: int, year=None, achievement_type=None, level=None, rank=None, keyword=None, start_year=None, end_year=None):
    query = select(Achievement).where(Achievement.user_id == user_id, Achievement.deleted_at.is_(None))
    if year: query = query.where(Achievement.year == year)
    if start_year: query = query.where(Achievement.year >= start_year)
    if end_year: query = query.where(Achievement.year <= end_year)
    if achievement_type: query = query.where(Achievement.achievement_type == achievement_type)
    if level: query = query.where(Achievement.level == level)
    if rank: query = query.where(Achievement.rank == rank)
    if keyword:
        pattern = f"%{keyword}%"
        query = query.where(or_(Achievement.title.like(pattern), Achievement.description.like(pattern), Achievement.organization.like(pattern)))
    return query


@app.get("/api/v1/achievements")
def list_achievements(page: int = Query(1, ge=1), page_size: int = Query(20, ge=1, le=200), year: Optional[int] = None,
                      achievement_type: Optional[str] = None, level: Optional[str] = None, rank: Optional[int] = None,
                      keyword: Optional[str] = None, start_year: Optional[int] = None, end_year: Optional[int] = None,
                      user=Depends(current_user), db: Session = Depends(get_db)):
    query = achievement_query(user.id, year, achievement_type, level, rank, keyword, start_year, end_year)
    total = db.scalar(select(func.count()).select_from(query.subquery()))
    items = db.scalars(query.order_by(Achievement.year.desc(), Achievement.created_at.desc()).offset((page - 1) * page_size).limit(page_size)).all()
    return {"items": [AchievementOut.model_validate(item) for item in items], "total": total, "page": page, "page_size": page_size}


@app.post("/api/v1/achievements", response_model=AchievementOut)
def create_achievement(payload: AchievementIn, user=Depends(current_user), db: Session = Depends(get_db)):
    item = Achievement(user_id=user.id, **payload.model_dump())
    db.add(item); db.commit(); db.refresh(item)
    return item


def owned_achievement(item_id: int, user_id: int, db: Session):
    item = db.scalar(select(Achievement).where(Achievement.id == item_id, Achievement.user_id == user_id, Achievement.deleted_at.is_(None)))
    if not item: raise HTTPException(404, "成果不存在")
    return item


@app.get("/api/v1/achievements/{item_id}", response_model=AchievementOut)
def get_achievement(item_id: int, user=Depends(current_user), db: Session = Depends(get_db)):
    return owned_achievement(item_id, user.id, db)


@app.put("/api/v1/achievements/{item_id}", response_model=AchievementOut)
def update_achievement(item_id: int, payload: AchievementIn, user=Depends(current_user), db: Session = Depends(get_db)):
    item = owned_achievement(item_id, user.id, db)
    if db.get(AwardDetail, item_id):
        raise HTTPException(409, "请在「获奖成果」中编辑此记录")
    for key, value in payload.model_dump().items(): setattr(item, key, value)
    db.commit(); db.refresh(item); return item


@app.delete("/api/v1/achievements/{item_id}")
def delete_achievement(item_id: int, user=Depends(current_user), db: Session = Depends(get_db)):
    item = owned_achievement(item_id, user.id, db); item.deleted_at = datetime.utcnow(); db.commit()
    return {"message": "已移入回收状态"}


@app.post("/api/v1/achievements/{item_id}/copy", response_model=AchievementOut)
def copy_achievement(item_id: int, user=Depends(current_user), db: Session = Depends(get_db)):
    source = owned_achievement(item_id, user.id, db)
    data = {c.name: getattr(source, c.name) for c in Achievement.__table__.columns if c.name not in {"id", "created_at", "updated_at", "deleted_at"}}
    data["title"] = f"{data['title'][:251]}（副本）"
    item = Achievement(**data)
    db.add(item)
    detail = db.get(AwardDetail, source.id)
    if detail is not None:
        db.flush()
        db.add(AwardDetail(achievement_id=item.id, template=detail.template, details=detail.details))
    db.commit()
    db.refresh(item)
    return item


@app.post("/api/v1/achievements/batch-delete")
def batch_delete(ids: list[int], user=Depends(current_user), db: Session = Depends(get_db)):
    items = db.scalars(select(Achievement).where(Achievement.id.in_(ids), Achievement.user_id == user.id, Achievement.deleted_at.is_(None))).all()
    for item in items: item.deleted_at = datetime.utcnow()
    db.commit(); return {"deleted": len(items)}


EXCEL_HEADERS = ["成果类型", "二级分类", "成果名称", "年度", "成果日期", "级别", "本人排名", "角色", "授予/组织单位", "证书编号", "积分", "描述", "备注"]
EXCEL_FIELDS = ["achievement_type", "category", "title", "year", "achievement_date", "level", "rank", "role", "organization", "certificate_no", "score", "description", "remark"]


@app.get("/api/v1/achievements/export/excel")
def export_achievements(user=Depends(current_user), db: Session = Depends(get_db)):
    items = db.scalars(achievement_query(user.id).order_by(Achievement.year.desc())).all()
    wb = Workbook(); ws = wb.active; ws.title = "成果清单"; ws.append(EXCEL_HEADERS)
    for item in items: ws.append([getattr(item, f) for f in EXCEL_FIELDS])
    for cell in ws[1]: cell.font = cell.font.copy(bold=True)
    stream = io.BytesIO(); wb.save(stream); stream.seek(0)
    return StreamingResponse(stream, media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", headers={"Content-Disposition": "attachment; filename=achievements.xlsx"})


@app.post("/api/v1/achievements/import/excel")
async def import_achievements(file: UploadFile = File(...), user=Depends(current_user), db: Session = Depends(get_db)):
    try: wb = load_workbook(io.BytesIO(await file.read()), read_only=True, data_only=True)
    except Exception as exc: raise HTTPException(400, "无法读取 Excel 文件") from exc
    rows = wb.active.iter_rows(values_only=True); headers = list(next(rows, [])); mapping = {h: i for i, h in enumerate(headers)}
    if not all(h in mapping for h in EXCEL_HEADERS[:4]): raise HTTPException(400, "Excel 缺少必要列")
    count = 0
    for row in rows:
        if not row[mapping["成果名称"]]: continue
        values = {field: row[mapping[header]] if header in mapping and mapping[header] < len(row) else None for field, header in zip(EXCEL_FIELDS, EXCEL_HEADERS)}
        values["year"] = int(values["year"]); values["score"] = float(values["score"] or 0)
        db.add(Achievement(user_id=user.id, **values)); count += 1
    db.commit(); return {"imported": count}


@app.post("/api/v1/achievements/{item_id}/files")
async def upload_file(item_id: int, file_category: str = Form("其他"), file: UploadFile = File(...), user=Depends(current_user), db: Session = Depends(get_db)):
    item = owned_achievement(item_id, user.id, db)
    name = Path((file.filename or "").replace("\\", "/")).name
    if not 1 <= len(name) <= 255 or any(ord(char) < 32 for char in name) or len(file_category) > 64:
        raise HTTPException(422, "文件名或类别无效")
    storage = StorageService()
    stored, relative, size, extension = await storage.save_upload(file, item.year, item.id)
    record = AchievementFile(achievement_id=item.id, original_name=name, stored_name=stored, file_path=relative, file_type=extension, file_size=size, file_category=file_category)
    try:
        db.add(record)
        db.commit()
    except Exception:
        db.rollback()
        storage.resolve(relative).unlink(missing_ok=True)
        raise
    db.refresh(record)
    return {c.name: getattr(record, c.name) for c in AchievementFile.__table__.columns}


@app.get("/api/v1/files")
def list_files(year: Optional[int] = None, achievement_type: Optional[str] = None, file_category: Optional[str] = None, keyword: Optional[str] = None, user=Depends(current_user), db: Session = Depends(get_db)):
    query = select(AchievementFile, Achievement).join(Achievement).where(Achievement.user_id == user.id, Achievement.deleted_at.is_(None), AchievementFile.deleted_at.is_(None))
    if year: query = query.where(Achievement.year == year)
    if achievement_type: query = query.where(Achievement.achievement_type == achievement_type)
    if file_category: query = query.where(AchievementFile.file_category == file_category)
    if keyword: query = query.where(or_(AchievementFile.original_name.like(f"%{keyword}%"), Achievement.title.like(f"%{keyword}%")))
    return [{"id": f.id, "original_name": f.original_name, "file_type": f.file_type, "file_size": f.file_size, "file_category": f.file_category, "uploaded_at": f.uploaded_at, "achievement_id": a.id, "achievement_title": a.title, "year": a.year, "achievement_type": a.achievement_type} for f, a in db.execute(query).all()]


def owned_file(file_id, user_id, db):
    result = db.execute(select(AchievementFile, Achievement).join(Achievement).where(AchievementFile.id == file_id, Achievement.user_id == user_id, AchievementFile.deleted_at.is_(None))).first()
    if not result: raise HTTPException(404, "文件不存在")
    return result


@app.get("/api/v1/files/{file_id}/download")
def download_file(file_id: int, user=Depends(current_user), db: Session = Depends(get_db)):
    record, _ = owned_file(file_id, user.id, db); path = StorageService().resolve(record.file_path)
    if not path.exists(): raise HTTPException(404, "磁盘文件不存在")
    return FileResponse(path, filename=record.original_name)


@app.delete("/api/v1/files/{file_id}")
def delete_file(file_id: int, user=Depends(current_user), db: Session = Depends(get_db)):
    record, _ = owned_file(file_id, user.id, db); record.deleted_at = datetime.utcnow(); db.commit(); return {"message": "已删除"}


@app.get("/api/v1/settings/options")
def options(user=Depends(current_user), db: Session = Depends(get_db)):
    categories = db.scalars(select(AchievementCategory).where(AchievementCategory.enabled == True).order_by(AchievementCategory.sort_order)).all()
    levels = db.scalars(select(AchievementLevel).where(AchievementLevel.enabled == True).order_by(AchievementLevel.sort_order)).all()
    parents = [c for c in categories if c.parent_id is None]
    return {"categories": [{"name": p.name, "children": [c.name for c in categories if c.parent_id == p.id]} for p in parents], "levels": [x.name for x in levels]}


def dashboard_data(user_id, db):
    items = db.scalars(achievement_query(user_id)).all(); current = datetime.now().year
    by_year = Counter(x.year for x in items); by_type = Counter(x.achievement_type for x in items); by_level = Counter(x.level or "未设置" for x in items)
    files = db.scalar(select(func.count(AchievementFile.id)).join(Achievement).where(Achievement.user_id == user_id, Achievement.deleted_at.is_(None), AchievementFile.deleted_at.is_(None))) or 0
    return {"metrics": {"this_year": by_year[current], "three_years": sum(v for y, v in by_year.items() if current - 2 <= y <= current), "five_years": sum(v for y, v in by_year.items() if current - 4 <= y <= current), "total": len(items), "files": files}, "trend": [{"year": y, "count": by_year[y], "score": sum(x.score for x in items if x.year == y)} for y in sorted(by_year)], "by_type": [{"name": k, "value": v} for k, v in by_type.items()], "by_level": [{"name": k, "value": v} for k, v in by_level.items()], "recent": [AchievementOut.model_validate(x) for x in sorted(items, key=lambda i: i.created_at, reverse=True)[:5]]}


@app.get("/api/v1/dashboard")
def dashboard(user=Depends(current_user), db: Session = Depends(get_db)):
    return dashboard_data(user.id, db)


@app.get("/api/v1/analytics")
def analytics(user=Depends(current_user), db: Session = Depends(get_db)):
    items = db.scalars(achievement_query(user.id)).all(); base = dashboard_data(user.id, db)
    base["rank"] = [{"name": f"第{k}名" if k else "未设置", "value": v} for k, v in Counter(x.rank for x in items).items()]
    base["category"] = [{"name": k, "value": v} for k, v in Counter(x.category for x in items).items()]
    return base


@app.get("/api/v1/annual/{year}")
def annual(year: int, user=Depends(current_user), db: Session = Depends(get_db)):
    items = db.scalars(achievement_query(user.id, year=year).order_by(Achievement.achievement_type)).all()
    ids = [x.id for x in items]
    file_count = db.scalar(select(func.count(AchievementFile.id)).where(AchievementFile.achievement_id.in_(ids), AchievementFile.deleted_at.is_(None))) if ids else 0
    return {"year": year, "total": len(items), "file_count": file_count or 0, "score": sum(x.score for x in items), "by_type": dict(Counter(x.achievement_type for x in items)), "items": [AchievementOut.model_validate(x) for x in items]}


@app.get("/api/v1/annual/{year}/word")
def annual_word(year: int, user=Depends(current_user), db: Session = Depends(get_db)):
    items = db.scalars(achievement_query(user.id, year=year).order_by(Achievement.achievement_type)).all()
    doc = Document(); doc.add_heading(f"{year} 年度成果汇总", 0); doc.add_paragraph(f"教师：{user.name}    成果总数：{len(items)}    总积分：{sum(x.score for x in items):g}")
    table = doc.add_table(rows=1, cols=6); table.style = "Table Grid"
    for i, text in enumerate(["序号", "类型", "分类", "成果名称", "级别", "排名"]): table.rows[0].cells[i].text = text
    for i, item in enumerate(items, 1):
        cells = table.add_row().cells
        for j, value in enumerate([i, item.achievement_type, item.category, item.title, item.level or "", item.rank or ""]): cells[j].text = str(value)
    stream = io.BytesIO(); doc.save(stream); stream.seek(0)
    return StreamingResponse(stream, media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document", headers={"Content-Disposition": f"attachment; filename=annual-{year}.docx"})


DEFAULT_TITLE_DIRS = ["基本情况", "学历学位", "现任专业技术资格", "教育教学业绩", "科研项目", "论文成果", "教材成果", "教学竞赛", "指导学生竞赛", "荣誉奖励", "社会服务", "教师培训与继续教育"]


@app.get("/api/v1/title-applications")
def list_apps(user=Depends(current_user), db: Session = Depends(get_db)):
    return db.scalars(select(TitleApplication).where(TitleApplication.user_id == user.id).order_by(TitleApplication.year.desc())).all()


@app.post("/api/v1/title-applications")
def create_app(payload: TitleApplicationIn, user=Depends(current_user), db: Session = Depends(get_db)):
    item = TitleApplication(user_id=user.id, **payload.model_dump()); db.add(item); db.flush()
    db.add_all([TitleApplicationCategory(application_id=item.id, name=name, sort_order=i) for i, name in enumerate(DEFAULT_TITLE_DIRS, 1)])
    db.commit(); db.refresh(item); return item


def owned_application(app_id, user_id, db):
    item = db.scalar(select(TitleApplication).where(TitleApplication.id == app_id, TitleApplication.user_id == user_id))
    if not item: raise HTTPException(404, "职称申报项目不存在")
    return item


@app.get("/api/v1/title-applications/{app_id}")
def app_detail(app_id: int, user=Depends(current_user), db: Session = Depends(get_db)):
    item = owned_application(app_id, user.id, db)
    cats = db.scalars(select(TitleApplicationCategory).where(TitleApplicationCategory.application_id == app_id).order_by(TitleApplicationCategory.sort_order)).all()
    workspace = build_workspace(db, item)
    links = [{"link": {"category_id": row["data"]["category_id"], "achievement_id": row["id"]},
              "achievement": db.get(Achievement, row["id"])} for row in workspace["rows"] if not row["deleted"]]
    rules = db.scalars(select(TitleRequirementRule).where(TitleRequirementRule.application_id == app_id)).all()
    checks = []
    for rule in rules:
        matched = [entry["achievement"] for entry in links if all(
            str(getattr(entry["achievement"], k, "")) == str(v) for k, v in rule.filters.items())]
        actual = sum(a.score for a in matched) if rule.metric == "score" else len(matched)
        ratio = min(actual / rule.target_value, 1) if rule.target_value else 1
        checks.append({"id": rule.id, "name": rule.name, "actual": actual, "target": rule.target_value, "status": "已满足" if ratio >= 1 else ("部分满足" if ratio > 0 else "未满足"), "ratio": ratio, "weight": rule.weight})
    total_weight = sum(x["weight"] for x in checks)
    completeness = round(sum(x["ratio"] * x["weight"] for x in checks) / total_weight * 100) if total_weight else 0
    return {"application": item, "categories": cats, "items": links, "requirements": checks, "completeness": completeness}


@app.post("/api/v1/title-applications/{app_id}/categories")
def add_title_category(app_id: int, payload: TitleCategoryIn, user=Depends(current_user), db: Session = Depends(get_db)):
    owned_application(app_id, user.id, db); item = TitleApplicationCategory(application_id=app_id, **payload.model_dump()); db.add(item); db.commit(); db.refresh(item); return item


@app.post("/api/v1/title-applications/{app_id}/items")
def add_title_item(app_id: int, payload: TitleItemIn, user=Depends(current_user), db: Session = Depends(get_db)):
    owned_application(app_id, user.id, db); owned_achievement(payload.achievement_id, user.id, db)
    cat = db.scalar(select(TitleApplicationCategory).where(TitleApplicationCategory.id == payload.category_id, TitleApplicationCategory.application_id == app_id))
    if not cat: raise HTTPException(400, "材料目录无效")
    item = TitleApplicationItem(application_id=app_id, **payload.model_dump()); db.add(item)
    try: db.commit()
    except Exception as exc: db.rollback(); raise HTTPException(409, "该成果已关联到此目录") from exc
    db.refresh(item); return item


@app.delete("/api/v1/title-applications/{app_id}/items/{item_id}")
def remove_title_item(app_id: int, item_id: int, user=Depends(current_user), db: Session = Depends(get_db)):
    owned_application(app_id, user.id, db); item = db.scalar(select(TitleApplicationItem).where(TitleApplicationItem.id == item_id, TitleApplicationItem.application_id == app_id))
    if not item: raise HTTPException(404, "关联不存在")
    db.delete(item); db.commit(); return {"message": "已移除关联，原成果仍保留"}


@app.post("/api/v1/title-applications/{app_id}/requirements")
def add_requirement(app_id: int, payload: RequirementIn, user=Depends(current_user), db: Session = Depends(get_db)):
    owned_application(app_id, user.id, db); item = TitleRequirementRule(application_id=app_id, **payload.model_dump()); db.add(item); db.commit(); db.refresh(item); return item


@app.get("/api/v1/title-applications/{app_id}/zip")
def title_zip(app_id: int, user=Depends(current_user), db: Session = Depends(get_db)):
    project = owned_application(app_id, user.id, db)
    workspace = build_workspace(db, project)
    storage = StorageService()
    stream = io.BytesIO()
    with zipfile.ZipFile(stream, "w", zipfile.ZIP_DEFLATED) as archive:
        for material in workspace["materials"]:
            if material["available"]:
                archive.write(storage.resolve(material["path"]), f"申报材料/{zip_name(material['category'])}/{material['id']}_{zip_name(material['name'])}")
        for row in workspace["rows"]:
            for file in row["evidence"]:
                if file["available"]:
                    archive.write(storage.resolve(file["path"]), f"成果佐证/{zip_name(row['directory'])}/{row['id']}_{zip_name(row['title'])}/{file['id']}_{zip_name(file['name'])}")
    stream.seek(0)
    return StreamingResponse(stream, media_type="application/zip", headers={"Content-Disposition": f"attachment; filename=title-application-{app_id}.zip"})


def zip_name(value: str) -> str:
    return "".join("_" if char in '<>:"/\\|?*' or ord(char) < 32 else char for char in value).strip(" .")[:100] or "材料"


@app.get("/api/v1/ai-summaries")
def summaries(user=Depends(current_user), db: Session = Depends(get_db)):
    return db.scalars(select(AISummary).where(AISummary.user_id == user.id).order_by(AISummary.created_at.desc())).all()


@app.post("/api/v1/ai-summaries/generate")
async def generate_summary(payload: SummaryGenerateIn, user=Depends(current_user), db: Session = Depends(get_db)):
    query = achievement_query(user.id, start_year=payload.start_year, end_year=payload.end_year)
    if payload.achievement_ids: query = query.where(Achievement.id.in_(payload.achievement_ids))
    if payload.category: query = query.where(or_(Achievement.category == payload.category, Achievement.achievement_type == payload.category))
    if payload.title_application_id:
        owned_application(payload.title_application_id, user.id, db)
        linked = selected_achievement_ids(db, payload.title_application_id)
        query = query.where(Achievement.id.in_(linked))
    items = db.scalars(query.order_by(Achievement.year)).all()
    if not items: raise HTTPException(400, "所选范围内没有真实成果，无法生成总结")
    service = LLMService(); instructions = payload.instructions or ""
    if payload.summary_type == "title": content = await service.generate_title_summary(user, items, instructions)
    elif payload.summary_type == "annual": content = await service.generate_annual_summary(user, items, instructions)
    else: content = await service.generate_category_summary(user, items, instructions)
    prompt = SYSTEM_PROMPT + "\n\n" + service.facts_text(user, items)
    record = AISummary(user_id=user.id, summary_type=payload.summary_type, title_application_id=payload.title_application_id, start_year=payload.start_year, end_year=payload.end_year, achievement_ids=[x.id for x in items], prompt_snapshot=prompt, model=settings.deepseek_model, generated_content=content)
    db.add(record); db.flush(); db.add(AISummaryVersion(summary_id=record.id, version=1, content=content, source="generated")); db.commit(); db.refresh(record); return record


@app.put("/api/v1/ai-summaries/{summary_id}")
def edit_summary(summary_id: int, payload: SummaryEditIn, user=Depends(current_user), db: Session = Depends(get_db)):
    item = db.scalar(select(AISummary).where(AISummary.id == summary_id, AISummary.user_id == user.id))
    if not item: raise HTTPException(404, "总结不存在")
    version = (db.scalar(select(func.max(AISummaryVersion.version)).where(AISummaryVersion.summary_id == summary_id)) or 0) + 1
    item.edited_content = payload.content; db.add(AISummaryVersion(summary_id=summary_id, version=version, content=payload.content, source="edited")); db.commit(); return item


@app.get("/api/v1/ai-summaries/{summary_id}/versions")
def summary_versions(summary_id: int, user=Depends(current_user), db: Session = Depends(get_db)):
    item = db.scalar(select(AISummary).where(AISummary.id == summary_id, AISummary.user_id == user.id))
    if not item: raise HTTPException(404, "总结不存在")
    return db.scalars(select(AISummaryVersion).where(AISummaryVersion.summary_id == summary_id).order_by(AISummaryVersion.version.desc())).all()


@app.post("/api/v1/backups")
def create_backup(user=Depends(require_admin), db: Session = Depends(get_db)):
    if not settings.database_url.startswith("sqlite"):
        raise HTTPException(501, "MySQL 备份请在部署环境配置 mysqldump 适配器")
    timestamp = datetime.now().strftime("%Y%m%d-%H%M%S"); backup_dir = settings.storage_root.resolve() / "backups"; backup_dir.mkdir(parents=True, exist_ok=True)
    output = backup_dir / f"teacher-platform-{timestamp}-{uuid.uuid4().hex}.zip"; source_db = Path(settings.database_url.replace("sqlite:///", "")).resolve()
    with tempfile.TemporaryDirectory() as tmp:
        snapshot = Path(tmp) / "database.db"
        src = sqlite3.connect(source_db)
        dst = sqlite3.connect(snapshot)
        try:
            src.backup(dst)
        finally:
            dst.close()
            src.close()
        manifest = {"version": app.version, "created_at": datetime.utcnow().isoformat(), "database": "database.db"}
        with zipfile.ZipFile(output, "w", zipfile.ZIP_DEFLATED) as archive:
            archive.write(snapshot, "database.db"); archive.writestr("manifest.json", json.dumps(manifest, ensure_ascii=False, indent=2))
            for folder in ("achievements", "applications", "exports"):
                files_root = settings.storage_root.resolve() / folder
                if files_root.exists():
                    for path in files_root.rglob("*"):
                        if path.is_file():
                            archive.write(path, f"storage/{folder}/{path.relative_to(files_root).as_posix()}")
    checksum = StorageService.sha256(output); record = BackupRecord(user_id=user.id, file_name=output.name, file_path=str(output.relative_to(settings.storage_root.resolve()).as_posix()), file_size=output.stat().st_size, checksum=checksum)
    db.add(record); db.commit(); db.refresh(record); return record


@app.get("/api/v1/backups")
def list_backups(user=Depends(require_admin), db: Session = Depends(get_db)):
    return db.scalars(select(BackupRecord).where(BackupRecord.user_id == user.id).order_by(BackupRecord.created_at.desc())).all()
