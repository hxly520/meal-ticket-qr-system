#!/usr/bin/env bash
set -euo pipefail

REPO_NAME="${1:-}"
VISIBILITY="${2:-private}"

if [ -z "$REPO_NAME" ]; then
  REPO_NAME="$(basename "$(pwd)" | tr '[:upper:]' '[:lower:]' | tr -cs 'a-z0-9._-' '-')"
  REPO_NAME="${REPO_NAME%-}"
fi

if [ "$VISIBILITY" != "private" ] && [ "$VISIBILITY" != "public" ]; then
  echo "Usage: scripts/github_publish.sh <repo-name> [public|private]" >&2
  exit 2
fi

require_cmd() {
  if ! command -v "$1" >/dev/null 2>&1; then
    echo "Missing command: $1" >&2
    exit 2
  fi
}

require_cmd git
require_cmd curl
require_cmd python3

get_token() {
  if [ -n "${GITHUB_TOKEN:-}" ]; then
    printf '%s' "$GITHUB_TOKEN"
    return
  fi

  if command -v gh >/dev/null 2>&1; then
    local gh_token
    gh_token="$(gh auth token 2>/dev/null || true)"
    if [ -n "$gh_token" ]; then
      printf '%s' "$gh_token"
      return
    fi
  fi

  if command -v git-credential-osxkeychain >/dev/null 2>&1; then
    local credential
    credential="$(printf 'protocol=https\nhost=github.com\n\n' | git credential-osxkeychain get || true)"
    local keychain_token
    keychain_token="$(printf '%s\n' "$credential" | awk -F= '$1=="password"{print $2; exit}')"
    if [ -n "$keychain_token" ]; then
      printf '%s' "$keychain_token"
      return
    fi
  fi

  if command -v security >/dev/null 2>&1; then
    local security_token
    security_token="$(security find-generic-password -s github.com -a x-access-token -w 2>/dev/null || true)"
    if [ -n "$security_token" ]; then
      printf '%s' "$security_token"
      return
    fi
  fi

  local credential
  credential="$(printf 'protocol=https\nhost=github.com\n\n' | git credential fill || true)"
  printf '%s\n' "$credential" | awk -F= '$1=="password"{print $2; exit}'
}

TOKEN="$(get_token)"
if [ -z "$TOKEN" ]; then
  cat >&2 <<'MSG'
GitHub token not found.

Recommended on macOS:
  security add-generic-password -U -s github.com -a x-access-token -w YOUR_GITHUB_TOKEN

Or run once with:
  GITHUB_TOKEN=YOUR_GITHUB_TOKEN scripts/github_publish.sh repo-name
MSG
  exit 1
fi

api() {
  curl -fsS \
    -H "Authorization: Bearer ${TOKEN}" \
    -H "Accept: application/vnd.github+json" \
    "$@"
}

USER_JSON="$(api https://api.github.com/user)"
OWNER="$(printf '%s' "$USER_JSON" | python3 -c 'import json,sys; print(json.load(sys.stdin)["login"])')"

if [ ! -d .git ]; then
  git init
fi

git config user.name >/dev/null 2>&1 || git config user.name "$OWNER"
git config user.email >/dev/null 2>&1 || git config user.email "${OWNER}@users.noreply.github.com"

git add .
if ! git diff --cached --quiet; then
  git commit -m "Initial project publish"
fi

CURRENT_BRANCH="$(git branch --show-current)"
if [ -z "$CURRENT_BRANCH" ]; then
  CURRENT_BRANCH="main"
  git checkout -b "$CURRENT_BRANCH"
fi

if [ "$CURRENT_BRANCH" = "master" ]; then
  git branch -M main
  CURRENT_BRANCH="main"
fi

REPO_API="https://api.github.com/repos/${OWNER}/${REPO_NAME}"
if ! api "$REPO_API" >/tmp/github_publish_repo.json 2>/tmp/github_publish_repo.err; then
  PRIVATE_JSON=true
  if [ "$VISIBILITY" = "public" ]; then
    PRIVATE_JSON=false
  fi
  CREATE_BODY="$(printf '{"name":"%s","private":%s,"auto_init":false}' "$REPO_NAME" "$PRIVATE_JSON")"
  curl -fsS \
    -H "Authorization: Bearer ${TOKEN}" \
    -H "Accept: application/vnd.github+json" \
    https://api.github.com/user/repos \
    -d "$CREATE_BODY" >/tmp/github_publish_repo.json
fi

HTML_URL="$(python3 -c 'import json,sys; print(json.load(open("/tmp/github_publish_repo.json"))["html_url"])')"
REMOTE_URL="https://github.com/${OWNER}/${REPO_NAME}.git"

if git remote get-url origin >/dev/null 2>&1; then
  git remote set-url origin "$REMOTE_URL"
else
  git remote add origin "$REMOTE_URL"
fi

AUTH="$(printf 'x-access-token:%s' "$TOKEN" | base64 | tr -d '\n')"
git -c "http.https://github.com/.extraheader=AUTHORIZATION: basic ${AUTH}" push -u origin "$CURRENT_BRANCH"

echo "Published: ${HTML_URL}"
