import json
import re
from datetime import date, datetime

import httpx
import pytest
from fastapi.testclient import TestClient

import app.main as main
from app.main import app

client = TestClient(app)


@pytest.fixture(autouse=True)
def clear_in_memory_protection_state():
    """요청별 캐시와 제한기는 프로세스 상태이므로 테스트 사이에 공유하지 않는다."""
    main.PUBLIC_API_RESPONSE_CACHE.clear()
    main.REQUEST_WINDOWS.clear()


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


# AdMob은 스토어 마케팅 URL 도메인에서 app-ads.txt를 찾는다. 하위 도메인이면 루트 도메인을
# 볼 수도 있어 앱 서브도메인(Vernissage, Keepsake)과 루트 도메인 모두에 같은 줄을 둔다.
@pytest.mark.parametrize("host", ["vernissage.atelierlabs.co.kr", "keepsake.atelierlabs.co.kr", "atelierlabs.co.kr"])
@pytest.mark.parametrize("method", ["GET", "HEAD"])
def test_app_ads_txt(host, method):
    res = client.request(method, "/app-ads.txt", headers={"host": host}, follow_redirects=False)
    assert res.status_code == 200
    assert res.headers["content-type"].startswith("text/plain")
    if method == "GET":
        assert res.text == "google.com, pub-4065599186318256, DIRECT, f08c47fec0942fa0\n"


FINGERPRINT_A = ":".join(["AB"] * 32)
FINGERPRINT_B = ":".join(["01"] * 32)


def test_vernissage_app_link_association_files(monkeypatch):
    fingerprints = (FINGERPRINT_A, FINGERPRINT_B)
    monkeypatch.setattr(main, "VERNISSAGE_ANDROID_APP_LINK_SHA256_CERT_FINGERPRINTS", fingerprints)
    monkeypatch.setattr(main, "APPLE_APP_LINK_TEAM_ID", "3BQ7Y687R9")

    assetlinks = get("/.well-known/assetlinks.json", "vernissage.atelierlabs.co.kr")
    assert assetlinks.status_code == 200
    assert assetlinks.headers["content-type"].startswith("application/json")
    assert assetlinks.json() == [
        {
            "relation": ["delegate_permission/common.handle_all_urls"],
            "target": {
                "namespace": "android_app",
                "package_name": "com.atelierlabs.vernissage",
                "sha256_cert_fingerprints": list(fingerprints),
            },
        }
    ]

    association = get("/.well-known/apple-app-site-association", "vernissage.atelierlabs.co.kr")
    assert association.status_code == 200
    assert association.headers["content-type"].startswith("application/json")
    detail = association.json()["applinks"]["details"][0]
    assert detail["appID"] == "3BQ7Y687R9.com.atelierlabs.vernissage"
    sections = [
        "exhibitions",
        "museums",
        "artworks",
        "artists",
        "art-concepts",
        "art-figures",
        "art-events",
        "docent/notes",
    ]
    # 앱에는 상세 화면만 있으므로 목록(/exhibitions)은 웹에 남고, 영어·일본어 주소도 앱으로 연다.
    assert detail["paths"] == [f"/{lang}{section}/?*" for lang in ("", "en/", "ja/") for section in sections]


def test_vernissage_dynamic_sitemap_includes_localized_about_pages(monkeypatch):
    """The dynamic sitemap replaces the static file when the API is available."""
    monkeypatch.setattr(main, "VERNISSAGE_SITEMAP_CACHE", None)

    async def public_json(_request, _endpoint, _language):
        return {"items": [], "has_next": False}, 200

    monkeypatch.setattr(main, "_vernissage_public_json", public_json)
    response = get("/sitemap.xml", "vernissage.atelierlabs.co.kr")
    assert response.status_code == 200
    for path in ("about", "en/about", "ja/about"):
        assert f"https://vernissage.atelierlabs.co.kr/{path}" in response.text
    for path in ("docent/notes", "en/exhibitions", "ja/art-events", "art-taste-test", "en/art-taste-test"):
        assert f"<loc>https://vernissage.atelierlabs.co.kr/{path}</loc>" in response.text




