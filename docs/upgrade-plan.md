# 饭票系统升级方案 v1.1

> 目标：修复审批回调错票问题，新增补发与申请原因，补齐数据持久化与 git 版本化部署。
> 状态：代码已完成并本地验证通过（6 项回归测试 + 前端构建 + 迁移 SQL 生成），**尚未动生产**。

---

## 一、变更总览

| # | 模块 | 改了什么 | 解决的问题 |
|---|---|---|---|
| 1 | 后台饭票 | 新增「补发」单条 + 批量补发 | 推送失败时人工补推 |
| 2 | 饭票字段 | 新增「申请原因」并贯通列表/导出 | 行政导出缺审批原因 |
| 3 | 导出 | 增加申请原因、推送状态、推送时间、推送次数 | 可追踪推送结果 |
| 4 | 审批出票 | 详情取不到就失败重试，不再兜底出票 | 本次 202610210018 错票的根因 |
| 5 | 回调 | 只落库立即返回，出票交给独立 worker | 回调 14~18 秒超时被企业微信重试 |
| 6 | 报文 | 重试合并而不是覆盖 | 重试会冲掉已解析的表单字段 |
| 7 | 幂等 | 唯一索引 + 事件领取锁 | 并发/重复回调重复出票 |
| 8 | 事务 | 整套票一次提交 | 中途失败留下「半套票」 |
| 9 | 撤销 | 审批撤销/驳回时作废未核销票 | 撤销后票仍可用 |
| 10 | 性能 | access_token 进程内缓存 | 单次回调十几次取 token，易被限流 |
| 11 | 时区 | 容器 TZ=Asia/Shanghai | UTC 下北京时间 0-8 点日期取错 |
| 12 | 部署 | git 化 + 每日备份 + 一键部署/回滚 | 更新无版本、数据无备份 |

改动规模：17 个文件，+1152 / -138 行，已提交为 `5b6d8e3`、`eaa6b28`。

---

## 二、功能改动明细

### 2.1 补发（你要的第 1 项）

**入口**
- 饭票记录 → 每行操作列：`补发`（在 `作废` 左边）
- 顶部批量操作区：`批量补发`

**规则**

| 饭票状态 | 补发 |
|---|---|
| 未核销 unused | ✅ 允许 |
| 已核销 used | ❌ 跳过（提示「已核销或已作废，跳过」） |
| 已作废 void | ❌ 跳过 |
| 已过期 expired | ✅ 允许（仍可补发给本人确认，但核销时会按过期拦截） |

**执行动作**
1. 重新签发二维码 token（**旧二维码立即失效**，防止一张票两个有效码）
2. 生成饭票卡片图 → 上传企业微信临时素材 → 图片消息推给申请人
3. 成功：`push_count+1`、`last_push_at` 更新、清空 `last_push_error`
4. 失败：保留旧 token（不影响已送达的旧码），写入 `last_push_error`，接口返回 502 + 原因

**接口**

```
POST /api/tickets/{id}/resend      单条补发   → TicketOut
POST /api/tickets/resend-batch     批量补发   → {sent, failed, skipped, missing, items[]}
```

权限 `admin` / `hr`；每次补发写 `audit_logs`（`ticket.resend` / `ticket.resend_batch`）。

### 2.2 申请原因（你要的第 2 项）

- 新字段 `meal_tickets.apply_reason`（varchar 500）
- 取值：审批表单里字段名为「申请原因」的控件（沿用可配置的 `wecom_field_reason`）
- 展示：饭票记录表格新增「申请原因」列，超长省略 + 悬浮看全文
- 导出：Excel 新增「申请原因」列
- **历史数据回填**：迁移脚本从 `wecom_approval_events.raw_payload->>'申请原因'` 回填到已有饭票

### 2.3 推送状态可视化

原有的问题是：推送失败只写在事件表的一句话里，事后查不到。现在每张票自带：

| 列 | 含义 |
|---|---|
| 推送 | `已推送` / `失败` / `未记录`（历史数据） |
| 最近推送时间 | 最后一次成功推送 |
| 推送次数 | 含补发 |

行政可以直接按「失败」筛出来批量补发。

---

## 三、稳定性修复（对应审计报告）

### 3.1 不再兜底出票（P0，本次事故根因）

改前：
```python
except Exception as exc:
    event.process_result = f"审批详情获取失败，使用回调字段生成: {exc}"   # 然后继续出票
...
meal_type_value = ... or "lunch"        # 默认午餐
diner_count = ... or 1                  # 默认 1 人
meal_date = ... else date.today()       # 默认今天
```

