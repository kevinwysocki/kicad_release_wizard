"""Generate the plugin logo (resources/logo.png and resources/logo_256.png).

Usage: python resources/make_logo.py   (requires Pillow)
"""

import math
from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter

HERE = Path(__file__).resolve().parent
S = 1024  # master canvas, downscaled for anti-aliasing

BOARD = (22, 110, 62)
BOARD_DARK = (12, 70, 38)
COPPER = (232, 176, 75)
COPPER_DARK = (170, 120, 40)
WHITE = (255, 255, 255)
STAR = (255, 236, 140)


def star_points(cx, cy, r_out, r_in, n=4, rot=-math.pi / 2):
    pts = []
    for i in range(2 * n):
        r = r_out if i % 2 == 0 else r_in
        a = rot + i * math.pi / n
        pts.append((cx + r * math.cos(a), cy + r * math.sin(a)))
    return pts


def thick_line(d, p0, p1, w, fill):
    d.line([p0, p1], fill=fill, width=w)
    for x, y in (p0, p1):
        d.ellipse([x - w / 2, y - w / 2, x + w / 2, y + w / 2], fill=fill)


def draw():
    img = Image.new("RGBA", (S, S), (0, 0, 0, 0))

    # Board with soft shadow
    shadow = Image.new("RGBA", (S, S), (0, 0, 0, 0))
    ImageDraw.Draw(shadow).rounded_rectangle(
        [70, 90, S - 50, S - 30], radius=170, fill=(0, 0, 0, 110)
    )
    img.alpha_composite(shadow.filter(ImageFilter.GaussianBlur(24)))

    d = ImageDraw.Draw(img)
    d.rounded_rectangle([48, 48, S - 48, S - 48], radius=170, fill=BOARD_DARK)
    d.rounded_rectangle([72, 72, S - 72, S - 72], radius=150, fill=BOARD)

    # Copper traces with pads (lower-left area)
    tw = 34
    traces = [
        [(150, 640), (330, 640), (470, 780), (470, 900)],
        [(150, 760), (260, 760), (350, 850), (350, 900)],
        [(640, 900), (640, 820), (780, 680), (880, 680)],
    ]
    for path in traces:
        for a, b in zip(path, path[1:]):
            thick_line(d, a, b, tw, COPPER)
    for x, y in [(150, 640), (150, 760), (880, 680)]:
        d.ellipse([x - 48, y - 48, x + 48, y + 48], fill=COPPER)
        d.ellipse([x - 20, y - 20, x + 20, y + 20], fill=BOARD_DARK)

    # Magic wand (diagonal), white body with copper band
    p0, p1 = (250, 830), (640, 440)
    thick_line(d, (p0[0] + 10, p0[1] + 14), (p1[0] + 10, p1[1] + 14), 96, (0, 0, 0, 90))
    thick_line(d, p0, p1, 92, WHITE)
    tip = (p1[0] - 0.22 * (p1[0] - p0[0]), p1[1] - 0.22 * (p1[1] - p0[1]))
    thick_line(d, tip, p1, 92, COPPER)
    thick_line(d, p0, (p0[0] + 70, p0[1] - 70), 92, (40, 40, 40))

    # Sparkles
    glow = Image.new("RGBA", (S, S), (0, 0, 0, 0))
    ImageDraw.Draw(glow).ellipse([560, 160, 920, 520], fill=(255, 240, 160, 150))
    img.alpha_composite(glow.filter(ImageFilter.GaussianBlur(60)))
    d = ImageDraw.Draw(img)
    d.polygon(star_points(740, 330, 230, 58), fill=STAR, outline=COPPER_DARK, width=8)
    d.polygon(star_points(470, 220, 90, 24), fill=WHITE)
    d.polygon(star_points(880, 560, 70, 18), fill=WHITE)
    return img


def main():
    master = draw()
    master.resize((256, 256), Image.LANCZOS).save(HERE / "logo_256.png")
    # KiCad toolbar icons are 24x24
    master.resize((24, 24), Image.LANCZOS).save(HERE / "logo.png")
    print("written:", HERE / "logo.png", HERE / "logo_256.png")


if __name__ == "__main__":
    main()