def test_install_page_only_for_app_only_sections():
    assert get("/museumsx/1", "vernissage.atelierlabs.co.kr").status_code == 404
    assert get("/museums/1", "keepsake.atelierlabs.co.kr").status_code == 404


@pytest.mark.parametrize("fingerprints", [(), (FINGERPRINT_A, "AA:BB:CC"), (FINGERPRINT_A.replace(":", ""),)])
def test_vernissage_assetlinks_requires_valid_android_certificate_fingerprints(monkeypatch, fingerprints):
    monkeypatch.setattr(main, "VERNISSAGE_ANDROID_APP_LINK_SHA256_CERT_FINGERPRINTS", fingerprints)
    response = get("/.well-known/assetlinks.json", "vernissage.atelierlabs.co.kr")
    assert response.status_code == 503
    assert response.headers["cache-control"] == "no-store"


@pytest.mark.parametrize("team_id", ["", "SHORT", "3BQ7Y687R9X"])
def test_vernissage_aasa_requires_valid_apple_team_id(monkeypatch, team_id):
    monkeypatch.setattr(main, "APPLE_APP_LINK_TEAM_ID", team_id)
    response = get("/.well-known/apple-app-site-association", "vernissage.atelierlabs.co.kr")
    assert response.status_code == 503
    assert response.headers["cache-control"] == "no-store"


@pytest.mark.parametrize("method", ["GET", "HEAD"])
def test_vernissage_app_link_files_answer_head_without_redirect(monkeypatch, method):
    monkeypatch.setattr(main, "VERNISSAGE_ANDROID_APP_LINK_SHA256_CERT_FINGERPRINTS", (FINGERPRINT_A,))
    monkeypatch.setattr(main, "APPLE_APP_LINK_TEAM_ID", "3BQ7Y687R9")
    for path in ("/.well-known/assetlinks.json", "/.well-known/apple-app-site-association"):
        res = client.request(method, path, headers={"host": "vernissage.atelierlabs.co.kr"}, follow_redirects=False)
        assert res.status_code == 200
        assert res.headers["content-type"].startswith("application/json")


def test_keepsake_app_link_association_files(monkeypatch):
    monkeypatch.setattr(main, "KEEPSAKE_ANDROID_APP_LINK_SHA256_CERT_FINGERPRINTS", (FINGERPRINT_B,))
    monkeypatch.setattr(main, "VERNISSAGE_ANDROID_APP_LINK_SHA256_CERT_FINGERPRINTS", (FINGERPRINT_A,))
    monkeypatch.setattr(main, "APPLE_APP_LINK_TEAM_ID", "3BQ7Y687R9")

    # Keepsake는 자기 서명 키 지문만 선언한다(Vernissage 지문과 섞이지 않는다).
    assetlinks = get("/.well-known/assetlinks.json", "keepsake.atelierlabs.co.kr")
    assert assetlinks.status_code == 200
    assert assetlinks.json()[0]["target"] == {
        "namespace": "android_app",
        "package_name": "com.atelierlabs.keepsake",
        "sha256_cert_fingerprints": [FINGERPRINT_B],
    }

    association = get("/.well-known/apple-app-site-association", "keepsake.atelierlabs.co.kr")
    assert association.status_code == 200
    detail = association.json()["applinks"]["details"][0]
    assert detail["appID"] == "3BQ7Y687R9.com.atelierlabs.keepsake"
    # 공유 앨범 초대 링크만 앱으로 연다.
    assert detail["paths"] == ["/join", "/en/join", "/ja/join"]


def test_keepsake_assetlinks_requires_its_own_fingerprints(monkeypatch):
    monkeypatch.setattr(main, "KEEPSAKE_ANDROID_APP_LINK_SHA256_CERT_FINGERPRINTS", ())
    monkeypatch.setattr(main, "VERNISSAGE_ANDROID_APP_LINK_SHA256_CERT_FINGERPRINTS", (FINGERPRINT_A,))
    response = get("/.well-known/assetlinks.json", "keepsake.atelierlabs.co.kr")
    assert response.status_code == 503
    assert "KEEPSAKE_ANDROID_APP_LINK_SHA256_CERT_FINGERPRINTS" in response.text


