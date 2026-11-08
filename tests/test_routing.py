import httpx
import pytest
from fastapi.testclient import TestClient

import app.main as main
from app.main import app

client = TestClient(app)


def get(path: str, host: str, **kwargs):
    return client.get(path, headers={"host": host}, follow_redirects=False, **kwargs)


@pytest.mark.parametrize(
    ("host", "marker"),
    [
        ("atelierlabs.co.kr", "<title>Atelier Labs"),
        ("vernissage.atelierlabs.co.kr", "<title>Vernissage"),
        ("keepsake.atelierlabs.co.kr", "<title>Keepsake"),
        ("vernissage.localhost:8000", "<title>Vernissage"),
        ("localhost:8000", "<title>Atelier Labs"),
        ("something.up.railway.app", "<title>Atelier Labs"),
    ],
)
def test_host_routing(host, marker):
    res = get("/", host)
    assert res.status_code == 200
    assert marker in res.text


def test_www_redirects_to_apex():
    res = get("/foo?x=1", "www.atelierlabs.co.kr")
    assert res.status_code == 301
    assert res.headers["location"] == "https://atelierlabs.co.kr/foo?x=1"


def test_unknown_subdomain_404():
    assert get("/", "nope.atelierlabs.co.kr").status_code == 404


@pytest.mark.parametrize(
    "path",
    [
        "/legal/terms-of-service",
        "/legal/privacy-policy",
        "/legal/account-deletion",
        "/en/legal/terms-of-service",
        "/en/legal/privacy-policy",
        "/en/legal/account-deletion",
    ],
)
def test_vernissage_legal_pages(monkeypatch, path):
    monkeypatch.setattr(main, "VERNISSAGE_API_BASE_URL", "")
    res = get(path, "vernissage.atelierlabs.co.kr")
    # 문서 원본은 별도 Vernissage 백엔드가 소유한다. 기본 테스트 환경에는 그
    # 백엔드가 없으므로 홈페이지가 올바르게 unavailable 상태를 돌려주는지만 본다.
    assert res.status_code == (503 if path.endswith(("terms-of-service", "privacy-policy")) else 200)


@pytest.mark.parametrize(
    ("host", "path"),
    [
        ("vernissage.localhost:8000", "/legal/terms-of-service"),
        ("keepsake.localhost:8000", "/legal/privacy-policy"),
    ],
)
def test_unconfigured_legal_document_apis_are_not_cached(monkeypatch, host, path):
    monkeypatch.setattr(main, "VERNISSAGE_API_BASE_URL", "")
    monkeypatch.setattr(main, "KEEPSAKE_API_BASE_URL", "")

    res = get(path, host)

    assert res.status_code == 503
    assert res.headers["cache-control"] == "no-store"


@pytest.mark.parametrize(
    ("host", "path", "lang"),
    [
        (host, path, lang)
        for host, paths in [
            ("atelierlabs.co.kr", ["/", "/support"]),
            ("vernissage.atelierlabs.co.kr", ["/"]),
            ("keepsake.atelierlabs.co.kr", ["/"]),
        ]
        for path in paths
        for lang in ("en", "ja")
    ],
)
def test_localized_pages(host, path, lang):
    res = get(f"/{lang}{path}", host)
    assert res.status_code == 200
    assert f'<html lang="{lang}">' in res.text


@pytest.mark.parametrize(
    ("path", "location"),
    [
        ("/jp/", "/ja/"),
        ("/jp/support", "/ja/support"),
        ("/legal/en/privacy-policy", "/en/legal/privacy-policy"),
        ("/ja/legal/terms-of-service", "/en/legal/terms-of-service"),
    ],
)
def test_language_redirects(path, location):
    res = get(path, "vernissage.atelierlabs.co.kr")
    assert res.status_code == 301
    assert res.headers["location"] == location


