# 贡献指南

欢迎基于本项目进行二次开发。提交改动前请先阅读文档：

- [架构设计](docs/architecture.md)
- [二次开发指南](docs/development.md)
- [配置项说明](docs/configuration.md)

## 开发流程

1. 从 `main` 创建功能分支。
2. 保持改动聚焦，避免同时混入无关格式化。
3. 数据库结构变更必须新增 Alembic 迁移。
4. 前端交互变更需兼顾桌面端和移动端。
5. 提交前运行检查命令。

```bash
python3 -m compileall backend/app
node --check frontend/src/main.js
cd frontend && npm run build
```

## 提交信息

建议使用简洁动词开头：

```text
Add meal window validation
Fix mobile verification layout
Update WeCom approval parsing
```

## 安全要求

不要提交：

- `.env`
- 真实企业微信 Secret
- GitHub Token
- 服务器密码
- 数据库备份
- 证书私钥
- 员工真实敏感数据

## 代码风格

- 后端优先保持业务逻辑在 `services`，路由层只做请求/响应编排。
- 前端保持操作工具风格，重点是清晰、稳定、可扫读。
- 失败提示必须能让一线使用者知道下一步该怎么处理。
