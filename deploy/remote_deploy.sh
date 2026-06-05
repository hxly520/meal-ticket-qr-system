#!/usr/bin/env bash
set -euo pipefail

if [ "${SSH_HOST:-}" = "" ] || [ "${SSH_USER:-}" = "" ]; then
  echo "Usage: SSH_HOST=1.2.3.4 SSH_USER=root [SSH_PORT=22] [REMOTE_DIR=/opt/meal-ticket] ./deploy/remote_deploy.sh"
  exit 1
fi

SSH_PORT="${SSH_PORT:-22}"
REMOTE_DIR="${REMOTE_DIR:-/opt/meal-ticket}"
SSH_TARGET="${SSH_USER}@${SSH_HOST}"
SSH_BASE=(ssh -p "$SSH_PORT")
RSYNC_SSH="ssh -p $SSH_PORT"

if [ "${SSH_PASSWORD:-}" != "" ]; then
  if ! command -v expect >/dev/null 2>&1; then
    echo "SSH_PASSWORD requires expect to be installed locally."
    exit 1
  fi
  SSH_BASE=(expect -c "set timeout -1; spawn ssh -p $SSH_PORT -o StrictHostKeyChecking=no $SSH_TARGET \$env(CMD); expect { *assword:* { send -- \"\$env(SSH_PASSWORD)\\r\"; exp_continue } eof }")
  RSYNC_SSH="ssh -p $SSH_PORT -o StrictHostKeyChecking=no"
fi

run_remote() {
  if [ "${SSH_PASSWORD:-}" != "" ]; then
    CMD="$1" "${SSH_BASE[@]}"
  else
    ssh -p "$SSH_PORT" "$SSH_TARGET" "$1"
  fi
}

run_remote "mkdir -p '$REMOTE_DIR'"

if [ "${SSH_PASSWORD:-}" != "" ]; then
  if ! command -v rsync >/dev/null 2>&1; then
    echo "rsync is required locally."
    exit 1
  fi
  expect <<EOF
set timeout -1
spawn rsync -az --delete --exclude .git --exclude .env --exclude node_modules --exclude __pycache__ -e "$RSYNC_SSH" ./ "$SSH_TARGET:$REMOTE_DIR/"
expect {
  "*assword:*" { send -- "$SSH_PASSWORD\r"; exp_continue }
  eof
}
EOF
else
  rsync -az --delete \
    --exclude '.git' \
    --exclude '.env' \
    --exclude 'node_modules' \
    --exclude '__pycache__' \
    -e "$RSYNC_SSH" \
    ./ "$SSH_TARGET:$REMOTE_DIR/"
fi

run_remote "cd '$REMOTE_DIR' && test -f .env || cp .env.example .env"
run_remote "cd '$REMOTE_DIR' && docker compose build && docker compose up -d"
run_remote "cd '$REMOTE_DIR' && docker compose ps"