@pytest.mark.parametrize("path", ["/privacy", "/terms"])
def test_policy_hubs_ko_en_only(path):
    """개인정보 처리방침·이용약관 안내는 한국어·영어만 두고, 일본어는 영어판으로 보낸다."""
    assert '<html lang="ko">' in get(path, "atelierlabs.co.kr").text
    assert '<html lang="en">' in get(f"/en{path}", "atelierlabs.co.kr").text
    res = get(f"/ja{path}", "atelierlabs.co.kr")
    assert res.status_code == 301
    assert res.headers["location"] == f"/en{path}"


def test_localized_404():
    res = get("/ja/nope", "atelierlabs.co.kr")
    assert res.status_code == 404 and '<html lang="ja">' in res.text
    res = get("/en/nope", "atelierlabs.co.kr")
    assert res.status_code == 404 and '<html lang="en">' in res.text


def test_internal_links_resolve():
    """모든 사이트 HTML의 내부 링크(같은 사이트, 다른 서브도메인 포함)가 200 또는 301로 응답하는지."""
    import re
    from pathlib import Path

    from app.main import ROOT_DOMAIN, SITES, SITES_DIR

    hosts = {site: (f"{sub}.{ROOT_DOMAIN}" if sub else ROOT_DOMAIN) for sub, site in SITES.items()}
    broken = []
    for site, host in hosts.items():
        for html in (SITES_DIR / site).rglob("*.html"):
            for href in re.findall(r'(?:href|src)="([^"#]+)', html.read_text()):
                target_host = host
                if href.startswith("https://"):
                    m = re.match(r"https://([^/]+)(/.*)?$", href)
                    if not m or not m.group(1).endswith(ROOT_DOMAIN):
                        continue
                    target_host, href = m.group(1), m.group(2) or "/"
                elif not href.startswith("/"):
                    continue
                res = get(href.split("?")[0], target_host)
                is_unconfigured_legal_document = (
                    res.status_code == 503
                    and target_host in ("vernissage.atelierlabs.co.kr", "keepsake.atelierlabs.co.kr")
                    and href.split("?", 1)[0]
                    in (
                        "/legal/terms-of-service",
                        "/legal/privacy-policy",
                        "/en/legal/terms-of-service",
                        "/en/legal/privacy-policy",
                    )
                )
                if res.status_code not in (200, 301) and not is_unconfigured_legal_document:
                    broken.append(f"{Path(html).relative_to(SITES_DIR)} -> {target_host}{href} ({res.status_code})")
    assert not broken, "\n".join(broken)


def test_assets_and_root_icons():
    res = get("/assets/hero-museum.jpg", "vernissage.atelierlabs.co.kr")
    assert res.status_code == 200
    assert res.headers["content-type"] == "image/jpeg"
    assert get("/favicon.ico", "vernissage.atelierlabs.co.kr").headers["content-type"] == "image/png"
    assert get("/favicon.ico", "atelierlabs.co.kr").headers["content-type"] == "image/png"


@pytest.mark.parametrize("host", ["atelierlabs.co.kr", "vernissage.atelierlabs.co.kr", "keepsake.atelierlabs.co.kr"])
def test_shared_hero_layout_asset(host):
    res = get("/shared/hero-layout.css", host)
    assert res.status_code == 200
    assert res.headers["content-type"].startswith("text/css")
    assert res.headers["cache-control"] == main.ASSET_CACHE
    assert "height: clamp(540px, 45vw, 620px)" in res.text


@pytest.mark.parametrize(
    "path",
    ["/shared/nope.css", "/shared/../atelierlabs/index.html", "/shared/%2e%2e/atelierlabs/index.html"],
)
def test_shared_assets_do_not_expose_other_files(path):
    assert get(path, "vernissage.atelierlabs.co.kr").status_code == 404


def test_every_homepage_loads_the_shared_hero_layout():
    for site in main.SITES.values():
        for home in ("index.html", "en/index.html", "ja/index.html"):
            html = (main.SITES_DIR / site / home).read_text(encoding="utf-8")
            assert 'href="/shared/hero-layout.css?v=' in html


