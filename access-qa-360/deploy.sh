#!/usr/bin/env bash
# Build and start (or update) the production stack. Safe to run again for every release.
#   ./deploy.sh          app on port ${WEB_PORT:-8080}; HTTPS handled by your platform or proxy
#   ./deploy.sh --tls    also run Caddy for automatic HTTPS on ports 80 and 443
set -euo pipefail
cd "$(dirname "$0")"

if [ ! -f .env.production ]; then
  echo "Missing .env.production. Copy .env.production.example and fill it in." >&2
  exit 1
fi

missing=0
for key in APP_URL POSTGRES_PASSWORD DATABASE_URL SYNC_DATABASE_URL SECRET_KEY; do
  value=$(grep -E "^${key}=" .env.production | tail -1 | cut -d= -f2- || true)
  if [ -z "$value" ]; then echo "Set ${key} in .env.production" >&2; missing=1; fi
done
if grep -Eq '^(DATABASE_URL|SYNC_DATABASE_URL)=.*:PASSWORD@' .env.production; then
  echo "Replace PASSWORD in DATABASE_URL and SYNC_DATABASE_URL with your database password" >&2; missing=1
fi
[ "$missing" -eq 0 ] || exit 1

compose=(docker compose --env-file .env.production -f docker-compose.prod.yml)
if [ "${1:-}" = "--tls" ]; then compose+=(--profile tls); fi

"${compose[@]}" build
# Migrations run first; the API and worker start only after they succeed.
"${compose[@]}" up -d --remove-orphans

echo "Waiting for the API to report healthy"
for _ in $(seq 1 40); do
  if "${compose[@]}" exec -T api curl -fsS http://127.0.0.1:8000/health >/dev/null 2>&1; then
    echo "Wiseflow is up."
    "${compose[@]}" ps
    exit 0
  fi
  sleep 3
done
echo "The API did not become healthy. Recent logs:" >&2
"${compose[@]}" logs --tail 60 api migrate >&2
exit 1
