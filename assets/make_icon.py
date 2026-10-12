"""Конвертирует исходное изображение (logo_source.png) в иконку .ico и .png."""
import os

from PIL import Image

HERE = os.path.dirname(os.path.abspath(__file__))
SRC = os.path.join(HERE, "logo_source.png")
ICO_PATH = os.path.join(HERE, "bioanalizator.ico")
PNG_PATH = os.path.join(HERE, "bioanalizator.png")
MASTER = 512


def build():
    if not os.path.exists(SRC):
        raise FileNotFoundError(f"Не найден исходник: {SRC}")

    img = Image.open(SRC).convert("RGBA")

    # делаем квадрат (при необходимости добавляем прозрачные поля)
    width, height = img.size
    side = max(width, height)
    square = Image.new("RGBA", (side, side), (0, 0, 0, 0))
    square.paste(img, ((side - width) // 2, (side - height) // 2))

    master = square.resize((MASTER, MASTER), Image.LANCZOS)
    master.save(PNG_PATH, format="PNG")
    master.save(
        ICO_PATH,
        format="ICO",
        sizes=[(16, 16), (24, 24), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)],
    )
    print("source:", SRC, img.size)
    print("saved", ICO_PATH)
    print("saved", PNG_PATH)


if __name__ == "__main__":
    build()