改后：取不到详情 → 抛 `ApprovalError` → 不出票 → 记录原因 → 自动重试；字段缺失（如表单改了标题）也直接失败并列出「表单实际字段」方便排查。

> 这一条直接消灭了 202610210018 那类「1 张午餐票」的产物。

### 3.2 回调秒回 + 异步出票

改前：回调线程里同步做 取详情 → 取人员 → 逐张渲染 PNG → 上传 → 发送，实测 6~18 秒，个别 135 秒，必然被企业微信判超时并重试（日志里 499 + 同签名重试）。

改后：回调只做「验签 + 落库 + 返回 success」（毫秒级），出票与推送由新增的 `worker` 容器消费；失败自动重试 5 次，超限标记「需人工处理」。

### 3.3 重试不再覆盖报文

改前：`existing.raw_payload = event.get("raw_payload") or event or existing.raw_payload` —— `or event` 让兜底永远不生效，每次重试都把已解析的表单字段冲成裸报文。

改后：`merge_approval_payload()` 合并，空值不覆盖。

### 3.4 幂等与并发

- DB 唯一索引 `uq_meal_tickets_approval_slot (approval_sp_no, meal_type, diner_index)`
- worker 用「条件 UPDATE 领取」抢占事件，多进程/多副本不会重复处理
- 人工票 `approval_sp_no` 为 NULL，不受唯一索引影响

### 3.5 整套票同事务

改前每张票单独 commit，第 3 张失败会留下 2 张，重试又因「已生成过」跳过 → 永久缺票。
改后一次审批的全部票在一个事务内提交，要么全成要么全无。

### 3.6 撤销回收 / token 缓存 / 时区

- 审批撤销或驳回（sp_status=3/4）→ 该单未核销票自动置为 `void`
- access_token 按 `expires_in` 缓存，避免单次回调十几次取 token
- compose 增加 `TZ=Asia/Shanghai`

---

## 四、数据库变更

迁移文件：`backend/alembic/versions/0005_ticket_reason_push.py`

```sql
-- 饭票
ALTER TABLE meal_tickets ADD COLUMN apply_reason VARCHAR(500);
ALTER TABLE meal_tickets ADD COLUMN push_count INTEGER NOT NULL DEFAULT 0;
ALTER TABLE meal_tickets ADD COLUMN last_push_at TIMESTAMPTZ;
ALTER TABLE meal_tickets ADD COLUMN last_push_error VARCHAR(255);

-- 审批事件
ALTER TABLE wecom_approval_events ADD COLUMN attempts INTEGER NOT NULL DEFAULT 0;
ALTER TABLE wecom_approval_events ADD COLUMN last_error VARCHAR(255);
ALTER TABLE wecom_approval_events ADD COLUMN processing BOOLEAN NOT NULL DEFAULT false;
ALTER TABLE wecom_approval_events ADD COLUMN processing_at TIMESTAMPTZ;

-- 历史回填申请原因
UPDATE meal_tickets t SET apply_reason = left(e.raw_payload::jsonb->>'申请原因', 500)
FROM wecom_approval_events e
WHERE t.approval_sp_no = e.sp_no AND t.apply_reason IS NULL
  AND (e.raw_payload::jsonb->>'申请原因') IS NOT NULL;

-- 幂等
CREATE UNIQUE INDEX uq_meal_tickets_approval_slot
  ON meal_tickets (approval_sp_no, meal_type, diner_index);
```

全部是加列/加索引，**不删不改现有列，可原地升级**。
唯一索引前置校验：已核对 87 单 0 重复，不会阻塞。

回滚：`alembic downgrade 0004_low_balance_alerts`（字段与索引一并撤销，业务数据不丢）。

---

## 五、部署与运维改造（你要的第 3 项）

### 5.1 数据持久化

**现状（已核实）**
- `postgres_data`、`redis_data` 是 Docker 命名卷 → `docker compose down` / 重建容器**不丢数据**
- 风险：`down -v` 会连卷删除；且**没有任何备份**

**加强**
1. 新增 `scripts/backup_db.sh`：`pg_dump` 全量导出到 `/opt/meal-ticket/backups/*.sql.gz`，保留 14 天
2. 新增 `scripts/restore_db.sh`：停写入 → 恢复 → 重启
3. 部署脚本**先备份再上线**，备份失败直接中止
4. 建议加一条 crontab（每天 2:00）：
   ```
   0 2 * * * cd /opt/meal-ticket && ./scripts/backup_db.sh >> backups/backup.log 2>&1
   ```
