# 企业微信自建应用饭卡余额入口

## 访问地址

自建应用主页地址填写：

```text
https://meal.example.com/my-card
```

如果后台“系统公网地址”调整过，则使用：

```text
{系统公网地址}/my-card
```

## 访问流程

1. 员工从企业微信自建应用打开 `/my-card`。
2. 前端请求 `/api/wecom/oauth-url` 生成企业微信网页授权地址。
3. 企业微信回跳 `/my-card?code=...`。
4. 前端请求 `/api/wecom/card-balance?code=...`。
5. 后端用 `code` 换取企业微信 `UserID`。
6. 后端按 `UserID` 查询企微-万傲绑定关系，并刷新/返回饭卡余额。

## 依赖配置

系统设置中需配置：

- 企业微信 CorpID
- 企业微信自建应用 AgentID
- 企业微信自建应用 Secret
- 系统公网地址
- 万傲瑞达平台地址与 access_token
- 万傲离线消费余额接口配置

## 常见结果

- `success`：已获取饭卡余额。
- `unbound`：当前企业微信用户尚未绑定万傲饭卡。
- `no_balance`：已绑定饭卡，但当前没有可显示余额。
- 实时刷新失败时，会显示最近一次同步缓存余额，并在返回消息中提示。
