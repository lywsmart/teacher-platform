from datetime import date, datetime
from typing import Optional
from sqlalchemy import Boolean, Date, DateTime, Float, ForeignKey, Integer, JSON, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.core.database import Base


def now():
    return datetime.utcnow()


class TimestampMixin:
    created_at: Mapped[datetime] = mapped_column(DateTime, default=now)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=now, onupdate=now)


class User(Base, TimestampMixin):
    __tablename__ = "users"
    id: Mapped[int] = mapped_column(primary_key=True)
    username: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    password_hash: Mapped[str] = mapped_column(String(255))
    name: Mapped[str] = mapped_column(String(64), default="教师")
    employee_no: Mapped[Optional[str]] = mapped_column(String(64))
    college: Mapped[Optional[str]] = mapped_column(String(128))
    major: Mapped[Optional[str]] = mapped_column(String(128))
    current_title: Mapped[Optional[str]] = mapped_column(String(64))
    education: Mapped[Optional[str]] = mapped_column(String(64))
    degree: Mapped[Optional[str]] = mapped_column(String(64))
    work_start_date: Mapped[Optional[date]] = mapped_column(Date)
    title_awarded_date: Mapped[Optional[date]] = mapped_column(Date)
    phone: Mapped[Optional[str]] = mapped_column(String(32))
    email: Mapped[Optional[str]] = mapped_column(String(128))
    bio: Mapped[Optional[str]] = mapped_column(Text)
    avatar: Mapped[Optional[str]] = mapped_column(String(255))
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)


class Role(Base, TimestampMixin):
    __tablename__ = "roles"
    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(64), unique=True)


class UserRole(Base, TimestampMixin):
    __tablename__ = "user_roles"
    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    role_id: Mapped[int] = mapped_column(ForeignKey("roles.id"))
    __table_args__ = (UniqueConstraint("user_id", "role_id"),)


class AchievementCategory(Base, TimestampMixin):
    __tablename__ = "achievement_categories"
    id: Mapped[int] = mapped_column(primary_key=True)
    parent_id: Mapped[Optional[int]] = mapped_column(ForeignKey("achievement_categories.id"))
    name: Mapped[str] = mapped_column(String(64))
    code: Mapped[str] = mapped_column(String(64), unique=True)
    sort_order: Mapped[int] = mapped_column(Integer, default=0)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)


class AchievementLevel(Base, TimestampMixin):
    __tablename__ = "achievement_levels"
    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(64), unique=True)
    sort_order: Mapped[int] = mapped_column(Integer, default=0)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)


class Achievement(Base, TimestampMixin):
    __tablename__ = "achievements"
    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    achievement_type: Mapped[str] = mapped_column(String(64), index=True)
    category: Mapped[str] = mapped_column(String(64), index=True)
    title: Mapped[str] = mapped_column(String(255), index=True)
    year: Mapped[int] = mapped_column(Integer, index=True)
    achievement_date: Mapped[Optional[date]] = mapped_column(Date)
    level: Mapped[Optional[str]] = mapped_column(String(64), index=True)
    rank: Mapped[Optional[int]] = mapped_column(Integer)
    role: Mapped[Optional[str]] = mapped_column(String(64))
    organization: Mapped[Optional[str]] = mapped_column(String(255))
    certificate_no: Mapped[Optional[str]] = mapped_column(String(128))
    score: Mapped[float] = mapped_column(Float, default=0)
    description: Mapped[Optional[str]] = mapped_column(Text)
    remark: Mapped[Optional[str]] = mapped_column(Text)
    deleted_at: Mapped[Optional[datetime]] = mapped_column(DateTime, index=True)
    files: Mapped[list["AchievementFile"]] = relationship(back_populates="achievement")


class AchievementFile(Base, TimestampMixin):
    __tablename__ = "achievement_files"
    id: Mapped[int] = mapped_column(primary_key=True)
    achievement_id: Mapped[int] = mapped_column(ForeignKey("achievements.id"), index=True)
    original_name: Mapped[str] = mapped_column(String(255))
    stored_name: Mapped[str] = mapped_column(String(255), unique=True)
    file_path: Mapped[str] = mapped_column(String(512))
    file_type: Mapped[str] = mapped_column(String(32))
    file_size: Mapped[int] = mapped_column(Integer)
    file_category: Mapped[str] = mapped_column(String(64), default="其他")
    uploaded_at: Mapped[datetime] = mapped_column(DateTime, default=now)
    deleted_at: Mapped[Optional[datetime]] = mapped_column(DateTime)
    achievement: Mapped[Achievement] = relationship(back_populates="files")


class AchievementUploadReceipt(Base):
    __tablename__ = "achievement_upload_receipts"
    achievement_id: Mapped[int] = mapped_column(ForeignKey("achievements.id"), primary_key=True)
    upload_id: Mapped[str] = mapped_column(String(36), primary_key=True)
    file_id: Mapped[int] = mapped_column(ForeignKey("achievement_files.id"))


