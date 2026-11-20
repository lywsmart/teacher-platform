# 教师综合成果与职称材料管理平台

面向高校教师和系统管理员的职称申报材料管理平台，支持个人成果、电子证明和申报项目归档。AI 仅对已录入的成果进行归纳。

## 2.0 多用户版

- Vue 前端与 FastAPI 后端可独立构建、启动。浏览器通过同源的 `/api/v1` 访问后端。
- 管理员通过「后台管理」开通教师账号、停用或启用账号及重置密码。系统全量备份仅向管理员开放。
- 教师在「职称申报」创建项目，在「申报材料」分类上传和下载文件，也可在申报详情打包导出。材料按项目所有者隔离。
- 分类参考柳州城市职业学院 2026 职称评审条件及加分计算表。申报类别与层级的具体适用条件由教师和审核部门核查，平台存档证明与加分明细。
- 升级时保留 `backend/data` 与 `backend/storage`。首次从旧版升级时，原有首个 `admin` 账号获得管理员角色，原密码保留。所有账号需重新登录。
- 新部署在 `backend/.env` 配置至少 12 位的 `BOOTSTRAP_ADMIN_PASSWORD`，首次启动后可移除。管理员可在右上角修改密码。

## 已实现

- JWT 登录、教师个人档案、未来多用户/角色数据模型
- 统一成果库 CRUD、复制、软删除、组合查询、Excel 导入导出
- 多附件上传、鉴权下载、文件中心
- 年度统计、Word 汇总
- 职称项目、默认/自定义目录、多对多成果关联、自定义条件完整度、材料 ZIP
- 工作台和成果分析图表
- DeepSeek 统一服务、事实结构化、空数据与服务异常处理、总结历史版本
- SQLite 数据库与成果附件完整 ZIP 备份
- MySQL 配置、Docker 部署、健康检查与核心 API 测试

详细设计见 [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md)。

## 本地启动

### 后端

```powershell
cd backend
python -m venv .venv
.venv\Scripts\Activate.ps1
pip install -r requirements.txt
Copy-Item .env.example .env
alembic upgrade head
uvicorn app.main:app --reload
```

接口文档：<http://127.0.0.1:8000/docs>，健康检查：<http://127.0.0.1:8000/api/v1/health>。

### 前端

```powershell
cd frontend
npm install
npm run dev
```

访问 <http://localhost:5173>。新部署使用账号 `admin` 和首次启动时配置的密码。

## DeepSeek 配置

复制 `backend/.env.example` 为 `.env`，填写：

```env
DEEPSEEK_API_KEY=your-key
DEEPSEEK_BASE_URL=https://api.deepseek.com
DEEPSEEK_MODEL=deepseek-chat
```

密钥不会写入数据库或返回前端。未配置时，其他功能仍可正常使用，AI 接口会返回明确提示。

## MySQL 8+

将 `DATABASE_URL` 设置为：

```env
DATABASE_URL=mysql+pymysql://user:password@mysql:3306/teacher_platform?charset=utf8mb4
```

随后执行 `alembic upgrade head`。生产环境请启用 HTTPS、设置强随机 `SECRET_KEY`、限制 CORS 来源，并将备份复制到异地介质。

## 数据目录

```text
backend/storage/
├── achievements/{year}/{achievement_id}/
├── title_review/
├── exports/
├── ai_summary/
└── backups/
```

上传文件使用 UUID 唯一命名，数据库保留原始文件名。请同时备份数据库与 `storage`；系统设置页可创建一体化 ZIP 备份。

## 测试和构建

```powershell
cd backend
pytest -q

cd ../frontend
npm run typecheck
npm run build
```

## 阶段完成记录

- Phase 1：项目、登录、用户模型、布局、Dashboard
- Phase 2：成果 CRUD、分类、查询、Excel
- Phase 3：附件上传下载、文件中心
- Phase 4：职称项目、目录、关联、完整度
- Phase 5：年度、趋势、类型/级别/积分/排名分析
- Phase 6：DeepSeek、三类总结、历史版本、Word
- Phase 7：目录 ZIP、备份、Docker、错误处理、测试、文档
