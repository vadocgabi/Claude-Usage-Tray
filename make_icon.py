"""Generates app.ico for the exe (run by build.bat)."""
from PIL import Image, ImageDraw, ImageFont


def main() -> None:
    size = 256
    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    d.rounded_rectangle((0, 0, size - 1, size // 2 - 4), 40, fill=(37, 99, 235))
    d.rounded_rectangle((0, size // 2 + 4, size - 1, size - 1), 40, fill=(225, 130, 0))
    try:
        font = ImageFont.truetype("arialbd.ttf", 100)
    except OSError:
        font = ImageFont.load_default()
    d.text((size / 2, size / 4), "5h", font=font, fill="white", anchor="mm")
    d.text((size / 2, size * 3 / 4), "7d", font=font, fill="white", anchor="mm")
    img.save("app.ico", sizes=[(16, 16), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)])


if __name__ == "__main__":
    main()
