# 运维手册

## 常用命令

```bash
cd /opt/meal-ticket
docker compose ps
docker compose logs -f backend      # 接口进程
docker compose logs -f worker       # 审批出票进程
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

服务应当有 6 个容器，其中 `backend`、`frontend`、`postgres` 为 healthy：

```bash
docker compose ps --format "table {{.Name}}\t{{.Status}}"
```

## 数据库备份

推荐直接用脚本（自动压缩、自动清理 14 天前的备份）：

```bash
cd /opt/meal-ticket
./scripts/backup_db.sh
```

产物：`/opt/meal-ticket/backups/meal_ticket_<时间戳>.sql.gz`

服务器已配置每日 02:00 自动备份：

```bash
crontab -l
# 0 2 * * * cd /opt/meal-ticket && ./scripts/backup_db.sh >> /opt/meal-ticket/backups/backup.log 2>&1
```

手工导出（不带压缩）：

```bash
docker compose exec -T postgres pg_dump -U meal -d meal_ticket --no-owner > backup-$(date +%F).sql
```

备份文件包含员工信息、饭票记录和系统设置，不要提交到 Git（`backups/` 已在 `.gitignore` 中）。

## 数据库恢复

```bash
cd /opt/meal-ticket
./scripts/restore_db.sh backups/meal_ticket_20261022_142546.sql.gz
```

脚本会自动停 `backend` / `worker`，恢复后重新拉起，避免恢复过程中写入。恢复前建议做好维护公告。

## 数据持久化

PostgreSQL 与 Redis 使用 Docker 命名卷，重建容器不会丢数据：

```bash
docker volume ls | grep meal-ticket
# meal-ticket_postgres_data
# meal-ticket_redis_data
```

注意事项：

- 升级只用 `docker compose up -d --build`，**不要用 `docker compose down -v`**（`-v` 会删除数据卷）。
- `.env` 里有 `COMPOSE_PROJECT_NAME=meal-ticket`，保证换目录部署时仍然复用同一个项目和数据卷。**不要删除这一行**。
- 迁移目录时必须保留 `backups/` 和 `.env`。

## 查看审批回调与出票

回调只做落库并立即返回，出票与图片推送由 `worker` 进程完成，看 worker 日志：

```bash
docker compose logs -f worker
```

审批事件状态在数据库里：

```bash
docker compose exec -T postgres psql -U meal -d meal_ticket -c "
select sp_no, sp_status, processed, attempts, processing,
       left(coalesce(last_error,''), 60) as err,
       left(coalesce(process_result,''), 60) as result
from wecom_approval_events order by id desc limit 20;"
```

字段含义：

| 字段 | 说明 |
| --- | --- |
| `processed=true` | 已处理完成（出票成功或明确不需出票） |
| `attempts` | 已重试次数，达到 5 次标记为「需人工处理」 |
| `processing` | 正在处理中；超过 10 分钟自动回收 |
| `last_error` | 最后一次失败原因（企业微信 errcode 会显示在这里） |

审批详情取不到时系统**不会出票**，而是重试并记录原因，避免生成错误餐次/人数的票。

## 饭票补发与推送状态

饭票记录里每张票都有推送状态：

| 状态 | 含义 |
| --- | --- |
| 已推送 | `push_count > 0`，最近一次推送成功 |
| 失败 | 有 `last_push_error`，鼠标悬浮可看原因 |
| 未记录 | 升级前的历史票，没有推送记录 |

补发方式：

- 单张：饭票记录 → 操作列「补发」
- 批量：勾选后点顶部「批量补发」

规则：已核销、已作废的票会跳过；补发会重新签发二维码，**旧二维码立即失效**。

## 常见问题

### 后台能打开但企业微信收不到二维码

检查：

- 后台系统设置里的 CorpID、AgentID、Secret 是否正确。
- 自建应用是否有发送消息和上传临时素材权限。
- 自建应用可见范围是否包含申请人。
- 审批回调是否真正到达 `/api/wecom/callback/approval`。
- `docker compose logs --tail 50 worker` 是否有推送失败记录；票上「推送」列显示失败时可直接补发。

### 审批通过了但没出票

按顺序排查：

1. `docker compose logs --tail 50 worker` 看是否在重试。
2. 查 `wecom_approval_events` 的 `last_error`：常见是审批详情接口 errcode（如 301026 单号不存在、45009 接口调用超限）或表单缺字段。
3. 若 `process_result` 显示「审批表单缺少字段」，说明审批模板的字段标题与后台「系统设置 → 审批字段名」不一致。
4. 若 `process_result` 显示「需人工处理」，修正后用后台手工制票或补发处理。

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

检查后台“系统设置”的系统时区与容器时区，两处都应为：

```text
Asia/Shanghai
```

容器时区由 `.env` 的 `TZ` 控制，改完需要 `docker compose up -d` 重建容器。

## 升级流程

推荐用脚本，一条命令完成「备份 → 拉代码 → 构建 → 迁移 → 重启 → 健康检查 → 失败自动回滚」：

```bash
cd /opt/meal-ticket
./scripts/deploy.sh            # 默认拉取 main
./scripts/deploy.sh v1.2       # 或指定分支
```

手工步骤（脚本不可用时）：

```bash
cd /opt/meal-ticket
./scripts/backup_db.sh                 # 1. 先备份，失败就停
git pull --ff-only origin main         # 2. 拉代码
docker compose build backend worker frontend   # 3. 构建
docker compose up -d --remove-orphans  # 4. 启动（backend 会自动执行 alembic upgrade head）
curl http://127.0.0.1/api/health       # 5. 健康检查
docker compose logs --tail 30 worker   # 6. 看出票进程
```

升级后确认：

- `docker compose ps` 六个容器都在。
- `alembic_version` 与代码中的迁移版本一致。
- 后台饭票记录能打开，导出 Excel 正常。

## 回滚建议

生产回滚前先保留：

- 当前 Git commit
- 数据库备份（`./scripts/backup_db.sh`）
- `.env`

仅代码回滚：

```bash
cd /opt/meal-ticket
git checkout <previous-commit>
docker compose build backend worker frontend
docker compose up -d
```

涉及数据库迁移时，评估后再降级：

```bash
docker compose exec backend alembic downgrade <previous-revision>
```

数据异常时用备份恢复：

```bash
./scripts/restore_db.sh backups/<备份文件>.sql.gz
```

