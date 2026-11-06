#!/bin/bash
# ./start.sh           -- 시작
# ./start.sh --build   -- 이미지 재빌드 후 시작 (pyproject.toml / uv.lock / Dockerfile 변경 시)

set -euo pipefail

BOLD="\033[1m"
GREEN="\033[32m"
CYAN="\033[36m"
YELLOW="\033[33m"
RESET="\033[0m"

case "${1:-}" in
  "")
    BUILD_FLAG=""
    ;;
  --build | -b)
    BUILD_FLAG="--build"
    ;;
  *)
    echo "사용법: $0 [--build|-b]" >&2
    exit 2
    ;;
esac

ROOT="$(cd "$(dirname "$0")" && pwd)"
COMPOSE=(docker compose --env-file "$ROOT/compose.dev.env" -f "$ROOT/docker-compose.yml")

# shellcheck disable=SC1091
source "$ROOT/compose.dev.env"

echo -e "${BOLD}Atelier Labs 시작${RESET}"
[ -n "$BUILD_FLAG" ] && echo -e "${YELLOW}이미지 재빌드 포함${RESET}"

# shellcheck disable=SC2086
"${COMPOSE[@]}" up -d --wait $BUILD_FLAG

echo ""
"${COMPOSE[@]}" ps
echo ""

MAC_IP=$(ipconfig getifaddr en0 2>/dev/null || ipconfig getifaddr en1 2>/dev/null || echo "감지 불가")
echo -e "${GREEN}회사 홈      →  http://localhost:${WEB_PORT}${RESET}"
echo -e "${GREEN}Vernissage   →  http://vernissage.localhost:${WEB_PORT}${RESET}"
echo -e "${GREEN}Keepsake     →  http://keepsake.localhost:${WEB_PORT}${RESET}"
echo -e "${CYAN}같은 Wi-Fi 기기 →  http://${MAC_IP}:${WEB_PORT}  (IP 접속은 회사 홈으로 열림)${RESET}"
