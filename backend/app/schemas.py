from datetime import date, datetime
from typing import Any, Optional
from pydantic import BaseModel, ConfigDict, Field


class ORMModel(BaseModel):
    model_config = ConfigDict(from_attributes=True)


class LoginIn(BaseModel):
    username: str
    password: str


class ProfileUpdate(BaseModel):
    name: str = Field(min_length=1, max_length=64)
    employee_no: Optional[str] = None
    college: Optional[str] = None
    major: Optional[str] = None
    current_title: Optional[str] = None
    education: Optional[str] = None
    degree: Optional[str] = None
    work_start_date: Optional[date] = None
    title_awarded_date: Optional[date] = None
    phone: Optional[str] = None
    email: Optional[str] = None
    bio: Optional[str] = None


class AchievementIn(BaseModel):
    achievement_type: str
    category: str
    title: str = Field(min_length=1, max_length=255)
    year: int = Field(ge=1950, le=2200)
    achievement_date: Optional[date] = None
    level: Optional[str] = None
    rank: Optional[int] = Field(default=None, ge=1)
    role: Optional[str] = None
    organization: Optional[str] = None
    certificate_no: Optional[str] = None
    score: float = 0
    description: Optional[str] = None
    remark: Optional[str] = None


class AchievementOut(AchievementIn, ORMModel):
    id: int
    user_id: int
    created_at: datetime
    updated_at: datetime


class TitleApplicationIn(BaseModel):
    name: str
    year: int
    target_title: str
    status: str = "准备中"
    start_date: Optional[date] = None
    remark: Optional[str] = None


class TitleCategoryIn(BaseModel):
    name: str
    sort_order: int = 0


class TitleItemIn(BaseModel):
    category_id: int
    achievement_id: int
    sort_order: int = 0
    note: Optional[str] = None


class RequirementIn(BaseModel):
    name: str
    filters: dict[str, Any] = {}
    metric: str = "count"
    operator: str = ">="
    target_value: float
    weight: float = 1


class SummaryGenerateIn(BaseModel):
    summary_type: str
    start_year: Optional[int] = None
    end_year: Optional[int] = None
    achievement_ids: Optional[list[int]] = None
    title_application_id: Optional[int] = None
    category: Optional[str] = None
    instructions: Optional[str] = None


class SummaryEditIn(BaseModel):
    content: str = Field(min_length=1)
