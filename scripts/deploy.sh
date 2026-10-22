#!/usr/bin/env bash
# 生产部署：git 拉取 → 备份数据库 → 构建镜像 → 迁移 → 滚动重启 → 健康检查 → 失败自动回滚
# 用法：./scripts/deploy.sh [分支名]
set -euo pipefail

APP_DIR="${APP_DIR:-/opt/meal-ticket}"
BRANCH="${1:-main}"
cd "$APP_DIR"

log() { echo -e "\n[deploy $(date '+%H:%M:%S')] $*"; }

if [ ! -d .git ]; then
  echo "[deploy] 当前目录不是 git 仓库，请先 git clone" >&2
  exit 1
fi

PREV_COMMIT="$(git rev-parse HEAD)"
PREV_BRANCH="$(git rev-parse --abbrev-ref HEAD)"
log "当前版本 $PREV_COMMIT ($PREV_BRANCH → $BRANCH)"

# 1. 备份数据库（失败即中止，绝不带风险上线）
log "备份数据库"
BACKUP_DIR="$APP_DIR/backups" ./scripts/backup_db.sh

# 2. 拉取代码
log "拉取代码"
git fetch --prune origin "$BRANCH"
git checkout "$BRANCH"
git pull --ff-only origin "$BRANCH"
NEW_COMMIT="$(git rev-parse --short HEAD)"
log "目标版本 $NEW_COMMIT"

# 3. 构建
log "构建镜像"
docker compose build backend worker frontend

# 4. 启动（backend 启动时会执行 alembic upgrade head）
log "启动服务"
docker compose up -d --remove-orphans

# 5. 健康检查
log "健康检查"
HEALTHY=0
for _ in $(seq 1 30); do
  if curl -fsS "http://127.0.0.1/api/health" >/dev/null 2>&1; then
    HEALTHY=1
    break
  fi
  sleep 2
done

if [ "$HEALTHY" != "1" ]; then
  log "健康检查失败，开始回滚到 $PREV_COMMIT"
  docker compose logs --tail 80 backend worker
  git checkout "$PREV_COMMIT"
  docker compose build backend worker frontend
  docker compose up -d --remove-orphans
  echo "[deploy] 已回滚代码，数据库请按需执行: ./scripts/restore_db.sh backups/<最新备份>" >&2
  exit 1
fi

docker image prune -f >/dev/null 2>&1 || true
log "部署完成：$PREV_COMMIT → $NEW_COMMIT"
log "校验数据卷：$(docker volume ls --filter name=postgres_data --format '{{.Name}}')"
