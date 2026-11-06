"""atelierlabs.co.kr 정적 사이트 서버.

하나의 Railway 서비스가 여러 도메인을 받고, 요청의 Host 헤더로 어떤 사이트를 보여줄지 정한다.

    atelierlabs.co.kr              -> sites/atelierlabs/
    www.atelierlabs.co.kr          -> atelierlabs.co.kr 로 301
    vernissage.atelierlabs.co.kr   -> sites/vernissage/
    keepsake.atelierlabs.co.kr     -> sites/keepsake/

로컬에서는 브라우저가 *.localhost 를 127.0.0.1 로 풀어주므로
http://vernissage.localhost:13000 처럼 열면 된다. 그 외 Host(localhost, Railway 기본
도메인 등)는 DEFAULT_SITE 환경변수(기본 atelierlabs)로 보낸다.

URL -> 파일 규칙 (sites/<site>/ 기준):
    /                     -> index.html
    /legal/privacy-policy -> legal/privacy-policy.html
    /legal/en/            -> legal/en/index.html
    /assets/icon.png      -> assets/icon.png

언어: 한국어는 루트, 영어·일본어는 /en/, /ja/ 아래 같은 경로 (예: /en/support -> en/support.html).
"""

from __future__ import annotations

import os
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.responses import FileResponse, HTMLResponse, PlainTextResponse, RedirectResponse, Response

ROOT_DOMAIN = os.environ.get("ROOT_DOMAIN", "atelierlabs.co.kr")
DEFAULT_SITE = os.environ.get("DEFAULT_SITE", "atelierlabs")
SITES_DIR = Path(os.environ.get("SITES_DIR", Path(__file__).resolve().parent.parent / "sites")).resolve()

# 서브도메인 이름 -> sites/ 아래 디렉터리. 루트 도메인은 "" 키.
SITES: dict[str, str] = {
    "": "atelierlabs",
    "vernissage": "vernissage",
    "keepsake": "keepsake",
}

# 루트 경로 요청 -> sites/<site>/assets/ 안에서 차례로 찾을 파일
ROOT_ICON_FALLBACKS: dict[str, tuple[str, ...]] = {
    "favicon.ico": ("favicon.png", "favicon.svg"),
    "apple-touch-icon.png": ("apple-touch-icon.png",),
    "apple-touch-icon-precomposed.png": ("apple-touch-icon.png",),
}

# 한국어는 루트(/), 나머지 언어는 /<lang>/ 아래에 같은 경로로 둔다.
LANGS = ("en", "ja")

HTML_CACHE = "public, max-age=300"
ASSET_CACHE = "public, max-age=86400"

app = FastAPI(docs_url=None, redoc_url=None, openapi_url=None)


def _hostname(request: Request) -> str:
    host = request.headers.get("host", "")
    return host.rsplit(":", 1)[0].lower().rstrip(".") if host else ""


def resolve_site(hostname: str) -> str | None:
    """Host 이름 -> 사이트 디렉터리 이름. 우리 도메인인데 모르는 서브도메인이면 None(404)."""
    for suffix in (ROOT_DOMAIN, "localhost"):
        if hostname == suffix:
            return SITES[""] if suffix == ROOT_DOMAIN else DEFAULT_SITE
        if hostname.endswith("." + suffix):
            return SITES.get(hostname[: -len(suffix) - 1])
    return DEFAULT_SITE


def resolve_file(site_dir: Path, url_path: str) -> Path | None:
    rel = url_path.lstrip("/")
    is_dir = rel == "" or rel.endswith("/")
    candidates = [rel + "index.html"] if is_dir else [rel, rel + ".html", rel + "/index.html"]
    for candidate in candidates:
        path = (site_dir / candidate).resolve()
        # 경로 조작(../)으로 사이트 디렉터리 밖을 읽지 못하게 한다.
        if path.is_relative_to(site_dir) and path.is_file():
            return path
    return None


def _not_found(site_dir: Path, url_path: str) -> Response:
    # /en/…, /ja/… 에서 못 찾으면 그 언어의 404.html을 먼저 찾는다.
    lang = url_path.split("/", 1)[0]
    candidates = [site_dir / lang / "404.html"] if lang in LANGS else []
    candidates.append(site_dir / "404.html")
    for page in candidates:
        if page.is_file():
            return HTMLResponse(page.read_text(encoding="utf-8"), status_code=404)
    return PlainTextResponse("Not Found", status_code=404)


def redirect_target(url_path: str) -> str | None:
    """옛 주소·별칭 -> 정식 주소. 해당 없으면 None."""
    # 일본어는 ISO 코드 ja가 정식. /jp 로 들어오면 옮긴다.
    if url_path == "jp" or url_path.startswith("jp/"):
        return "/ja" + url_path[2:]
    # 언어 폴더를 앞에 두기 전의 영문 약관 주소
    if url_path.startswith("legal/en/"):
        return "/en/legal/" + url_path[len("legal/en/") :]
    # 약관은 일본어판을 두지 않고 영어판을 쓴다.
    if url_path.startswith("ja/legal/"):
        return "/en/legal/" + url_path[len("ja/legal/") :]
    return None


@app.get("/healthz", include_in_schema=False)
async def healthz() -> dict[str, str]:
    return {"status": "ok"}


@app.api_route("/{url_path:path}", methods=["GET", "HEAD"], include_in_schema=False)
async def serve(request: Request, url_path: str) -> Response:
    hostname = _hostname(request)

    if hostname == f"www.{ROOT_DOMAIN}":
        target = f"https://{ROOT_DOMAIN}{request.url.path}"
        if request.url.query:
            target += f"?{request.url.query}"
        return RedirectResponse(target, status_code=301)

    site = resolve_site(hostname)
    if site is None:
        return PlainTextResponse("Not Found", status_code=404)
    site_dir = (SITES_DIR / site).resolve()

    # 브라우저가 <link rel="icon"> 없이도 루트에서 찾는 파일들
    if url_path in ROOT_ICON_FALLBACKS:
        found = next((n for n in ROOT_ICON_FALLBACKS[url_path] if (site_dir / "assets" / n).is_file()), None)
        if found:
            url_path = f"assets/{found}"

    target = redirect_target(url_path)
    if target:
        if request.url.query:
            target += f"?{request.url.query}"
        return RedirectResponse(target, status_code=301)

    path = resolve_file(site_dir, url_path)
    if path is None:
        return _not_found(site_dir, url_path)

    cache = HTML_CACHE if path.suffix == ".html" else ASSET_CACHE
    return FileResponse(path, headers={"Cache-Control": cache})
