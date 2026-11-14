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
    /legal/...            -> Vernissage는 앱 백엔드가 소유한 법률 문서 프록시,
                             Keepsake는 sites/keepsake/legal/의 정적 HTML
    /assets/icon.png      -> assets/icon.png
    /shared/...           -> sites/shared/ 아래 공통 정적 자산

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
SHARED_DIR = (SITES_DIR / "shared").resolve()

# Vernissage 공개 웹 데이터는 별도 프로젝트의 API가 소유한다. 페이지는 이 서버와
# 같은 origin의 /api/vernissage/public-web/...만 호출하므로, 브라우저에 API의 내부
# 주소나 PUBLIC_WEB_API_TOKEN을 노출하지 않는다.
VERNISSAGE_API_BASE_URL = os.environ.get("VERNISSAGE_API_BASE_URL", "").rstrip("/")
VERNISSAGE_PUBLIC_WEB_API_TOKEN = os.environ.get("VERNISSAGE_PUBLIC_WEB_API_TOKEN", "")


def _env_fingerprints(name: str) -> tuple[str, ...]:
    return tuple(
        fingerprint.strip().upper() for fingerprint in os.environ.get(name, "").split(",") if fingerprint.strip()
    )


# Android App Links는 Google Play 앱 서명 인증서의 SHA-256 지문을 요구한다. 업로드 키는
# 서명 키와 다를 수 있으므로 저장소에 고정하지 않고 Railway 환경 변수에서 받는다. 앱마다 서명 키가 다르다.
VERNISSAGE_ANDROID_APP_LINK_SHA256_CERT_FINGERPRINTS = _env_fingerprints("ANDROID_APP_LINK_SHA256_CERT_FINGERPRINTS")
KEEPSAKE_ANDROID_APP_LINK_SHA256_CERT_FINGERPRINTS = _env_fingerprints(
    "KEEPSAKE_ANDROID_APP_LINK_SHA256_CERT_FINGERPRINTS"
)
# Apple Team ID는 공개 식별자지만, 환경별로 바꿀 여지를 위해 변수로 둔다. 두 앱이 같은 팀에 있다.
APPLE_APP_LINK_TEAM_ID = os.environ.get("APPLE_APP_LINK_TEAM_ID", "3BQ7Y687R9").strip().upper()
VERNISSAGE_APP_ID = "com.atelierlabs.vernissage"
KEEPSAKE_APP_ID = "com.atelierlabs.keepsake"
# mobile/app.json의 Android intentFilters와 같은 경로를 유지한다. 앱에는 상세 화면만 있으므로
# 목록(/exhibitions 등)은 웹에 남기고 상세(/exhibitions/<id>)만 앱으로 연다. 언어 접두사는
# 앱의 +native-intent.tsx가 떼어낸다.
VERNISSAGE_APP_LINK_PREFIXES = (
    "exhibitions",
    "museums",
    "artworks",
    "artists",
    "art-concepts",
    "art-figures",
    "art-events",
    "docent/notes",
)
# 웹에 페이지가 없고 앱에만 있는 상세 화면. 앱이 없는 사람에게는 설치 안내(get-app)를 보여준다.
VERNISSAGE_APP_ONLY_PREFIXES = ("museums", "artworks", "artists", "art-concepts", "art-figures")
# keytool/Play Console 형식: 콜론으로 구분한 32바이트 16진수(대문자).
SHA256_CERT_FINGERPRINT = re.compile(r"(?:[0-9A-F]{2}:){31}[0-9A-F]{2}")
APPLE_TEAM_ID = re.compile(r"[A-Z0-9]{10}")

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
# "?*"는 한 글자 이상: 상세 id 없는 /exhibitions/는 앱에 화면이 없으므로 웹에 남긴다
# (mobile/app.json의 pathPattern "/exhibitions/..*"와 같은 범위).
VERNISSAGE_APP_LINK_PATHS = tuple(
    f"/{lang}{prefix}/?*" for lang in ("", *(f"{code}/" for code in LANGS)) for prefix in VERNISSAGE_APP_LINK_PREFIXES
)
# Keepsake는 공유 앨범 초대 링크(/join?code=…)만 앱으로 연다. mobile/app.json의 Android intentFilters와
# 같은 경로다. 앱이 없으면 join.html이 초대 코드와 참여 방법을 보여준다.
KEEPSAKE_APP_LINK_PATHS = tuple(f"/{lang}join" for lang in ("", *(f"{code}/" for code in LANGS)))

