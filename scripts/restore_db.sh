#!/usr/bin/env bash
# 从备份恢复数据库（会覆盖当前数据，请先停业务写入）。
# 用法：./scripts/restore_db.sh backups/meal_ticket_20261022_130000.sql.gz
set -euo pipefail

APP_DIR="${APP_DIR:-/opt/meal-ticket}"
cd "$APP_DIR"

FILE="${1:-}"
if [ -z "$FILE" ] || [ ! -f "$FILE" ]; then
  echo "用法: $0 <备份文件.sql.gz>" >&2
  exit 1
fi

set -a
# shellcheck disable=SC1091
source ./.env
set +a

echo "[restore] 将用 $FILE 覆盖数据库 ${POSTGRES_DB}，10 秒内可 Ctrl+C 取消"
sleep 10
echo "[restore] 停止 backend 与 worker，避免恢复过程中写入"
docker compose stop backend worker

echo "[restore] 恢复中..."
gunzip -c "$FILE" | docker compose exec -T postgres psql -U "${POSTGRES_USER}" -d "${POSTGRES_DB}"

echo "[restore] 重启服务"
docker compose start backend worker
echo "[restore] 完成"
