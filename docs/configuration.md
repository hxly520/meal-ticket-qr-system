# 配置项说明

系统配置分两类：基础运行配置写入 `.env`，业务可变配置在后台“系统设置”维护。

## `.env` 基础配置

`.env` 不应提交到仓库。首次部署可复制 `.env.example`：

```bash
cp .env.example .env
```

常用项：

| 变量 | 说明 | 示例 |
| --- | --- | --- |
| `POSTGRES_DB` | 数据库名 | `meal_ticket` |
| `POSTGRES_USER` | 数据库用户 | `meal` |
| `POSTGRES_PASSWORD` | 数据库密码 | `change-me` |
| `DATABASE_URL` | 后端数据库连接 | `postgresql+psycopg://...` |
| `REDIS_URL` | Redis 连接 | `redis://redis:6379/0` |
| `APP_BASE_URL` | 默认系统公网地址 | `https://meal.example.com` |
| `APP_TIMEZONE` | 默认时区 | `Asia/Shanghai` |
| `JWT_SECRET_KEY` | 登录 token 签名密钥 | 随机长字符串 |
| `INITIAL_ADMIN_PASSWORD` | 首次初始化管理员密码；留空时自动生成并写入后端容器日志 | `随机长字符串` |
| `BACKEND_WORKERS` | 后端 worker 数量 | `2` |
| `HTTP_PORT` | 本机 HTTP 端口 | `80` |
| `PUBLIC_HTTP_PORT` | 额外公开端口 | `18001` |

## 后台系统设置

登录后台后进入“系统设置”，保存后立即生效。

基础设置：

- 系统公网地址
- 系统时区
- 票面公司名称
- 票面版权声明

核销时间限制：

- 早餐核销时间段，默认 `06:00-09:00`
- 午餐核销时间段，默认 `11:00-13:30`
- 晚餐核销时间段，默认 `17:00-19:30`

留空表示该餐别不限制时间段。格式支持 `HH:MM-HH:MM`。

企业微信应用：

- CorpID
- AgentID
- Secret

审批回调：

- Token
- EncodingAESKey
- 审批模板 ID

审批字段映射：

- 用餐日期字段名
- 餐别字段名
- 用餐人数字段名
- 部门字段名
- 申请原因字段名
- 部门ID映射

部门ID映射示例：

```text
28=IT部
35=行政部
```

饭卡低余额提醒：

- 启用提醒：是否执行定时企业微信消息推送。
- 判断金额：饭卡余额低于该金额时进入提醒范围。
- 推送间隔分钟：同一用户两次低余额提醒的最小间隔。
- 标题模板、内容模板：支持 `{name}`、`{balance}`、`{threshold}`、`{department}`、`{card_no}`、`{wanoa_pin}`、`{now}` 等变量。
- 测试条件：只预览命中用户、预计推送时间和消息内容，不会实际发送消息。

## 安全配置建议

- 首次登录后必须修改初始化管理员密码。
- `JWT_SECRET_KEY` 必须使用随机长字符串。
- `.env` 文件权限建议限制为部署用户可读。
- 企业微信 Secret、回调 Token、EncodingAESKey 只应在后台设置或 `.env` 中保存，不应出现在 Git 历史。
- GitHub Token 不要写入项目脚本，建议使用 macOS Keychain、GitHub CLI 或 CI Secret。
