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
import re
from contextlib import asynccontextmanager
from pathlib import Path

import httpx
from fastapi import FastAPI, Request
from fastapi.responses import FileResponse, HTMLResponse, PlainTextResponse, RedirectResponse, Response

ROOT_DOMAIN = os.environ.get("ROOT_DOMAIN", "atelierlabs.co.kr")
DEFAULT_SITE = os.environ.get("DEFAULT_SITE", "atelierlabs")
SITES_DIR = Path(os.environ.get("SITES_DIR", Path(__file__).resolve().parent.parent / "sites")).resolve()

# Vernissage 공개 웹 데이터는 별도 프로젝트의 API가 소유한다. 페이지는 이 서버와
# 같은 origin의 /api/vernissage/public-web/...만 호출하므로, 브라우저에 API의 내부
# 주소나 PUBLIC_WEB_API_TOKEN을 노출하지 않는다.
VERNISSAGE_API_BASE_URL = os.environ.get("VERNISSAGE_API_BASE_URL", "").rstrip("/")
VERNISSAGE_PUBLIC_WEB_API_TOKEN = os.environ.get("VERNISSAGE_PUBLIC_WEB_API_TOKEN", "")

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

# Vernissage 공개 데이터 화면은 하나의 작은 클라이언트 앱이 목록·상세 경로를 모두 렌더링한다.
# 정적 파일 규칙으로는 /exhibitions/123 같은 동적 상세 경로를 찾을 수 없어서 여기서 shell을 준다.
VERNISSAGE_PUBLIC_WEB_PREFIXES = ("docent/notes", "exhibitions", "art-events")
VERNISSAGE_CLIENT_API_PATHS = {"test", "score", "web-events"}

HTML_CACHE = "public, max-age=300"
ASSET_CACHE = "public, max-age=86400"


@asynccontextmanager
async def lifespan(app: FastAPI):
    # 목록 화면은 여러 공개 API를 연속 호출할 수 있다. 요청마다 연결을 새로 열지 않고
    # 앱 수명 동안 하나의 connection pool을 재사용한다.
    async with httpx.AsyncClient(timeout=10.0) as client:
        app.state.vernissage_http_client = client
        yield


app = FastAPI(docs_url=None, redoc_url=None, openapi_url=None, lifespan=lifespan)


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


def _not_found(site_dir: Path, url_path: str, rewrite=None) -> Response:
    # /en/…, /ja/… 에서 못 찾으면 그 언어의 404.html을 먼저 찾는다.
    lang = url_path.split("/", 1)[0]
    candidates = [site_dir / lang / "404.html"] if lang in LANGS else []
    candidates.append(site_dir / "404.html")
    for page in candidates:
        if page.is_file():
            html = page.read_text(encoding="utf-8")
            if rewrite:
                html = rewrite(html)
            return HTMLResponse(html, status_code=404)
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
    # 개인정보 처리방침·이용약관 안내 페이지도 한국어·영어만 둔다.
    if url_path in ("ja/privacy", "ja/terms"):
        return "/en/" + url_path[len("ja/") :]
    return None


def _local_origin_rewriter(request: Request):
    """*.localhost로 열었으면 HTML 속 https://(<sub>.)ROOT_DOMAIN 링크를 같은 로컬 서버로 바꾸는 함수.

    운영 HTML에는 서브도메인 간 링크를 절대주소로 두되, 로컬에서는 클릭해도 운영 사이트로
    빠져나가지 않게 한다. localhost가 아니면 None.
    """
    hostname = _hostname(request)
    if hostname != "localhost" and not hostname.endswith(".localhost"):
        return None
    host = request.headers.get("host", "")
    port = host.rsplit(":", 1)[1] if ":" in host else ""
    suffix = f"localhost:{port}" if port else "localhost"
    pattern = re.compile(r"https://((?:[a-z0-9-]+\.)?)" + re.escape(ROOT_DOMAIN) + r"(?![a-z0-9.-])")
    return lambda html: pattern.sub(lambda m: f"http://{m.group(1)}{suffix}", html)


def _vernissage_public_shell(site_dir: Path, url_path: str) -> Path | None:
    """공개 데이터 화면 경로면 그 언어의 client shell(/public/index.html, /<lang>/public/index.html)."""
    lang, _, rest = url_path.partition("/")
    lang_dir = lang if lang in LANGS else ""
    rel = rest if lang_dir else url_path
    if rel != "art-taste-test" and not any(
        rel == prefix or rel.startswith(prefix + "/") for prefix in VERNISSAGE_PUBLIC_WEB_PREFIXES
    ):
        return None
    shell = site_dir / lang_dir / "public" / "index.html"
    return shell if shell.is_file() else None


def _vernissage_api_headers(request: Request) -> dict[str, str]:
    """Vernissage API는 X-App-Language(ko/en/ja)로 응답 언어를 정한다. 아는 값만 넘긴다."""
    headers = {"Accept": request.headers.get("accept", "application/json")}
    lang = request.headers.get("x-app-language", "").strip().lower()
    if lang in ("ko", *LANGS):
        headers["X-App-Language"] = lang
    return headers