class AchievementScoreRule(Base, TimestampMixin):
    __tablename__ = "achievement_score_rules"
    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    name: Mapped[str] = mapped_column(String(128))
    conditions: Mapped[dict] = mapped_column(JSON, default=dict)
    score: Mapped[float] = mapped_column(Float)
    priority: Mapped[int] = mapped_column(Integer, default=0)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)


class TitleApplication(Base, TimestampMixin):
    __tablename__ = "title_applications"
    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    name: Mapped[str] = mapped_column(String(128))
    year: Mapped[int] = mapped_column(Integer)
    target_title: Mapped[str] = mapped_column(String(64))
    status: Mapped[str] = mapped_column(String(32), default="准备中")
    start_date: Mapped[Optional[date]] = mapped_column(Date)
    remark: Mapped[Optional[str]] = mapped_column(Text)


class TitleApplicationCategory(Base, TimestampMixin):
    __tablename__ = "title_application_categories"
    id: Mapped[int] = mapped_column(primary_key=True)
    application_id: Mapped[int] = mapped_column(ForeignKey("title_applications.id"), index=True)
    name: Mapped[str] = mapped_column(String(128))
    sort_order: Mapped[int] = mapped_column(Integer, default=0)


class TitleApplicationItem(Base, TimestampMixin):
    __tablename__ = "title_application_items"
    id: Mapped[int] = mapped_column(primary_key=True)
    application_id: Mapped[int] = mapped_column(ForeignKey("title_applications.id"), index=True)
    category_id: Mapped[int] = mapped_column(ForeignKey("title_application_categories.id"))
    achievement_id: Mapped[int] = mapped_column(ForeignKey("achievements.id"), index=True)
    sort_order: Mapped[int] = mapped_column(Integer, default=0)
    note: Mapped[Optional[str]] = mapped_column(Text)
    __table_args__ = (UniqueConstraint("application_id", "category_id", "achievement_id"),)


class TitleRequirementRule(Base, TimestampMixin):
    __tablename__ = "title_requirement_rules"
    id: Mapped[int] = mapped_column(primary_key=True)
    application_id: Mapped[int] = mapped_column(ForeignKey("title_applications.id"), index=True)
    name: Mapped[str] = mapped_column(String(128))
    filters: Mapped[dict] = mapped_column(JSON, default=dict)
    metric: Mapped[str] = mapped_column(String(32), default="count")
    operator: Mapped[str] = mapped_column(String(8), default=">=")
    target_value: Mapped[float] = mapped_column(Float)
    weight: Mapped[float] = mapped_column(Float, default=1)


class AIPromptTemplate(Base, TimestampMixin):
    __tablename__ = "ai_prompt_templates"
    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(128))
    summary_type: Mapped[str] = mapped_column(String(64), index=True)
    system_prompt: Mapped[str] = mapped_column(Text)
    user_prompt_template: Mapped[str] = mapped_column(Text)
    version: Mapped[int] = mapped_column(Integer, default=1)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)


class AISummary(Base, TimestampMixin):
    __tablename__ = "ai_summaries"
    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    summary_type: Mapped[str] = mapped_column(String(64))
    title_application_id: Mapped[Optional[int]] = mapped_column(ForeignKey("title_applications.id"))
    start_year: Mapped[Optional[int]] = mapped_column(Integer)
    end_year: Mapped[Optional[int]] = mapped_column(Integer)
    achievement_ids: Mapped[list] = mapped_column(JSON, default=list)
    prompt_snapshot: Mapped[str] = mapped_column(Text)
    model: Mapped[str] = mapped_column(String(128))
    generated_content: Mapped[str] = mapped_column(Text)
    edited_content: Mapped[Optional[str]] = mapped_column(Text)


class AISummaryVersion(Base, TimestampMixin):
    __tablename__ = "ai_summary_versions"
    id: Mapped[int] = mapped_column(primary_key=True)
    summary_id: Mapped[int] = mapped_column(ForeignKey("ai_summaries.id"), index=True)
    version: Mapped[int] = mapped_column(Integer)
    content: Mapped[str] = mapped_column(Text)
    source: Mapped[str] = mapped_column(String(32), default="generated")


class SystemSetting(Base, TimestampMixin):
    __tablename__ = "system_settings"
    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    key: Mapped[str] = mapped_column(String(128))
    value: Mapped[dict] = mapped_column(JSON, default=dict)
    __table_args__ = (UniqueConstraint("user_id", "key"),)


class BackupRecord(Base, TimestampMixin):
    __tablename__ = "backup_records"
    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    file_name: Mapped[str] = mapped_column(String(255))
    file_path: Mapped[str] = mapped_column(String(512))
    file_size: Mapped[int] = mapped_column(Integer, default=0)
    checksum: Mapped[str] = mapped_column(String(64))
    status: Mapped[str] = mapped_column(String(32), default="completed")
    note: Mapped[Optional[str]] = mapped_column(Text)
