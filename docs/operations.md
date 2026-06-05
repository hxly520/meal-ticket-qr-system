# 运维手册

## 常用命令

```bash
cd /opt/meal-ticket
docker compose ps
docker compose logs -f backend
docker compose logs -f nginx
docker compose up -d --build
```

## 健康检查

```bash
curl http://127.0.0.1/api/health
curl http://127.0.0.1:18001/api/health
```

正常返回：

```json
{"status":"ok"}
```

## 数据库备份

```bash
cd /opt/meal-ticket
docker compose exec postgres pg_dump -U meal meal_ticket > backup-$(date +%F).sql
```

备份文件可能包含员工信息、饭票记录和系统设置，不要提交到 Git。

## 数据库恢复

```bash
cd /opt/meal-ticket
docker compose exec -T postgres psql -U meal -d meal_ticket < backup.sql
```

恢复前建议先停止业务入口或做好维护公告。

## 查看企业微信回调处理

```bash
docker compose logs -f backend
```

也可进入数据库查看审批事件：

```bash
docker compose exec postgres psql -U meal -d meal_ticket
select sp_no, sp_status, processed, process_result, created_at from wecom_approval_events order by id desc limit 20;
```

## 常见问题

### 后台能打开但企业微信收不到二维码

检查：

- 后台系统设置里的 CorpID、AgentID、Secret 是否正确。
- 自建应用是否有发送消息和上传临时素材权限。
- 自建应用可见范围是否包含申请人。
- 审批回调是否真正到达 `/api/wecom/callback/approval`。

### 部门显示为部门ID

检查：

- 自建应用是否有通讯录部门读取权限。
- 后台“部门ID映射”是否配置。

示例：

```text
28=IT部
```

### 核销失败

系统会在移动端显示具体原因。常见原因：

- 饭票已核销，不能重复核销。
- 饭票已过期，不能核销。
- 饭票已作废，不能核销。
- 饭票用餐日期不是当天。
- 当前时间不在对应餐别核销时间段内。

### 时间显示不对

检查后台“系统设置”的系统时区，默认应为：

```text
Asia/Shanghai
```

## 升级流程

1. 备份数据库。
2. 同步新代码到服务器。
3. 执行 `docker compose up -d --build`。
4. 检查 `/api/health`。
5. 检查后台页面、饭票列表和核销流程。

## 回滚建议

生产回滚前先保留：

- 当前 Git commit
- 数据库备份
- `.env`

如仅代码回滚：

```bash
git checkout <previous-commit>
docker compose up -d --build
```

如涉及数据库迁移，需要先评估 Alembic downgrade 是否安全。
