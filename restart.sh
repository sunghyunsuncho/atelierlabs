#!/bin/bash
# ./restart.sh           -- 재시작
# ./restart.sh --build   -- 이미지 재빌드 후 재시작 (pyproject.toml / uv.lock / Dockerfile 변경 시)

set -euo pipefail

BOLD="\033[1m"
GREEN="\033[32m"
YELLOW="\033[33m"
RESET="\033[0m"

ROOT="$(cd "$(dirname "$0")" && pwd)"
COMPOSE=(docker compose --env-file "$ROOT/compose.dev.env" -f "$ROOT/docker-compose.yml")

echo -e "${BOLD}Atelier Labs 재시작${RESET}"

case "${1:-}" in
  "")
    "${COMPOSE[@]}" restart
    ;;
  --build | -b)
    echo -e "${YELLOW}이미지 재빌드 포함${RESET}"
    "${COMPOSE[@]}" up -d --wait --build
    ;;
  *)
    echo "사용법: $0 [--build|-b]" >&2
    exit 2
    ;;
esac

echo ""
"${COMPOSE[@]}" ps
echo -e "${GREEN}재시작 완료${RESET}"
