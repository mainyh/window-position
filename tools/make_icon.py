"""Generate icon.ico: a ghost window snapping to a solid window position."""

from pathlib import Path

from PIL import Image, ImageDraw

SIZE = 1024
OUT = Path(__file__).resolve().parent.parent / "icon.ico"


def main() -> None:
    img = Image.new("RGBA", (SIZE, SIZE), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    d.rounded_rectangle((0, 0, SIZE - 1, SIZE - 1), radius=230, fill=(37, 99, 235, 255))

    # Ghost window (previous position): dashed outline, top-left.
    gx0, gy0, gx1, gy1 = 150, 150, 600, 520
    dash = 46
    light = (191, 219, 254, 255)
    for x in range(gx0, gx1, dash * 2):
        d.line((x, gy0, min(x + dash, gx1), gy0), fill=light, width=22)
        d.line((x, gy1, min(x + dash, gx1), gy1), fill=light, width=22)
    for y in range(gy0, gy1, dash * 2):
        d.line((gx0, y, gx0, min(y + dash, gy1)), fill=light, width=22)
        d.line((gx1, y, gx1, min(y + dash, gy1)), fill=light, width=22)

    # Solid window (saved position): bottom-right, with title bar.
    x0, y0, x1, y1 = 400, 400, 880, 840
    bar = (147, 197, 253, 255)
    d.rounded_rectangle((x0, y0, x1, y1), radius=44, fill=(255, 255, 255, 255))
    d.rounded_rectangle((x0, y0, x1, y0 + 100), radius=44, fill=bar)
    d.rectangle((x0, y0 + 60, x1, y0 + 100), fill=bar)
    for i in range(3):
        cx = x0 + 60 + i * 56
        d.ellipse((cx - 14, y0 + 36, cx + 14, y0 + 64), fill=(37, 99, 235, 255))

    # Arrow from the ghost toward the saved window.
    d.line((470, 380, 560, 470), fill=(255, 255, 255, 255), width=34)
    d.polygon([(590, 500), (500, 490), (580, 410)], fill=(255, 255, 255, 255))

    img.save(OUT, sizes=[(s, s) for s in (16, 24, 32, 48, 64, 128, 256)])
    print("wrote", OUT)


if __name__ == "__main__":
    main()
