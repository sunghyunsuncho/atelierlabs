#!/bin/bash
# ./logs.sh   -- 사이트 서버 실시간 로그

set -euo pipefail

ROOT="$(cd "$(dirname "$0")" && pwd)"
COMPOSE=(docker compose --env-file "$ROOT/compose.dev.env" -f "$ROOT/docker-compose.yml")

"${COMPOSE[@]}" logs -f --tail=100 web
