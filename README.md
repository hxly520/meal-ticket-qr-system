# 饭票二维码核销系统

Python + FastAPI + Vue + PostgreSQL 的饭票二维码核销系统，支持 Docker Compose 部署、后台饭票管理、扫码核销、企业微信审批通过自动生成饭票、行政导出核实表。

## 已实现能力

- 后台登录与角色权限：`admin`、`hr`、`verifier`、`auditor`
- 单张饭票生成、批量生成 API
- 一次性二维码 token，数据库只保存 token hash
- 核销权限控制与重复核销防护
- 饭票作废、列表查询、Excel 导出
- 企业微信审批回调验签、AES 解密、明文 JSON 联调入口
- 系统设置页面维护企业微信参数、审批字段映射、系统公网地址和时区
- Docker Compose 生产部署

## 快速部署

```bash
cp .env.example .env
docker compose up -d --build
```

远程生产环境同步：

```bash
SSH_HOST=your-server SSH_USER=root REMOTE_DIR=/opt/meal-ticket ./deploy/remote_deploy.sh
```

建议使用临时 SSH key 或受限部署账号联调，不建议在聊天中直接发送长期有效的服务器密码。

默认账号：

```text
admin / admin123456
```

生产部署与企业微信配置见 [docs/production-setup.md](docs/production-setup.md)，后台使用见 [docs/user-guide.md](docs/user-guide.md)。

当前服务器部署记录见 [docs/deployment-record-172.26.80.101.md](docs/deployment-record-172.26.80.101.md)。
