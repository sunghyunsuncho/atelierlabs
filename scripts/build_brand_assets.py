"""brand/ 원본으로 세 사이트(atelierlabs·vernissage·keepsake)의 로고 이미지를 만든다.

- 아이콘은 brand/<name>_icon_logo.png 원본에서 잘라 쓴다.
- 워드마크(글자)는 이미지 원본을 쓰지 않고 brand/fonts/의 폰트로 코드에서 직접 그린다.
  세 로고가 같은 폰트·굵기·크기·자간·색을 갖게 하기 위해서다.
  기본은 사이트 제목(h1)과 같은 Pretendard Bold(700), 자간 -0.05em. (SIL OFL 1.1)
  원본 Atelier Labs 로고 글자에 더 가까운 모양을 원하면 FONT_PRESET을 "outfit"으로 바꾼다.
- favicon: atelierlabs는 brand/atelierlabs_icon.png, 앱(keepsake)은 로고 원본의 아이콘으로 투명 배경 favicon을 만든다.

원본이나 아래 상수를 바꾸면 다시 실행한다:
    uv run --with pillow python scripts/build_brand_assets.py
"""

import shutil
from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter, ImageFont, ImageOps

ROOT = Path(__file__).resolve().parent.parent
BRAND = ROOT / "brand"
SITES = ROOT / "sites"
OUT = SITES / "atelierlabs" / "assets"
WHITE = (255, 255, 255, 255)

# ── 워드마크 ──────────────────────────────────────────────
FONT_PRESETS = {
    # 사이트 h1과 같은 글꼴(Pretendard 700). 자간은 h1(-0.07em)보다 살짝 넓혀 작은 크기에서 rn이 붙지 않게
    "pretendard": dict(path=BRAND / "fonts" / "PretendardVariable.ttf", weight=700, tracking_em=-0.05, corner_round=0),
    # 원본 Atelier Labs 로고 글자와 가장 닮은 공개 폰트 (획 두께·평평한 A·한 층 a). 모서리를 살짝 둥글린다.
    "outfit": dict(path=BRAND / "fonts" / "Outfit-Variable.ttf", weight=600, tracking_em=-0.028, corner_round=0.02),
}
FONT_PRESET = "pretendard"
_F = FONT_PRESETS[FONT_PRESET]
FONT_PATH = _F["path"]
FONT_WEIGHT = _F["weight"]
TRACKING_EM = _F["tracking_em"]  # 자간, 글자 크기(em) 대비 — CSS letter-spacing과 같은 단위
CORNER_ROUND = _F["corner_round"]  # 모서리 둥글림, 대문자 높이 대비
TEXT_COLOR = (21, 21, 21)  # 사이트 글자색 --ink #151515
ACCENT_COLOR = (178, 102, 52)  # 사이트 코랄 #B26634 — 앱 워드마크 끝 점
DARK_TEXT_COLOR = (255, 255, 255)  # 어두운 푸터용 logo-dark.png 글자색
SUPERSAMPLE = 8

# 사이트별 워드마크: (글자, 코랄색으로 칠할 끝 점 여부) — 바꾸려면 여기만 고친다.
WORDMARKS = {
    "atelierlabs": ("Atelier Labs.", True),
    "vernissage": ("Vernissage.", True),
    "keepsake": ("Keepsake.", True),
}

# 로고 원본의 아이콘으로 투명 배경 favicon을 만들 앱 (vernissage는 앱 아이콘 favicon을 그대로 쓴다)
FAVICON_FROM_LOGO = ("keepsake",)

# ── 헤더 가로 로고 공통 틀 (scale=1일 때 높이 120px, 화면에선 30px) ──
# 세 사이트를 오갈 때 아이콘 위치·크기, 글자 시작점, 대문자 높이, 기준선이 같아 보이게 한다.
LOGO_H = 120
ICON_H = 112  # 아이콘 높이 (위아래 4px 여백)
TEXT_X = 146  # 글자 시작 x — 가장 넓은 아이콘(Atelier Labs의 A) 폭 + 간격
CAP_H = 52  # 대문자 높이
CAP_TOP = (LOGO_H - CAP_H) // 2  # 대문자를 아이콘 세로 가운데에 둔다


