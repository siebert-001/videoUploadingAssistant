"""从 PNG 生成 assets/icon.ico，或生成默认蓝色上传图标。用法: python scripts/generate_icon.py [源图.png]"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "assets" / "icon.ico"
SIZES = [16, 32, 48, 64, 128, 256]


def _default_icons():
    from PIL import Image, ImageDraw

    imgs = []
    for s in SIZES:
        img = Image.new("RGBA", (s, s), (22, 119, 255, 255))
        d = ImageDraw.Draw(img)
        m = max(2, s // 6)
        d.rounded_rectangle(
            [m, m, s - m - 1, s - m - 1],
            radius=max(1, s // 8),
            outline=(255, 255, 255, 255),
            width=max(1, s // 12),
        )
        cx, cy = s // 2, s // 2
        ah, aw = max(2, s // 5), max(2, s // 6)
        d.polygon([(cx, cy - ah), (cx - aw, cy), (cx + aw, cy)], fill=(255, 255, 255, 255))
        d.rectangle([cx - aw // 2, cy, cx + aw // 2, cy + ah], fill=(255, 255, 255, 255))
        imgs.append(img)
    return imgs


def main() -> None:
    try:
        from PIL import Image
    except ImportError:
        print("请先安装: pip install pillow")
        sys.exit(1)

    OUT.parent.mkdir(exist_ok=True)
    if len(sys.argv) > 1:
        src = Path(sys.argv[1])
        base = Image.open(src).convert("RGBA")
        imgs = [base.resize((s, s), Image.Resampling.LANCZOS) for s in SIZES]
    else:
        imgs = _default_icons()

    imgs[-1].save(OUT, format="ICO", sizes=[(s, s) for s in SIZES])
    print(OUT)


if __name__ == "__main__":
    main()
