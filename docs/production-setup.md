# 生产环境部署与企业微信联调

## 1. 服务器准备

推荐 Ubuntu 22.04/24.04，最低 2C4G。服务器需要能被企业微信公网 HTTPS 回调访问。

当前 Compose 内置 Nginx 默认监听 HTTP `80`。生产 HTTPS 建议放在云负载均衡、宝塔/Nginx Proxy Manager、Caddy 或宿主机 Nginx 上做证书终止，再反代到本服务的 HTTP 端口。

首次安装 Docker：

```bash
ssh root@your-server
cd /opt/meal-ticket
# Ubuntu
bash deploy/bootstrap_ubuntu.sh

# CentOS 7
bash deploy/bootstrap_centos7.sh
```

如果服务器直连 Docker Hub 超时，可使用项目内的镜像加速配置：

```bash
mkdir -p /etc/docker
cp deploy/docker-daemon.json /etc/docker/daemon.json
systemctl restart docker
```

## 2. 代码同步到服务器

本项目按服务器远程构建与调试设计，本机不需要启动服务。

建议使用临时 SSH key、受限部署账号或堡垒机账号。若只能使用密码登录，请在联调完成后立即修改密码或关闭密码登录。

```bash
SSH_HOST=your-server \
SSH_USER=root \
SSH_PORT=22 \
REMOTE_DIR=/opt/meal-ticket \
./deploy/remote_deploy.sh
```

如果临时只能使用密码登录，可使用环境变量传入密码。不要把密码写入脚本或提交到仓库：

```bash
SSH_HOST=your-server \
SSH_USER=root \
SSH_PASSWORD='your-temporary-password' \
REMOTE_DIR=/opt/meal-ticket \
./deploy/remote_deploy.sh
```

首次部署后登录服务器编辑 `.env`，这里主要保留数据库密码、JWT 密钥等基础运行参数：

```bash
cd /opt/meal-ticket
cp .env.example .env
vim .env
docker compose up -d --build
```

默认管理员：

```text
账号：admin
密码：admin123456
```

上线后请立即修改默认密码。

## 3. 后台系统设置

企业微信参数和审批字段映射不需要修改服务器 `.env`。部署完成后，用管理员账号登录后台，进入“系统设置”页面维护：

- 系统公网地址：员工打开饭票、饭堂扫码核销使用的域名，例如 `https://meal.example.com`
- 系统时区：默认 `Asia/Shanghai`
- 票面公司名称：企业微信饭票图片顶部显示
- 票面版权声明：企业微信饭票图片底部显示，默认“版权归IT部所有，有问题联系欧阳祖宇”
- 企业微信 CorpID
- 企业微信 AgentID
- 企业微信 Secret
- 审批回调 Token
- 审批回调 EncodingAESKey
- 审批模板 ID
- 审批字段映射：用餐日期、餐别、用餐人数、部门、申请原因

保存后立即生效，企业微信回调验签、审批详情拉取、饭票二维码生成、消息发送都会读取数据库中的设置。

## 4. 企业微信审批配置

企业微信后台需要准备，然后填入后台“系统设置”：

- 企业 ID：`WECOM_CORP_ID`
- 自建应用 AgentID：`WECOM_AGENT_ID`
- 自建应用 Secret：`WECOM_SECRET`
- 审批回调 Token：`WECOM_APPROVAL_TOKEN`
- 审批回调 EncodingAESKey：`WECOM_APPROVAL_AES_KEY`
- 饭票审批模板 ID：`WECOM_APPROVAL_TEMPLATE_ID`

审批回调 URL：

```text
http://sec-agent.poly-energy.com:18001/api/wecom/callback/approval
```

系统已实现企业微信回调验签、AES 解密和审批通过后生成饭票。审批通过状态 `SpStatus=2` 时会生成饭票，并将带用餐信息的核销二维码 PNG 图片通过自建应用发给申请人，不再发送跳转链接卡片。

如果审批模板字段名称不同，在后台“系统设置”中修改：

```text
WECOM_FIELD_MEAL_DATE=用餐日期
WECOM_FIELD_MEAL_TYPE=餐别
WECOM_FIELD_DINER_COUNT=用餐人数
WECOM_FIELD_DEPARTMENT=部门
WECOM_FIELD_REASON=申请原因
```

餐别字段支持多选。系统会读取多选项并按“用餐人数 x 餐别数量”生成饭票，例如 2 人选择早餐、午餐、晚餐，会生成 6 张饭票。

申请人姓名和部门优先从企业微信通讯录读取；如果通讯录接口暂时失败，则使用审批详情或回调字段中的姓名、部门兜底。

## 5. 联调用明文回调

在企业微信参数未齐全时，可先用 JSON 模拟审批通过：

```bash
curl -X POST https://your-domain.com/api/wecom/callback/approval \
  -H 'Content-Type: application/json' \
  -d '{
    "sp_no": "TEST-20260604-001",
    "sp_status": 2,
    "applicant_userid": "zhangsan",
    "employee_name": "张三",
    "department": "行政部",
    "meal_date": "2026-06-04",
    "meal_type": "早餐,午餐,晚餐",
    "diner_count": 2
  }'
```

## 6. 常用运维命令

```bash
docker compose ps
docker compose logs -f backend
docker compose logs -f nginx
docker compose exec backend alembic upgrade head
docker compose exec postgres pg_dump -U meal meal_ticket > backup.sql
```

## 7. 联调检查清单

- 后台系统设置中的系统公网地址必须是企业微信用户和饭堂扫码设备都可访问的 HTTPS 域名。
- 企业微信审批回调 URL 使用 `https://your-domain.com/api/wecom/callback/approval`。
- 审批模板字段名与 `WECOM_FIELD_MEAL_DATE`、`WECOM_FIELD_MEAL_TYPE`、`WECOM_FIELD_DEPARTMENT` 一致。
- 审批模板里“餐别”建议配置为多选控件，“用餐人数”建议配置为数字控件。
- 自建应用可见范围包含申请员工，否则消息发送可能失败。
- 自建应用需要具备给员工发送应用消息、上传临时素材图片、读取通讯录用户和部门的权限。
- 首次上线后修改默认管理员密码，并为饭堂工作人员分配 `verifier` 角色。
- 员工企业微信会直接收到二维码图片；饭堂工作人员使用手机相机、微信或企业微信扫一扫打开核销链接，系统自动核销并用颜色提示成功或失败。
- 生产环境建议为 `sec-agent.poly-energy.com:18001` 配置 HTTPS，提升访问和登录安全性；当前核销流程不依赖网页摄像头权限。

后台日常操作见 [user-guide.md](user-guide.md)。