@pytest.mark.parametrize("path", ["/../app/main.py", "/%2e%2e/app/main.py", "/assets/../../keepsake/index.html"])
def test_path_traversal_blocked(path):
    res = get(path, "vernissage.atelierlabs.co.kr")
    assert res.status_code == 404


def test_missing_page_404():
    assert get("/nope", "keepsake.atelierlabs.co.kr").status_code == 404


def test_healthz():
    assert get("/healthz", "atelierlabs.co.kr").json() == {"status": "ok"}


def test_vernissage_public_api_proxy(monkeypatch):
    class StubClient:
        def __init__(self, **kwargs):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            return False

        async def get(self, url, headers):
            assert str(url) == "http://vernissage-api:8000/public-web/home?lang=ko"
            assert headers["X-Public-Web-Token"] == "shared-token"
            return httpx.Response(200, json={"docent_notes": []}, headers={"Cache-Control": "max-age=60"})

    monkeypatch.setattr(main, "VERNISSAGE_API_BASE_URL", "http://vernissage-api:8000")
    monkeypatch.setattr(main, "VERNISSAGE_PUBLIC_WEB_API_TOKEN", "shared-token")
    monkeypatch.setattr(main.httpx, "AsyncClient", StubClient)
    res = get("/api/vernissage/public-web/home?lang=ko", "vernissage.localhost:8000")
    assert res.status_code == 200
    assert res.json() == {"docent_notes": []}
    assert res.headers["cache-control"] == "max-age=60"
    assert res.headers["vary"] == "X-App-Language"


def test_vernissage_public_api_proxy_is_not_available_on_other_sites():
    assert get("/api/vernissage/public-web/home", "atelierlabs.co.kr").status_code == 404


def test_vernissage_public_details_are_server_rendered_for_search(monkeypatch):
    async def upstream(request, url, headers):
        assert str(url) == "http://vernissage-api:8000/public-web/docent/notes/35"
        assert headers["X-App-Language"] == "ko"
        return httpx.Response(
            200,
            json={
                "note": {
                    "title": "A museum story",
                    "excerpt": "A search-ready summary.",
                    "content": "A search-ready body.",
                    "thumbnail_url": "https://images.example/note.jpg",
                    "published_at": "2026-11-01T00:00:00Z",
                }
            },
        )

    monkeypatch.setattr(main, "VERNISSAGE_API_BASE_URL", "http://vernissage-api:8000")
    monkeypatch.setattr(main, "_upstream_get", upstream)
    res = get("/docent/notes/35", "vernissage.localhost:8000")
    assert res.status_code == 200
    assert 'name="robots" content="index, follow"' in res.text
    assert 'rel="canonical" href="https://vernissage.atelierlabs.co.kr/docent/notes/35"' in res.text
    assert "A search-ready body." in res.text
    assert '"@type": "Article"' in res.text
    assert 'name="robots" content="noindex"' not in res.text


def test_missing_vernissage_public_detail_is_a_real_404(monkeypatch):
    async def upstream(request, url, headers):
        return httpx.Response(404)

    monkeypatch.setattr(main, "VERNISSAGE_API_BASE_URL", "http://vernissage-api:8000")
    monkeypatch.setattr(main, "_upstream_get", upstream)
    assert get("/exhibitions/999999", "vernissage.localhost:8000").status_code == 404