# 앱이 없는 회사 사이트는 소유 선언을 내보내지 않는다.
def test_app_link_files_not_on_company_site(monkeypatch):
    monkeypatch.setattr(main, "VERNISSAGE_ANDROID_APP_LINK_SHA256_CERT_FINGERPRINTS", (FINGERPRINT_A,))
    assert get("/.well-known/assetlinks.json", "atelierlabs.co.kr").status_code == 404
    assert get("/.well-known/apple-app-site-association", "atelierlabs.co.kr").status_code == 404


@pytest.mark.parametrize(
    ("path", "lang", "marker"),
    [
        ("/join?code=ABCD2345", "ko", "공유 앨범에 초대받았어요"),
        ("/en/join?code=ABCD2345", "en", "invited to a shared album"),
        ("/ja/join?code=ABCD2345", "ja", "共有アルバムに招待されました"),
    ],
)
def test_keepsake_invite_page(path, lang, marker):
    res = get(path, "keepsake.atelierlabs.co.kr")
    assert res.status_code == 200
    assert f'<html lang="{lang}">' in res.text
    assert marker in res.text
    # 초대 코드가 담긴 주소이므로 검색에 나오지 않게 한다.
    assert '<meta name="robots" content="noindex" />' in res.text
    assert "/assets/join.js" in res.text
    assert "data-open-app hidden" in res.text


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
        ("vernissage.localhost:8000", "/en/legal/privacy-policy"),
    ],
)
def test_unconfigured_legal_document_apis_are_not_cached(monkeypatch, host, path):
    monkeypatch.setattr(main, "VERNISSAGE_API_BASE_URL", "")

    res = get(path, host)

    assert res.status_code == 503
    assert res.headers["cache-control"] == "no-store"


