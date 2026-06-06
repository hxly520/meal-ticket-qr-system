# 饭票二维码核销系统

饭票二维码核销系统用于处理员工忘带饭卡、来访人员临时用餐等场景。系统支持企业微信审批通过后自动生成饭票二维码图片，饭堂人员扫码后按权限、用餐日期和餐别时间段完成核销，行政人员可在后台查询、作废和导出核销记录。

## 功能概览

- 企业微信审批通过后自动生成饭票。
- 支持用餐人数 x 多选餐别批量生成，一人一餐一码。
- 饭票二维码图片包含公司名称、用餐日期、餐别、申请人、部门、饭票编号和版权说明。
- 手机相机、微信或企业微信扫一扫后自动打开核销页面。
- 核销时校验饭票状态、用餐日期、餐别时间段和过期时间。
- 后台支持饭票分页查询、按日期/状态筛选、批量作废、Excel 导出。
- 角色权限：`admin`、`hr`、`verifier`、`auditor`。
- 企业微信参数、审批字段、部门映射、核销时间段均可在后台设置。
- 支持企业微信用户与万傲瑞达饭卡用户同步、绑定和余额展示。
- 支持同步记录、访问记录、操作记录分离审计。
- Docker Compose 一键部署 PostgreSQL、Redis、FastAPI、Vue 和 Nginx。

## 技术栈

- 后端：Python 3.12、FastAPI、SQLAlchemy、Alembic、PostgreSQL、Redis
- 前端：Vue 3、Element Plus、Vite、Lucide Icons
- 集成：企业微信审批回调、审批详情、应用消息、临时素材图片、万傲瑞达离线消费余额
- 部署：Docker Compose、Nginx

## 快速开始

```bash
cp .env.example .env
docker compose up -d --build
```

首次启动会创建默认管理员账号：

```text
用户名：admin
密码：使用 .env 中的 INITIAL_ADMIN_PASSWORD；留空时查看后端容器日志中的随机密码
```

上线前请设置新的 `JWT_SECRET_KEY`、数据库密码和后台系统设置；首次登录后请立即修改管理员密码。

## 文档导航

- [架构设计](docs/architecture.md)
- [部署与企业微信联调](docs/production-setup.md)
- [后台操作手册](docs/user-guide.md)
- [配置项说明](docs/configuration.md)
- [万傲瑞达 V6000 饭卡余额对接方案](docs/wanoa-v6000-integration-plan.md)
- [万傲瑞达 V6600 API 文档探查记录](docs/wanoa-v6600-api-discovery.md)
- [界面升级原型与前端架构优化方案](docs/ui-refresh-prototype.md)
- [二次开发指南](docs/development.md)
- [运维手册](docs/operations.md)
- [GitHub 自动建仓与推送](docs/github-publish.md)

## 开发与验证

本地前端构建需要 Node.js `20.19+` 或 `22.12+`；Docker 构建使用 `node:22-alpine`。

```bash
python3 -m compileall backend/app
node --check frontend/src/main.js
cd frontend && npm run build
```

远程生产环境同步：

```bash
SSH_HOST=your-server SSH_USER=root REMOTE_DIR=/opt/meal-ticket ./deploy/remote_deploy.sh
```

建议使用临时 SSH key、受限部署账号或堡垒机账号联调，不建议在聊天、文档或脚本中保存长期有效的服务器密码。

如需记录单台生产服务器的部署过程，建议在私有运维知识库或本地 `docs/deployment-record-*.md` 文件中维护；此类文件包含内网地址、域名或排障信息时不建议提交到开源仓库。

## 安全提示

- `.env`、证书、数据库备份、真实企业微信 Secret、GitHub Token 不应提交到仓库。
- GitHub Token 请存入系统钥匙串或 GitHub CLI，不要写入脚本、README 或 `.git/config`。
- 生产环境建议启用 HTTPS。
- 默认管理员只用于初始化，上线后必须修改。

## 许可证

本项目使用 MIT License。详见 [LICENSE](LICENSE)。
