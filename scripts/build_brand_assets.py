"""brand/ 원본으로 회사 홈(sites/atelierlabs/assets/)에 쓸 이미지를 만든다.

원본을 바꾸면 다시 실행한다:
    uv run --with pillow python scripts/build_brand_assets.py
"""

from pathlib import Path

from PIL import Image

ROOT = Path(__file__).resolve().parent.parent
BRAND = ROOT / "brand"
OUT = ROOT / "sites" / "atelierlabs" / "assets"
WHITE = (255, 255, 255, 255)


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


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    icon = trim(Image.open(BRAND / "atelierlabs_icon.png").convert("RGBA"))
    logo = trim(Image.open(BRAND / "atelierlabs_icon_logo.png").convert("RGBA"))

    fit_square(icon, 512, 0.06).save(OUT / "icon.png", optimize=True)
    fit_square(icon, 64, 0.04).save(OUT / "favicon.png", optimize=True)
    # iOS는 투명 영역을 검게 채우므로 흰 바탕에 여백을 둔다.
    fit_square(icon, 180, 0.14, WHITE).convert("RGB").save(OUT / "apple-touch-icon.png", optimize=True)

    # 헤더용 가로 로고: 표시 높이 ~40px의 2~3배
    h = 120
    logo.resize((round(logo.width * h / logo.height), h), Image.LANCZOS).save(OUT / "logo.png", optimize=True)

    # 공유 미리보기(og:image) 1200x630, 흰 바탕 가운데 로고
    og = Image.new("RGBA", (1200, 630), WHITE)
    scaled = logo.copy()
    scaled.thumbnail((840, 280), Image.LANCZOS)
    og.alpha_composite(scaled, ((1200 - scaled.width) // 2, (630 - scaled.height) // 2))
    og.convert("RGB").save(OUT / "og-image.png", optimize=True)

    for f in ("icon.png", "favicon.png", "apple-touch-icon.png", "logo.png", "og-image.png"):
        path = OUT / f
        print(f"{path.relative_to(ROOT)}  {Image.open(path).size}  {path.stat().st_size // 1024}KB")


if __name__ == "__main__":
    main()
