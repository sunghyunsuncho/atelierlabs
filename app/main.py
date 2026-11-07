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
    일반 경로              -> 확장자 없는 정적 HTML 파일
    /legal/...            -> 앱 백엔드가 소유한 법률 문서 프록시
    /assets/icon.png      -> assets/icon.png

언어: 한국어는 루트, 영어·일본어는 /en/, /ja/ 아래 같은 경로 (예: /en/support -> en/support.html).
"""

from __future__ import annotations

import html
import json
import os
import re
import time
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
KEEPSAKE_API_BASE_URL = os.environ.get("KEEPSAKE_API_BASE_URL", "").rstrip("/")
KEEPSAKE_PUBLIC_WEB_API_TOKEN = os.environ.get("KEEPSAKE_PUBLIC_WEB_API_TOKEN", "")

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
VERNISSAGE_SEO_DETAIL = re.compile(r"^(?:(en|ja)/)?(docent/notes|exhibitions|art-events)/(\d+)$")

HTML_CACHE = "public, max-age=300"
ASSET_CACHE = "public, max-age=86400"
VERNISSAGE_SITEMAP_CACHE: tuple[float, str] | None = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    # 공개 API·법률 문서는 요청마다 연결을 새로 열지 않고 앱 수명 동안 하나의
    # connection pool을 재사용한다.
    async with httpx.AsyncClient(timeout=10.0) as client:
        app.state.upstream_http_client = client
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


async def _upstream_get(request: Request, url: httpx.URL, headers: dict[str, str]) -> httpx.Response:
    """수명 주기 client가 있으면 connection pool을 재사용한다.

    lifespan을 시작하지 않는 단위 테스트 등에서는 짧게 사는 client로도 동작하게 한다.
    """
    if client := getattr(request.app.state, "upstream_http_client", None):
        return await client.get(url, headers=headers)
    async with httpx.AsyncClient(timeout=10.0) as client:
        return await client.get(url, headers=headers)


def _legal_document_request(site: str, url_path: str) -> tuple[str, str, str] | None:
    """법률 문서 URL을 해당 앱 백엔드의 공개 문서 API 요청으로 바꾼다.

    홈페이지는 URL과 페이지 외관만 맡고, 실제 약관 원문은 각 앱 백엔드가 소유한다.
    일본어 법률 문서는 기존처럼 영어판으로 리다이렉트된 뒤 이 함수에 도달한다.
    """
    language = "ko"
    document_path = url_path
    if document_path.startswith("en/"):
        language = "en"
        document_path = document_path[3:]

    if document_path not in ("legal/terms-of-service", "legal/privacy-policy"):
        return None
    document = document_path.rsplit("/", 1)[1]

    if site == "vernissage":
        return (VERNISSAGE_API_BASE_URL, VERNISSAGE_PUBLIC_WEB_API_TOKEN, f"legal/{language}/{document}")
    if site == "keepsake":
        return (KEEPSAKE_API_BASE_URL, KEEPSAKE_PUBLIC_WEB_API_TOKEN, f"legal/{language}/{document}")
    return None


async def _proxy_legal_document(request: Request, site: str, url_path: str) -> Response | None:
    """앱 백엔드가 소유한 법률 문서를 같은 공개 사이트 URL로 전달한다."""
    target = _legal_document_request(site, url_path)
    if target is None:
        return None
    api_base_url, token, api_path = target
    if not api_base_url:
        return PlainTextResponse(
            f"{site.title()} legal API is not configured", status_code=503, headers={"Cache-Control": "no-store"}
        )

    headers = {"Accept": "text/html"}
    if token:
        headers["X-Public-Web-Token"] = token
    try:
        upstream = await _upstream_get(request, httpx.URL(f"{api_base_url}/public-web/{api_path}"), headers)
    except httpx.HTTPError:
        return PlainTextResponse(
            f"{site.title()} legal API is unavailable", status_code=502, headers={"Cache-Control": "no-store"}
        )

    response_headers = {
        name: upstream.headers[name] for name in ("content-type", "etag", "last-modified") if name in upstream.headers
    }
    # 법률 문서는 변경 후 홈페이지를 다시 배포하지 않아도 즉시 보여야 한다.
    response_headers["cache-control"] = "no-store"
    return Response(content=upstream.content, status_code=upstream.status_code, headers=response_headers)


async def _vernissage_upstream_request(
    request: Request, method: str, url: str, content: bytes, headers: dict[str, str]
) -> httpx.Response:
    if client := getattr(request.app.state, "upstream_http_client", None):
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


async def _vernissage_public_json(request: Request, endpoint: str, language: str) -> tuple[dict | None, int]:
    """공개 API에서 SEO 문서용 데이터만 서버에서 가져온다."""
    if not VERNISSAGE_API_BASE_URL:
        return None, 503
    headers = {"Accept": "application/json", "X-App-Language": language}
    if VERNISSAGE_PUBLIC_WEB_API_TOKEN:
        headers["X-Public-Web-Token"] = VERNISSAGE_PUBLIC_WEB_API_TOKEN
    try:
        response = await _upstream_get(request, httpx.URL(f"{VERNISSAGE_API_BASE_URL}/public-web/{endpoint}"), headers)
    except httpx.HTTPError:
        return None, 502
    if response.status_code != 200:
        return None, response.status_code
    try:
        return response.json(), 200
    except ValueError:
        return None, 502


def _seo_text(value: object, limit: int = 160) -> str:
    text = re.sub(r"\s+", " ", str(value or "")).strip()
    return text if len(text) <= limit else f"{text[: limit - 1].rstrip()}…"


def _public_url(path: str) -> str:
    return f"https://vernissage.{ROOT_DOMAIN}/{path.lstrip('/')}"


def _render_vernissage_detail_shell(
    site_dir: Path, language: str, path: str, title: str, description: str, body: str, image: str | None, schema: dict
) -> str:
    """기존 인터랙티브 셸에 크롤러가 즉시 읽을 수 있는 본문과 메타데이터를 넣는다."""
    lang_dir = language if language in LANGS else ""
    shell = (site_dir / lang_dir / "public" / "index.html").read_text(encoding="utf-8")
    canonical = _public_url(path)
    content_path = re.sub(r"^(?:en|ja)/", "", path)

    def alternate_url(prefix: str) -> str:
        return _public_url(f"{prefix}/{content_path}" if prefix else content_path)

    alternates = "\n".join(
        f'<link rel="alternate" hreflang="{code}" href="{alternate_url(prefix)}" />'
        for code, prefix in (("ko", ""), ("en", "en"), ("ja", "ja"))
    )
    image_meta = f'<meta property="og:image" content="{html.escape(str(image), quote=True)}" />' if image else ""
    schema_json = json.dumps(schema, ensure_ascii=False).replace("</", "<\\/")
    head = "\n".join(
        (
            '<meta name="robots" content="index, follow" />',
            f'<link rel="canonical" href="{canonical}" />',
            alternates,
            f'<link rel="alternate" hreflang="x-default" href="{_public_url(content_path)}" />',
            f'<meta name="description" content="{html.escape(description, quote=True)}" />',
            f'<meta property="og:title" content="{html.escape(title, quote=True)}" />',
            f'<meta property="og:description" content="{html.escape(description, quote=True)}" />',
            '<meta property="og:type" content="article" />',
            f'<meta property="og:url" content="{canonical}" />',
            image_meta,
            '<meta name="twitter:card" content="summary_large_image" />',
            f'<script type="application/ld+json">{schema_json}</script>',
        )
    )
    shell = shell.replace('<meta name="robots" content="noindex" />', "")
    shell = re.sub(r"<title>.*?</title>", lambda _: f"<title>{html.escape(title)} | Vernissage</title>", shell, count=1)
    shell = shell.replace("</head>", f"{head}\n</head>", 1)
    return re.sub(
        r'<main id="public-web-app" class="public-main" aria-live="polite">.*?</main>',
        f'<main id="public-web-app" class="public-main" aria-live="polite">{body}</main>',
        shell,
        count=1,
        flags=re.S,
    )


async def _vernissage_seo_detail(request: Request, site_dir: Path, url_path: str) -> Response | None:
    match = VERNISSAGE_SEO_DETAIL.fullmatch(url_path)
    if not match:
        return None
    language = match.group(1) or "ko"
    section, item_id = match.group(2), match.group(3)
    data, status = await _vernissage_public_json(request, f"{section}/{item_id}", language)
    if data is None:
        # API 장애·미설정 시 기존 클라이언트 셸로 계속 제공한다. 실제로 존재하지 않는
        # 콘텐츠만 404로 응답해 soft 404를 만들지 않는다.
        return PlainTextResponse("Not Found", status_code=404) if status == 404 else None
    item = data.get({"docent/notes": "note", "exhibitions": "exhibition", "art-events": "event"}[section])
    if not isinstance(item, dict):
        return PlainTextResponse("Not Found", status_code=404)
    series = item.get("series") if isinstance(item.get("series"), dict) else {}
    title = _seo_text(item.get("display_title") or item.get("title") or series.get("name"), 180)
    if not title:
        return PlainTextResponse("Not Found", status_code=404)
    description = _seo_text(
        item.get("excerpt") or item.get("description") or item.get("content") or series.get("description") or title
    )
    image = item.get("thumbnail_url") or item.get("image_url")
    if section == "docent/notes":
        content = item.get("content") or item.get("excerpt") or ""
        schema = {
            "@context": "https://schema.org",
            "@type": "Article",
            "headline": title,
            "description": description,
            "image": image,
            "datePublished": item.get("published_at"),
            "mainEntityOfPage": _public_url(url_path),
        }
    else:
        content = item.get("description") or series.get("description") or ""
        schema = {
            "@context": "https://schema.org",
            "@type": "Event",
            "name": title,
            "description": description,
            "image": image,
            "startDate": item.get("start_date"),
            "endDate": item.get("end_date"),
            "url": _public_url(url_path),
        }
    content_html = html.escape(str(content)).replace("\n", "<br />")
    image_url = html.escape(str(image), quote=True)
    escaped_title = html.escape(title, quote=True)
    image_html = f'<img class="detail-image" src="{image_url}" alt="{escaped_title}" />' if image else ""
    body = "".join(
        (
            '<article class="detail">',
            f"<h1>{html.escape(title)}</h1>",
            image_html,
            f'<p class="detail-text">{content_html}</p>',
            "</article>",
        )
    )
    return HTMLResponse(
        _render_vernissage_detail_shell(site_dir, language, url_path, title, description, body, image, schema),
        headers={"Cache-Control": HTML_CACHE},
    )


async def _vernissage_dynamic_sitemap(request: Request) -> Response | None:
    """공개 API의 현재 노출 가능한 상세 URL을 언어별로 사이트맵에 추가한다."""
    global VERNISSAGE_SITEMAP_CACHE
    if VERNISSAGE_SITEMAP_CACHE and time.monotonic() - VERNISSAGE_SITEMAP_CACHE[0] < 300:
        return Response(
            VERNISSAGE_SITEMAP_CACHE[1], media_type="application/xml", headers={"Cache-Control": HTML_CACHE}
        )
    groups = (
        ("docent/notes", "docent/notes"),
        ("exhibitions?tab=ongoing", "exhibitions"),
        ("art-events?status=current", "art-events"),
    )
    entries: list[tuple[str, str | None]] = []
    for endpoint, section in groups:
        page = 1
        while page <= 50:  # API의 비정상적인 has_next 응답으로 무한 요청하지 않는다.
            page_endpoint = endpoint if page == 1 else f"{endpoint}{'&' if '?' in endpoint else '?'}page={page}"
            data, status = await _vernissage_public_json(request, page_endpoint, "ko")
            if data is None or status != 200:
                return None
            for item in data.get("items", []):
                if not isinstance(item, dict) or not item.get("id"):
                    continue
                modified = str(item.get("updated_at") or item.get("published_at") or "")[:10] or None
                for prefix in ("", "en/", "ja/"):
                    entries.append((f"{prefix}{section}/{item['id']}", modified))
            if not data.get("has_next"):
                break
            page += 1
    static = (
        "",
        "en/",
        "ja/",
        "legal/terms-of-service",
        "legal/privacy-policy",
        "legal/account-deletion",
        "en/legal/terms-of-service",
        "en/legal/privacy-policy",
        "en/legal/account-deletion",
    )
    rows = []
    for path in static:
        rows.append(f"  <url><loc>{html.escape(_public_url(path))}</loc></url>")
    for path, modified in entries:
        lastmod = f"<lastmod>{modified}</lastmod>" if modified else ""
        rows.append(f"  <url><loc>{html.escape(_public_url(path))}</loc>{lastmod}</url>")
    xml = (
        '<?xml version="1.0" encoding="UTF-8"?>\n<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n'
        + "\n".join(rows)
        + "\n</urlset>\n"
    )
    VERNISSAGE_SITEMAP_CACHE = (time.monotonic(), xml)
    return Response(xml, media_type="application/xml", headers={"Cache-Control": HTML_CACHE})


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
        upstream = await _upstream_get(request, url, headers)
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

    if site == "vernissage" and url_path == "sitemap.xml" and (sitemap := await _vernissage_dynamic_sitemap(request)):
        return sitemap

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

    legal_document = await _proxy_legal_document(request, site, url_path)
    if legal_document is not None:
        return legal_document

    if site == "vernissage" and (seo_detail := await _vernissage_seo_detail(request, site_dir, url_path)):
        return seo_detail

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