# Vernissage 공개 데이터 화면은 하나의 작은 클라이언트 앱이 목록·상세 경로를 모두 렌더링한다.
# 정적 파일 규칙으로는 /exhibitions/123 같은 동적 상세 경로를 찾을 수 없어서 여기서 shell을 준다.
VERNISSAGE_PUBLIC_WEB_PREFIXES = ("docent/notes", "exhibitions", "art-events")
VERNISSAGE_CLIENT_API_PATHS = {"test", "score", "web-events"}
VERNISSAGE_SEO_DETAIL = re.compile(r"^(?:(en|ja)/)?(docent/notes|exhibitions|art-events)/(\d+)$")

HTML_CACHE = "public, max-age=300"
ASSET_CACHE = "public, max-age=86400"
VERNISSAGE_SITEMAP_CACHE: tuple[float, str] | None = None


def _env_int(name: str, default: int, minimum: int = 0) -> int:
    """잘못된 운영 환경 변수 하나가 앱 시작 전체를 막지 않게 한다."""
    try:
        return max(minimum, int(os.environ.get(name, default)))
    except ValueError:
        return default


# 공개 API는 검색 엔진·링크 미리보기·카드 렌더링이 같은 데이터를 반복 요청한다. 응답을
# 짧게 공유해 원본 API와 이미지 메타데이터 조회가 요청 수만큼 늘지 않게 한다.
VERNISSAGE_PUBLIC_API_CACHE_SECONDS = _env_int("VERNISSAGE_PUBLIC_API_CACHE_SECONDS", 300)
VERNISSAGE_PUBLIC_API_REQUESTS_PER_MINUTE = _env_int("VERNISSAGE_PUBLIC_API_REQUESTS_PER_MINUTE", 120, 1)
VERNISSAGE_DETAIL_REQUESTS_PER_MINUTE = _env_int("VERNISSAGE_DETAIL_REQUESTS_PER_MINUTE", 60, 1)
PUBLIC_API_CACHE_MAX_ENTRIES = 256
PUBLIC_API_CACHE_MAX_BYTES = 1_000_000
PUBLIC_API_RESPONSE_CACHE: dict[tuple[str, str, str], tuple[float, bytes, int, dict[str, str]]] = {}
REQUEST_WINDOWS: dict[tuple[str, str], tuple[float, int]] = {}


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


def _app_link_association(site: str, url_path: str) -> Response | None:
    """앱 사이트(Vernissage·Keepsake)의 App Links/Universal Links 도메인 소유 선언을 반환한다.

    검증 파일은 리다이렉트 없이 HTTPS 루트의 ``/.well-known/``에서 제공해야 한다.
    설정이 없거나 형식이 틀린 배포를 성공처럼 보이지 않게 503으로 명시한다.
    """
    # 지문은 테스트가 바꿔 끼울 수 있게 요청 때 모듈 변수에서 읽는다.
    if site == "vernissage":
        app_id, paths = VERNISSAGE_APP_ID, VERNISSAGE_APP_LINK_PATHS
        fingerprints, fingerprints_env = (
            VERNISSAGE_ANDROID_APP_LINK_SHA256_CERT_FINGERPRINTS,
            "ANDROID_APP_LINK_SHA256_CERT_FINGERPRINTS",
        )
    elif site == "keepsake":
        app_id, paths = KEEPSAKE_APP_ID, KEEPSAKE_APP_LINK_PATHS
        fingerprints, fingerprints_env = (
            KEEPSAKE_ANDROID_APP_LINK_SHA256_CERT_FINGERPRINTS,
            "KEEPSAKE_ANDROID_APP_LINK_SHA256_CERT_FINGERPRINTS",
        )
    else:
        return None

    if url_path == ".well-known/assetlinks.json":
        if not fingerprints:
            return _misconfigured(f"{fingerprints_env} is not configured")
        # 형식이 틀린 지문이 하나라도 섞이면 검증이 조용히 실패하므로 전체를 거부한다.
        if not all(SHA256_CERT_FINGERPRINT.fullmatch(fingerprint) for fingerprint in fingerprints):
            return _misconfigured(f"{fingerprints_env} is invalid")
        body: object = [
            {
                "relation": ["delegate_permission/common.handle_all_urls"],
                "target": {
                    "namespace": "android_app",
                    "package_name": app_id,
                    "sha256_cert_fingerprints": list(fingerprints),
                },
            }
        ]
    elif url_path == ".well-known/apple-app-site-association":
        team_id = APPLE_APP_LINK_TEAM_ID
        if not team_id:
            return _misconfigured("APPLE_APP_LINK_TEAM_ID is not configured")
        if not APPLE_TEAM_ID.fullmatch(team_id):
            return _misconfigured("APPLE_APP_LINK_TEAM_ID is invalid")
        body = {
            "applinks": {
                "apps": [],
                "details": [
                    {
                        "appID": f"{team_id}.{app_id}",
                        "paths": list(paths),
                    }
                ],
            }
        }
    else:
        return None
    return Response(content=json.dumps(body), media_type="application/json", headers={"Cache-Control": HTML_CACHE})


