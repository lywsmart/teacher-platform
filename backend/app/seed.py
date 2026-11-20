from sqlalchemy import select
from sqlalchemy.orm import Session
from app.models import AchievementCategory, AchievementLevel, AIPromptTemplate, Role, User, UserRole
from app.core.security import hash_password
from app.core.config import get_settings
from app.services.llm_service import SYSTEM_PROMPT


CATEGORIES = {
    "教学成果": ["课程建设", "专业建设", "教学改革", "教材建设", "教学成果奖", "教学比赛", "实训基地建设", "资源库建设"],
    "科研成果": ["论文", "课题", "专利", "软件著作权", "教材", "科研获奖", "横向项目"],
    "竞赛成果": ["教师竞赛", "指导学生竞赛", "创新创业竞赛", "技能竞赛"],
    "荣誉奖励": ["优秀教师", "优秀班主任", "先进个人", "优秀党员", "其他荣誉"],
    "社会服务": ["企业培训", "社会培训", "技术服务", "企业项目", "技术咨询"],
    "教师发展": ["教师培训", "企业实践", "挂职锻炼", "访学", "继续教育"],
    "其他成果": ["其他"],
}


def seed(db: Session):
    for role_name in ("admin", "teacher"):
        if not db.scalar(select(Role).where(Role.name == role_name)):
            db.add(Role(name=role_name))
    db.flush()
    admin_role = db.scalar(select(Role).where(Role.name == "admin"))
    if not db.scalar(select(UserRole.id).where(UserRole.role_id == admin_role.id).limit(1)):
        user = db.scalar(select(User).where(User.username == "admin"))
        if user and user.id != db.scalar(select(User.id).order_by(User.id).limit(1)):
            raise RuntimeError("无法识别旧版管理员，请检查用户角色配置")
        if user is None:
            password = get_settings().bootstrap_admin_password
            if len(password) < 12:
                raise RuntimeError("首次启动请设置至少 12 位的 BOOTSTRAP_ADMIN_PASSWORD")
            user = User(username="admin", password_hash=hash_password(password), name="系统管理员")
            db.add(user)
            db.flush()
        db.add(UserRole(user_id=user.id, role_id=admin_role.id))
    if not db.scalar(select(AchievementCategory).limit(1)):
        order = 0
        for parent_name, children in CATEGORIES.items():
            parent = AchievementCategory(name=parent_name, code=f"type_{order}", sort_order=order)
            db.add(parent); db.flush()
            for child_order, child in enumerate(children):
                db.add(AchievementCategory(parent_id=parent.id, name=child, code=f"cat_{order}_{child_order}", sort_order=child_order))
            order += 1
    if not db.scalar(select(AchievementLevel).limit(1)):
        db.add_all([AchievementLevel(name=name, sort_order=i) for i, name in enumerate(["国家级", "省部级", "市厅级", "校级", "院级", "其他"])] )
    if not db.scalar(select(AIPromptTemplate).limit(1)):
        db.add(AIPromptTemplate(name="成果总结默认模板", summary_type="annual", system_prompt=SYSTEM_PROMPT, user_prompt_template="请根据事实数据生成正式总结。"))
    db.commit()
