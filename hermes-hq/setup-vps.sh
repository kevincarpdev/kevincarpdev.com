#!/usr/bin/env bash
# One-time setup for Ubuntu VPS (Hostinger KVM-2). Run as root from the repo dir:
#   bash setup-vps.sh
set -euo pipefail

echo "==> Installing Docker + compose plugin"
if ! command -v docker >/dev/null 2>&1; then
  curl -fsSL https://get.docker.com | sh
fi

echo "==> Basic firewall (SSH, HTTP, HTTPS)"
if command -v ufw >/dev/null 2>&1; then
  ufw allow 22/tcp && ufw allow 80/tcp && ufw allow 443/tcp
  ufw --force enable
fi

echo "==> Preparing .env"
if [ ! -f .env ]; then
  cp .env.example .env
  sed -i "s/^SECRET_KEY=.*/SECRET_KEY=$(openssl rand -hex 32)/" .env
  echo ""
  echo "  !! Edit .env now and set ANTHROPIC_API_KEY and HONCHO_API_KEY, then re-run this script."
  exit 1
fi

echo "==> Building and starting"
mkdir -p data
docker compose up -d --build

echo "==> Seeding orgs/projects/contacts (idempotent)"
docker compose exec app python -m app.seed

echo ""
echo "Done. Create your first user:"
echo "  docker compose exec app python -m app.add_user kevin"
echo "Then open: http://\$(curl -s ifconfig.me)  (or https://\$DOMAIN if set)"