@pytest.mark.parametrize(
    ("host", "path", "lang"),
    [
        (host, path, lang)
        for host, paths in [
            ("atelierlabs.co.kr", ["/", "/support"]),
            ("vernissage.atelierlabs.co.kr", ["/", "/about"]),
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
                    and target_host == "vernissage.atelierlabs.co.kr"
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


def test_nav_script_copies_stay_identical():
    # atelierlabs와 vernissage는 같은 ☰ 메뉴 스크립트를 각자 assets/에 둔다
    atelier = (main.SITES_DIR / "atelierlabs/assets/nav.js").read_text(encoding="utf-8")
    vernissage = (main.SITES_DIR / "vernissage/assets/nav.js").read_text(encoding="utf-8")
    assert atelier == vernissage


def test_pages_with_a_header_menu_have_the_menu_button():
    # 상단 메뉴가 있는 페이지는 좁은 화면에서 메뉴를 열 ☰ 버튼과 nav.js가 함께 있어야 한다
    pages = [p for site in ("atelierlabs", "vernissage") for p in (main.SITES_DIR / site).rglob("*.html")]
    checked = 0
    for page in pages:
        html = page.read_text(encoding="utf-8")
        if '<nav class="site-nav"' not in html:
            continue
        checked += 1
        assert 'id="site-nav"' in html, page
        assert 'class="nav-toggle"' in html and 'aria-controls="site-nav"' in html, page
        assert 'src="/assets/nav.js?v=' in html, page
    assert checked >= 13


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


def test_vernissage_public_api_caches_identical_bot_requests(monkeypatch):
    calls = 0

    async def upstream(request, url, headers):
        nonlocal calls
        calls += 1
        assert headers["Accept"] == "application/json"
        return httpx.Response(200, json={"items": []})

    monkeypatch.setattr(main, "VERNISSAGE_API_BASE_URL", "http://vernissage-api:8000")
    monkeypatch.setattr(main, "_upstream_get", upstream)
    first = client.get(
        "/api/vernissage/public-web/docent/notes",
        headers={"host": "vernissage.localhost:8000", "accept": "text/html"},
        follow_redirects=False,
    )
    second = get("/api/vernissage/public-web/docent/notes", "vernissage.localhost:8000")
    assert first.status_code == second.status_code == 200
    assert calls == 1


def test_vernissage_public_api_rate_limits_a_single_client(monkeypatch):
    async def upstream(request, url, headers):
        return httpx.Response(200, json={})

    monkeypatch.setattr(main, "VERNISSAGE_API_BASE_URL", "http://vernissage-api:8000")
    monkeypatch.setattr(main, "VERNISSAGE_PUBLIC_API_REQUESTS_PER_MINUTE", 1)
    monkeypatch.setattr(main, "_upstream_get", upstream)
    assert get("/api/vernissage/public-web/docent/notes", "vernissage.localhost:8000").status_code == 200
    limited = get("/api/vernissage/public-web/exhibitions", "vernissage.localhost:8000")
    assert limited.status_code == 429
    assert limited.headers["retry-after"] == "60"


def test_public_api_cache_evicts_the_least_recently_used_item(monkeypatch):
    monkeypatch.setattr(main, "PUBLIC_API_CACHE_MAX_ENTRIES", 2)
    main._cache_put(("one", "", "ko"), b'{"one": 1}', 200, {})
    main._cache_put(("two", "", "ko"), b'{"two": 2}', 200, {})
    assert main._cache_get(("one", "", "ko")) is not None
    main._cache_put(("three", "", "ko"), b'{"three": 3}', 200, {})
    assert main._cache_get(("one", "", "ko")) is not None
    assert main._cache_get(("two", "", "ko")) is None
    assert main._cache_get(("three", "", "ko")) is not None


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


def test_vernissage_docent_embeds_render_images_and_artwork_cards(monkeypatch):
    async def upstream(request, url, headers):
        return httpx.Response(
            200,
            json={
                "note": {
                    "title": "Embedded story",
                    "content": (
                        "Before ![A painting](https://images.example/painting.jpg) "
                        "after **an important point** [[cards:artwork:2649,artist:40,art_concept:566]] "
                        "[[image:https://images.example/archive.jpg|Archive caption]]\n"
                        "[[image:https://images.example/archive-2.jpg|Second archive caption]]"
                    ),
                }
            },
        )

    monkeypatch.setattr(main, "VERNISSAGE_API_BASE_URL", "http://vernissage-api:8000")
    monkeypatch.setattr(main, "_upstream_get", upstream)
    res = get("/docent/notes/35", "vernissage.localhost:8000")
    assert '<img src="https://images.example/painting.jpg" alt="A painting" loading="lazy" />' in res.text
    assert "<strong>an important point</strong>" in res.text
    assert 'data-docent-card-kind="artwork" data-docent-card-id="2649"' in res.text
    assert 'data-docent-card-kind="artist" data-docent-card-id="40"' in res.text
    assert 'href="/artists/40"' in res.text
    assert 'data-docent-card-kind="art_concept" data-docent-card-id="566"' in res.text
    assert 'href="/art-concepts/566"' in res.text
    assert '<img src="https://images.example/archive.jpg" alt="Archive caption" loading="lazy" />' in res.text
    assert '<div class="docent-image-grid" data-count="2">' in res.text
    assert '<div class="docent-card-grid" data-count="3">' in res.text
    assert "[[cards:artwork:2649,artist:40]]" not in res.text


def test_vernissage_docent_card_grid_preserves_exact_card_count():
    content = "[[cards:artist:1,artist:2,artist:3,artist:4]]"
    rendered = main._render_docent_content(content)
    assert '<div class="docent-card-grid" data-count="4">' in rendered
    assert rendered.count('class="docent-card"') == 4


def test_missing_vernissage_public_detail_is_a_real_404(monkeypatch):
    async def upstream(request, url, headers):
        return httpx.Response(404)

    monkeypatch.setattr(main, "VERNISSAGE_API_BASE_URL", "http://vernissage-api:8000")
    monkeypatch.setattr(main, "_upstream_get", upstream)
    assert get("/exhibitions/999999", "vernissage.localhost:8000").status_code == 404


def _json_ld(text: str) -> dict:
    return json.loads(re.search(r'<script type="application/ld\+json">(.*?)</script>', text, re.S).group(1))


def test_vernissage_exhibition_structured_data_has_a_location(monkeypatch):
    """Google Event 리치 결과는 location이 필수다(실제 /ja/exhibitions/16758 응답 기반)."""

    async def upstream(request, url, headers):
        return httpx.Response(
            200,
            json={
                "indexable": True,
                "exhibition": {
                    "id": 16758,
                    "title": "《군락: 여섯 개의 뜰》",
                    "start_date": "2026-10-09",
                    "end_date": "2027-05-30",
                    "description": "2026.10.24\n          ~\n          2026.10.24",
                    "image_url": "https://images.example/ex.jpg",
                    "place_name": "소마미술관 2관",
                    "institution_name": "소마미술관",
                    "museum": {
                        "name": "SOMA美術館",
                        "city": "서울특별시 송파구",
                        "address": "서울특별시 송파구 올림픽로 424",
                        "latitude": 37.5169172,
                        "longitude": 127.1179749,
                        "website": "https://soma.kspo.or.kr/",
                    },
                },
            },
        )

    monkeypatch.setattr(main, "VERNISSAGE_API_BASE_URL", "http://vernissage-api:8000")
    monkeypatch.setattr(main, "_upstream_get", upstream)
    res = get("/ja/exhibitions/16758", "vernissage.localhost:8000")
    schema = _json_ld(res.text)
    assert schema["@type"] == "ExhibitionEvent"
    assert schema["location"]["name"] == "SOMA美術館"
    assert schema["location"]["address"]["streetAddress"] == "서울특별시 송파구 올림픽로 424"
    assert schema["location"]["geo"]["latitude"] == 37.5169172
    assert schema["organizer"]["name"] == "소마미술관"
    assert schema["eventStatus"] == "https://schema.org/EventScheduled"
    # 날짜만 있는 수집 설명은 쓰지 않고 장소·기간으로 설명을 만든다.
    assert "2026.10.24" not in res.text
    assert schema["description"] == "《군락: 여섯 개의 뜰》 · SOMA美術館 · 2026-10-09 ~ 2027-05-30"


def test_vernissage_art_event_structured_data_has_a_location(monkeypatch):
    """실제 /en/art-events/206 응답 기반: 장소는 도시·나라, 주최·이미지는 시리즈에서."""

    async def upstream(request, url, headers):
        return httpx.Response(
            200,
            json={
                "event": {
                    "id": 206,
                    "display_title": "Art Cologne 2026",
                    "start_date": "2026-11-05",
                    "end_date": "2026-11-08",
                    "city": "쾰른",
                    "country": "독일",
                    "country_code": "DE",
                    "image_url": None,
                    "description": None,
                    "venues": [],
                    "series": {
                        "name": "Art Cologne",
                        "organizer": "Koelnmesse",
                        "description": "Art Cologne is an art fair held annually in Cologne.",
                        "thumbnail_url": "https://images.example/logo.png",
                    },
                }
            },
        )

    monkeypatch.setattr(main, "VERNISSAGE_API_BASE_URL", "http://vernissage-api:8000")
    monkeypatch.setattr(main, "_upstream_get", upstream)
    schema = _json_ld(get("/en/art-events/206", "vernissage.localhost:8000").text)
    assert schema["@type"] == "Event"
    assert schema["location"] == {
        "@type": "Place",
        "name": "쾰른, 독일",
        "address": {"@type": "PostalAddress", "addressLocality": "쾰른", "addressCountry": "DE"},
    }
    assert schema["organizer"] == {"@type": "Organization", "name": "Koelnmesse"}
    assert schema["image"] == "https://images.example/logo.png"
    assert None not in schema.values()


def test_vernissage_event_without_a_place_is_not_an_invalid_event(monkeypatch):
    async def upstream(request, url, headers):
        return httpx.Response(200, json={"event": {"id": 7, "display_title": "Unknown fair", "series": {}}})

    monkeypatch.setattr(main, "VERNISSAGE_API_BASE_URL", "http://vernissage-api:8000")
    monkeypatch.setattr(main, "_upstream_get", upstream)
    schema = _json_ld(get("/art-events/7", "vernissage.localhost:8000").text)
    assert schema["@type"] == "WebPage"
    assert "location" not in schema


def test_vernissage_event_without_a_start_date_is_not_an_invalid_event(monkeypatch):
    """실제 /en/art-events/46 응답 기반: 장소는 정해졌지만 날짜가 아직 발표되지 않은 회차."""

    async def upstream(request, url, headers):
        return httpx.Response(
            200,
            json={
                "event": {
                    "id": 46,
                    "display_title": "Frieze Seoul 2027",
                    "start_date": None,
                    "end_date": None,
                    "city": "서울",
                    "country_code": "KR",
                    "venues": [{"name": "Dongdaemun Design Plaza"}],
                    "series": {"organizer": "Frieze"},
                }
            },
        )

    monkeypatch.setattr(main, "VERNISSAGE_API_BASE_URL", "http://vernissage-api:8000")
    monkeypatch.setattr(main, "_upstream_get", upstream)
    schema = _json_ld(get("/en/art-events/46", "vernissage.localhost:8000").text)
    assert schema["@type"] == "WebPage"
    assert "startDate" not in schema


@pytest.mark.parametrize("status", [500, 502, 403])
def test_unavailable_vernissage_api_is_a_temporary_error_not_noindex(monkeypatch, status):
    """API 장애 때 noindex 셸을 200으로 주면 검색엔진이 정상 페이지를 색인에서 뺀다."""

    async def upstream(request, url, headers):
        return httpx.Response(status)

    monkeypatch.setattr(main, "VERNISSAGE_API_BASE_URL", "http://vernissage-api:8000")
    monkeypatch.setattr(main, "_upstream_get", upstream)
    for path in ("/docent/notes/35", "/en/exhibitions/1", "/exhibitions", "/ja/docent/notes"):
        res = get(path, "vernissage.localhost:8000")
        assert res.status_code == 503, path
        assert res.headers["retry-after"] == "120"
        assert 'id="public-web-app"' in res.text


@pytest.mark.parametrize(
    ("path", "lang", "section", "endpoint", "payload", "href", "marker"),
    [
        (
            "/docent/notes",
            "ko",
            "docent/notes",
            "docent/notes",
            {"items": [{"id": 36, "title": "모네의 정원", "excerpt": "**빛**의 이야기"}]},
            'href="/docent/notes/36"',
            "<h1>도슨트</h1>",
        ),
        (
            "/en/exhibitions",
            "en",
            "exhibitions",
            "exhibitions?tab=ongoing",
            {"items": [{"id": 16915, "title": "Light & Shadow", "museum": {"name": "Leeum"}}]},
            'href="/en/exhibitions/16915"',
            "<h1>Exhibitions</h1>",
        ),
        (
            "/ja/art-events",
            "ja",
            "art-events",
            "art-events?status=current",
            {"items": [{"id": 37, "series": {"name": "光州ビエンナーレ"}, "city": "光州"}]},
            'href="/ja/art-events/37"',
            "<h1>ビエンナーレ・アートフェア</h1>",
        ),
    ],
)
def test_vernissage_listings_are_server_rendered_for_search(
    monkeypatch, path, lang, section, endpoint, payload, href, marker
):
    async def upstream(request, url, headers):
        assert str(url).rsplit("/public-web/", 1)[1] == endpoint
        assert headers["X-App-Language"] == lang
        return httpx.Response(200, json=payload)

    monkeypatch.setattr(main, "VERNISSAGE_API_BASE_URL", "http://vernissage-api:8000")
    monkeypatch.setattr(main, "_upstream_get", upstream)
    res = get(path, "vernissage.localhost:8000")
    assert res.status_code == 200
    assert 'name="robots" content="index, follow"' in res.text
    assert 'name="robots" content="noindex"' not in res.text
    assert f'rel="canonical" href="https://vernissage.atelierlabs.co.kr{path}"' in res.text
    assert f'hreflang="x-default" href="https://vernissage.atelierlabs.co.kr/{section}"' in res.text
    assert marker in res.text
    assert href in res.text
    assert '"@type": "CollectionPage"' in res.text
    assert "**" not in res.text


@pytest.mark.parametrize(
    ("lang", "heading"), [("", "나의 예술 취향은?"), ("en/", "taste in art?"), ("ja/", "アートの好み")]
)
def test_vernissage_taste_test_is_indexable_without_the_api(monkeypatch, lang, heading):
    monkeypatch.setattr(main, "VERNISSAGE_API_BASE_URL", "")
    res = get(f"/{lang}art-taste-test", "vernissage.localhost:8000")
    assert res.status_code == 200
    assert 'name="robots" content="index, follow"' in res.text
    assert 'name="robots" content="noindex"' not in res.text
    assert f'rel="canonical" href="https://vernissage.atelierlabs.co.kr/{lang}art-taste-test"' in res.text
    assert heading in res.text
    assert 'id="public-web-app"' in res.text


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
    monkeypatch.setattr(main.httpx, "AsyncClient", StubClient)

    vernissage = get("/en/legal/privacy-policy", "vernissage.localhost:8000")
    vernissage_ko = get("/legal/terms-of-service", "vernissage.localhost:8000")

    assert vernissage.status_code == vernissage_ko.status_code == 200
    assert vernissage.headers["cache-control"] == vernissage_ko.headers["cache-control"] == "no-store"
    assert vernissage.headers["content-type"] == "text/html"
    assert vernissage.text == "<h1>Current legal document</h1>"
    assert seen == [
        (
            "http://vernissage-api:8000/public-web/legal/en/privacy-policy",
            {"Accept": "text/html", "X-Public-Web-Token": "vern-token"},
        ),
        (
            "http://vernissage-api:8000/public-web/legal/ko/terms-of-service",
            {"Accept": "text/html", "X-Public-Web-Token": "vern-token"},
        ),
    ]


@pytest.mark.parametrize(
    ("path", "lang"),
    [
        ("/legal/terms-of-service", "ko"),
        ("/legal/privacy-policy", "ko"),
        ("/legal/account-deletion", "ko"),
        ("/en/legal/terms-of-service", "en"),
        ("/en/legal/privacy-policy", "en"),
        ("/en/legal/account-deletion", "en"),
    ],
)
def test_keepsake_legal_documents_are_static_pages(monkeypatch, path, lang):
    """Keepsake 약관은 이 저장소의 sites/keepsake/legal/이 원본이다. 앱 백엔드를 부르지 않는다."""

    def no_upstream(*args, **kwargs):
        raise AssertionError("Keepsake legal documents must not be proxied")

    monkeypatch.setattr(main.httpx, "AsyncClient", no_upstream)

    res = get(path, "keepsake.atelierlabs.co.kr")

    assert res.status_code == 200
    assert res.headers["content-type"].startswith("text/html")
    assert f'<html lang="{lang}">' in res.text
    assert f'<link rel="canonical" href="https://keepsake.atelierlabs.co.kr{path}" />' in res.text


@pytest.mark.parametrize("document", ["terms-of-service", "privacy-policy"])
def test_keepsake_korean_and_english_legal_documents_match(document):
    """영어판은 직역이 아니어도 조항 수·표 수·시행일은 한국어판과 같아야 한다."""
    ko = (main.SITES_DIR / "keepsake" / "legal" / f"{document}.html").read_text(encoding="utf-8")
    en = (main.SITES_DIR / "keepsake" / "en" / "legal" / f"{document}.html").read_text(encoding="utf-8")

    assert ko.count("<h2>") == en.count("<h2>")
    assert ko.count("<table>") == en.count("<table>")
    ko_date = re.search(r"시행일: (\d{4})년 (\d{1,2})월 (\d{1,2})일", ko)
    en_date = re.search(r"Effective [Dd]ate: (\w+ \d{1,2}, \d{4})", en)
    assert ko_date and en_date
    assert date(*map(int, ko_date.groups())) == datetime.strptime(en_date[1], "%B %d, %Y").date()


def test_keepsake_korean_and_english_account_deletion_pages_match():
    """계정 삭제 안내도 영어판의 항목 수·목록 수·수정일이 한국어판과 같아야 한다."""
    ko = (main.SITES_DIR / "keepsake" / "legal" / "account-deletion.html").read_text(encoding="utf-8")
    en = (main.SITES_DIR / "keepsake" / "en" / "legal" / "account-deletion.html").read_text(encoding="utf-8")

    assert ko.count("<h2>") == en.count("<h2>")
    assert ko.count("<li>") == en.count("<li>")
    ko_date = re.search(r"최종 수정일: (\d{4}-\d{2}-\d{2})", ko)
    en_date = re.search(r"Last updated: (\w+ \d{1,2}, \d{4})", en)
    assert ko_date and en_date
    assert date.fromisoformat(ko_date[1]) == datetime.strptime(en_date[1], "%B %d, %Y").date()


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

    monkeypatch.setattr(main, "VERNISSAGE_API_BASE_URL", "http://vernissage-api:8000")
    monkeypatch.setattr(main.httpx, "AsyncClient", UnavailableClient)

    res = get("/legal/privacy-policy", "vernissage.localhost:8000")

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


def json_ld_graph(html: str) -> list[dict]:
    return json.loads(re.search(r'<script type="application/ld\+json">(.*?)</script>', html, re.S)[1])["@graph"]


def test_company_home_carries_korean_brand_name():
    """'아틀리에 랩스' 검색에 걸리도록 한국어 홈의 제목·h1·사이트 이름에 한글 이름이 있어야 한다."""
    res = get("/", "atelierlabs.co.kr")
    assert "<title>Atelier Labs 아틀리에 랩스" in res.text
    assert re.search(r"<h1[^>]*>.*아틀리에 랩스.*</h1>", res.text)
    website = next(node for node in json_ld_graph(res.text) if node["@type"] == "WebSite")
    assert website["name"] == "아틀리에 랩스" and website["url"] == "https://atelierlabs.co.kr/"


def test_company_home_carries_japanese_brand_name():
    res = get("/ja/", "atelierlabs.co.kr")
    assert "<title>Atelier Labs アトリエラボ" in res.text
    assert 'property="og:title" content="Atelier Labs アトリエラボ"' in res.text


@pytest.mark.parametrize(
    ("host", "path", "brand_name"),
    [
        ("vernissage.atelierlabs.co.kr", "/", "Vernissage 베르니사주"),
        ("vernissage.atelierlabs.co.kr", "/ja/", "Vernissage ヴェルニサージュ"),
        ("keepsake.atelierlabs.co.kr", "/", "Keepsake 킵세이크"),
        ("keepsake.atelierlabs.co.kr", "/ja/", "Keepsake キープセイク"),
    ],
)
def test_app_homes_carry_localized_brand_names(host, path, brand_name):
    res = get(path, host)
    assert f"<title>{brand_name}" in res.text
    assert f'property="og:title" content="{brand_name}' in res.text


@pytest.mark.parametrize("path", ["/", "/en/", "/ja/"])
def test_company_homes_share_organization(path):
    graph = json_ld_graph(get(path, "atelierlabs.co.kr").text)
    org = next(node for node in graph if node["@type"] == "Organization")
    assert org["@id"] == "https://atelierlabs.co.kr/#organization"
    assert set(org["alternateName"]) == {"아틀리에 랩스", "아틀리에랩스", "アトリエラボ"}
    assert [node["@type"] for node in graph].count("MobileApplication") == 2


def test_company_sitemap_lists_only_live_pages():
    res = get("/sitemap.xml", "atelierlabs.co.kr")
    entry = r"<url><loc>https://atelierlabs\.co\.kr(/[^<]*)</loc><lastmod>\d{4}-\d{2}-\d{2}</lastmod></url>"
    urls = re.findall(entry, res.text)
    assert len(urls) == res.text.count("<url>") > 0
    for path in urls:
        assert get(path, "atelierlabs.co.kr").status_code == 200, path


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