def _misconfigured(message: str) -> Response:
    return PlainTextResponse(message, status_code=503, headers={"Cache-Control": "no-store"})


def _split_lang(url_path: str) -> tuple[str, str]:
    """``en/foo`` -> (``en``, ``foo``), ``foo`` -> (``""``, ``foo``)."""
    lang, _, rest = url_path.partition("/")
    return (lang, rest) if lang in LANGS else ("", url_path)


def _under_prefix(rel: str, prefixes: tuple[str, ...]) -> bool:
    return any(rel == prefix or rel.startswith(prefix + "/") for prefix in prefixes)


def _vernissage_public_shell(site_dir: Path, url_path: str) -> Path | None:
    """공개 데이터 화면 경로면 그 언어의 client shell(/public/index.html, /<lang>/public/index.html)."""
    lang_dir, rel = _split_lang(url_path)
    if rel != "art-taste-test" and not _under_prefix(rel, VERNISSAGE_PUBLIC_WEB_PREFIXES):
        return None
    shell = site_dir / lang_dir / "public" / "index.html"
    return shell if shell.is_file() else None


def _vernissage_get_app_page(site_dir: Path, url_path: str) -> Path | None:
    """앱에만 있는 화면(작가·작품·미술관 등) 링크를 앱 없이 열면 그 언어의 설치 안내 페이지."""
    lang_dir, rel = _split_lang(url_path)
    if not _under_prefix(rel, VERNISSAGE_APP_ONLY_PREFIXES):
        return None
    page = site_dir / lang_dir / "get-app.html"
    return page if page.is_file() else None


def _vernissage_api_headers(request: Request) -> dict[str, str]:
    """공개 JSON API에 필요한 고정 Accept·안전한 언어 헤더만 원본으로 전달한다."""
    headers = {"Accept": "application/json"}
    lang = request.headers.get("x-app-language", "").strip().lower()
    if lang in ("ko", *LANGS):
        headers["X-App-Language"] = lang
    return headers


def _client_ip(request: Request) -> str:
    """Uvicorn이 신뢰 프록시 헤더를 처리한 뒤의 연결 IP를 사용한다."""
    return request.client.host if request.client else "unknown"


def _rate_limit(request: Request, scope: str, maximum: int) -> Response | None:
    """인스턴스 단위의 고정 윈도우 제한. CDN/WAF가 없는 경우의 원본 API 안전망이다."""
    now = time.monotonic()
    key = (scope, _client_ip(request))
    started, count = REQUEST_WINDOWS.get(key, (now, 0))
    if now - started >= 60:
        started, count = now, 0
    if count >= maximum:
        return PlainTextResponse(
            "Too Many Requests", status_code=429, headers={"Cache-Control": "no-store", "Retry-After": "60"}
        )
    REQUEST_WINDOWS[key] = (started, count + 1)
    # IP를 바꿔가며 요청해도 메모리가 끝없이 자라지 않도록 지난 윈도우를 정리한다.
    if len(REQUEST_WINDOWS) > 2048:
        active = {window_key: value for window_key, value in REQUEST_WINDOWS.items() if now - value[0] < 60}
        REQUEST_WINDOWS.clear()
        REQUEST_WINDOWS.update(active)
        while len(REQUEST_WINDOWS) > 2048:
            REQUEST_WINDOWS.pop(next(iter(REQUEST_WINDOWS)))
    return None


def _cache_get(key: tuple[str, str, str]) -> tuple[bytes, int, dict[str, str]] | None:
    cached = PUBLIC_API_RESPONSE_CACHE.get(key)
    if not cached or time.monotonic() - cached[0] >= VERNISSAGE_PUBLIC_API_CACHE_SECONDS:
        PUBLIC_API_RESPONSE_CACHE.pop(key, None)
        return None
    # dict 삽입 순서를 최근 사용 순서로 유지해 용량 초과 시 가장 오래 안 쓰인 항목을 버린다.
    PUBLIC_API_RESPONSE_CACHE.pop(key)
    PUBLIC_API_RESPONSE_CACHE[key] = cached
    _, content, status, headers = cached
    return content, status, headers.copy()