def trim(im: Image.Image) -> Image.Image:
    # 가장자리의 거의 투명한 픽셀까지 bbox에 잡히지 않게 alpha 임계값을 둔다.
    alpha = im.getchannel("A").point(lambda a: 255 if a > 8 else 0)
    return im.crop(alpha.getbbox())


def fit_square(im: Image.Image, size: int, padding: float, background=(0, 0, 0, 0)) -> Image.Image:
    inner = round(size * (1 - 2 * padding))
    im = im.copy()
    im.thumbnail((inner, inner), Image.LANCZOS)
    canvas = Image.new("RGBA", (size, size), background)
    canvas.alpha_composite(im, ((size - im.width) // 2, (size - im.height) // 2))
    return canvas


def extract_icon(logo_src: Image.Image) -> Image.Image:
    """아이콘+워드마크 원본에서 왼쪽 첫 잉크 덩어리(아이콘)만 잘라낸다."""
    alpha = logo_src.getchannel("A").point(lambda a: 255 if a > 40 else 0)
    x = 0
    while alpha.crop((x, 0, x + 1, logo_src.height)).getbbox() is None:
        x += 1
    start = x
    while alpha.crop((x, 0, x + 1, logo_src.height)).getbbox() is not None:
        x += 1
    box = alpha.crop((start, 0, x, logo_src.height)).getbbox()
    return logo_src.crop((start, box[1], x, box[3]))


def _font(size: int) -> ImageFont.FreeTypeFont:
    font = ImageFont.truetype(str(FONT_PATH), size)
    font.set_variation_by_axes([FONT_WEIGHT])
    return font


def render_wordmark(
    text: str, cap_h: float, accent_dot: bool = False, text_color=TEXT_COLOR
) -> tuple[Image.Image, int]:
    """대문자 높이가 cap_h(px)인 워드마크를 그린다. (이미지, 이미지 위쪽에서 대문자 윗선까지 px)

    accent_dot이면 마지막 글자(끝 점)를 ACCENT_COLOR로 칠한다.
    """
    ss_cap = cap_h * SUPERSAMPLE
    probe = _font(1000)
    h_box = probe.getbbox("H")
    font = _font(round(1000 * ss_cap / (h_box[3] - h_box[1])))
    cap_top = font.getbbox("H")[1]

    pad = round(ss_cap * 0.5)
    track = TRACKING_EM * font.size
    xs = [font.getlength(text[:i]) + i * track for i in range(len(text))]  # 커닝 유지 + 자간
    size = (round(xs[-1] + font.getlength(text[-1])) + pad * 2, round(ss_cap * 2) + pad * 2)
    masks = [Image.new("L", size), Image.new("L", size)]  # [본문, 강조 점]
    for i, (x, ch) in enumerate(zip(xs, text, strict=True)):
        layer = masks[1] if accent_dot and i == len(text) - 1 else masks[0]
        ImageDraw.Draw(layer).text((pad + x, pad - cap_top), ch, font=font, fill=255)

    if CORNER_ROUND:
        # 흐리게 한 뒤 다시 날카롭게 → 볼록한 모서리만 살짝 둥글어진다.
        masks = [
            m.filter(ImageFilter.GaussianBlur(CORNER_ROUND * ss_cap)).point(
                lambda v: max(0, min(255, (v - 128) * 8 + 128))
            )
            for m in masks
        ]

    union = masks[0].copy()
    union.paste(255, mask=masks[1])
    box = union.getbbox()
    cap_offset = (pad - box[1]) / SUPERSAMPLE
    small = (round((box[2] - box[0]) / SUPERSAMPLE), round((box[3] - box[1]) / SUPERSAMPLE))

    out = Image.new("RGBA", small, (0, 0, 0, 0))
    for mask, color in zip(masks, (text_color, ACCENT_COLOR), strict=True):
        layer = Image.new("RGBA", small, color + (0,))
        layer.putalpha(mask.crop(box).resize(small, Image.LANCZOS))
        out.alpha_composite(layer)
    return out, round(cap_offset)


def _icon_on_dark(icon: Image.Image) -> Image.Image:
    """어두운 배경용 아이콘: 예전 CSS filter(invert(1) grayscale(1) brightness(1.6))와 같은 처리."""
    alpha = icon.getchannel("A")
    gray = ImageOps.invert(icon.convert("RGB")).convert("L").point(lambda v: min(255, round(v * 1.6)))
    out = Image.merge("RGBA", (gray, gray, gray, alpha))
    return out


def compose_logo(
    icon_src: Image.Image, text: str, accent_dot: bool = False, scale: int = 1, dark: bool = False
) -> Image.Image:
    """dark=True면 어두운 배경(푸터)용: 아이콘·글자를 밝게, 강조 점은 그대로 코랄."""
    icon_h, logo_h = ICON_H * scale, LOGO_H * scale
    icon = icon_src.resize((round(icon_src.width * icon_h / icon_src.height), icon_h), Image.LANCZOS)
    assert icon.width < TEXT_X * scale, f"아이콘 폭 {icon.width}px가 TEXT_X보다 크다"
    if dark:
        icon = _icon_on_dark(icon)

    word, cap_offset = render_wordmark(text, CAP_H * scale, accent_dot, DARK_TEXT_COLOR if dark else TEXT_COLOR)
    canvas = Image.new("RGBA", (TEXT_X * scale + word.width, logo_h), (0, 0, 0, 0))
    canvas.alpha_composite(icon, (0, (logo_h - icon_h) // 2))
    canvas.alpha_composite(word, (TEXT_X * scale, CAP_TOP * scale - cap_offset))
    return canvas


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    outputs: list[Path] = []

    icon = trim(Image.open(BRAND / "atelierlabs_icon.png").convert("RGBA"))
    fit_square(icon, 512, 0.06).save(OUT / "icon.png", optimize=True)
    fit_square(icon, 64, 0.04).save(OUT / "favicon.png", optimize=True)
    # iOS는 투명 영역을 검게 채우므로 흰 바탕에 여백을 둔다.
    fit_square(icon, 180, 0.14, WHITE).convert("RGB").save(OUT / "apple-touch-icon.png", optimize=True)
    outputs += [OUT / "icon.png", OUT / "favicon.png", OUT / "apple-touch-icon.png"]

    # 헤더·푸터용 가로 로고 (세 사이트 같은 틀)
    for name, (text, accent_dot) in WORDMARKS.items():
        src_icon = extract_icon(Image.open(BRAND / f"{name}_icon_logo.png").convert("RGBA"))
        path = SITES / name / "assets" / "logo.png"
        compose_logo(src_icon, text, accent_dot).save(path, optimize=True)
        dark_path = path.with_name("logo-dark.png")
        compose_logo(src_icon, text, accent_dot, dark=True).save(dark_path, optimize=True)
        outputs += [path, dark_path]

        if name in FAVICON_FROM_LOGO:
            # 투명 배경 favicon (브라우저 탭은 투명 영역을 탭 색으로 보여준다)
            fav = SITES / name / "assets" / "favicon.png"
            fit_square(src_icon, 64, 0.04).save(fav, optimize=True)
            outputs.append(fav)

        if name != "atelierlabs":
            # 히어로 아이콘 마크 — atelierlabs icon.png와 같은 크기·여백(투명 배경)
            mark = SITES / name / "assets" / "hero-mark.png"
            fit_square(src_icon, 512, 0.06).save(mark, optimize=True)
            outputs.append(mark)

        if name == "atelierlabs":
            # 공유 미리보기(og:image) 1200x630, 흰 바탕 가운데 로고
            big = compose_logo(src_icon, text, accent_dot, scale=3)
            big.thumbnail((840, 280), Image.LANCZOS)
            og = Image.new("RGBA", (1200, 630), WHITE)
            og.alpha_composite(big, ((1200 - big.width) // 2, (630 - big.height) // 2))
            og.convert("RGB").save(OUT / "og-image.png", optimize=True)
            outputs.append(OUT / "og-image.png")

    # 앱 사이트 푸터의 "Made by Atelier Labs" 서명 — 사이트끼리는 다른 origin이라 각자 사본을 둔다.
    for name in WORDMARKS:
        if name != "atelierlabs":
            maker = SITES / name / "assets" / "atelierlabs-logo-dark.png"
            shutil.copyfile(OUT / "logo-dark.png", maker)
            outputs.append(maker)

    for path in outputs:
        print(f"{path.relative_to(ROOT)}  {Image.open(path).size}  {path.stat().st_size // 1024}KB")


if __name__ == "__main__":
    main()
