# 二次开发指南

## 环境要求

- Python 3.12+
- Node.js 20+
- Docker 与 Docker Compose
- PostgreSQL 16，推荐使用 Compose 内置服务

## 本地运行

完整服务推荐直接用 Docker Compose：

```bash
cp .env.example .env
docker compose up -d --build
```

后端单独检查：

```bash
python3 -m compileall backend/app
```

前端单独检查：

```bash
node --check frontend/src/main.js
cd frontend
npm install
npm run build
```

## 后端开发

安装开发依赖：

```bash
cd backend
python3 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
```

常用命令：

```bash
ruff check app
alembic revision --autogenerate -m "describe change"
alembic upgrade head
```

新增接口建议放置：

- 路由：`backend/app/api`
- Schema：`backend/app/schemas`
- 业务逻辑：`backend/app/services`
- 模型：`backend/app/models`

## 前端开发

前端目前是单文件 Vue 应用，主要代码在：

```text
frontend/src/main.js
frontend/src/style.css
```

如继续扩大功能，建议逐步拆分：

```text
frontend/src/api/
frontend/src/components/
frontend/src/views/
frontend/src/stores/
```

保持原则：

- 后台页面偏生产工具风格，减少装饰，强调信息密度和可读性。
- 移动端核销页优先保证扫码后结果清晰。
- 按角色显示菜单和操作按钮，不仅依赖后端拦截。

## 数据库迁移

模型变更后新增 Alembic 迁移：

```bash
cd backend
alembic revision --autogenerate -m "add field"
alembic upgrade head
```

迁移文件提交到：

```text
backend/alembic/versions
```

生产容器启动时会自动执行 `alembic upgrade head`。

## 企业微信二开

企业微信核心逻辑在：

```text
backend/app/services/wecom.py
backend/app/api/wecom.py
backend/app/utils/wecom_crypto.py
```

可扩展方向：

- 支持更多审批字段类型。
- 根据不同审批模板生成不同票种。
- 失败消息回推给申请人或管理员。
- 增加企业微信通讯录部门缓存。

## 核销规则二开

核销规则集中在：

```text
backend/app/services/tickets.py
```

当前规则：

1. 票据必须存在。
2. 状态必须是 `unused`。
3. 用餐日期必须是当天。
4. 当前时间必须在对应餐别时间段。
5. 过期票不可核销。
6. 原子更新防止重复核销。

新增规则时建议返回明确中文失败原因，并写入 `verification_logs.reason`。

## 提交前检查

```bash
python3 -m compileall backend/app
node --check frontend/src/main.js
cd frontend && npm run build
git status --short
```

确认不要提交：

- `.env`
- 真实证书或私钥
- 数据库备份
- `node_modules`
- `frontend/dist`
- `__pycache__`
- GitHub Token、企业微信 Secret、服务器密码
