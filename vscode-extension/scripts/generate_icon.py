"""
Generate the Gitlane Marketplace icon.

Design: indigo rounded square + white double-chevron pointing right.
The chevron reads as "fast-forward / ship it" — matches the brand's
"one-click commit & push" pitch. The two layers (front + muted) give
visual depth at small sizes.

Run once after the package.json version bumps; the output is committed.
"""
from pathlib import Path
from PIL import Image, ImageDraw, ImageFilter

OUT_DIR = Path(__file__).resolve().parent.parent
SIZE    = 512  # render large, downscale for crispness

BG       = (99, 102, 241, 255)        # indigo #6366f1 — matches dashboard accent
FG_FULL  = (255, 255, 255, 255)
FG_MUTED = (255, 255, 255, 165)


def draw_chevron(d: ImageDraw.ImageDraw, x_start: int, x_tip: int,
                 color: tuple, stroke: int) -> None:
    """A '>' shape from (x_start, y_top) to (x_tip, y_mid) to (x_start, y_bot)."""
    y_top, y_mid, y_bot = round(SIZE * 0.28), SIZE // 2, round(SIZE * 0.72)
    pts = [(x_start, y_top), (x_tip, y_mid), (x_start, y_bot)]
    d.line(pts, fill=color, width=stroke, joint="curve")
    # Round the open ends
    r = stroke // 2
    for px, py in [(x_start, y_top), (x_start, y_bot)]:
        d.ellipse((px - r, py - r, px + r, py + r), fill=color)


def render(size: int = SIZE) -> Image.Image:
    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    d   = ImageDraw.Draw(img, "RGBA")

    # Rounded square background — feels native in macOS dock + VS Code marketplace
    d.rounded_rectangle((0, 0, size, size), radius=round(size * 0.22), fill=BG)

    stroke = round(size * 0.085)

    # Muted (back) chevron sits to the right
    draw_chevron(d, x_start=round(size * 0.46), x_tip=round(size * 0.79),
                 color=FG_MUTED, stroke=stroke)
    # Bold (front) chevron sits left
    draw_chevron(d, x_start=round(size * 0.24), x_tip=round(size * 0.57),
                 color=FG_FULL,  stroke=stroke)

    return img


def main() -> None:
    big = render(SIZE)

    # Marketplace standard: 128 PNG (icon.png). We also save 256 for retina.
    icon_path     = OUT_DIR / "icon.png"
    icon_2x_path  = OUT_DIR / "icon@2x.png"

    big.resize((128, 128), Image.LANCZOS).save(icon_path,    "PNG", optimize=True)
    big.resize((256, 256), Image.LANCZOS).save(icon_2x_path, "PNG", optimize=True)

    print(f"OK  {icon_path}  (128×128)")
    print(f"OK  {icon_2x_path} (256×256)")


if __name__ == "__main__":
    main()
