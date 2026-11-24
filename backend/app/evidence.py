from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field
from sqlalchemy import ForeignKey, String, select
from sqlalchemy.orm import Mapped, Session, mapped_column

from app.admin import require_admin
from app.core.database import Base, get_db
from app.materials import ApplicationMaterial
from app.models import Achievement, AchievementFile, TimestampMixin, TitleApplication, User
from app.project_access import active_project
from app.services.storage_service import StorageService

Kind = Literal["achievement", "application"]
ReviewStatus = Literal["待审核", "通过", "需补充"]
router = APIRouter(prefix="/api/v1/admin/evidence", dependencies=[Depends(require_admin)])


class EvidenceReview(Base, TimestampMixin):
    __tablename__ = "evidence_reviews"
    kind: Mapped[str] = mapped_column(String(16), primary_key=True)
    file_id: Mapped[int] = mapped_column(primary_key=True)
    status: Mapped[str] = mapped_column(String(16))
    note: Mapped[str] = mapped_column(String(500))
    reviewer_id: Mapped[int] = mapped_column(ForeignKey("users.id"))


class ReviewInput(BaseModel):
    status: ReviewStatus
    note: str = Field(default="", max_length=500)


def evidence_query(kind: Kind):
    if kind == "application":
        return (select(ApplicationMaterial, TitleApplication, User)
                .join(TitleApplication, ApplicationMaterial.application_id == TitleApplication.id)
                .join(User, TitleApplication.user_id == User.id)
                .where(active_project())), ApplicationMaterial
    return (select(AchievementFile, Achievement, User)
            .join(Achievement, AchievementFile.achievement_id == Achievement.id)
            .join(User, Achievement.user_id == User.id)
            .where(AchievementFile.deleted_at.is_(None), Achievement.deleted_at.is_(None))), AchievementFile


def review_info(review):
    return {"status": review.status, "note": review.note, "reviewed_at": review.updated_at} if review else {
        "status": "待审核", "note": "", "reviewed_at": None
    }


@router.get("")
def list_evidence(kind: Kind = "achievement", before: int = Query(0, ge=0),
                  owner: str = Query("", max_length=64), db: Session = Depends(get_db)):
    query, model = evidence_query(kind)
    if owner.strip():
        query = query.where(User.username == owner.strip().lower())
    if before:
        query = query.where(model.id < before)
    rows = db.execute(query.order_by(model.id.desc()).limit(51)).all()
    reviews = {item.file_id: item for item in db.scalars(select(EvidenceReview).where(
        EvidenceReview.kind == kind, EvidenceReview.file_id.in_([row[0].id for row in rows])
    ))}
    items = []
    for file, parent, user in rows[:50]:
        achievement = kind == "achievement"
        items.append({
            "id": file.id, "kind": kind, "filename": file.original_name if achievement else file.name,
            "category": file.file_category if achievement else file.category,
            "parent": parent.title if achievement else parent.name,
            "username": user.username, "teacher": user.name, "uploaded_at": file.created_at,
            **review_info(reviews.get(file.id)),
        })
    return {"items": items, "next": rows[49][0].id if len(rows) > 50 else None}


def find_file(kind, file_id, db):
    query, model = evidence_query(kind)
    row = db.execute(query.where(model.id == file_id)).first()
    if row is None:
        raise HTTPException(404, "佐证材料不存在")
    return row[0]


@router.get("/{kind}/{file_id}/download")
def download_evidence(kind: Kind, file_id: int, db: Session = Depends(get_db)):
    file = find_file(kind, file_id, db)
    path = StorageService().resolve(file.file_path if kind == "achievement" else file.path)
    if not path.is_file():
        raise HTTPException(404, "佐证文件不存在")
    return FileResponse(path, filename=file.original_name if kind == "achievement" else file.name,
                        media_type="application/octet-stream",
                        headers={"Cache-Control": "private, no-store", "X-Content-Type-Options": "nosniff"})


@router.put("/{kind}/{file_id}")
def review_evidence(kind: Kind, file_id: int, payload: ReviewInput,
                    reviewer: User = Depends(require_admin), db: Session = Depends(get_db)):
    find_file(kind, file_id, db)
    if payload.status == "需补充" and not payload.note.strip():
        raise HTTPException(422, "请填写需要补充的材料")
    review = db.get(EvidenceReview, (kind, file_id))
    if review is None:
        review = EvidenceReview(kind=kind, file_id=file_id)
        db.add(review)
    review.status = payload.status
    review.note = payload.note.strip()
    review.reviewer_id = reviewer.id
    db.commit()
    return review_info(review)
