# 万傲瑞达 V6600 API 文档探查记录

## 当前访问地址

脱敏后的示例 Swagger 地址：

```text
https://wanoa.example.com/skip.do?page=system_swagger_index&clientId=1780637368051
```

平台访问状态示例：

- `wanoa.example.com` TCP 端口可连通。
- 平台登录页标题显示为“万傲瑞达6600”。
- 页面版权显示 `ZKTECO CO., LTD.`。
- 未登录访问 Swagger 会被重定向到 `/bioLogin.do`。

## 已验证的受保护端点

以下端点未登录时均返回 302 到登录页：

```text
/skip.do?page=system_swagger_index&clientId=1780637368051
/v2/api-docs
/v3/api-docs
/swagger-resources
/swagger-ui.html
/doc.html
/swagger-ui/index.html
/swagger/index.html
/knife4j/doc.html
```

说明当前 Swagger/OpenAPI 文档需要平台登录态，无法匿名读取。

## 登录页线索

登录页表单：

```text
POST /login.do
username=<用户名>
password=<前端处理后的密码>
loginType=NORMAL
```

页面中存在：

- 用户登录。
- 员工自助登录。
- 指纹登录。
- 可选验证码/2FA 区域。
- 前端 JS：`public/js/authSecurityParam.js`。

登录脚本中能看到密码会经过 MD5/AES 等前端处理，建议后续优先通过浏览器页面登录获取正常会话，再查看 Swagger，不建议手工拼接登录请求。

## 已读取到的 Swagger 分组

登录后 Swagger 页面已能读取，当前渲染出约 112 个接口，主要分组包括：

```text
AccDevice
AccDoor
AccLevel
AccReader
AccTransaction
AttApply
AttAreaPerson
AttDevice
AttPerson
AttTransaction
EleDevice
EleFloor
EleLevel
EleTransaction
PersBioTemplate
PersCard
PersDepartment
Person
PosTransaction
```

与饭卡余额对接最相关的是：

- `Person`：人员基础信息，核心标识是 `pin`。
- `PersCard`：人员卡片信息，可通过 `pin` 查询卡号。
- `PosTransaction`：消费流水查询，可通过 `personPin` 查询人员消费记录。
- `PersDepartment`：部门信息，可用于人员部门映射。

## 重点接口清单

### 人员接口

| 方法 | 路径 | 用途 | 关键参数 |
| --- | --- | --- | --- |
| `GET` | `/api/v2/person/get` | 按人员编号查询人员 | `pin` |
| `POST` | `/api/v2/person/getPersonList` | 按人员编号、部门、姓名查询人员列表 | `pins`、`deptCodes`、`name`、`lastName`、`pageNo`、`pageSize` |
| `GET` | `/api/person/get/{pin}` | 按人员编号查询人员，旧版路径 | `pin` |
| `POST` | `/api/person/getPersonList` | 查询人员列表，旧版路径 | `deptCodes`、`pageNo`、`pageSize` |

### 卡片接口

| 方法 | 路径 | 用途 | 关键参数 |
| --- | --- | --- | --- |
| `GET` | `/api/v2/card/getCards` | 按人员编号查询卡片列表 | `pin` |
| `GET` | `/api/card/getCards/{pin}` | 按人员编号查询卡片列表，旧版路径 | `pin` |
| `POST` | `/api/card/set` | 给人员设置卡片 | body: `PersApiCardItem` |

`PersApiCardItem` 示例字段在 Swagger 页面可见到 `cardNo`。余额字段是否在卡片列表返回的 `data` 中，需要调用接口后确认。

### 消费流水接口

| 方法 | 路径 | 用途 | 关键参数 |
| --- | --- | --- | --- |
| `GET` | `/api/transaction/listPosTransaction` | 查询消费流水列表 | `personPin`、`deptCode`、`startDate`、`endDate`、`pageNo`、`pageSize` |

该接口名称为 `Get Pos Transactions List`，可作为后续“消费记录”扩展接口。它不一定等同于余额查询接口。

现场确认：离线卡消费场景可通过该接口取最近一条消费流水中的余额字段作为当前卡余额。

脱敏用户 `EMP00001` 只读测试返回的关键字段：