def test_vernissage_sitemap_adds_public_details_and_caches(monkeypatch):
    calls = []

    async def upstream(request, url, headers):
        calls.append(str(url))
        endpoint = str(url).rsplit("/public-web/", 1)[1]
        payloads = {
            "docent/notes": {"items": [{"id": 36, "published_at": "2026-11-06T15:00:00Z"}], "has_next": False},
            "exhibitions?tab=ongoing": {
                "items": [{"id": 16915, "updated_at": "2026-11-02T13:29:55Z"}],
                "has_next": False,
            },
            "art-events?status=current": {"items": [{"id": 37}], "has_next": False},
        }
        return httpx.Response(200, json=payloads[endpoint])

    monkeypatch.setattr(main, "VERNISSAGE_API_BASE_URL", "http://vernissage-api:8000")
    monkeypatch.setattr(main, "VERNISSAGE_SITEMAP_CACHE", None)
    monkeypatch.setattr(main, "_upstream_get", upstream)
    first = get("/sitemap.xml", "vernissage.localhost:8000")
    assert first.status_code == 200
    assert "https://vernissage.atelierlabs.co.kr/docent/notes/36" in first.text
    assert "https://vernissage.atelierlabs.co.kr/en/exhibitions/16915" in first.text
    assert "<lastmod>2026-11-02</lastmod>" in first.text
    assert "art-events/37</loc><lastmod>" not in first.text
    first_call_count = len(calls)
    assert get("/sitemap.xml", "vernissage.localhost:8000").text == first.text
    assert len(calls) == first_call_count


def test_legal_documents_are_proxied_from_the_owning_backend(monkeypatch):
    seen = []

    class StubClient:
        def __init__(self, **kwargs):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            return False

        async def get(self, url, headers):
            seen.append((str(url), headers))
            return httpx.Response(200, text="<h1>Current legal document</h1>", headers={"Content-Type": "text/html"})

    monkeypatch.setattr(main, "VERNISSAGE_API_BASE_URL", "http://vernissage-api:8000")
    monkeypatch.setattr(main, "VERNISSAGE_PUBLIC_WEB_API_TOKEN", "vern-token")
    monkeypatch.setattr(main, "KEEPSAKE_API_BASE_URL", "http://keepsake-api:8010")
    monkeypatch.setattr(main, "KEEPSAKE_PUBLIC_WEB_API_TOKEN", "keep-token")
    monkeypatch.setattr(main.httpx, "AsyncClient", StubClient)

    vernissage = get("/en/legal/privacy-policy", "vernissage.localhost:8000")
    keepsake = get("/legal/terms-of-service", "keepsake.localhost:8000")
    keepsake_en = get("/en/legal/privacy-policy", "keepsake.localhost:8000")

    assert vernissage.status_code == keepsake.status_code == keepsake_en.status_code == 200
    assert (
        vernissage.headers["cache-control"]
        == keepsake.headers["cache-control"]
        == keepsake_en.headers["cache-control"]
        == "no-store"
    )
    assert (
        vernissage.headers["content-type"]
        == keepsake.headers["content-type"]
        == keepsake_en.headers["content-type"]
        == "text/html"
    )
    assert vernissage.text == keepsake.text == keepsake_en.text == "<h1>Current legal document</h1>"
    assert seen == [
        (
            "http://vernissage-api:8000/public-web/legal/en/privacy-policy",
            {"Accept": "text/html", "X-Public-Web-Token": "vern-token"},
        ),
        (
            "http://keepsake-api:8010/public-web/legal/ko/terms-of-service",
            {"Accept": "text/html", "X-Public-Web-Token": "keep-token"},
        ),
        (
            "http://keepsake-api:8010/public-web/legal/en/privacy-policy",
            {"Accept": "text/html", "X-Public-Web-Token": "keep-token"},
        ),
    ]


def test_unavailable_legal_document_api_is_not_cached(monkeypatch):
    class UnavailableClient:
        def __init__(self, **kwargs):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            return False

        async def get(self, url, headers):
            raise httpx.ConnectError("backend is unavailable")

    monkeypatch.setattr(main, "KEEPSAKE_API_BASE_URL", "http://keepsake-api:8010")
    monkeypatch.setattr(main.httpx, "AsyncClient", UnavailableClient)

    res = get("/legal/privacy-policy", "keepsake.localhost:8000")

    assert res.status_code == 502
    assert res.headers["cache-control"] == "no-store"


@pytest.mark.parametrize("api_path", ["../private", "./home", "/home", "home//latest", ""])
def test_vernissage_public_api_path_cannot_escape_public_prefix(api_path):
    """URL 정규화로 /public-web/ 밖의 내부 API를 프록시하면 안 된다."""
    assert not main._is_safe_api_path(api_path)


