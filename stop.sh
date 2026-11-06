#!/bin/bash
# ./stop.sh           -- 컨테이너 중지
# ./stop.sh --clean   -- 컨테이너 + 네트워크 제거

set -euo pipefail

BOLD="\033[1m"
GREEN="\033[32m"
RESET="\033[0m"

ROOT="$(cd "$(dirname "$0")" && pwd)"
COMPOSE=(docker compose --env-file "$ROOT/compose.dev.env" -f "$ROOT/docker-compose.yml")

case "${1:-}" in
  --clean)
    echo -e "${BOLD}컨테이너 및 네트워크 제거${RESET}"
    "${COMPOSE[@]}" down
    echo -e "${GREEN}완료${RESET}"
    ;;
  *)
    echo -e "${BOLD}서비스 중지${RESET}"
    "${COMPOSE[@]}" stop
    echo -e "${GREEN}중지 완료. 재시작: ./start.sh${RESET}"
    ;;
esac
