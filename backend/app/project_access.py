from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import DeletedTitleApplication, TitleApplication, User


def active_project():
    return ~select(DeletedTitleApplication.project_id).where(
        DeletedTitleApplication.project_id == TitleApplication.id
    ).exists()


def get_project(project_id: int, user: User, db: Session) -> TitleApplication:
    project = db.scalar(select(TitleApplication).where(
        TitleApplication.id == project_id, TitleApplication.user_id == user.id, active_project(),
    ))
    if project is None:
        raise HTTPException(404, "申报项目不存在")
    return project