def test_vernissage_public_api_path_accepts_nested_public_resource():
    assert main._is_safe_api_path("exhibitions/22054")


@pytest.mark.parametrize(
    "path",
    ["/docent/notes", "/docent/notes/35", "/exhibitions", "/exhibitions/22054", "/art-events", "/art-taste-test"],
)
def test_vernissage_public_web_routes_use_client_shell(path):
    res = get(path, "vernissage.localhost:8000")
    assert res.status_code == 200
    assert 'id="public-web-app"' in res.text


@pytest.mark.parametrize("lang", ["en", "ja"])
@pytest.mark.parametrize(
    "path",
    ["/docent/notes", "/docent/notes/35", "/exhibitions", "/exhibitions/22054", "/art-events/7", "/art-taste-test"],
)
def test_vernissage_public_web_routes_have_language_shells(lang, path):
    res = get(f"/{lang}{path}", "vernissage.localhost:8000")
    assert res.status_code == 200
    assert 'id="public-web-app"' in res.text
    assert f'<html lang="{lang}">' in res.text
    assert f'href="/{lang}/exhibitions"' in res.text


@pytest.mark.parametrize("path", ["/en/unknown", "/fr/exhibitions", "/en/exhibitionsX"])
def test_vernissage_unknown_paths_are_not_shells(path):
    assert get(path, "vernissage.localhost:8000").status_code == 404


@pytest.mark.parametrize("sent, forwarded", [("ja", "ja"), ("EN", "en"), ("fr", None), (None, None)])
def test_vernissage_public_api_proxy_forwards_language(monkeypatch, sent, forwarded):
    seen = {}

    class StubClient:
        def __init__(self, **kwargs):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            return False

        async def get(self, url, headers):
            seen.update(headers)
            return httpx.Response(200, json={}, headers={"Vary": "X-App-Language"})

    monkeypatch.setattr(main, "VERNISSAGE_API_BASE_URL", "http://vernissage-api:8000")
    monkeypatch.setattr(main.httpx, "AsyncClient", StubClient)
    headers = {"host": "vernissage.localhost:8000", **({"X-App-Language": sent} if sent else {})}
    res = client.get("/api/vernissage/public-web/exhibitions", headers=headers)
    assert res.status_code == 200
    assert seen.get("X-App-Language") == forwarded
    assert res.headers["vary"] == "X-App-Language"


@pytest.mark.parametrize("path", ["/en/", "/ja/"])
def test_vernissage_home_links_to_localized_public_pages(path):
    res = get(path, "vernissage.localhost:8000")
    lang = path.strip("/")
    for page in ("docent/notes", "exhibitions", "art-events", "art-taste-test"):
        assert f'href="/{lang}/{page}"' in res.text


def test_company_pages():
    res = get("/support", "atelierlabs.co.kr")
    assert res.status_code == 200 and "고객지원" in res.text
    res = get("/does-not-exist", "atelierlabs.co.kr")
    assert res.status_code == 404 and "페이지를 찾을 수 없어요" in res.text
    assert get("/assets/site.css", "atelierlabs.co.kr").headers["content-type"].startswith("text/css")


def test_localhost_rewrites_cross_site_links():
    """로컬(*.localhost)에서는 운영 도메인 링크가 같은 포트의 로컬 서브도메인으로 바뀐다."""
    res = get("/", "localhost:13000")
    assert 'href="http://keepsake.localhost:13000/"' in res.text
    assert "atelierlabs.co.kr/" not in res.text.replace("atelierlabs.kr@gmail.com", "")
    res = get("/privacy", "localhost:13000")
    assert 'href="http://vernissage.localhost:13000/legal/privacy-policy"' in res.text
    res = get("/", "keepsake.localhost:13000")
    assert 'href="http://localhost:13000/"' in res.text
    # 운영 도메인으로 열면 그대로 둔다.
    res = get("/privacy", "atelierlabs.co.kr")
    assert 'href="https://vernissage.atelierlabs.co.kr/legal/privacy-policy"' in res.text
