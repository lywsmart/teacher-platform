from datetime import date
from io import BytesIO
from typing import Literal, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import StreamingResponse
from openpyxl import Workbook
from pydantic import BaseModel, Field
from sqlalchemy import ForeignKey, JSON, String, select
from sqlalchemy.orm import Mapped, Session, mapped_column

from app.core.database import Base, get_db
from app.core.security import current_user
from app.evidence import EvidenceReview, review_info
from app.models import Achievement, AchievementFile, User
from app.project_access import get_project

router = APIRouter(prefix="/api/v1/awards")
Kind = Literal["honor", "teacher_contest", "student_contest", "teaching_award", "research_award"]
# Display name, achievement group, Attachment 18 group, template-specific fields.
TEMPLATES = {
    "honor": ("综合表彰与荣誉", "荣誉奖励", "综合奖励", {"recipient": "表彰对象"}),
    "teacher_contest": ("教师或辅导员职业能力竞赛", "竞赛成果", "教师、辅导员（职业）能力大赛获奖",
                        {"event": "赛项或组别", "participant": "参赛身份"}),
    "student_contest": ("指导学生竞赛获奖", "竞赛成果", "指导学生参加比赛获奖",
                        {"event": "赛项或组别", "student": "获奖学生或团队"}),
    "teaching_award": ("教学成果奖", "教学成果", "教学、科研成果奖",
                       {"work": "教学成果名称", "team_size": "完成人总数"}),
    "research_award": ("科研成果奖", "科研成果", "教学、科研成果奖",
                       {"work": "科研成果名称", "award_family": "奖励类别", "team_size": "完成人总数"}),
}


class AwardDetail(Base):
    __tablename__ = "award_details"
    achievement_id: Mapped[int] = mapped_column(ForeignKey("achievements.id"), primary_key=True)
    template: Mapped[str] = mapped_column(String(32))
    details: Mapped[dict] = mapped_column(JSON)


class AwardApplication(Base):
    __tablename__ = "award_applications"
    application_id: Mapped[int] = mapped_column(ForeignKey("title_applications.id"), primary_key=True)
    achievement_id: Mapped[int] = mapped_column(ForeignKey("award_details.achievement_id"), primary_key=True)
    review_data: Mapped[dict] = mapped_column(JSON)


class AwardInput(BaseModel):
    template: Kind
    title: str = Field(min_length=1, max_length=255)
    achievement_date: date
    organization: str = Field(min_length=1, max_length=255)
    level: str = Field(default="", max_length=64)
    prize: str = Field(default="", max_length=64)
    certificate_no: str = Field(default="", max_length=128)
    scope: Literal["个人", "团队"]
    role: str = Field(default="", max_length=64)
    rank: Optional[int] = Field(default=None, ge=1, le=9999)
    extras: dict[str, str] = Field(default_factory=dict, max_length=4)


class ApplicationUse(BaseModel):
    review_type: Literal["教学为主型", "教学科研并重型", "社会服务型", "思政课教师", "专职辅导员"]
    use_for: Literal["教学（工作）业绩", "科研业绩", "仅计分"]
    clause: str = Field(default="", max_length=500)
    basis: str = Field(default="", max_length=500)
    self_score: Optional[float] = Field(default=None, ge=0, le=100, allow_inf_nan=False)
    missing: str = Field(default="", max_length=500)


def owned_awards(user_id):
    return select(Achievement, AwardDetail).join_from(
        Achievement, AwardDetail, AwardDetail.achievement_id == Achievement.id
    ).where(
        Achievement.user_id == user_id, Achievement.deleted_at.is_(None)
    )


def get_award(award_id, user, db):
    row = db.execute(owned_awards(user.id).where(Achievement.id == award_id)).first()
    if not row:
        raise HTTPException(404, "获奖记录不存在")
    return row


@router.get("/templates")
def templates(user: User = Depends(current_user)):
    return [{"id": key, "name": value[0], "fields": value[3]} for key, value in TEMPLATES.items()]


def award_info(item, detail):
    fields = ("id", "title", "achievement_date", "organization", "level", "role", "rank", "certificate_no")
    return {**{field: getattr(item, field) for field in fields}, "template": detail.template, **detail.details}


@router.get("")
def list_awards(template: Optional[Kind] = None, before: int = Query(0, ge=0),
                user: User = Depends(current_user), db: Session = Depends(get_db)):
    query = owned_awards(user.id)
    if template:
        query = query.where(AwardDetail.template == template)
    if before:
        query = query.where(Achievement.id < before)
    rows = db.execute(query.order_by(Achievement.id.desc()).limit(51)).all()
    return {"items": [award_info(*row) for row in rows[:50]],
            "next": rows[49][0].id if len(rows) > 50 else None}


def save_award(item, detail, payload, db):
    label, group, _, fields = TEMPLATES[payload.template]
    if not payload.title.strip() or not payload.organization.strip():
        raise HTTPException(422, "请填写获奖名称和授奖单位")
    if any(key not in fields or len(value) > 255 for key, value in payload.extras.items()):
        raise HTTPException(422, "模板专用字段无效")
    size = payload.extras.get("team_size", "").strip()
    if size and (not size.isascii() or not size.isdecimal() or not 1 <= int(size) <= 9999):
        raise HTTPException(422, "完成人总数应为 1 至 9999 的整数")
    if size and payload.rank and payload.rank > int(size):
        raise HTTPException(422, "本人排名不能超过完成人总数")
    for key, value in payload.model_dump(include={
        "title", "achievement_date", "organization", "level", "role", "rank", "certificate_no"
    }).items():
        setattr(item, key, value.strip() if isinstance(value, str) else value)
    item.achievement_type, item.category = group, label
    item.year = payload.achievement_date.year
    detail.template = payload.template
    detail.details = payload.model_dump(include={"prize", "scope", "extras"})
    db.add(item)
    db.flush()
    detail.achievement_id = item.id
    db.add(detail)
    db.commit()
    return award_info(item, detail)