5. 卷不要手动删；升级只用 `docker compose up -d --build`，不用 `down -v`

### 5.2 git 版本化

**现状（已核实，问题比预想严重）**
- 服务器上有 `.git`，但**系统没装 git 命令**
- `.git` 的 HEAD 停在 `b9165a4`（6 月的老提交），而工作区文件已被手工覆盖成新版本
- 结论：这个仓库**无法直接 pull**，必须重建

**方案**
1. `yum install -y git`（源里是 1.8.3.1，够用）
2. 旧目录整体备份为 `/opt/meal-ticket.bak.<日期>`
3. 重新 clone 到 `/opt/meal-ticket`，`.env` 单独保留（不入库）
4. 新增 `.gitattributes` 强制 `*.sh` 用 LF，避免 Windows 换行导致脚本在 Linux 上「bad interpreter」
5. 以后更新统一走 `scripts/deploy.sh`，不再手工传文件

> 校验过：生产 `nginx/nginx.conf` 与仓库内容一致（仅换行符差异），没有需要保留的本地魔改；`.env` 是唯一需要搬运的文件。

### 5.3 一键部署

`scripts/deploy.sh` 流程：

```
备份数据库 → git pull --ff-only → docker compose build → up -d
→ 健康检查（最多 60 秒）→ 成功则清理旧镜像
→ 失败自动 git checkout 回上一版本 + 重建 + 重启，并提示恢复数据库
```

数据库迁移由 backend 容器启动时 `alembic upgrade head` 自动执行。

---

## 六、上线步骤（建议 30 分钟窗口，非用餐时段）

| 步骤 | 动作 | 预计 |
|---|---|---|
| 1 | 停企业微信回调验证？不需要，回调天然幂等 | — |
| 2 | `./scripts/backup_db.sh` 手工备份一份 | 1 min |
| 3 | `yum install -y git` | 1 min |
| 4 | `cp -a /opt/meal-ticket /opt/meal-ticket.bak.20261022` | 1 min |
| 5 | clone 新代码到 `/opt/meal-ticket.new`，拷回 `.env` | 2 min |
| 6 | `mv` 切换目录 | 10 s |
| 7 | `docker compose build backend worker frontend` | 3~8 min（首次拉依赖较慢） |
| 8 | `docker compose up -d`（自动迁移） | 1 min |
| 9 | 验证（见下） | 5 min |
| 10 | 观察 worker 日志 10 分钟 | 10 min |

**验证清单**
- [ ] `curl -s -o /dev/null -w '%{time_total}' http://172.26.80.101/api/health` < 1s
- [ ] `docker compose ps` 六个服务全 healthy/running（多一个 worker）
- [ ] 提交一张真实审批单 → 秒级返回 → 5 秒内出整套票，票上带申请原因
- [ ] 后台点「补发」→ 企业微信收到图片
- [ ] 导出 Excel 含「申请原因 / 推送状态」
- [ ] `docker compose logs worker` 无异常堆栈
- [ ] 数据库 `alembic_version = 0005_ticket_reason_push`

**回滚**：`git checkout 442a004 && docker compose build && docker compose up -d`，
若迁移引起异常再 `alembic downgrade 0004_low_balance_alerts`；数据有第 2 步的备份兜底。

---

## 七、风险与对策

| 风险 | 影响 | 对策 |
|---|---|---|
| 唯一索引创建失败 | 迁移中断 | 已核对无重复；迁移在事务内，失败自动回滚 |
| 首次构建慢（拉 pip/npm 依赖） | 上线时间拉长 | 已排除在业务窗口外执行；构建失败不影响旧容器运行 |
| worker 与 backend 版本不一致 | 事件格式不兼容 | 同一镜像、同一 commit 构建，`up -d` 同时切换 |
| 回调堆积 | 通过后延迟出票 | worker 每 3 秒轮询，重启后自动补处理；`processing` 超 10 分钟自动回收 |
| 补发把旧码作废 | 员工手上旧图失效 | 属预期行为（避免一票多码）；推送失败时不轮换 token |

---

## 八、待你确认

1. **代码推送方式**：我没有 GitHub 写权限（`git push` 需要凭据）。
   - 方案 A：给我一个 GitHub Personal Access Token，我推到 `main`
   - 方案 B：我把代码包安全传到服务器先上线，git 仅用于后续拉取
2. **上线窗口**：建议今天非用餐时段（如 14:00-15:00 或 20:00 后）。
3. 是否同时加每日 2:00 的自动备份 crontab（推荐加）。
