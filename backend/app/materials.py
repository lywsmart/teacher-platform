from pathlib import Path

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from fastapi.responses import FileResponse
from sqlalchemy import ForeignKey, String, select
from sqlalchemy.orm import Mapped, Session, mapped_column

from app.core.database import Base, get_db
from app.core.security import current_user
from app.models import TimestampMixin, User
from app.project_access import get_project
from app.services.storage_service import StorageService

router = APIRouter(prefix="/api/v1/title-applications")
MATERIAL_CATEGORIES = (
    "学历学位与任职资历", "教师资格与继续教育", "年度考核与师德师风",
    "双师型与传帮带", "教学工作量与工作效果", "企业实践与社会服务",
    "表彰奖励与竞赛", "教学质量工程项目", "论文著作教材",
    "创新研究与成果转化", "加分计算表及审核材料", "其他证明",
)


class ApplicationMaterial(Base, TimestampMixin):
    __tablename__ = "application_materials"
    id: Mapped[int] = mapped_column(primary_key=True)
    application_id: Mapped[int] = mapped_column(ForeignKey("title_applications.id"), index=True)
    category: Mapped[str] = mapped_column(String(64))
    name: Mapped[str] = mapped_column(String(255))
    path: Mapped[str] = mapped_column(String(512))
    size: Mapped[int] = mapped_column()


def material_info(item: ApplicationMaterial):
    return {"id": item.id, "category": item.category, "name": item.name,
            "size": item.size, "created_at": item.created_at}


@router.get("/{application_id}/materials")
def list_materials(application_id: int, user: User = Depends(current_user), db: Session = Depends(get_db)):
    from app.evidence import EvidenceReview, review_info

    get_project(application_id, user, db)
    items = db.execute(select(ApplicationMaterial, EvidenceReview).outerjoin(
        EvidenceReview, (EvidenceReview.kind == "application") & (EvidenceReview.file_id == ApplicationMaterial.id)
    ).where(
        ApplicationMaterial.application_id == application_id
    ).order_by(ApplicationMaterial.id.desc())).all()
    return {"categories": MATERIAL_CATEGORIES,
            "items": [{**material_info(item), **review_info(review)} for item, review in items]}


@router.post("/{application_id}/materials", status_code=201)
async def upload_material(application_id: int, category: str = Form(...), file: UploadFile = File(...),
                          user: User = Depends(current_user), db: Session = Depends(get_db)):
    get_project(application_id, user, db)
    if category not in MATERIAL_CATEGORIES:
        raise HTTPException(422, "请选择有效的材料类别")
    name = Path((file.filename or "").replace("\\", "/")).name
    if not 1 <= len(name) <= 255 or any(ord(char) < 32 for char in name):
        raise HTTPException(422, "文件名无效")
    storage = StorageService()
    _, relative, size, _ = await storage.save(file, Path("applications") / str(application_id))
    item = ApplicationMaterial(application_id=application_id, category=category, name=name, path=relative, size=size)
    try:
        db.add(item)
        db.commit()
    except Exception:
        db.rollback()
        storage.resolve(relative).unlink(missing_ok=True)
        raise
    return material_info(item)


@router.get("/{application_id}/materials/{material_id}")
def download_material(application_id: int, material_id: int,
                      user: User = Depends(current_user), db: Session = Depends(get_db)):
    get_project(application_id, user, db)
    item = db.get(ApplicationMaterial, material_id)
    if item is None or item.application_id != application_id:
        raise HTTPException(404, "材料不存在")
    path = StorageService().resolve(item.path)
    if not path.is_file():
        raise HTTPException(404, "材料文件不存在")
    return FileResponse(path, filename=item.name, media_type="application/octet-stream",
                        headers={"Cache-Control": "private, no-store", "X-Content-Type-Options": "nosniff"})
