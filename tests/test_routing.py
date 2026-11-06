import pytest
from fastapi.testclient import TestClient

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
def test_vernissage_legal_pages(path):
    res = get(path, "vernissage.atelierlabs.co.kr")
    assert res.status_code == 200
    assert res.headers["content-type"].startswith("text/html")


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
                if res.status_code not in (200, 301):
                    broken.append(f"{Path(html).relative_to(SITES_DIR)} -> {target_host}{href} ({res.status_code})")
    assert not broken, "\n".join(broken)


def test_assets_and_root_icons():
    res = get("/assets/hero-museum.jpg", "vernissage.atelierlabs.co.kr")
    assert res.status_code == 200
    assert res.headers["content-type"] == "image/jpeg"
    assert get("/favicon.ico", "vernissage.atelierlabs.co.kr").headers["content-type"] == "image/png"
    assert get("/favicon.ico", "atelierlabs.co.kr").headers["content-type"] == "image/png"


@pytest.mark.parametrize("path", ["/../app/main.py", "/%2e%2e/app/main.py", "/assets/../../keepsake/index.html"])
def test_path_traversal_blocked(path):
    res = get(path, "vernissage.atelierlabs.co.kr")
    assert res.status_code == 404


def test_missing_page_404():
    assert get("/nope", "keepsake.atelierlabs.co.kr").status_code == 404


def test_healthz():
    assert get("/healthz", "atelierlabs.co.kr").json() == {"status": "ok"}


def test_company_pages():
    res = get("/support", "atelierlabs.co.kr")
    assert res.status_code == 200 and "고객지원" in res.text
    res = get("/does-not-exist", "atelierlabs.co.kr")
    assert res.status_code == 404 and "페이지를 찾을 수 없어요" in res.text
    assert get("/assets/site.css", "atelierlabs.co.kr").headers["content-type"].startswith("text/css")