def _cache_put(key: tuple[str, str, str], content: bytes, status: int, headers: dict[str, str]) -> None:
    """작고 cacheable한 성공 응답만 제한된 LRU 캐시에 보관한다."""
    if status != 200 or not VERNISSAGE_PUBLIC_API_CACHE_SECONDS or len(content) > PUBLIC_API_CACHE_MAX_BYTES:
        return
    if "no-store" in headers.get("cache-control", "").lower():
        return
    now = time.monotonic()
    for stale_key, stale in tuple(PUBLIC_API_RESPONSE_CACHE.items()):
        if now - stale[0] >= VERNISSAGE_PUBLIC_API_CACHE_SECONDS:
            PUBLIC_API_RESPONSE_CACHE.pop(stale_key)
    PUBLIC_API_RESPONSE_CACHE.pop(key, None)
    while len(PUBLIC_API_RESPONSE_CACHE) >= PUBLIC_API_CACHE_MAX_ENTRIES:
        PUBLIC_API_RESPONSE_CACHE.pop(next(iter(PUBLIC_API_RESPONSE_CACHE)))
    PUBLIC_API_RESPONSE_CACHE[key] = (now, content, status, headers.copy())


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

    Vernissage 약관 원문은 앱 백엔드가 소유한다. Keepsake 약관은 이 저장소의
    sites/keepsake/legal/이 원본이라 프록시하지 않고 정적 파일로 보여준다.
    일본어 법률 문서는 기존처럼 영어판으로 리다이렉트된 뒤 이 함수에 도달한다.
    """
    if site != "vernissage":
        return None

    language = "ko"
    document_path = url_path
    if document_path.startswith("en/"):
        language = "en"
        document_path = document_path[3:]

    if document_path not in ("legal/terms-of-service", "legal/privacy-policy"):
        return None
    document = document_path.rsplit("/", 1)[1]
    return (VERNISSAGE_API_BASE_URL, VERNISSAGE_PUBLIC_WEB_API_TOKEN, f"legal/{language}/{document}")


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
    endpoint_path, _, query = endpoint.partition("?")
    cache_key = (endpoint_path, query, language)
    if cached := _cache_get(cache_key):
        try:
            return json.loads(cached[0]), cached[1]
        except (TypeError, ValueError):
            PUBLIC_API_RESPONSE_CACHE.pop(cache_key, None)
    headers = {"Accept": "application/json", "X-App-Language": language}
    if VERNISSAGE_PUBLIC_WEB_API_TOKEN:
        headers["X-Public-Web-Token"] = VERNISSAGE_PUBLIC_WEB_API_TOKEN
    try:
        url = httpx.URL(f"{VERNISSAGE_API_BASE_URL}/public-web/{endpoint_path}")
        if query:
            url = httpx.URL(str(url), query=query.encode("utf-8"))
        response = await _upstream_get(request, url, headers)
    except httpx.HTTPError:
        return None, 502
    if response.status_code != 200:
        return None, response.status_code
    try:
        data = response.json()
    except ValueError:
        return None, 502
    _cache_put(
        cache_key,
        response.content,
        response.status_code,
        {
            **{
                name: response.headers[name]
                for name in ("content-type", "cache-control", "etag", "last-modified")
                if name in response.headers
            },
            "vary": _vary_with_language(response.headers.get("vary")),
        },
    )
    return data, 200


def _seo_text(value: object, limit: int = 160) -> str:
    text = re.sub(r"\s+", " ", str(value or "")).strip()
    return text if len(text) <= limit else f"{text[: limit - 1].rstrip()}…"


DOCENT_CARD_PATHS = {
    "artwork": "artworks",
    "artist": "artists",
    "art_concept": "art-concepts",
    "art_figure": "art-figures",
    "museum": "museums",
    "exhibition": "exhibitions",
    "art_event": "art-events",
}
DOCENT_CARD_KINDS = "|".join(DOCENT_CARD_PATHS)
DOCENT_EMBED = re.compile(
    r"!\[([^]]*)\]\((https?://[^\s)]+)\)|"
    rf"\[\[cards:((?:(?:{DOCENT_CARD_KINDS}):\d+)(?:,(?:{DOCENT_CARD_KINDS}):\d+)*)\]\]|"
    r"\[\[image:(https?://[^\]|]+)(?:\|([^]]*))?\]\]"
)
DOCENT_IMAGE_GROUP = re.compile(r'(?:<figure class="docent-image">(?:(?!</figure>).)*</figure>(?:<br />)*){2,}', re.S)
DOCENT_IMAGE = re.compile(r'<figure class="docent-image">(?:(?!</figure>).)*</figure>', re.S)
DOCENT_BOLD = re.compile(r"\*\*([^*\n](?:[^*\n]|\*(?!\*))*)\*\*")


def _docent_plain_text(content: object) -> str:
    """검색 설명에는 편집기 문법 대신 사람이 읽을 수 있는 텍스트만 넣는다."""
    text = DOCENT_EMBED.sub(lambda match: match.group(1) or match.group(5) or "작품", str(content or ""))
    return DOCENT_BOLD.sub(r"\1", text)


def _render_docent_text(text: str) -> str:
    """HTML은 이스케이프한 뒤 지원하는 강조 문법만 안전한 태그로 바꾼다."""
    escaped = html.escape(text)
    return DOCENT_BOLD.sub(r"<strong>\1</strong>", escaped).replace("\n", "<br />")


def _render_docent_content(content: object) -> str:
    """도슨트 편집기가 저장한 이미지·작품 카드 문법만 안전한 HTML로 출력한다."""
    text = str(content or "")
    rendered: list[str] = []
    cursor = 0
    for match in DOCENT_EMBED.finditer(text):
        rendered.append(_render_docent_text(text[cursor : match.start()]))
        alt, image_url, cards, embedded_image_url, caption = match.groups()
        if image_url:
            rendered.append(
                f'<figure class="docent-image"><img src="{html.escape(image_url, quote=True)}" '
                f'alt="{html.escape(alt or "", quote=True)}" loading="lazy" /></figure>'
            )
        elif cards:
            card_html: list[str] = []
            for reference in cards.split(","):
                kind, item_id = reference.split(":", 1)
                path = DOCENT_CARD_PATHS[kind]
                card_html.append(
                    f'<a class="docent-card" data-docent-card-kind="{kind}" data-docent-card-id="{item_id}" '
                    f'href="/{path}/{item_id}"><span class="docent-card-image" '
                    'aria-hidden="true"></span>'
                    '<span class="docent-card-copy">자세히 보기</span></a>'
                )
            if len(card_html) > 1:
                cards_html = "".join(card_html)
                rendered.append(f'<div class="docent-card-grid" data-count="{len(card_html)}">{cards_html}</div>')
            else:
                rendered.append(card_html[0])
        else:
            rendered.append(
                f'<figure class="docent-image"><img src="{html.escape(embedded_image_url, quote=True)}" '
                f'alt="{html.escape(caption or "", quote=True)}" loading="lazy" />'
                f"{f'<figcaption>{html.escape(caption)}</figcaption>' if caption else ''}</figure>"
            )
        cursor = match.end()
    rendered.append(_render_docent_text(text[cursor:]))

    def group_images(match: re.Match[str]) -> str:
        images = DOCENT_IMAGE.findall(match.group())
        return f'<div class="docent-image-grid" data-count="{len(images)}">{"".join(images)}</div>'

    return DOCENT_IMAGE_GROUP.sub(group_images, "".join(rendered))


def _public_url(path: str) -> str:
    return f"https://vernissage.{ROOT_DOMAIN}/{path.lstrip('/')}"


def _render_vernissage_detail_shell(
    site_dir: Path,
    language: str,
    path: str,
    title: str,
    description: str,
    body: str,
    image: str | None,
    schema: dict,
    og_type: str = "article",
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
            f'<meta property="og:type" content="{og_type}" />',
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
    if limited := _rate_limit(request, "vernissage-detail", VERNISSAGE_DETAIL_REQUESTS_PER_MINUTE):
        return limited
    language = match.group(1) or "ko"
    section, item_id = match.group(2), match.group(3)
    data, status = await _vernissage_public_json(request, f"{section}/{item_id}", language)
    if data is None:
        # 실제로 존재하지 않는 콘텐츠만 404로 응답해 soft 404를 만들지 않는다.
        if status in (404, 410):
            return PlainTextResponse("Not Found", status_code=404)
        return _vernissage_unavailable_shell(site_dir, language)
    item = data.get({"docent/notes": "note", "exhibitions": "exhibition", "art-events": "event"}[section])
    if not isinstance(item, dict):
        return PlainTextResponse("Not Found", status_code=404)
    series = item.get("series") if isinstance(item.get("series"), dict) else {}
    title = _seo_text(item.get("display_title") or item.get("title") or series.get("name"), 180)
    if not title:
        return PlainTextResponse("Not Found", status_code=404)
    if section != "docent/notes":
        # 수집처에 따라 설명 칸에 "2026.10.24 ~ 2026.10.24" 같은 날짜만 들어오는 경우가 있다.
        # 그런 값은 검색 설명·본문으로 쓰지 않고 장소·기간으로 만든 설명을 쓴다.
        item = {**item, "description": _meaningful_text(item.get("description"))}
        series = {**series, "description": _meaningful_text(series.get("description"))}
    description_source = (
        item.get("excerpt")
        or item.get("description")
        or item.get("content")
        or series.get("description")
        or (_event_summary(title, item, series) if section != "docent/notes" else title)
    )
    description = _seo_text(_docent_plain_text(description_source) if section == "docent/notes" else description_source)
    image = item.get("thumbnail_url") or item.get("image_url") or series.get("thumbnail_url")
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
        schema = _event_schema(section, item, series, title, description, image, _public_url(url_path))
    content_html = (
        _render_docent_content(content)
        if section == "docent/notes"
        else html.escape(str(content)).replace("\n", "<br />")
    )
    image_url = html.escape(str(image), quote=True)
    escaped_title = html.escape(title, quote=True)
    image_html = f'<img class="detail-image" src="{image_url}" alt="{escaped_title}" />' if image else ""
    body = "".join(
        (
            '<article class="detail">',
            f"<h1>{html.escape(title)}</h1>",
            image_html,
            f'<div class="detail-text{(" docent-content" if section == "docent/notes" else "")}">{content_html}</div>',
            "</article>",
        )
    )
    return HTMLResponse(
        _render_vernissage_detail_shell(site_dir, language, url_path, title, description, body, image, schema),
        headers={"Cache-Control": HTML_CACHE},
    )


def _meaningful_text(value: object) -> str:
    """글자 없이 숫자·기호(날짜, 물결표 등)만 있는 설명은 빈 값으로 본다."""
    text = re.sub(r"\s+", " ", str(value or "")).strip()
    return text if re.search(r"[^\W\d_]", text) else ""


def _event_place(item: dict, series: dict) -> tuple[str, str]:
    """(도시, 나라) — 회차에 없으면 시리즈의 개최지를 쓴다."""
    return (
        str(item.get("city") or series.get("home_city") or ""),
        str(item.get("country") or series.get("home_country") or ""),
    )


def _event_summary(title: str, item: dict, series: dict) -> str:
    museum = item.get("museum") if isinstance(item.get("museum"), dict) else {}
    place = museum.get("name") or item.get("place_name") or ", ".join(filter(None, _event_place(item, series)))
    period = " ~ ".join(str(item.get(key))[:10] for key in ("start_date", "end_date") if item.get(key))
    return " · ".join(filter(None, (title, str(place or ""), period)))


def _drop_empty(value: object) -> object:
    """구조화 데이터에서 값이 없는 필드는 빼야 Google이 잘못된 값으로 읽지 않는다."""
    if isinstance(value, dict):
        cleaned = {key: _drop_empty(item) for key, item in value.items()}
        return {key: item for key, item in cleaned.items() if item not in (None, "", [], {})}
    return value


def _event_location(section: str, item: dict, series: dict) -> dict | None:
    """Google Event 구조화 데이터의 필수 항목인 location(Place + address)."""
    if section == "exhibitions":
        museum = item.get("museum") if isinstance(item.get("museum"), dict) else {}
        name = museum.get("name") or item.get("place_name") or item.get("institution_name")
        address = museum.get("address") or museum.get("city")
        geo = (
            {"@type": "GeoCoordinates", "latitude": museum["latitude"], "longitude": museum["longitude"]}
            if museum.get("latitude") is not None and museum.get("longitude") is not None
            else None
        )
        if not (name and address):
            return None
        return {
            "@type": "Place",
            "name": name,
            "address": {
                "@type": "PostalAddress",
                "streetAddress": museum.get("address"),
                "addressLocality": museum.get("city"),
            },
            "geo": geo,
            "url": museum.get("website"),
        }
    venues = [venue for venue in item.get("venues") or [] if isinstance(venue, dict)]
    venue = venues[0] if venues else {}
    city, country = _event_place(item, series)
    if not (city or country or venue.get("address")):
        return None
    return {
        "@type": "Place",
        "name": venue.get("name") or ", ".join(filter(None, (city, country))),
        "address": {
            "@type": "PostalAddress",
            "streetAddress": venue.get("address"),
            "addressLocality": city,
            "addressCountry": item.get("country_code") or country,
        },
    }


def _event_schema(
    section: str, item: dict, series: dict, title: str, description: str, image: object, url: str
) -> dict:
    """전시·아트이벤트 상세의 JSON-LD. 장소나 시작일을 알 수 없으면 Event 필수 항목(location, startDate)을
    채울 수 없으므로 잘못된 Event 대신 WebPage로 내보낸다(예: 날짜 미발표인 다음 회차)."""
    location = _event_location(section, item, series) if item.get("start_date") else None
    if location is None:
        return _drop_empty(
            {
                "@context": "https://schema.org",
                "@type": "WebPage",
                "name": title,
                "description": description,
                "url": url,
            }
        )
    if section == "exhibitions":
        museum = item.get("museum") if isinstance(item.get("museum"), dict) else {}
        organizer = {
            "@type": "Organization",
            "name": item.get("institution_name") or museum.get("name"),
            "url": museum.get("website"),
        }
        event_type = "ExhibitionEvent"
    else:
        organizer = {"@type": "Organization", "name": series.get("organizer")}
        event_type = "Event"
    return _drop_empty(
        {
            "@context": "https://schema.org",
            "@type": event_type,
            "name": title,
            "description": description,
            "image": image,
            "startDate": item.get("start_date"),
            "endDate": item.get("end_date"),
            "eventStatus": "https://schema.org/EventScheduled",
            "eventAttendanceMode": "https://schema.org/OfflineEventAttendanceMode",
            "location": location,
            "organizer": organizer if organizer.get("name") else None,
            "url": url,
        }
    )


def _vernissage_unavailable_shell(site_dir: Path, language: str) -> Response | None:
    """공개 API 장애 시 noindex 셸을 200으로 주면 검색엔진이 정상 페이지를 색인에서 뺀다.
    503으로 응답해 크롤러는 나중에 다시 오게 하고, 사람에게는 셸이 브라우저에서 다시 시도하게 한다.
    API 주소가 없는 로컬 개발 환경만 기존처럼 클라이언트 셸(200)을 준다."""
    if not VERNISSAGE_API_BASE_URL:
        return None
    lang_dir = language if language in LANGS else ""
    shell = site_dir / lang_dir / "public" / "index.html"
    return HTMLResponse(
        shell.read_text(encoding="utf-8"),
        status_code=503,
        headers={"Cache-Control": "no-store", "Retry-After": "120"},
    )


# 목록·취향 테스트 화면의 서버 렌더링 문구(ko/en/ja). h1·intro는 public.js의 T와 같은 문구라
# 브라우저에서 셸 앱이 화면을 다시 그려도 내용이 바뀌지 않는다.
VERNISSAGE_LISTING_COPY: dict[str, dict[str, dict]] = json.loads(
    (Path(__file__).with_name("vernissage_listing_copy.json")).read_text(encoding="utf-8")
)
VERNISSAGE_SEO_LISTING = re.compile(r"^(?:(en|ja)/)?(docent/notes|exhibitions|art-events|art-taste-test)$")
VERNISSAGE_LISTING_ENDPOINTS = {
    "docent/notes": "docent/notes",
    "exhibitions": "exhibitions?tab=ongoing",
    "art-events": "art-events?status=current",
}


def _listing_card(section: str, item: dict, prefix: str) -> tuple[str, str, str] | None:
    """목록 항목 하나를 (제목, id, 카드 HTML)로. 상세 링크를 만들 수 없는 항목은 건너뛴다."""
    item_id = item.get("id")
    if not isinstance(item_id, int) and not str(item_id or "").isdigit():
        return None
    series = item.get("series") if isinstance(item.get("series"), dict) else {}
    museum = item.get("museum") if isinstance(item.get("museum"), dict) else {}
    title = _seo_text(item.get("display_title") or item.get("title") or series.get("name"), 180)
    if not title:
        return None
    period = " — ".join(str(item.get(key) or "")[:10] for key in ("start_date", "end_date") if item.get(key))
    if section == "docent/notes":
        meta = " · ".join(filter(None, (str(item.get("entity_label") or ""), str(item.get("published_at") or "")[:10])))
        image = item.get("thumbnail_url")
        extra = (
            f"<p>{html.escape(_seo_text(_docent_plain_text(item.get('excerpt'))))}</p>" if item.get("excerpt") else ""
        )
    elif section == "exhibitions":
        meta = " · ".join(filter(None, (str(museum.get("name") or item.get("place_name") or ""), period)))
        image, extra = item.get("image_url"), ""
    else:
        place = " · ".join(
            str(value)
            for value in (
                item.get("city") or series.get("home_city"),
                item.get("country") or series.get("home_country"),
            )
            if value
        )
        meta = " · ".join(filter(None, (place, period)))
        image, extra = item.get("image_url"), ""
    thumb = (
        f'<img class="thumb" src="{html.escape(str(image), quote=True)}" alt="" loading="lazy" />'
        if image
        else '<span class="thumb"></span>'
    )
    return (
        title,
        str(item_id),
        (
            f'<a class="card" href="{prefix}/{section}/{item_id}">{thumb}<div class="body">'
            f'<p class="meta">{html.escape(meta)}</p><h2>{html.escape(title)}</h2>{extra}</div></a>'
        ),
    )


async def _vernissage_seo_listing(request: Request, site_dir: Path, url_path: str) -> Response | None:
    """도슨트·전시·행사 목록과 취향 테스트 첫 화면을 크롤러가 바로 읽을 수 있게 서버에서 그린다."""
    match = VERNISSAGE_SEO_LISTING.fullmatch(url_path)
    if not match:
        return None
    language = match.group(1) or "ko"
    section = match.group(2)
    prefix = "" if language == "ko" else f"/{language}"
    copy = VERNISSAGE_LISTING_COPY[section][language]
    page_url = _public_url(url_path)
    if section == "art-taste-test":
        tips = "".join(f"<li>{html.escape(tip)}</li>" for tip in copy["tips"])
        # lead 문구의 <br />만 신뢰하는 고정 문구다(사용자 입력 아님).
        body = (
            '<section class="quiz taste-intro"><p class="highlight-label">ART TASTE TEST</p>'
            f"<h1>{html.escape(copy['heading'])}</h1>"
            f'<p class="taste-question">{html.escape(copy["question"])}</p>'
            f'<p class="intro">{copy["lead1"]}</p><p class="intro">{copy["lead2"]}</p>'
            f'<div class="taste-guide"><h2>{html.escape(copy["tips_title"])}</h2><ul>{tips}</ul></div></section>'
        )
        title = f"{copy['title']} — {copy['heading']}"
        schema = {
            "@context": "https://schema.org",
            "@type": "WebPage",
            "name": copy["title"],
            "description": copy["description"],
            "url": page_url,
            "inLanguage": language,
        }
    else:
        if limited := _rate_limit(request, "vernissage-detail", VERNISSAGE_DETAIL_REQUESTS_PER_MINUTE):
            return limited
        data, status = await _vernissage_public_json(request, VERNISSAGE_LISTING_ENDPOINTS[section], language)
        if data is None or status != 200:
            return _vernissage_unavailable_shell(site_dir, language)
        items = data.get("items") if isinstance(data.get("items"), list) else []
        cards = [card for item in items if isinstance(item, dict) and (card := _listing_card(section, item, prefix))]
        heading = f'<h2 class="listing-all-title">{html.escape(copy["heading"])}</h2>' if copy.get("heading") else ""
        grid = "".join(card for *_, card in cards)
        body = (
            f'<h1>{html.escape(copy["title"])}</h1><p class="intro">{html.escape(copy["intro"])}</p>'
            f'<section class="listing-all">{heading}<div class="grid">{grid}</div></section>'
        )
        title = copy["title"]
        schema = {
            "@context": "https://schema.org",
            "@type": "CollectionPage",
            "name": copy["title"],
            "description": copy["description"],
            "url": page_url,
            "inLanguage": language,
            "mainEntity": {
                "@type": "ItemList",
                "itemListElement": [
                    {"@type": "ListItem", "position": index, "name": name, "url": _public_url(f"{url_path}/{item_id}")}
                    for index, (name, item_id, _) in enumerate(cards[:50], start=1)
                ],
            },
        }
    return HTMLResponse(
        _render_vernissage_detail_shell(
            site_dir, language, url_path, title, copy["description"], body, None, schema, og_type="website"
        ),
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
        "about",
        "en/about",
        "ja/about",
        *(
            f"{prefix}{section}"
            for section in ("docent/notes", "exhibitions", "art-events", "art-taste-test")
            for prefix in ("", "en/", "ja/")
        ),
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
    if limited := _rate_limit(request, "vernissage-public-api", VERNISSAGE_PUBLIC_API_REQUESTS_PER_MINUTE):
        return limited

    requested_language = request.headers.get("x-app-language", "").strip().lower()
    language = requested_language if requested_language in ("ko", *LANGS) else ""
    cache_key = (api_path, request.url.query, language)
    if cached := _cache_get(cache_key):
        content, status, headers = cached
        return Response(content=content, status_code=status, headers=headers)

    url = httpx.URL(f"{VERNISSAGE_API_BASE_URL}/public-web/{api_path}", query=request.url.query.encode("utf-8"))
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
    if upstream.status_code == 200:
        _cache_put(cache_key, upstream.content, upstream.status_code, response_headers)
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

    # 사이트 구분 없이 같은 공통 스타일·자산을 제공한다.
    if url_path.startswith("shared/"):
        path = resolve_file(SHARED_DIR, url_path.removeprefix("shared/"))
        if path is None:
            return PlainTextResponse("Not Found", status_code=404)
        return FileResponse(path, headers={"Cache-Control": ASSET_CACHE})

    if site == "vernissage" and url_path == "sitemap.xml" and (sitemap := await _vernissage_dynamic_sitemap(request)):
        return sitemap

    if association := _app_link_association(site, url_path):
        return association

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

    if site == "vernissage" and (seo_listing := await _vernissage_seo_listing(request, site_dir, url_path)):
        return seo_listing

    path = resolve_file(site_dir, url_path)
    if path is None:
        shell = (
            _vernissage_public_shell(site_dir, url_path) or _vernissage_get_app_page(site_dir, url_path)
            if site == "vernissage"
            else None
        )
        if shell is None:
            return _not_found(site_dir, url_path, _local_origin_rewriter(request))
        path = shell

    cache = HTML_CACHE if path.suffix == ".html" else ASSET_CACHE
    if path.suffix == ".html" and (rewrite := _local_origin_rewriter(request)):
        return HTMLResponse(rewrite(path.read_text(encoding="utf-8")), headers={"Cache-Control": "no-store"})
    return FileResponse(path, headers={"Cache-Control": cache})
