"""Generates the graphics for the exe and the installer (run by build.bat):
app.ico, installer_side.bmp (wizard sidebar) and installer_small.bmp (wizard header)."""
from PIL import Image, ImageDraw, ImageFont

BLUE, ORANGE, NAVY = (37, 99, 235), (225, 130, 0), (15, 23, 42)


def font(size: int, bold: bool = True):
    for name in ("arialbd.ttf" if bold else "arial.ttf", "segoeuib.ttf", "arial.ttf"):
        try:
            return ImageFont.truetype(name, size)
        except OSError:
            continue
    return ImageFont.load_default()


def logo(size: int) -> Image.Image:
    """Two coloured bars: session (top) and week (bottom)."""
    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    r, gap = size // 6, size // 32
    d.rounded_rectangle((0, 0, size - 1, size // 2 - gap), r, fill=BLUE)
    d.rounded_rectangle((0, size // 2 + gap, size - 1, size - 1), r, fill=ORANGE)
    f = font(size * 2 // 5)
    d.text((size / 2, size / 4), "5h", font=f, fill="white", anchor="mm")
    d.text((size / 2, size * 3 / 4), "7d", font=f, fill="white", anchor="mm")
    return img


def sidebar(w: int = 328, h: int = 628) -> Image.Image:
    """Vertical navy-to-blue gradient with logo and title (2x of Inno's 164x314)."""
    img = Image.new("RGB", (w, h))
    d = ImageDraw.Draw(img)
    for y in range(h):
        t = y / (h - 1)
        d.line((0, y, w, y), fill=tuple(int(NAVY[i] + (BLUE[i] - NAVY[i]) * t * 0.8) for i in range(3)))
    img.paste(logo(150), ((w - 150) // 2, 110), logo(150))
    d.text((w / 2, 320), "Claude", font=font(40), fill="white", anchor="mm")
    d.text((w / 2, 366), "Usage Tray", font=font(40), fill="white", anchor="mm")
    d.text((w / 2, h - 40), "Vadóc Gábor · 2026", font=font(20, False), fill=(190, 205, 235), anchor="mm")
    return img


def header(size: int = 110) -> Image.Image:
    img = Image.new("RGB", (size, size), "white")
    img.paste(logo(size - 24), (12, 12), logo(size - 24))
    return img


def main() -> None:
    logo(256).save("app.ico", sizes=[(16, 16), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)])
    sidebar().save("installer_side.bmp")
    header().save("installer_small.bmp")


if __name__ == "__main__":
    main()
