# GitHub 自动建仓与推送

项目提供 `scripts/github_publish.sh`，用于在本机自动创建 GitHub 私有仓库、提交代码并推送。

## 推荐凭据方式

推荐使用 GitHub CLI 或 macOS Keychain 保存 GitHub Token。

如果已安装 GitHub CLI：

```bash
gh auth login
```

如果使用 macOS Keychain：

```bash
security add-generic-password -U -s github.com -a x-access-token -w YOUR_GITHUB_TOKEN
```

保存后不要再把 Token 写入聊天、文档或脚本。

也可以使用环境变量临时传入：

```bash
GITHUB_TOKEN=YOUR_GITHUB_TOKEN scripts/github_publish.sh my-repo
```

环境变量适合临时使用，不建议写入 shell 历史或配置文件。

## 使用方式

在项目根目录执行：

```bash
scripts/github_publish.sh meal-ticket-qr-system
```

默认行为：

- 如果当前目录还没有 Git 仓库，会初始化 Git。
- 如果没有提交，会自动提交一次。
- 如果 GitHub 仓库不存在，会创建私有仓库。
- 设置远程 `origin` 为普通 HTTPS URL，不包含 Token。
- 推送当前分支到 GitHub。

Token 读取顺序：

- `GITHUB_TOKEN` 环境变量。
- GitHub CLI：`gh auth token`。
- macOS Keychain：`security find-generic-password -s github.com -a x-access-token -w`。
- Git 凭据系统：`git credential fill`。

## 常用参数

```bash
scripts/github_publish.sh <repo-name> [public|private]
```

示例：

```bash
scripts/github_publish.sh meal-ticket-qr-system private
scripts/github_publish.sh open-meal-ticket public
```

## 注意事项

- 脚本不会提交 `.gitignore` 已排除的 `.env`、证书、构建产物、依赖目录。
- 创建公开仓库前请重新检查文档和代码，确认不包含内网地址、默认密码、真实业务数据。
- 私有仓库未来开源前建议新增 Issue 模板、CI、单元测试和脱敏示例数据。
