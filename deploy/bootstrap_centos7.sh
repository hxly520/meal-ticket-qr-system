#!/usr/bin/env bash
set -euo pipefail

yum install -y yum-utils device-mapper-persistent-data lvm2 curl ca-certificates

if ! command -v docker >/dev/null 2>&1; then
  yum-config-manager --add-repo https://download.docker.com/linux/centos/docker-ce.repo
  yum install -y docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin || {
    yum install -y docker
  }
fi

systemctl enable docker
systemctl start docker

if ! docker compose version >/dev/null 2>&1; then
  mkdir -p /usr/local/lib/docker/cli-plugins
  curl -fsSL \
    https://github.com/docker/compose/releases/download/v2.27.1/docker-compose-linux-x86_64 \
    -o /usr/local/lib/docker/cli-plugins/docker-compose
  chmod +x /usr/local/lib/docker/cli-plugins/docker-compose
fi

docker --version
docker compose version