- `money`：本次消费金额，示例为 `13.0`。
- `balance`：本次消费后的卡余额，示例为 `1301.0`。
- `subBalance`：补贴/子钱包余额，示例为 `0.0`。
- `posTime`：消费时间。
- `card`：物理饭卡号。

离线消费余额建议配置：

```text
wanoa_balance_path=/api/transaction/listPosTransaction
wanoa_balance_method=GET
wanoa_balance_pin_param=personPin
wanoa_balance_card_param=
wanoa_balance_extra_params=pageNo=1&pageSize=1
wanoa_balance_json_path=data.0.balance
wanoa_balance_amount_unit=yuan
```

## 脱敏测试记录：张三

已在登录后的 Swagger 页面使用 `Try it` 验证人员与饭卡接口。

### 人员查询

请求：

```text
POST /api/v2/person/getPersonList?name=张三&pageNo=1&pageSize=20
```

返回核心字段：

```json
{
  "code": 0,
  "message": "success",
  "data": {
    "total": 1,
    "data": [
      {
        "id": "person-id-demo",
        "pin": "EMP00001",
        "deptCode": "017",
        "deptName": "IT部",
        "name": "张三",
        "cardNo": "1000000001",
        "isDisabled": false
      }
    ]
  }
}
```

### 饭卡查询

请求：

```text
GET /api/v2/card/getCards?pin=EMP00001
```

返回核心字段：

```json
{
  "code": 0,
  "message": "success",
  "data": [
    {
      "pin": "EMP00001",
      "cardNo": "1000000001",
      "cardType": "0"
    }
  ]
}
```

结论：

- 可通过姓名获取万傲人员编号 `pin=EMP00001`、部门 `IT部`、卡号 `1000000001`。
- 卡片接口当前返回中未包含余额字段。
- 当前 Swagger 渲染出的 112 个接口未发现 `balance`、`account`、`余额`、`账户`、`钱包`、`充值`、`补贴` 等余额/账户关键词。
- `PosTransaction` 可用于后续消费流水核对，但不建议用流水倒推余额。

### 离线消费余额联调结果

使用厂商提供的 API 客户端密钥作为 `access_token` 进行只读测试：

- `POST /api/v2/person/getPersonList?name=张三...` 返回成功，说明授权参数可用于标准人员接口。
- `GET /api/transaction/listPosTransaction?personPin=EMP00001&pageNo=1&pageSize=1...` 返回成功，最近一条消费后余额为 `1301.0`。

判断：

- 现场万傲环境的标准人员接口已开放。
- 当前系统使用离线卡消费，余额以离线消费流水最近一条记录的 `balance` 字段为准。
- `balance` 字段单位为元，系统按元保存和展示。

## 对接路径

企业微信 UserID 到饭卡余额的最小链路建议：

1. 定时同步企业微信用户候选和万傲人员候选。
2. 对同名且双方唯一的候选自动建立企业微信 `userid` 与 V6600 `pin` 绑定。
3. 通过 `GET /api/v2/card/getCards?pin=...` 获取人员卡片和卡号。
4. 通过 `GET /api/transaction/listPosTransaction?personPin=...&pageNo=1&pageSize=1&access_token=...` 获取最近消费后余额。

## 当前结论

公开互联网未找到稳定可引用的 V6600 Swagger/API 文档；真实接口文档应以现场系统内置 Swagger 为准。

目前已确认人员、卡片和离线消费流水接口。厂商已明确客户端密钥可作为 `access_token` 随请求携带。

```text
消费
余额
账户
饭卡
卡片
人员
用户
card
account
balance
consume
person
employee
```

## 与本项目对接的初步判断

当前项目已按适配器模式落地第一阶段后台能力：

- 后台“系统设置”页面支持手动同步企业微信与万傲全部用户。
- 后台“饭卡用户”页面用于查看候选、维护映射和查询余额。
- 通过候选用户选择建立企业微信 `userid` 与万傲 `pin` 的人工确认绑定。
- 定时同步双方用户，并对同名且唯一的候选自动绑定。
- 支持按姓名快速查询饭卡人员、卡号和离线消费余额。
- 系统设置保留万傲平台地址、access_token、人员接口、卡片接口和同步间隔等必要配置项。