def _is_safe_api_path(api_path: str) -> bool:
    """공개 API 접두사 밖으로 나갈 수 있는 경로 정규화를 막는다.

    httpx.URL은 ``public-web/../../private`` 같은 경로의 ``..``를 정규화한다.
    프록시는 공개 API 아래만 노출해야 하므로 빈 세그먼트와 dot 세그먼트도 허용하지 않는다.
    """
    return bool(api_path) and all(segment not in ("", ".", "..") for segment in api_path.split("/"))


async def _vernissage_upstream_get(request: Request, url: httpx.URL, headers: dict[str, str]) -> httpx.Response:
    """수명 주기 client가 있으면 connection pool을 재사용한다.

    lifespan을 시작하지 않는 단위 테스트 등에서는 짧게 사는 client로도 동작하게 한다.
    """
    if client := getattr(request.app.state, "vernissage_http_client", None):
        return await client.get(url, headers=headers)
    async with httpx.AsyncClient(timeout=10.0) as client:
        return await client.get(url, headers=headers)


async def _vernissage_upstream_request(
    request: Request, method: str, url: str, content: bytes, headers: dict[str, str]
) -> httpx.Response:
    if client := getattr(request.app.state, "vernissage_http_client", None):
        return await client.request(method, url, content=content, headers=headers)
    async with httpx.AsyncClient(timeout=10.0) as client:
        return await client.request(method, url, content=content, headers=headers)


def _vary_with_language(vary: str | None) -> str:
    """공개 API 캐시가 언어별 응답을 섞지 않도록 Vary를 보장한다."""
    if vary == "*":
        return vary
    values = [value.strip() for value in (vary or "").split(",") if value.strip()]
    if not any(value.lower() == "x-app-language" for value in values):
        values.append("X-App-Language")
    return ", ".join(values)


@app.get("/healthz", include_in_schema=False)
async def healthz() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/api/vernissage/public-web/{api_path:path}", include_in_schema=False)
async def vernissage_public_web_api(request: Request, api_path: str) -> Response:
    """Vernissage의 읽기 전용 공개 웹 API를 같은 origin으로 전달한다.

    이 범위 밖의 API(로그인·관리자·사용자 데이터)는 절대 프록시하지 않는다.
    """
    if resolve_site(_hostname(request)) != "vernissage":
        return PlainTextResponse("Not Found", status_code=404)
    if not _is_safe_api_path(api_path):
        return PlainTextResponse("Not Found", status_code=404)
    if not VERNISSAGE_API_BASE_URL:
        return PlainTextResponse("Vernissage API is not configured", status_code=503)

    url = httpx.URL(
        f"{VERNISSAGE_API_BASE_URL}/public-web/{api_path}",
        query=request.url.query.encode("utf-8"),
    )
    headers = _vernissage_api_headers(request)
    if VERNISSAGE_PUBLIC_WEB_API_TOKEN:
        headers["X-Public-Web-Token"] = VERNISSAGE_PUBLIC_WEB_API_TOKEN

    try:
        upstream = await _vernissage_upstream_get(request, url, headers)
    except httpx.HTTPError:
        return PlainTextResponse("Vernissage API is unavailable", status_code=502)

    response_headers = {
        name: upstream.headers[name]
        for name in ("content-type", "cache-control", "etag", "last-modified")
        if name in upstream.headers
    }
    response_headers["vary"] = _vary_with_language(upstream.headers.get("vary"))
    return Response(content=upstream.content, status_code=upstream.status_code, headers=response_headers)


@app.api_route("/api/vernissage/art-taste/{api_path}", methods=["GET", "POST"], include_in_schema=False)
async def vernissage_art_taste_api(request: Request, api_path: str) -> Response:
    """공개 예술 취향 테스트에 필요한 세 엔드포인트만 같은 origin으로 전달한다."""
    if resolve_site(_hostname(request)) != "vernissage" or api_path not in VERNISSAGE_CLIENT_API_PATHS:
        return PlainTextResponse("Not Found", status_code=404)
    if not VERNISSAGE_API_BASE_URL:
        return PlainTextResponse("Vernissage API is not configured", status_code=503)

    headers = _vernissage_api_headers(request)
    if content_type := request.headers.get("content-type"):
        headers["Content-Type"] = content_type
    try:
        upstream = await _vernissage_upstream_request(
            request,
            request.method,
            f"{VERNISSAGE_API_BASE_URL}/art-taste/{api_path}",
            await request.body(),
            headers,
        )
    except httpx.HTTPError:
        return PlainTextResponse("Vernissage API is unavailable", status_code=502)
    return Response(
        content=upstream.content,
        status_code=upstream.status_code,
        headers={
            "content-type": upstream.headers.get("content-type", "application/json"),
            "vary": _vary_with_language(upstream.headers.get("vary")),
        },
    )


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
        shell = _vernissage_public_shell(site_dir, url_path) if site == "vernissage" else None
        if shell is None:
            return _not_found(site_dir, url_path, _local_origin_rewriter(request))
        path = shell

    cache = HTML_CACHE if path.suffix == ".html" else ASSET_CACHE
    if path.suffix == ".html" and (rewrite := _local_origin_rewriter(request)):
        return HTMLResponse(rewrite(path.read_text(encoding="utf-8")), headers={"Cache-Control": "no-store"})
    return FileResponse(path, headers={"Cache-Control": cache})