@router.post("", status_code=201)
def create_award(payload: AwardInput, user: User = Depends(current_user), db: Session = Depends(get_db)):
    return save_award(Achievement(user_id=user.id), AwardDetail(), payload, db)


@router.put("/{award_id}")
def update_award(award_id: int, payload: AwardInput, user: User = Depends(current_user), db: Session = Depends(get_db)):
    item, detail = get_award(award_id, user, db)
    return save_award(item, detail, payload, db)


@router.get("/{award_id}/evidence")
def list_award_evidence(award_id: int, user: User = Depends(current_user), db: Session = Depends(get_db)):
    item, _ = get_award(award_id, user, db)
    rows = db.execute(select(AchievementFile, EvidenceReview).outerjoin(
        EvidenceReview, (EvidenceReview.kind == "achievement") & (EvidenceReview.file_id == AchievementFile.id)
    ).where(AchievementFile.achievement_id == item.id, AchievementFile.deleted_at.is_(None))).all()
    return [{"id": file.id, "name": file.original_name, **review_info(review)} for file, review in rows]


@router.get("/{award_id}/applications/{project_id}")
def read_use(award_id: int, project_id: int, user: User = Depends(current_user), db: Session = Depends(get_db)):
    from app.project_workspace import build_workspace

    get_award(award_id, user, db)
    result = build_workspace(db, get_project(project_id, user, db))
    row = next((row for row in result["rows"] if row["id"] == award_id), None)
    return {**row["data"], "review_type": result["settings"]["review_type"] or "教学为主型"} if row else None


@router.put("/{award_id}/applications/{project_id}")
def save_use(award_id: int, project_id: int, payload: ApplicationUse,
             user: User = Depends(current_user), db: Session = Depends(get_db)):
    from app.project_workspace import ProjectSettings, SelectionInput, build_workspace, set_selection

    _, award = get_award(award_id, user, db)
    project = get_project(project_id, user, db)
    result = build_workspace(db, project)
    row = next((row for row in result["rows"] if row["id"] == award_id), None)
    data = row["data"] if row else {"score_group": TEMPLATES[award.template][2]}
    settings = db.get(ProjectSettings, project.id)
    if settings and settings.settings["review_type"] != payload.review_type:
        raise HTTPException(409, "请在申报项目中统一修改评审类型")
    if not settings:
        db.merge(ProjectSettings(project_id=project.id, settings={"review_type": payload.review_type, "rule_year": None}))
    selection = SelectionInput(**{**data, **payload.model_dump(exclude={"review_type"})})
    return {**set_selection(db, project, award_id, selection), "review_type": payload.review_type}


@router.delete("/{award_id}/applications/{project_id}", status_code=204)
def remove_use(award_id: int, project_id: int, user: User = Depends(current_user), db: Session = Depends(get_db)):
    from app.project_workspace import remove_item

    get_award(award_id, user, db)
    return remove_item(project_id, award_id, user, db)


def append_text(sheet, values):
    sheet.append(values)
    for cell in sheet[sheet.max_row]:
        if isinstance(cell.value, str):
            cell.data_type = "s"


@router.get("/export")
def export_awards(project_id: Optional[int] = None, user: User = Depends(current_user), db: Session = Depends(get_db)):
    workbook = Workbook()
    summary = workbook.active
    summary.title = "获奖成果汇总"
    append_text(summary, ["类别", "获奖名称", "日期", "授奖单位", "级别", "奖等", "本人角色", "本人排名", "证书编号"])
    for item, detail in db.execute(owned_awards(user.id).order_by(Achievement.year.desc(), Achievement.id.desc())):
        append_text(summary, [TEMPLATES[detail.template][0], item.title, item.achievement_date, item.organization,
                              item.level, detail.details["prize"], item.role, item.rank, item.certificate_no])
    if project_id is not None:
        from app.project_workspace import build_workspace

        project = get_project(project_id, user, db)
        workspace = build_workspace(db, project)
        score = workbook.create_sheet("附件18获奖计分明细")
        conditions = workbook.create_sheet("附件2业绩条件对照")
        append_text(score, ["计分栏目", "获奖名称", "计分依据", "自评得分", "审核得分", "审核签字"])
        append_text(conditions, ["申报项目", "申报职称", "评审类型", "业绩用途", "适用条款", "成果", "级别", "排名", "待补佐证"])
        for row in workspace["rows"]:
            if row["prize"] is None or row["deleted"]:
                continue
            data = row["data"]
            append_text(score, [data["score_group"], row["title"], data["basis"], data["self_score"],
                                data.get("audited_score"), data.get("auditor")])
            append_text(conditions, [project.name, project.target_title, workspace["settings"]["review_type"],
                                     data["use_for"], data["clause"], row["title"], row["level"], row["rank"], data["missing"]])
    for sheet in workbook:
        sheet.freeze_panes = "A2"
        sheet.auto_filter.ref = sheet.dimensions
    output = BytesIO()
    workbook.save(output)
    output.seek(0)
    return StreamingResponse(output, media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                             headers={"Content-Disposition": "attachment; filename=awards.xlsx"})
