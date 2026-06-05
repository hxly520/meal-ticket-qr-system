# 部署记录：172.26.80.101

## 部署结果

部署目录：

```text
/opt/meal-ticket
```

访问地址：

```text
http://172.26.80.101/
http://172.26.80.101:18001/
http://sec-agent.poly-energy.com:18001/
```

默认管理员：

```text
admin / admin123456
```

首次登录后请立即修改默认密码。

## 服务器环境

- 操作系统：CentOS Linux 7
- Docker：26.1.4
- Docker Compose：v2.27.1
- 服务端口：HTTP 80、18001

## 已处理事项

- 将 CentOS 7 yum 源切换到阿里云 CentOS Vault。
- 安装 Docker CE 和 Docker Compose 插件。
- 配置 Docker 镜像加速源，解决服务器直连 Docker Hub 超时问题。
- 部署 PostgreSQL、Redis、后端、前端、Nginx。
- 初始化默认管理员。
- 企业微信参数改为后台“系统设置”页面维护。
- 2026-06-04：新增用餐人数、多选餐别批量生成、申请人姓名/部门读取、企业微信二维码图片消息、权限管理。
- 2026-06-04：数据库迁移到 `0002_multi_ticket_approval`，`meal_tickets` 增加 `diner_count`、`diner_index`，取消 `approval_sp_no` 唯一限制以支持一个审批单生成多张饭票。
- 2026-06-04：企业微信二维码图片改为带票面信息的 PNG，核销端改为移动端扫码工作台，支持摄像头扫码和拍照识别。

## 验收结果

```text
backend: healthy
frontend: healthy
postgres: healthy
redis: running
nginx: running
/api/health: {"status":"ok"}
登录接口: OK
系统设置接口: OK，12 项
饭票列表接口: HTTP 200
权限管理接口: HTTP 200
批量生成接口: 2 人 x 早餐/午餐/晚餐 = 6 张，验证通过，测试数据已清理
二维码图片接口: image/png，验证通过
票面二维码 PNG 生成: 验证通过
前端移动扫码页面: 生产构建通过
```

公网域名检查：

```text
服务器本机 http://127.0.0.1:18001/api/health: HTTP 200
服务器本机 Host=sec-agent.poly-energy.com: HTTP 200
本机访问 http://sec-agent.poly-energy.com:18001/: HTTP 502
```

当前服务容器和宿主机 18001 监听正常，502 更可能来自外部公网代理、NAT、端口映射或域名解析链路。当前解析结果为 `198.18.0.38`，不是服务器内网地址 `172.26.80.101`。

## 常用命令

```bash
cd /opt/meal-ticket
docker compose ps
docker compose logs -f backend
docker compose logs -f nginx
docker compose up -d --build
```

## 下一步

登录后台后进入“系统设置”，维护：

- 系统公网地址
- 企业微信 CorpID
- 企业微信 AgentID
- 企业微信 Secret
- 审批回调 Token
- 审批回调 EncodingAESKey
- 审批模板 ID
- 审批字段映射：用餐日期、餐别、用餐人数、部门、申请原因

企业微信审批回调 URL：

```text
http://sec-agent.poly-energy.com:18001/api/wecom/callback/approval
```

正式对接企业微信建议使用 HTTPS 域名，配置好域名后在后台“系统设置”中修改系统公网地址。
