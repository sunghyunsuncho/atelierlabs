# atelierlabs.co.kr

Atelier Labs 회사 홈페이지와 앱별 서브도메인 페이지를 서비스하는 정적 사이트 서버.
Railway 서비스 하나가 모든 도메인을 받고, 요청의 `Host` 헤더로 사이트를 고른다.

| 도메인 | 내용 | 디렉터리 |
|---|---|---|
| `atelierlabs.co.kr` | 회사 홈(`/`: 소개·앱·원칙), 고객지원(`/support`) | [sites/atelierlabs/](sites/atelierlabs/) |
| `www.atelierlabs.co.kr` | `atelierlabs.co.kr`로 301 | — |
| `vernissage.atelierlabs.co.kr` | Vernissage 소개, 약관·개인정보 처리방침·계정 삭제 안내 | [sites/vernissage/](sites/vernissage/) |
| `keepsake.atelierlabs.co.kr` | Keepsake 소개, 출시 소식·앱 안내(이 사이트에서 관리) | [sites/keepsake/](sites/keepsake/) |

모든 페이지는 한국어(`/…`)·영어(`/en/…`)·일본어(`/ja/…`)로 제공한다. 아래 [다국어](#다국어) 참고.

## 구조

```
app/main.py      FastAPI 서버: Host로 사이트 선택, URL을 파일로 매핑
sites/<site>/    사이트별 정적 파일 (HTML, assets/, robots.txt, sitemap.xml)
  en/, ja/       영어·일본어 페이지 (한국어 페이지와 같은 경로)
                 스타일은 페이지마다 넣지 않고 공용 CSS를 쓴다:
                 atelierlabs/assets/site.css, vernissage/assets/home.css(랜딩), vernissage/assets/legal.css(약관)
brand/           Atelier Labs 로고 원본 (서비스되지 않음)
scripts/         brand/ 원본으로 웹용 이미지를 만드는 스크립트
tests/           라우팅 테스트
```

### 브랜드 이미지

`brand/atelierlabs_icon.png`(심볼), `brand/atelierlabs_icon_logo.png`(심볼+워드마크)가 원본이다. 둘 다 투명 배경.
원본을 바꾸면 아래 명령으로 `sites/atelierlabs/assets/`의 `icon.png`(512), `favicon.png`(64),
`apple-touch-icon.png`(180, 흰 바탕), `logo.png`(헤더용 가로 로고), `og-image.png`(1200×630)를 다시 만든다.

```bash
uv run --with pillow python scripts/build_brand_assets.py
```

URL은 `sites/<site>/` 아래 파일로 이렇게 매핑된다.

- `/` → `index.html`
- `/legal/privacy-policy` → `legal/privacy-policy.html` (`.html`은 생략)
- `/en/legal/privacy-policy` → `en/legal/privacy-policy.html`
- `/favicon.ico`, `/apple-touch-icon.png` → `assets/favicon.png`, `assets/apple-touch-icon.png`
- 없는 경로 → `<lang>/404.html`, 없으면 `404.html`, 그것도 없으면 일반 텍스트 404

## 다국어

- 한국어는 루트, 영어·일본어는 `/en/`, `/ja/` 아래 **같은 경로**에 둔다. 페이지를 추가하면 세 언어를 함께 만든다.
- 각 페이지에는 `canonical`(자기 주소), `hreflang` ko/en/ja + `x-default`(한국어), 헤더의 KO·EN·JA 전환, 푸터의 언어 링크를 넣는다.
- 사이트맵에 언어별 주소를 모두 싣는다.
- **약관·개인정보 처리방침·계정 삭제 안내는 한국어·영어만 있다.** 일본어 페이지는 영어판(`/en/legal/…`)으로 링크하고
  "（英語）"라고 표시한다. `/ja/legal/…`로 들어오면 서버가 `/en/legal/…`로 301 한다.
- 영어판 약관은 "한국어판이 우선한다"는 문구를 둔다. 한국어판을 고치면 영어판도 함께 고친다.
- Vernissage 영어·일본어 랜딩은 스토어 등록정보(vernissage 리포 `store-assets/listing/`)를 따른다:
  한국어로만 제공되는 도슨트 글과 vernissage.kr의 한국어 페이지(전시·취향 테스트 등)는 소개·링크하지 않고,
  진행 중 전시 목록이 한국 중심이라는 점은 FAQ에 밝힌다. 스크린샷도 언어별 스토어 스크린샷(`assets/screens/en|ja/`)을 쓴다.
- 서버의 리다이렉트: `/jp/…` → `/ja/…`, 옛 영문 약관 주소 `/legal/en/…` → `/en/legal/…`

## 로컬 실행

```bash
./start.sh           # 백그라운드 시작 (Docker Compose)
./start.sh --build   # 이미지 재빌드 후 시작 (pyproject.toml·uv.lock·Dockerfile 변경 시)
```

브라우저는 `*.localhost`를 127.0.0.1로 연결하므로 서브도메인 그대로 확인할 수 있다.

- http://localhost:13000 — 회사 홈 (`DEFAULT_SITE`)
- http://vernissage.localhost:13000
- http://keepsake.localhost:13000

`app/`, `sites/`는 컨테이너에 마운트되므로 HTML·CSS 수정은 새로고침만 하면 되고, `app/*.py`를 고치면 서버가 자동으로 다시 뜬다.

| 명령어 | 설명 |
|---|---|
| `./start.sh` | 백그라운드 시작 |
| `./start.sh --build` | 재빌드 후 시작 |
| `./stop.sh` | 중지 |
| `./stop.sh --clean` | 컨테이너·네트워크 제거 |
| `./restart.sh` | 재시작 (`--build`로 재빌드) |
| `./logs.sh` | 실시간 로그 |

로컬 포트는 [compose.dev.env](compose.dev.env)에 고정해 vernissage·keepsake와 동시에 띄울 수 있게 했다.
Compose 프로젝트명도 `atelierlabs`로 고정되어 컨테이너·네트워크가 다른 리포와 섞이지 않는다.

| 용도 | 포트 |
|---|---|
| 웹 개발 서버 (사이트 서버) | 13000 |
| API (예약, 미사용) | 18010 |
| Postgres 호스트 (예약, 미사용) | 15433 |
| Redis 호스트 (예약, 미사용) | 16380 |

Docker 없이 띄우려면:

```bash
uv sync
uv run uvicorn app.main:app --reload --port 13000
```

테스트·린트:

```bash
uv run pytest
uv run ruff check . && uv run ruff format --check .
```

## 새 앱 사이트 추가

1. `sites/<앱이름>/index.html` 작성 (자산은 `sites/<앱이름>/assets/`)
2. [app/main.py](app/main.py)의 `SITES`에 `"<서브도메인>": "<디렉터리>"` 추가
3. Railway 서비스에 `<서브도메인>.atelierlabs.co.kr` 커스텀 도메인을 추가하고 DNS에 CNAME 등록
4. 회사 홈(`sites/atelierlabs/index.html`, `en/`, `ja/`)의 앱 목록에 카드 추가

## 배포 (Railway)

[Dockerfile](Dockerfile)로 빌드하고 `/healthz`로 헬스체크한다([railway.json](railway.json)). `PORT`는 Railway가 준다.

1. Railway에서 이 리포지토리로 서비스를 만든다.
2. Settings → Networking → Custom Domain에 `atelierlabs.co.kr`, `www.atelierlabs.co.kr`,
   `vernissage.atelierlabs.co.kr`, `keepsake.atelierlabs.co.kr`를 각각 추가한다.
3. 도메인 DNS에 Railway가 알려주는 레코드를 등록한다.
   서브도메인은 CNAME, 루트 도메인(`atelierlabs.co.kr`)은 CNAME flattening/ALIAS를 지원하는 DNS가 필요하다.

환경변수(모두 선택):

| 이름 | 기본값 | 설명 |
|---|---|---|
| `ROOT_DOMAIN` | `atelierlabs.co.kr` | 서브도메인 판별 기준 |
| `DEFAULT_SITE` | `atelierlabs` | 우리 도메인이 아닌 Host(`localhost`, `*.up.railway.app`)에 보여줄 사이트 |

## Vernissage 웹 이전

vernissage 웹페이지는 `www.vernissage.kr`에서 `vernissage.atelierlabs.co.kr`로 옮기는 중이다.
vernissage 리포는 이 사이트가 필요로 하는 데이터를 넘겨주는 API만 남기고, 화면은 모두 이 리포로 온다.
약관·개인정보 처리방침의 정식 주소도 `vernissage.atelierlabs.co.kr/legal/…`이다.

`sites/vernissage/`는 vernissage 리포 `backend/home/`, `backend/legal/`에서 옮겨왔다(2026-11-06).

- 자산 경로 `/home/assets/…` → `/assets/…`, 영문 약관 `legal/*.en.html` → `en/legal/*.html`
- vernissage 리포에서는 `backend/home/`, `backend/legal/`을 지우는 중이다. **약관 원본은 이제 이 리포다.**
- `canonical`·`hreflang`·`og:*`·JSON-LD 주소는 `https://vernissage.atelierlabs.co.kr`
- 아직 옮기지 않은 화면은 `https://www.vernissage.kr`로 링크한다:
  도슨트·전시·비엔날레·아트페어·예술취향테스트·`/about`. 홈의 "도슨트·곧 끝나는 전시" 섹션과
  AdSense 자리표시는 뺐다. vernissage API가 준비되면 이 화면들을 여기로 옮긴다.
- 개인정보 처리방침 제11조에서 웹사이트 AdSense·쿠키 고지를 뺐다(웹 광고는 게재하지 않음). 앱의 AdMob 고지는 남아 있다.
