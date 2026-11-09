# atelierlabs.co.kr

Atelier Labs 회사 홈페이지와 앱별 서브도메인 페이지를 서비스하는 정적 사이트 서버.
Railway 서비스 하나가 모든 도메인을 받고, 요청의 `Host` 헤더로 사이트를 고른다.

| 도메인 | 내용 | 디렉터리 |
|---|---|---|
| `atelierlabs.co.kr` | 회사 홈(`/`: 소개·앱·원칙), 고객지원(`/support`) | [sites/atelierlabs/](sites/atelierlabs/) |
| `www.atelierlabs.co.kr` | `atelierlabs.co.kr`로 301 | — |
| `vernissage.atelierlabs.co.kr` | Vernissage 소개, 공개 도슨트·전시·아트 이벤트·예술 취향 테스트, 약관 안내 | [sites/vernissage/](sites/vernissage/) |
| `keepsake.atelierlabs.co.kr` | Keepsake 소개, 출시 소식·앱 안내, 약관 안내 | [sites/keepsake/](sites/keepsake/) |

모든 페이지는 한국어(`/…`)·영어(`/en/…`)·일본어(`/ja/…`)로 제공한다. 아래 [다국어](#다국어) 참고.

## 구조

```
app/main.py      FastAPI 서버: Host로 사이트 선택, URL을 파일로 매핑
sites/<site>/    사이트별 정적 파일 (HTML, assets/, robots.txt, sitemap.xml)
  en/, ja/       영어·일본어 페이지 (한국어 페이지와 같은 경로)
                 스타일은 페이지마다 넣지 않고 공용 CSS를 쓴다:
                 atelierlabs/assets/site.css, vernissage/assets/home.css(랜딩), vernissage/assets/public.css(공개 콘텐츠), vernissage/assets/legal.css·keepsake/assets/legal.css(약관)
  shared/        세 사이트가 함께 쓰는 정적 자산 (hero-layout.css)
brand/           사이트 로고·폰트 원본 (서비스되지 않음)
scripts/         brand/ 원본으로 웹용 이미지를 만드는 스크립트
tests/           라우팅 테스트
```

### 브랜드 이미지

`brand/`에는 Atelier Labs·Vernissage·Keepsake의 심볼 원본과 워드마크 생성용 폰트가 있다.
원본을 바꾸면 아래 명령으로 세 사이트의 헤더·푸터 로고와 앱 심볼을 다시 만든다.

```bash
uv run --with pillow python scripts/build_brand_assets.py
```

### 홈페이지 대표 이미지

세 서비스의 홈페이지는 사진 기반 히어로 영역으로 각 서비스의 분위기와 이야기를 먼저 보여 준다.
Vernissage와 Keepsake는 이전·현재 대표 이미지를 번갈아 보여 주고, Atelier Labs는 세 서비스의
대표 이미지를 함께 순환해 스튜디오 전체의 방향을 소개한다.

세 홈의 히어로 규격(데스크톱·휴대폰 모두)은 `sites/shared/hero-layout.css`에서 함께 관리한다. 각 도메인은
동일한 `/shared/hero-layout.css` 경로로 이 파일을 받아, 세 사이트가 같은 영역 크기와 같은 아이콘·글자 위치를 쓴다.

Atelier Labs와 Vernissage의 상단 메뉴는 좁은 화면에서 ☰ 버튼으로 여닫는다. 두 사이트는 같은
`assets/nav.js`를 각자 두고 쓰므로 한쪽을 고치면 다른 쪽에도 복사한다(테스트가 두 파일이 같은지 확인한다).

URL은 `sites/<site>/` 아래 파일로 이렇게 매핑된다.

- `/` → `index.html`
- 일반 URL은 확장자 없는 정적 HTML 파일로 매핑된다. 단, 앱의 이용약관·개인정보 처리방침 URL은
  해당 앱 백엔드에서 프록시한다. 아래 [이용약관·개인정보 처리방침](#이용약관개인정보-처리방침)을 참고한다.
- `/favicon.ico`, `/apple-touch-icon.png` → `assets/favicon.png`, `assets/apple-touch-icon.png`
- `/shared/...` → `sites/shared/`의 모든 사이트 공통 자산
- `/app-ads.txt` → AdMob 앱 인증용 정적 파일. Vernissage 및 Atelier Labs 루트 도메인에서 제공한다.
- `/.well-known/assetlinks.json`, `/.well-known/apple-app-site-association` → Vernissage Android App Links·iOS Universal Links 검증 선언. 경로 목록은 Vernissage `mobile/app.json`의 intentFilters와 맞춘다. 앱에는 상세 화면만 있으므로 상세(`/exhibitions/<id>`, `/en/…`, `/ja/…`)만 앱으로 열고 목록은 웹에 남긴다. 언어 접두사는 앱의 `+native-intent.tsx`가 떼어낸다. Android 지문·Apple Team ID가 없거나 형식이 틀리면 503으로 실패한다.
- 없는 경로 → `<lang>/404.html`, 없으면 `404.html`, 그것도 없으면 일반 텍스트 404

## 다국어

- 한국어는 루트, 영어·일본어는 `/en/`, `/ja/` 아래 **같은 경로**에 둔다. 페이지를 추가하면 세 언어를 함께 만든다.
- 각 페이지에는 `canonical`(자기 주소), `hreflang` ko/en/ja + `x-default`(한국어), 헤더의 KO·EN·JA 전환, 푸터의 언어 링크를 넣는다.
- 사이트맵에 언어별 주소를 모두 싣는다.
- 각 사이트 홈(ko/en/ja)에는 `og:locale`, `twitter:*`, JSON-LD(`Organization`·`WebSite`·`MobileApplication`)를 둔다.
  Atelier Labs 홈의 JSON-LD에는 Vernissage·Keepsake 앱을 모두 싣는다. 사이트맵에 실린 정적 문서(예: 계정 삭제 안내)에는
  `description`, `robots`(index, follow), `og:*`를 넣는다.
- Atelier Labs 한국어 페이지는 '아틀리에 랩스' 검색에 걸리도록 `<title>`·`og:title`에 `Atelier Labs(아틀리에 랩스)`를 쓰고,
  홈 h1 안에 한글 이름(`.hero-reading`)을 둔다. 루트 홈 `WebSite`의 `name`("아틀리에 랩스")은 구글 검색 결과의 사이트 이름이 된다.
  회사 `Organization`(`#organization`)은 세 언어 홈에서 `alternateName`까지 똑같이 유지한다.
- 정적 `sitemap.xml`의 `lastmod`는 페이지를 실제로 고친 날짜로 갱신한다.
- **Vernissage·Keepsake의 약관·개인정보 처리방침은 한국어·영어만 있다** (Vernissage는 계정 삭제 안내 포함). 일본어 페이지는
  영어판(`/en/legal/…`)으로 링크하고 "（英語）"라고 표시한다. `/ja/legal/…`로 들어오면 서버가 `/en/legal/…`로 301 한다.
  문서 원문은 각 앱 백엔드가 `/public-web/legal/{ko|en}/{문서}`로 서빙하고 이 서버는 프록시만 한다. Atelier Labs의 개인정보 처리방침·이용약관
  안내(`/privacy`, `/terms`)도 한국어·영어만 제공하며 `/ja/privacy`, `/ja/terms`는 영어로 301 한다.
- Vernissage·Keepsake 영어판 약관은 "한국어판이 우선한다"는 문구를 둔다. 한국어판을 고치면 영어판도 함께 고친다.
- Vernissage 공개 콘텐츠 화면도 루트·`/en/`·`/ja/` 경로로 같은 기능을 제공하고, 데이터 언어는 요청 언어 헤더로 정한다.
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
| Vernissage API (별도 `vernissage` 리포) | 18000 |
| Keepsake API (별도 `keepsake` 리포) | 18020 |
| API (atelierlabs용 예약) | 18010 |
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
| `ANDROID_APP_LINK_SHA256_CERT_FINGERPRINTS` | — | 쉼표로 구분한 Vernissage **Google Play 앱 서명** SHA-256 지문(`AB:CD:…` 콜론 구분 32바이트). `vernissage.atelierlabs.co.kr/.well-known/assetlinks.json`에 사용하며, 누락되거나 형식이 틀리면 Android 검증 파일은 503이다. |
| `APPLE_APP_LINK_TEAM_ID` | `3BQ7Y687R9` | Vernissage Universal Links의 Apple Team ID(영문 대문자·숫자 10자리). 형식이 틀리면 iOS 검증 파일은 503이다. |

## Vernissage 웹 이전

vernissage 웹페이지는 `vernissage.atelierlabs.co.kr`으로 이전을 완료했다. 기존 `www.vernissage.kr` 주소는
새 주소로 리다이렉트되며, 앱 링크 검증과 새 공유 링크는 새 주소만 사용한다.
vernissage 리포는 이 사이트가 필요로 하는 데이터를 넘겨주는 API만 남기고, 화면은 모두 이 리포로 온다.
약관·개인정보 처리방침의 정식 주소도 `vernissage.atelierlabs.co.kr/legal/…`이다.

`sites/vernissage/`는 vernissage 리포 `backend/home/`에서 옮겨왔다(2026-11-06).

- 자산 경로 `/home/assets/…` → `/assets/…`
- 화면 shell은 이 리포가 관리하지만, 이용약관·개인정보 처리방침의 원본은 Vernissage 백엔드가 관리하고 이 서버가 프록시한다.
- `canonical`·`hreflang`·`og:*`·JSON-LD 주소는 `https://vernissage.atelierlabs.co.kr`
- 공개 도슨트·전시·비엔날레·아트페어·예술취향테스트 화면은 이 리포의 정적 shell과 Vernissage 공개 API로 제공한다.
  도슨트·전시·아트이벤트의 상세 페이지는 같은 API 데이터로 서버 HTML과 검색 메타데이터를 먼저 제공하고,
  `sitemap.xml`에도 공개 상세 URL을 자동으로 반영한다. 소개 페이지는 `https://vernissage.atelierlabs.co.kr/about`을 링크한다. 홈의 "도슨트·곧 끝나는 전시" 섹션과
  AdSense 자리표시는 두지 않는다.
- 도슨트 본문은 일반 텍스트뿐 아니라 강조 문장, 출처를 포함한 이미지, 작품·작가·미술 개념 등의 참조 카드를 표시한다. 여러 참조·이미지는 화면 크기에 맞춰 그리드로 묶어 보여 준다.
- 웹 페이지가 없는 앱 전용 상세(`/museums`, `/artworks`, `/artists`, `/art-concepts`, `/art-figures` 아래, 언어별)는 앱이 없는 사람에게 `<lang>/get-app.html` 설치 안내를 보여준다. `assets/get-app.js` 동작: 카카오톡·인스타그램 등 인앱 브라우저와 Android는 먼저 앱을 직접 열고(Android `intent://`, iOS `vernissage://`), 1.6초 안에 앱이 열리지 않으면 스토어로 보낸다. iOS Safari는 앱이 있으면 Universal Links가 이미 열었을 것이므로 바로 App Store로 보낸다. 데스크톱은 스토어 배지만 보여준다.
- 개인정보 처리방침 제11조에서 웹사이트 AdSense·쿠키 고지를 뺐다(웹 광고는 게재하지 않음). 앱의 AdMob 고지는 남아 있다.

### 앱 API 연결

웹 페이지에서 Vernissage 데이터가 필요하면 백엔드를 브라우저에서 직접 호출하지 말고,
같은 origin의 아래 주소를 호출한다.

```
GET /api/vernissage/public-web/home
GET /api/vernissage/public-web/exhibitions?tab=ongoing
```

사이트 서버는 공개 콘텐츠 요청을 `VERNISSAGE_API_BASE_URL/public-web/...`로 전달하고,
`VERNISSAGE_PUBLIC_WEB_API_TOKEN`은 서버에서만 `X-Public-Web-Token` 헤더로 붙인다.
예술 취향 테스트에 필요한 제한된 API도 같은 origin에서 전달한다. 로그인·관리자·사용자 API는 이 프록시 범위에 포함하지 않는다.
응답 캐시는 `X-App-Language`로 분리된다.

로컬에서는 두 프로젝트를 각각 시작하면 된다.

```bash
# ../vernissage
./start.sh

# ../atelierlabs
./start.sh
```

`compose.dev.env`의 `VERNISSAGE_API_BASE_URL=http://host.docker.internal:18000`이
atelierlabs 컨테이너에서 vernissage 백엔드의 호스트 포트로 연결한다. 백엔드 로컬
`PUBLIC_WEB_API_TOKEN`은 비워도 된다. 토큰을 테스트하려면 두 프로젝트에 같은 값을 넣는다.

현재처럼 두 서비스가 **서로 다른 Railway 프로젝트**에 있으면 private network는 서로 보이지 않는다.
이 경우 vernissage 백엔드에 Railway public domain(또는 API 전용 커스텀 도메인)을 만들고,
atelierlabs 서비스에 다음을 설정한다.

| 변수 | 값 |
|---|---|
| `VERNISSAGE_API_BASE_URL` | `https://<vernissage 백엔드의 public domain>` |
| `VERNISSAGE_PUBLIC_WEB_API_TOKEN` | 백엔드의 `PUBLIC_WEB_API_TOKEN`과 같은 랜덤 값 |
| `VERNISSAGE_PUBLIC_API_CACHE_SECONDS` | 공개 API 응답의 프로세스 내 캐시 시간(초, 기본 `300`) |
| `VERNISSAGE_PUBLIC_API_REQUESTS_PER_MINUTE` | 방문자 IP별 공개 API 최대 요청 수(기본 `120`) |
| `VERNISSAGE_DETAIL_REQUESTS_PER_MINUTE` | 방문자 IP별 공개 상세 페이지 최대 요청 수(기본 `60`) |

Vernissage 백엔드에도 `PUBLIC_WEB_API_TOKEN`을 같은 값으로 설정한다. 호출은 사이트 서버에서
백엔드로만 나가므로 이 구성에도 백엔드 CORS 추가는 필요 없다. API 공개 도메인은 외부에서
접속 가능하지만, 이 프록시가 쓰는 `/public-web/*`는 공유 토큰 없이는 401을 반환한다.

두 서비스를 같은 Railway **프로젝트·환경**으로 모을 수 있다면 public domain을 거치지 않는
편이 낫다. atelierlabs의 `VERNISSAGE_API_BASE_URL`을 Railway reference variable로 아래처럼
설정한다(서비스 이름이 `vernissage-api`인 예).

```
http://${{vernissage-api.RAILWAY_PRIVATE_DOMAIN}}:${{vernissage-api.PORT}}
```

private network는 `http`를 사용하며, 같은 프로젝트·환경 안에서만 해석된다.

### 이용약관·개인정보 처리방침

법률 문서의 원본은 홈페이지 리포가 아니라 각 앱 백엔드에 둔다. 홈페이지는 기존 공개 URL을 유지한 채
해당 문서를 프록시하므로, 앱 백엔드에서 문서를 배포하면 홈페이지를 다시 배포하지 않아도 최신 원문이
반영된다. 문서와 오류 응답은 캐시하지 않는다. API는 공개 웹 공유 토큰으로 보호하며, 운영 환경에서는
아래 두 쌍을 같은 무작위 값으로 설정한다.

| 홈페이지 환경변수 | 앱 백엔드 환경변수 |
|---|---|
| `VERNISSAGE_API_BASE_URL`, `VERNISSAGE_PUBLIC_WEB_API_TOKEN` | `PUBLIC_WEB_API_TOKEN` |
| `KEEPSAKE_API_BASE_URL`, `KEEPSAKE_PUBLIC_WEB_API_TOKEN` | `PUBLIC_WEB_API_TOKEN` |

Keepsake 로컬 API 기본 포트는 `18020`이다. Keepsake도 Vernissage와 같이 한국어·영어 법률 문서를
각각 제공하며, 일본어 홈페이지에서는 영어 문서를 안내한다.
