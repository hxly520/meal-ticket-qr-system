#!/usr/bin/env bash
# 数据库备份：pg_dump 全量导出到宿主机目录，默认保留 14 天。
# 用法：./scripts/backup_db.sh
set -euo pipefail

APP_DIR="${APP_DIR:-/opt/meal-ticket}"
BACKUP_DIR="${BACKUP_DIR:-$APP_DIR/backups}"
KEEP_DAYS="${KEEP_DAYS:-14}"
STAMP="$(date +%Y%m%d_%H%M%S)"

cd "$APP_DIR"
mkdir -p "$BACKUP_DIR"

# 从 .env 读取库名与账号，避免硬编码
set -a
# shellcheck disable=SC1091
source ./.env
set +a

TARGET="$BACKUP_DIR/meal_ticket_${STAMP}.sql.gz"

docker compose exec -T postgres \
  pg_dump -U "${POSTGRES_USER}" -d "${POSTGRES_DB}" --no-owner --no-privileges \
  | gzip -9 > "$TARGET"

if [ ! -s "$TARGET" ]; then
  echo "[backup] 备份文件为空，备份失败" >&2
  rm -f "$TARGET"
  exit 1
fi

echo "[backup] 完成: $TARGET ($(du -h "$TARGET" | cut -f1))"

find "$BACKUP_DIR" -name 'meal_ticket_*.sql.gz' -type f -mtime "+${KEEP_DAYS}" -delete
echo "[backup] 已清理 ${KEEP_DAYS} 天前的备份"
